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


def get_rabbitmq_channel():
    """Create a RabbitMQ connection + channel"""
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT)
    )
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    return connection, channel


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
# RABBITMQ CONSUMER
# =========================
def callback(ch, method, properties, body):
    """Consume messages and forward downstream"""
    try:
        message = json.loads(body.decode())
        logging.info(f"📥 Consumed from RabbitMQ: {message}")

        # Try sending downstream
        resp = requests.post(DOWNSTREAM_URL, json=message, timeout=5)

        if resp.status_code == 200:
            logging.info(f"✅ Forwarded to {DOWNSTREAM_URL} successfully")
            ch.basic_ack(delivery_tag=method.delivery_tag)  # Ack only on success
        else:
            logging.error(f"❌ Downstream returned {resp.status_code}, retry later")
            # No ack → stays in queue
    except requests.exceptions.RequestException as e:
        logging.error(f"🌐 Network/Downstream error: {e}, will retry later")
        # No ack → stays in queue
    except Exception as e:
        logging.error(f"🔥 Unexpected error: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def start_consumer():
    """Keep consumer alive, retry if RabbitMQ/connection fails"""
    while True:
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT)
            )
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_NAME, durable=True)

            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)

            logging.info("🚀 RabbitMQ consumer started. Waiting for messages...")
            channel.start_consuming()
        except Exception as e:
            logging.error(f"❌ Consumer crashed: {e}, retrying in 5s...")
            time.sleep(5)


@app.on_event("startup")
def startup_event():
    logging.info("⚡ FastAPI startup event triggered, launching consumer thread...")
    consumer_thread = threading.Thread(target=start_consumer, daemon=True)
    consumer_thread.start()


# =========================
# MAIN ENTRYPOINT
# =========================
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
