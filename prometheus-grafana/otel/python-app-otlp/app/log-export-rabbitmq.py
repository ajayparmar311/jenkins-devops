from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
import logging
import time
from typing import Optional
import uvicorn
import re
import pika
import json
import threading
import requests

app = FastAPI()


class LogData(BaseModel):
    app_info: str
    message_id: str
    event: str
    event_value: str
    timestamp: Optional[str] = None
    duration_ms: Optional[int] = None
    user_id: Optional[str] = None



# ========== RABBITMQ CONNECTION ==========
def get_rabbitmq_channel():
    """Establish and return a RabbitMQ channel"""
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host="rabbitmq", port=5672)  # rabbitmq is service name in docker network
    )
    channel = connection.channel()
    channel.queue_declare(queue="logs_queue", durable=True)
    return connection, channel

def publish_to_rabbitmq(message: dict):
    """Publish message to RabbitMQ"""
    connection, channel = get_rabbitmq_channel()
    channel.basic_publish(
        exchange="",
        routing_key="logs_queue",
        body=json.dumps(message),
        properties=pika.BasicProperties(
            delivery_mode=2,  # make message persistent
        )
    )
    connection.close()


@app.post("/log")
async def handle_log(log_data: LogData):
    try:
        if not log_data.timestamp:
            log_data.timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

        # Build enriched payload for RabbitMQ
        payload = {
            "store_id": "store_123",   # static or dynamic if needed
            "timestamp": log_data.timestamp,
            "app_info": log_data.app_info,
            "message_id": log_data.message_id,
            "event": log_data.event,
            "event_value": log_data.event_value,
            "insert_id": f"unique_message_id_{int(time.time())}"  # you can also pass externally
        }

        # Publish to RabbitMQ
        publish_to_rabbitmq(payload)

        logging.info(f"Published to RabbitMQ: {payload}")

        return {
            "status": "success",
            "message_id": log_data.message_id,
            "processed_at": time.time()
        }
    except Exception as e:
        logging.error(f"Error processing log: {e}")
        raise HTTPException(status_code=500, detail=str(e))


DOWNSTREAM_URL = "http://192.168.1.9:5001/v1/metrics"  # Replace with target application URL

def callback(ch, method, properties, body):
    """Callback for RabbitMQ messages"""
    try:
        message = json.loads(body.decode())
        logging.info(f"Consumed from RabbitMQ: {message}")

        # Send to downstream
        resp = requests.post(DOWNSTREAM_URL, json=message, timeout=5)

        if resp.status_code == 200:
            logging.info(f"Forwarded to {DOWNSTREAM_URL} successfully")
            ch.basic_ack(delivery_tag=method.delivery_tag)  # ✅ Ack only on success
        else:
            logging.error(f"Downstream returned {resp.status_code}, retry later")
            # ❌ Do not ack → RabbitMQ keeps the message
    except requests.exceptions.RequestException as e:
        logging.error(f"Network/Downstream error: {e}, retry later")
        # ❌ No ack → message stays in queue
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def start_consumer():
    """Start RabbitMQ consumer loop"""
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host="rabbitmq", port=5672)
        )
        channel = connection.channel()
        channel.queue_declare(queue="logs_queue", durable=True)

        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue="logs_queue", on_message_callback=callback)

        logging.info("✅ RabbitMQ consumer started. Waiting for messages...")
        channel.start_consuming()   # <- BLOCKS FOREVER, keeps consumer alive
    except Exception as e:
        logging.error(f"❌ Consumer crashed: {e}")
        time.sleep(5)
        start_consumer()  # auto-restart if crash


# Launch consumer in background thread when FastAPI starts
@app.on_event("startup")
def startup_event():
    consumer_thread = threading.Thread(target=start_consumer, daemon=True)
    consumer_thread.start()




# ========== MAIN ==========
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Start the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5000,
        log_config=None  # Use default logging config
    )
