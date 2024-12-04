from flask import Flask, jsonify
from flask_cors import CORS
from routes import routes

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://musester.onrender.com"}})

app.register_blueprint(routes)

if __name__ == '__main__':
    # app.run(host='0.0.0.0', debug=True)
    app.run(debug=False)