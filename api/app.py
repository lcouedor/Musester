import logging
import os
import secrets

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from routes import bp
from services.auth import init_db
import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s — %(message)s',
    datefmt='%H:%M:%S',
)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'web')


def create_app() -> Flask:
    app = Flask(__name__, static_folder=FRONTEND_DIR)
    app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))
    is_prod = bool(os.getenv('RENDER') or os.getenv('FLASK_ENV') == 'production')
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE']   = is_prod
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    CORS(app)
    app.register_blueprint(bp)
    init_db()

    @app.route('/')
    def index():
        return send_from_directory(FRONTEND_DIR, 'index.html')

    @app.route('/<path:filename>')
    def static_files(filename):
        return send_from_directory(FRONTEND_DIR, filename)

    @app.route('/api')
    def home():
        return jsonify({'error': None, 'data': {'message': 'Musester API is running'}})

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=config.PORT)
