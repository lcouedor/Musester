import spotipy
from spotipy.oauth2 import SpotifyOAuth
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import numpy as np
import cred
import math as Math

def main():
    music1ID = '17i5jLpzndlQhbS4SrTd0B'
    music2ID = '22Jl3U3TwB9jYy0rPZiT6C'
    music3ID = '11Ojp7JniVvwd0gmgvyKkd'

    scope = "playlist-read-private playlist-modify-private playlist-modify-public"
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope, redirect_uri=cred.redirect_url, client_id=cred.client_ID, client_secret=cred.client_SECRET, username='leoco'))

    #On récupère les features des musiques:
    musique1 = sp.audio_features(music1ID)
    musique2 = sp.audio_features(music2ID)
    musique3 = sp.audio_features(music3ID)

    #Distance dans l'espace d'un plan à 7 dimensions: (acousticness, danceability, energy, instrumentalness, liveness, speechiness, valence)
    distancemusique1musique2 = Math.sqrt((musique1[0]['acousticness'] - musique2[0]['acousticness'])**2 + (musique1[0]['danceability'] - musique2[0]['danceability'])**2 + (musique1[0]['energy'] - musique2[0]['energy'])**2 + (musique1[0]['instrumentalness'] - musique2[0]['instrumentalness'])**2 + (musique1[0]['liveness'] - musique2[0]['liveness'])**2 + (musique1[0]['speechiness'] - musique2[0]['speechiness'])**2 + (musique1[0]['valence'] - musique2[0]['valence'])**2)
    distancemusique1musique3 = Math.sqrt((musique1[0]['acousticness'] - musique3[0]['acousticness'])**2 + (musique1[0]['danceability'] - musique3[0]['danceability'])**2 + (musique1[0]['energy'] - musique3[0]['energy'])**2 + (musique1[0]['instrumentalness'] - musique3[0]['instrumentalness'])**2 + (musique1[0]['liveness'] - musique3[0]['liveness'])**2 + (musique1[0]['speechiness'] - musique3[0]['speechiness'])**2 + (musique1[0]['valence'] - musique3[0]['valence'])**2)
    print(distancemusique1musique2)
    print(distancemusique1musique3)
    

if __name__ == "__main__":
    main()
