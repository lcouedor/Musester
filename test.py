import spotipy
from spotipy.oauth2 import SpotifyOAuth
import cred
from pprint import pprint

# Remplacez YOUR_CLIENT_ID et YOUR_CLIENT_SECRET par vos propres informations d'identification de l'API Spotify.
scope = "playlist-read-private playlist-modify-private playlist-modify-public"
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=cred.client_ID, client_secret= cred.client_SECRET, redirect_uri=cred.redirect_url, scope=scope))

# ID Spotify de la piste que vous souhaitez analyser
track_id = '7fZBQnc0zXwVybgCIrQQil'

# Récupérer les informations audio de la piste
track = sp.track(track_id)
# pprint(track["primary_language"])
audio_features = sp.audio_features(tracks=[track_id])

pprint(audio_features)

#afficher les genres d'un artiste à l'uri donné
artist_uri = 'spotify:artist:2ac0Lmf5nfZU6sq2t6MJLh'
artist = sp.artist(artist_uri)
# pprint(artist)