import json
import logging
import threading
import time

import pika
import requests
from fastapi import FastAPI, Request
import uvicorn

# =========================
# CONFIG
# =========================
RABBITMQ_HOST = "rabbitmq"
RABBITMQ_PORT = 5672
QUEUE_NAME = "logs_queue"
DOWNSTREAM_URL = "http://192.168.1.9:5001/v1/metrics"

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
            channel.queue_declare(queue=QUEUE_NAME, durable=True)
            return connection, channel
        except Exception as e:
            logging.error(f"Failed to connect to RabbitMQ: {e}, retrying in 5s...")
            time.sleep(5)


def get_rabbitmq_channel():
    """Helper to quickly open connection+channel for publishing"""
    connection, channel = get_connection()
    return connection, channel


# --- Downstream Sender ---
def send_downstream(body):
    while True:
        try:
            res = requests.post(DOWNSTREAM_URL, json=json.loads(body), timeout=5)
            res.raise_for_status()
            logging.info(f"✅ Sent to downstream: {body}")
            return True
        except Exception as e:
            logging.error(f"🌐 Downstream error: {e}, retrying in 5s...")
            time.sleep(5)  # retry forever until success


# --- Consumer Callback ---
def callback(ch, method, properties, body):
    logging.info(f"📥 Got message: {body}")
    if send_downstream(body):  # retry until success
        ch.basic_ack(delivery_tag=method.delivery_tag)


# --- Consumer Worker ---
def start_consumer():
    while True:
        try:
            connection, channel = get_connection()
            channel.basic_qos(prefetch_count=1)  # Fair dispatch
            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)

            logging.info("🚀 RabbitMQ consumer started. Waiting for messages...")
            channel.start_consuming()
        except Exception as e:
            logging.error(f"❌ Consumer crashed: {e}, retrying in 5s...")
            time.sleep(5)


# =========================
# FASTAPI ROUTES
# =========================
@app.post("/log")
async def log_message(request: Request):
    """Publish incoming JSON to RabbitMQ"""
    data = await request.json()
    connection, channel = get_rabbitmq_channel()
    channel.basic_publish(
        exchange="",
        routing_key=QUEUE_NAME,
        body=json.dumps(data),
        properties=pika.BasicProperties(delivery_mode=2)  # persistent
    )
    logging.info(f"📤 Published to RabbitMQ: {data}")
    connection.close()
    return {"status": "Message sent to RabbitMQ", "data": data}


# =========================
# FASTAPI STARTUP EVENT
# =========================
@app.on_event("startup")
def startup_event():
    logging.info("⚡ Launching RabbitMQ consumer in background thread...")
    consumer_thread = threading.Thread(target=start_consumer, daemon=True)
    consumer_thread.start()


# =========================
# MAIN ENTRYPOINT
# =========================
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)