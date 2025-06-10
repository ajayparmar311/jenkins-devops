from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/compute_average_age', methods=['POST'])
def compute_average_age():  

    # Process the request data
    data = request.json['data']
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Extract ages from the data
    ages = [item['age'] for item in data if 'age' in item]
    if not ages:
        return jsonify({'error': 'No age data available'}), 400
    
    # Compute the average age
    average_age = round(sum(ages) / len(ages), 1)

    return jsonify({'average_age': average_age})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)