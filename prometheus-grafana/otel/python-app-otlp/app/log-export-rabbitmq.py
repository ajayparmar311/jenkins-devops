import json
import logging
import threading
import time

import pika
import requests
from fastapi import FastAPI, Request, HTTPException
import uvicorn

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
def transform_metric(raw_body: bytes) -> dict:
    """
    Convert OTLP-like payload into BigQuery-friendly JSON.
    Here I assume Collector sends JSON. If Protobuf → you need a parser.
    """
    try:
        msg = json.loads(raw_body)
    except Exception:
        logging.error("⚠️ Could not parse metric body as JSON")
        return None

    # Example transformation → flatten into schema
    transformed = []
    resource_attrs = msg.get("resource", {}).get("attributes", {})

    for scope_metric in msg.get("scopeMetrics", []):
        for metric in scope_metric.get("metrics", []):
            name = metric.get("name")
            for dp in metric.get("dataPoints", []):
                row = {
                    "store_id": store_id,
                    "metric_name": name,
                    "timestamp": dp.get("timeUnixNano"),
                    "value": dp.get("asDouble") or dp.get("asInt"),
                    "attributes": json.dumps(dp.get("attributes", {})),
                    "resource": json.dumps(resource_attrs)
                }
                transformed.append(row)

    return transformed


# --- Downstream Sender ---
def send_downstream(body, is_metric=False):
    payload = body
    if is_metric:
        payload = transform_metric(body)
        if not payload:
            return False

    while True:
        try:
            res = requests.post(DOWNSTREAM_URL, json=payload, timeout=5)
            res.raise_for_status()
            logging.info(f"✅ Sent to downstream: {payload}")
            return True
        except Exception as e:
            logging.error(f"🌐 Downstream error: {e}, retrying in 5s...")
            time.sleep(5)  # retry forever until success


# --- Consumer Callback ---
def callback(ch, method, properties, body, queue_type="logs"):
    logging.info(f"📥 Got message from {queue_type}: {body[:200]}...")
    if queue_type == "metrics":
        ok = send_downstream(body, is_metric=True)
    else:
        ok = send_downstream(body, is_metric=False)

    if ok:
        ch.basic_ack(delivery_tag=method.delivery_tag)


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


@app.post("/log")
async def log_message(request: Request):
    try:
        """Publish incoming JSON to RabbitMQ"""
        data = await request.json()
        
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
    uvicorn.run(app, host="0.0.
