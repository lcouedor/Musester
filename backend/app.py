# from flask import Flask, jsonify, request
# from flask_cors import CORS
# from routes import routes
# from config import mode

# app = Flask(__name__)
# # CORS(app, resources={r"/*": {"origins": ["https://musester.onrender.com", "http://localhost:5173"]}})
# CORS(app, resources={r"/*": {"origins": "*"}})

# app.register_blueprint(routes)

# @app.before_request
# def handle_options():
#     if request.method == "OPTIONS":
#         response = app.make_response("")
#         response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
#         response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
#         response.headers["Access-Control-Allow-Headers"] = "Content-Type, AuthorizationUser, AuthorizationPassword"
#         response.headers["Access-Control-Allow-Credentials"] = "true"
#         response.status_code = 204  # No Content
#         return response


# if __name__ == '__main__':
#     if mode == "dev":
#         app.run(debug=False)
#     elif mode == "prod":
#         app.run(host='0.0.0.0', debug=True)
    


import os
from flask import Flask, redirect, request, session, url_for
from flask_cors import CORS
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from utils import getSecret
from dotenv import load_dotenv
from routes import routes

load_dotenv()

app = Flask(__name__)
app.register_blueprint(routes)

CORS(app, resources={r"/*": {"origins": "*"}})

# Configurations de Spotify
SPOTIPY_CLIENT_ID = getSecret('SPOTIFY_ID')
SPOTIPY_CLIENT_SECRET = getSecret('SPOTIFY_SECRET')
SPOTIPY_REDIRECT_URI = getSecret('SPOTIFY_REDIRECT')

# Clé secrète Flask pour la gestion des sessions
app.secret_key = os.urandom(24)

# Création de l'objet OAuth de Spotipy
sp_oauth = SpotifyOAuth(client_id=SPOTIPY_CLIENT_ID,
                         client_secret=SPOTIPY_CLIENT_SECRET,
                         redirect_uri=SPOTIPY_REDIRECT_URI,
                         scope="playlist-modify-public playlist-modify-private user-library-read")


# @app.route('/')
# def home():
    # if not session.get('token_info'):
    #     return redirect(url_for('login'))
    # return "Vous êtes déjà connecté, parfait!"

# @app.route('/login')
# def login():
#     auth_url = sp_oauth.get_authorize_url()
#     return redirect(auth_url)

# @app.route('/logout')
# def logout():
#     return redirect("https://www.spotify.com/logout/")

# def get_spotify_client():
#     token_info = session.get('token_info')
#     sp = Spotify(auth=token_info['access_token'])
#     return sp

if __name__ == '__main__':
    app.run(debug=True)
