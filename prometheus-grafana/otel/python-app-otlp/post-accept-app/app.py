from flask import Flask, request, jsonify
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/v1/metrics', methods=['POST'])
def handle_post_request():
    try:
        # Get JSON data from request
        json_data = request.get_json()
        
        if json_data is None:
            logger.warning("No JSON data received")
            return jsonify({"error": "No JSON data received"}), 400
        
        # Print the JSON data with timestamp
        logger.info("Received JSON data: %s", json_data)
        
        return jsonify({
            "message": "Data received successfully",
            "received_data": json_data
        }), 200
        
    except Exception as e:
        logger.error("Error processing request: %s", str(e))
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "service": "flask-api"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
