import spotipy
from spotipy.oauth2 import SpotifyOAuth
import cred

def get_spotify_client():
    # ---------- AUTHENTIFICATION ----------
    # Création de l'objet SpotifyOAuth pour obtenir les informations d'identification de l'utilisateur
    scope = "playlist-read-private playlist-modify-private playlist-modify-public"
    return spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope, redirect_uri=cred.redirect_url, client_id=cred.client_ID, client_secret=cred.client_SECRET, username=cred.username))
