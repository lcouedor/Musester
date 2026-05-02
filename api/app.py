import logging
import os
import secrets

from flask import Flask, jsonify
from flask_cors import CORS

from routes import bp
from services.auth import init_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s — %(message)s',
    datefmt='%H:%M:%S',
)


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
    app.register_blueprint(bp)
    init_db()

    @app.route('/')
    def home():
        return jsonify({'error': None, 'data': {'message': 'Musester API is running'}})

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.getenv('SECRET_KEY')
    app.config['SESSION_COOKIE_SAMESITE'] = 'None'
    app.config['SESSION_COOKIE_SECURE'] = False
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    ...