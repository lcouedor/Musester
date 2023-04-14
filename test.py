import spotipy
from spotipy.oauth2 import SpotifyOAuth
import cred
from pprint import pprint

# Remplacez YOUR_CLIENT_ID et YOUR_CLIENT_SECRET par vos propres informations d'identification de l'API Spotify.
scope = "playlist-read-private playlist-modify-private playlist-modify-public"
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=cred.client_ID, client_secret= cred.client_SECRET, redirect_uri=cred.redirect_url, scope=scope))


# ID Spotify de la piste que vous souhaitez analyser
track_id = '2FY7b99s15jUprqC0M5NCT'

# Récupérer les informations audio de la piste
audio_features = sp.audio_features(tracks=[track_id])

# print(audio_features)
pprint(audio_features)

# Récupérer la valence de la piste à partir des informations audio
valence = audio_features[0]['valence']

# Afficher la valence
# print('Valence de la piste :', valence)
