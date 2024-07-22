import json
import os

# Récupérer les pistes d'une playlist
def get_source_playlist_tracks(sp, username, playlist_id):
    results = sp.user_playlist_tracks(username,playlist_id)
    tracks = results['items']
    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])

    return tracks

# Supprimer des playlists les musiques qui ne sont plus dans la playlist source
#TODO possible d'optimiser en faisant d'abord un set de toutes les musiques à retirer par playlist
def clean_playlists(sp, playlist_tracks, source_playlist, playlistsNamesId):
    for p in playlist_tracks:
        for track in playlist_tracks[p]:
            if track not in [track['track']['id'] for track in source_playlist]: #Si la musique n'est plus dans la playlist source
                sp.playlist_remove_all_occurrences_of_items(p, [track])

# Récupération des caractéristiques audio des musiques de la playlist source (100 par 100 pour l'API Spotify)
# Si les musiques ne sont pas déjà dans la bdd, on les ajoute
# On retourne un tableau avec les caractéristiques audio des musiques de la playlist source (track_ids)
def get_audio_features(sp, track_ids, data_songs):
    audio_features = []

    audio_to_search = []

    for i in range(0, len(track_ids)):
        if track_ids[i] not in data_songs:
            audio_to_search.append(track_ids[i])
        else: 
            audio_features.append(data_songs[track_ids[i]])

    #On récupère les caractéristiques audio des musiques (par 100)
    for i in range(0, len(audio_to_search), 100):
        audio_features += sp.audio_features(tracks=audio_to_search[i:i+100])

    #On ajoute les musiques à la bdd si elles n'y sont pas déjà
    for track in audio_features:
        if track['id'] not in data_songs:
            data_songs[track['id']] = track

    #On sauvegarde la bdd
    save_database('data_songs', data_songs)

    return audio_features

#On tourne les genres des artistes passés en paramètre
#Si un ou des artistes ne sont pas dans la bdd, on les ajoute
#TODO possible d'optimiser en faisant d'abord un set de tous les artistes à rechercher
def get_artists_genres(sp, artists_to_search, data_artists):
    artists_genres = []
    for artist in artists_to_search:
        artist = artist['id']
        if artist not in data_artists:
            data_artists[artist] = sp.artist(artist)['genres']
        artists_genres.append(data_artists[artist])

    save_database('data_artists', data_artists)

    return artists_genres

# Pour ajouter toutes les musiques des playlists locales aux playlists spotify
def addAllTracks(sp, local_playlist):
    for playlist_id in local_playlist:
        #Ajout 100 par 100 des musiques
        for i in range(0, len(local_playlist[playlist_id]), 100):
            sp.playlist_add_items(playlist_id, local_playlist[playlist_id][i:i+100])

def configLoad():
    # On importe les noms de playlist et leurs seuils depuis config.json
    with open('config.json', 'r') as f:
        return json.load(f)

def open_database(dbName): #Le fichier dbName ne contient pas l'extension .json
    if os.path.exists(f'{dbName}.json'):
        with open(f'{dbName}.json', 'r') as file:
            return json.load(file)
    else:
        return {}

def save_database(dbName, db):
    with open(f'{dbName}.json', 'w') as file:
        json.dump(db, file, indent=4)