import spotipy
from spotipy.oauth2 import SpotifyOAuth
from cred import client_ID, client_SECRET, username, redirect_url

# Récupérer le client Spotify
# @return Spotify client
def get_spotify_client():
    scope = "playlist-read-private playlist-modify-private playlist-modify-public"
    return spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope, redirect_uri=redirect_url, client_id=client_ID, client_secret=client_SECRET, username=username))

# Récupérer les pistes d'une playlist
# @param sp: Spotify client
# @param playlist_id: str
# @return list[dict]
def get_playlist_tracks(sp, playlist_id):
    results = sp.playlist_tracks(playlist_id)
    tracks = results['items']
    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])

    return tracks

# Récupérer les caractéristiques audio des pistes d'une playlist
# @param sp: Spotify client 
# @param tracks: list[dict]
# @return list[dict]
def get_audio_features(sp, tracks):
    audio_features = []
    for i in range(0, len(tracks), 50):
        audio_features.extend(sp.audio_features([track['track']['id'] for track in tracks[i:i+50]]))

    return audio_features
    
