from flask import Flask, jsonify, request

app = Flask(__name__)

# Routes
@app.route('/')
def home():
    return jsonify({"message": "Welcome to the Flask Music API"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)