import logging
from flask import Flask, jsonify
from flask_cors import CORS
from routes import bp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s — %(message)s',
    datefmt='%H:%M:%S',
)

def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}})
    app.register_blueprint(bp)

    @app.route('/')
    def home():
        return jsonify({'error': None, 'data': {'message': 'Musester API is running'}})

    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
