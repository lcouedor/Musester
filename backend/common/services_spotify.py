import spotipy
from spotipy.oauth2 import SpotifyOAuth

from config import playlistPrefix

from utils import getSecret
from dotenv import load_dotenv

load_dotenv()

from pprint import pprint
import asyncio

def get_spotify_client():
    scope = "playlist-read-private playlist-modify-private playlist-modify-public"
    return spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope, redirect_uri=getSecret('SPOTIFY_REDIRECT'), client_id=getSecret('SPOTIFY_ID'), client_secret=getSecret('SPOTIFY_SECRET'), username=getSecret('SPOTIFY_USERNAME')))

def get_playlist_tracks(playlist_id):
    spotify = get_spotify_client()

    results = spotify.playlist_tracks(playlist_id)
    tracks = results['items']
    while results['next']:
        results = spotify.next(results)
        tracks.extend(results['items'])
    
    songs = []
    for item in tracks:
        track = item['track']
        
        #Pour les artistes je fais juste une string de leurs noms spérarés par un tiret
        artists = ''
        for artist in track['artists']:
            artists += artist['name'] + '-'
        song_info = {
            'song_name': track['name'],
            'song_spotify_id': track['id'],
            'song_artists': artists[:-1],
            'tag_ids': []
        }
        songs.append(song_info)
        
    return songs

def createThemePlaylist(songs: list, playlist_name: str):
    spotify_ids = [song['song_spotify_id'] for song in songs]
    
    #Je m'authentifie
    spotify = get_spotify_client()

    #Je crée une playlist
    playlist = spotify.user_playlist_create(spotify.current_user()['id'], playlistPrefix + playlist_name, public=False)

    for i in range(0, len(spotify_ids), 100):
        spotify.playlist_add_items(playlist['id'], spotify_ids[i:i+100])

    return {"message": "Playlist created"}