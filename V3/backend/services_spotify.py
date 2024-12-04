import spotipy
from spotipy.oauth2 import SpotifyOAuth

from services_bdd import addSong, removeSong, getAllSongsService, addTagService, isPlaylistSongInDb, getTagIdByNameForSpotify, get_or_create_tag, addSongsBatch
from services_chatgpt import getSongAutomaticTags

from config import playlistPrefix

from utils import getSecret
from dotenv import load_dotenv

load_dotenv()

from pprint import pprint
import asyncio

def get_spotify_client():
    scope = "playlist-read-private playlist-modify-private playlist-modify-public"
    return spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope, redirect_uri=getSecret('SPOTIFY_REDIRECT'), client_id=getSecret('SPOTIFY_ID'), client_secret=getSecret('SPOTIFY_SECRET'), username=getSecret('SPOTIFY_USERNAME')))

def get_playlist_tracks(sp, playlist_id):
    results = sp.playlist_tracks(playlist_id)
    tracks = results['items']
    while results['next']:
        results = sp.next(results)
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

async def syncService(sourcePlaylistId):
    #Je m'authentifie
    spotify = get_spotify_client()

    #Je récupère les pistes de la playlist source
    playlist_tracks = get_playlist_tracks(spotify, sourcePlaylistId)

    tasks = [prepareSongData(song) for song in playlist_tracks]
    prepared_songs = await asyncio.gather(*tasks)

    new_songs = [song for song in prepared_songs if song is not None]
    #J'ajoute les musiques par batchs de 100
    for i in range(0, len(new_songs), 100):
        addSongsBatch(new_songs[i:i+100])

    return {"success": "Synchronization successful"}

async def prepareSongData(song):
    #Si la piste n'est pas dans la base de données, je l'ajoute
    if isPlaylistSongInDb(song['song_spotify_id']):
        return None

    #Je récupère les tags de la piste
    song_tags = getSongAutomaticTags(song['song_name'], song['song_artists'])

    #Pour chaque tag, si il existe, je récupère son id, sinon je le crée
    song_tags_ids = []
    for tag in song_tags:
        tag_id = get_or_create_tag(tag)

        song_tags_ids.append(tag_id)

    #J'ajoute à song les ids des tags
    song['tag_ids'] = song_tags_ids
    return song

def createThemePlaylist(songs: list, playlist_name: str):
    spotify_ids = [song['song_spotify_id'] for song in songs]
    
    # #Je m'authentifie
    spotify = get_spotify_client()

    #Je crée une playlist
    playlist = spotify.user_playlist_create(spotify.current_user()['id'], playlistPrefix + playlist_name, public=False)

    for i in range(0, len(spotify_ids), 100):
        spotify.playlist_add_items(playlist['id'], spotify_ids[i:i+100])

    return {"error": "Not implemented yet"}