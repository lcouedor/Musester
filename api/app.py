from flask import Flask, jsonify
from flask_cors import CORS
from routes import bp

def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}})
    app.register_blueprint(bp)

    @app.route('/')
    def home():
        return jsonify({'message': 'Welcome to Musester API'})

    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
