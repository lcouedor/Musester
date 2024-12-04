import spotipy
from spotipy.oauth2 import SpotifyOAuth

from cred import client_ID, client_SECRET, username, redirect_url
from services_bdd import addSong, removeSong, getAllSongsService, getTagIdByName, addTagService, isPlaylistSongInDb
from services_chatgpt import getSongAutomaticTags

from config import playlistPrefix

from pprint import pprint

def get_spotify_client():
    scope = "playlist-read-private playlist-modify-private playlist-modify-public"
    return spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope, redirect_uri=redirect_url, client_id=client_ID, client_secret=client_SECRET, username=username))

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

def syncService(sourcePlaylistId):
    #Je m'authentifie
    spotify = get_spotify_client()

    #Je récupère les pistes de la playlist source
    playlist_tracks = get_playlist_tracks(spotify, sourcePlaylistId)
    #Je récupère toutes les pistes de la base de données
    allSongsInDb = getAllSongsService()

    idx = 0

    # Je compare les pistes de la playlist source avec celles de la base de données
    for song in playlist_tracks:
        print(f"{idx}/{len(playlist_tracks)}")
        idx += 1
        
        #Si la piste n'est pas dans la base de données, je l'ajoute
        if not isPlaylistSongInDb(song['song_spotify_id']):
            #Je récupère les tags de la piste
            song_tags = getSongAutomaticTags(song['song_name'], song['song_artists'])

            #Pour chaque tag, si il existe, je récupère son id, sinon je le crée
            song_tags_ids = []
            for tag in song_tags:
                tag_id = getTagIdByName(tag).json
                if 'error' in tag_id:
                    tag_id = addTagService(tag)
                    tag_id = tag_id[0]['id']
                else: 
                    tag_id = tag_id['tag_id']

                song_tags_ids.append(tag_id)

            #J'ajoute à song les ids des tags
            song['tag_ids'] = song_tags_ids
            addSong(song)            

    return {"success": "Synchronization successful"}

def createThemePlaylist(songs: list, playlist_name: str):
    spotify_ids = [song['song_spotify_id'] for song in songs]
    
    # #Je m'authentifie
    spotify = get_spotify_client()

    #Je crée une playlist
    playlist = spotify.user_playlist_create(spotify.current_user()['id'], playlistPrefix + playlist_name, public=False)

    for i in range(0, len(spotify_ids), 100):
        spotify.playlist_add_items(playlist['id'], spotify_ids[i:i+100])

    return {"error": "Not implemented yet"}
