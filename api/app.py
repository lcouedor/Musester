import logging
import os
import secrets

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from routes import bp
from services.auth import init_db
from services.jobs import init_jobs_table
import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s — %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'web')


def create_app() -> Flask:
    app = Flask(__name__, static_folder=FRONTEND_DIR)
    secret_key = os.getenv('SECRET_KEY')
    if not secret_key:
        # Sans SECRET_KEY fixe, chaque worker gunicorn génère sa propre clé au
        # démarrage — un /auth/login et le /auth/callback qui suit peuvent alors
        # tomber sur deux workers différents, et la vérification d'oauth_state
        # échoue de façon intermittente et difficile à diagnostiquer sans ce log.
        logger.warning(
            "SECRET_KEY non défini — clé de session générée à la volée pour ce "
            "process. Avec plusieurs workers, la validation oauth_state échouera "
            "aléatoirement. Définir SECRET_KEY dans l'environnement."
        )
        secret_key = secrets.token_hex(32)
    app.secret_key = secret_key
    is_prod = bool(os.getenv('RENDER') or os.getenv('FLASK_ENV') == 'production')
    # Ce cookie ne sert plus qu'à `oauth_state` pendant le hand-off OAuth (Render <-> Spotify),
    # toujours en navigation top-level donc jamais cross-site : Lax suffit.
    # L'auth API elle-même passe par un bearer token (voir services/auth.py) — un cookie de
    # session classique ne survivrait pas sur Safari (ITP tue les cookies tiers cross-site).
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE']   = is_prod
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    CORS(app, origins=[config.FRONTEND_URL], allow_headers=["Content-Type", "Authorization"])
    app.register_blueprint(bp)
    init_db()
    init_jobs_table()

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
