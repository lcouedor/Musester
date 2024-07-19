import spotipy
from spotipy.oauth2 import SpotifyOAuth
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import numpy as np
import cred
import matplotlib.pyplot as plt

def get_playlist_audio_features(playlist_id):
    scope = "playlist-read-private playlist-modify-private playlist-modify-public"
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope, redirect_uri=cred.redirect_url, client_id=cred.client_ID, client_secret=cred.client_SECRET, username='leoco'))

    results = sp.playlist_tracks(playlist_id)
    tracks = results['items']

    audio_features = []

    for track in tracks:
        audio_features.append(sp.audio_features(track['track']['id'])[0])

    return audio_features

def get_playlist_tracks_names(sp, username, playlist_id):
    results = sp.user_playlist_tracks(username, playlist_id)
    tracks = results['items']
    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])

    return [track['track']['name'] for track in tracks]

def cluster_songs(audio_features, max_clusters):
    selected_features = ['valence', 'danceability', 'energy', 'acousticness', 'instrumentalness', 'tempo', 'speechiness']
    data = np.array([[track[feature] for feature in selected_features] for track in audio_features])

    scaler = StandardScaler()
    normalized_data = scaler.fit_transform(data)

    kmeans = KMeans(n_clusters=max_clusters, max_iter=1000, random_state=42)
    labels = kmeans.fit_predict(normalized_data)

    return labels


def main():
    max_clusters = 6
    playlist_id = '2ZP8XFhmRfBUlXK1T0Taxu'

    scope = "playlist-read-private playlist-modify-private playlist-modify-public"
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope, redirect_uri=cred.redirect_url, client_id=cred.client_ID, client_secret=cred.client_SECRET, username='leoco'))

    tracks_names = get_playlist_tracks_names(sp, 'leoco', playlist_id)

    audio_features = get_playlist_audio_features(playlist_id)

    # cluster_labels = cluster_songs(audio_features, max_clusters)
    cluster_labels = cluster_songs(audio_features, max_clusters)

    for i in range(max(cluster_labels) + 1):
        print(f'Cluster {i}:')
        for j in range(len(cluster_labels)):
            if cluster_labels[j] == i:
                print(f'    - {tracks_names[j]}')

if __name__ == "__main__":
    main()
