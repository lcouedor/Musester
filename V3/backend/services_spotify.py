import spotipy
from spotipy.oauth2 import SpotifyOAuth

from services_bdd import addSong, removeSong, getAllSongsService, addTagService, isPlaylistSongInDb, getTagIdByNameForSpotify, addSongsBatch
from services_chatgpt import getSongAutomaticTagsBatch

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
    # Je m'authentifie
    spotify = get_spotify_client()

    # Je récupère les pistes de la playlist source
    playlist_tracks = get_playlist_tracks(spotify, sourcePlaylistId)

    total_songs = len(playlist_tracks)

    songs_to_tag = [
        song for song in playlist_tracks
        if not isPlaylistSongInDb(song['song_spotify_id'])
    ]

    prepared_songs = []

    # Par paquet, je fais une requête à chatGPT pour récupérer les tags
    batch_size = 12

    async def process_batch(batch, start_index):
        # Je prépare une variable data qui m'affiche une ligne par chanson, avec le titre et les artistes
        data = ''
        for song in batch:
            data += 'Titre : ' + song['song_name'] + '\nArtiste(s) : ' + song['song_artists'] + '\n\n'
        
        song_tags = getSongAutomaticTagsBatch(data)  # Appel synchrone

        #Pour chaque chanson, je récupère les tags
        for song in batch:
            song_tags_ids = getTagIdByNameForSpotify(song_tags[batch.index(song)])
            song['tag_ids'] = song_tags_ids
            prepared_songs.append(song)
        
        progress = (start_index + len(batch)) / total_songs * 100
        print(f"Avancement : {progress:.2f}%")

    # Traitement en parallèle des lots
    tasks = [
        process_batch(songs_to_tag[i:i + batch_size], start_index=i)
        for i in range(0, len(songs_to_tag), batch_size)
    ]

    for i, song in enumerate(playlist_tracks):
        if isPlaylistSongInDb(song['song_spotify_id']):
            progress = (len(songs_to_tag) + i) / total_songs * 100
            print(f"Avancement : {progress:.2f}%")
    
    await asyncio.gather(*tasks)

    # Je les ajoute à la base de données par batchs de 100
    for i in range(0, len(prepared_songs), 100):
        addSongsBatch(prepared_songs[i:i + 100])

    return {"success": "Synchronization successful"}

def createThemePlaylist(songs: list, playlist_name: str):
    spotify_ids = [song['song_spotify_id'] for song in songs]
    
    # #Je m'authentifie
    spotify = get_spotify_client()

    #Je crée une playlist
    playlist = spotify.user_playlist_create(spotify.current_user()['id'], playlistPrefix + playlist_name, public=False)

    for i in range(0, len(spotify_ids), 100):
        spotify.playlist_add_items(playlist['id'], spotify_ids[i:i+100])

    return {"message": "Playlist created"}