import json
import logging
import threading
import time

import pika
import requests
from fastapi import FastAPI, Request, HTTPException,Response
import uvicorn

from prometheus_client import Counter, Histogram, Gauge, generate_latest
from pydantic import BaseModel
import re
from typing import Optional

# =========================
# CONFIG
# =========================
RABBITMQ_HOST = "rabbitmq"
RABBITMQ_PORT = 5672
LOG_QUEUE = "logs_queue"
METRIC_QUEUE = "otel-metrics"
DOWNSTREAM_URL = "http://post-flask-app:5001/v1/metrics"
store_id = "5555"

# =========================
# LOGGING SETUP
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# =========================
# FASTAPI APP
# =========================
app = FastAPI()


# --- RabbitMQ Connection ---
def get_connection():
    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
            channel = connection.channel()
            channel.queue_declare(queue=LOG_QUEUE, durable=True)
            channel.queue_declare(queue=METRIC_QUEUE, durable=True)
            return connection, channel
        except Exception as e:
            logging.error(f"Failed to connect to RabbitMQ: {e}, retrying in 5s...")
            time.sleep(5)


def get_rabbitmq_channel():
    """Helper to quickly open connection+channel for publishing"""
    connection, channel = get_connection()
    return connection, channel


# --- Metric Transformer ---
def transform_metric(raw_body: bytes) -> list[dict]:
    """
    Convert OTLP metrics payload into flat JSON rows (BigQuery-friendly).
    """
    try:
        msg = json.loads(raw_body)
    except Exception as e:
        logging.error(f"⚠️ Could not parse metric body as JSON: {e}")
        return None

    transformed = []

    # OTLP metrics are nested under resourceMetrics
    for rm in msg.get("resourceMetrics", []):
        resource_attrs = rm.get("resource", {}).get("attributes", [])

        # flatten resource attrs
        resource_attrs_dict = {
            a["key"]: list(a["value"].values())[0] for a in resource_attrs
        }

        for sm in rm.get("scopeMetrics", []):
            for metric in sm.get("metrics", []):
                metric_name = metric.get("name")

                # Handle SUM metrics
                if "sum" in metric:
                    for dp in metric["sum"].get("dataPoints", []):
                        dp_attrs = {
                            a["key"]: list(a["value"].values())[0]
                            for a in dp.get("attributes", [])
                        }

                        row = {
                            "store_id": store_id,
                            "metric_name": metric_name,
                            "timestamp": dp.get("timeUnixNano"),
                            "value": dp.get("asDouble") or dp.get("asInt"),
                            "attributes": json.dumps(dp_attrs),
                            "resource": json.dumps(resource_attrs_dict),
                        }
                        transformed.append(row)

                # TODO: also handle "gauge", "histogram" etc. if needed

    return transformed


# --- Downstream Sender ---
def send_downstream(body, is_metric=False):
    if is_metric:
        payload = transform_metric(body)
        logging.info(f"📥 Got Transform data : {payload[:200]}...")
        if not payload:
            return False
    else:
        # Decode bytes to string for non-metric messages
        try:
            payload = json.loads(body.decode('utf-8'))
        except Exception as e:
            logging.error(f"⚠️ Could not decode message body: {e}")
            return False

    while True:
        try:
            res = requests.post(DOWNSTREAM_URL, json=payload, timeout=5)
            res.raise_for_status()
            logging.info(f"✅ Sent to downstream: {payload}")
            return True
        except Exception as e:
            logging.error(f"🌐 Downstream error: {e}, retrying in 5s...")
            time.sleep(5)


# --- Consumer Callback ---
def callback(ch, method, properties, body, queue_type="logs"):
    logging.info(f"📥 Got message from {queue_type}: {body}...")
    if queue_type == "metrics":
        ok = send_downstream(body, is_metric=True)
    else:
        ok = send_downstream(body, is_metric=False)

    if ok:
        ch.basic_ack(delivery_tag=method.delivery_tag)
    else:
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


# --- Consumer Worker ---
def start_consumer(queue_name, queue_type="logs"):
    while True:
        try:
            connection, channel = get_connection()
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(
                queue=queue_name,
                on_message_callback=lambda ch, method, props, body: callback(ch, method, props, body, queue_type)
            )

            logging.info(f"🚀 RabbitMQ consumer started for {queue_type} queue: {queue_name}")
            channel.start_consuming()
        except Exception as e:
            logging.error(f"❌ Consumer for {queue_type} crashed: {e}, retrying in 5s...")
            time.sleep(5)

class LogData(BaseModel):
    app_info: str
    message_id: str
    event: str
    event_value: str
    timestamp: Optional[str] = None
    duration_ms: Optional[int] = None
    user_id: Optional[str] = None


EVENT_COUNTER = Counter(
    'app_events_total',
    'Total count of application events by type and value',
    ['app_name', 'store', 'filter_type', 'error_type','cam_id']
)

def record_metrics(log_data: LogData):
    """Extract and record metrics from log data"""
    labels = {
        'app_name': log_data.app_info,
        'store' : '1111',
    }
    
    # Count all events
    if log_data.message_id in 'LOG_ERROR':
      match = re.search(r":\s*(\d+)", log_data.event_value)
      extracted_number = match.group(1) if match else None
      logging.info(f"message contain: {log_data.message_id} : CAM_ID : {extracted_number}")
      
      EVENT_COUNTER.labels(
          **labels,
          filter_type=log_data.message_id,
          error_type=log_data.event,
          cam_id=extracted_number
      ).inc()


@app.post("/log")
async def log_message(request: LogData):
    try:
        """Publish incoming JSON to RabbitMQ"""
        data = await request.json()

        record_metrics(request)

        timestamp = data.get("timestamp") or time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

        # Build enriched payload
        payload = {
            "store_id": "store_123",
            "timestamp": timestamp,
            "app_info": data.get("app_info"),
            "message_id": data.get("message_id"),
            "event": data.get("event"),
            "event_value": data.get("event_value"),
            "insert_id": f"unique_message_id_{store_id}_{int(time.time())}"
        }

        connection, channel = get_rabbitmq_channel()
        channel.basic_publish(
            exchange="",
            routing_key=LOG_QUEUE,
            body=json.dumps(payload),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        logging.info(f"📤 Published to RabbitMQ logs_queue: {payload}")
        connection.close()
        return {"status": "Message sent to RabbitMQ", "data": data}
    except Exception as e:
        logging.error(f"Error processing log: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# expose health metric endpoint for prometheus metric data
# =========================
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(
        content=generate_latest(),
        media_type="text/plain"
    )


# =========================
# FASTAPI STARTUP EVENT
# =========================
@app.on_event("startup")
def startup_event():
    logging.info("⚡ Launching RabbitMQ consumers in background threads...")
    threading.Thread(target=start_consumer, args=(LOG_QUEUE, "logs"), daemon=True).start()
    threading.Thread(target=start_consumer, args=(METRIC_QUEUE, "metrics"), daemon=True).start()




# =========================
# MAIN ENTRYPOINT
# =========================
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
