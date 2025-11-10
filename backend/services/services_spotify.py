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

def get_playlist_tracks_infos(playlist_id, extended=False):
    spotify = get_spotify_client()

    results = spotify.playlist_tracks(playlist_id)
    tracks = results['items']
    while results['next']:
        results = spotify.next(results)
        tracks.extend(results['items'])
    
    songs = []
    # pprint(tracks[0])
    for item in tracks:
        track = item['track']
        
        artists = ''
        for artist in track['artists']:
            artists += artist['name'] + '-'
        song_info = {
            'id': track['id'],
            'title': track['name'],
            'artists': artists[:-1],
            'album': track['album']['name'],
        }
        
        if extended:
            song_info['added_at'] = item['added_at']

        songs.append(song_info)
        
    return songs

def get_matching_songs_ids(songs, iaDecisions, treshold_match_percentage):
    selected_songs = []
    for decision in iaDecisions:
        # si l'id est aussi présent dans les chansons et que le pourcentage est au dessus du seuil
        if any(song['id'] == decision['id'] for song in songs) and int(decision['match']) >= treshold_match_percentage:
            selected_songs.append(next(song['id'] for song in songs if song['id'] == decision['id']))

    return selected_songs

def create_user_playlist(playlist_name: str, description: str, songs_ids: list):
    spotify = get_spotify_client()
    user_id = spotify.current_user()['id']
    playlist = spotify.user_playlist_create(user=user_id, name=playlistPrefix + playlist_name, public=False, description=description)
    for i in range(0, len(songs_ids), 100):
        spotify.playlist_add_items(playlist_id=playlist['id'], items=songs_ids[i:i+100])
    return playlist['id']

def remove_songs_from_playlist(playlist_id: str, songs_ids: list):
    spotify = get_spotify_client()
    for i in range(0, len(songs_ids), 100):
        spotify.playlist_remove_all_occurrences_of_items(playlist_id=playlist_id, items=songs_ids[i:i+100])