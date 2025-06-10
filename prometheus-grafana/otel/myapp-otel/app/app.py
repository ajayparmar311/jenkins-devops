from flask import Flask
import time
import random

app = Flask(__name__)

@app.route('/')
def index():
    time.sleep(random.uniform(0.1, 0.5))  # Simulate latency
    return "Hello from Flask with OpenTelemetry!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

