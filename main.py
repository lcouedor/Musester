import spotipy
from spotipy.oauth2 import SpotifyOAuth
import cred 
import json

scope = "playlist-read-private playlist-modify-private playlist-modify-public"

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=cred.client_ID, client_secret= cred.client_SECRET, redirect_uri=cred.redirect_url, scope=scope))

def get_playlist_tracks(username,playlist_id):
    results = sp.user_playlist_tracks(username,playlist_id)
    tracks = results['items']
    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])
    return tracks

results = sp.current_user()
user_id = results['id']

playlist = sp.user_playlist_create(user_id, "cacatoès", public=False)
# print(json.dumps(playlist, sort_keys=1,indent=1))
# sp.user_playlist_add_tracks(user_id,playlist['id'],items=uris)

results = sp.playlist_tracks("2IDgys0kHnHd4VJ5suENKy")
track_ids = []
for idx, item in enumerate(results['items']):
    track = item['track']
    track_ids.append(track['id'])
    # print(json.dumps(track, sort_keys=1,indent=1))
    # print(idx)
    # print(idx, track['artists'][0]['name'], " – ", track['name'])

sp.user_playlist_add_tracks(user_id,playlist['id'],track_ids)
# print(get_playlist_tracks('spotify','2IDgys0kHnHd4VJ5suENKy'))