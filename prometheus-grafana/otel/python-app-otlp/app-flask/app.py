# flask_health_app.py
from flask import Flask, jsonify
import random
import time

app = Flask(__name__)

@app.route('/health')
def health_check():
    # Simulate some processing time
    delay = random.uniform(0.1, 0.5)
    time.sleep(delay)
    
    # Simulate occasional failures (10% chance)
    if random.random() < 0.1:
        return jsonify({
            "status": "down",
            "details": {
                "database": "error",
                "cache": "ok"
            }
        }), 500
    
    return jsonify({
        "status": "up",
        "details": {
            "database": "ok",
            "cache": "ok"
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
