from flask import Flask, jsonify, request
from flask_cors import CORS
from routes import routes
from config import mode

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["https://musester.onrender.com", "http://localhost:5173"]}})

app.register_blueprint(routes)

@app.before_request
def handle_options():
    if request.method == "OPTIONS":
        response = app.make_response("")
        response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, AuthorizationUser, AuthorizationPassword"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.status_code = 204  # No Content
        return response


if __name__ == '__main__':
    if mode == "dev":
        app.run(debug=False)
    elif mode == "prod":
        app.run(host='0.0.0.0', debug=True)
    