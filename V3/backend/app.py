from flask import Flask, jsonify
from flask_cors import CORS
from routes import routes
from config import mode

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://musester.onrender.com"}})

app.register_blueprint(routes)

if __name__ == '__main__':
    if mode == "dev":
        app.run(debug=False)
    else if mode == "prod":
        app.run(host='0.0.0.0', debug=True)
    