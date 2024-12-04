from flask import Flask, jsonify, request

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://musester.onrender.com"}})

# Routes
@app.route('/')
def home():
    return jsonify({"message": "Welcome to the Flask Music API"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)