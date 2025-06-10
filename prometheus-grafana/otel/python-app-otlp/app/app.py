from flask import Flask
import logging
import time
import random

app = Flask(__name__)

# Python logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/')
def index():
    sleep_time = random.uniform(0.1, 0.5)
    time.sleep(sleep_time)
    logger.info(f"Handling request, simulated delay: {sleep_time:.2f}s")
    return "Hello from Flask with OpenTelemetry!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

