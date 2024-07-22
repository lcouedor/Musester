import json
import os

# Récupérer une playlist
def get_playlist(sp, playlist_name):
    playlists = sp.current_user_playlists()
    for playlist in playlists['items']:
        if playlist['name'] == playlist_name:
            return playlist
    return None

# Récupérer les pistes d'une playlist
def get_source_playlist_tracks(sp, username, playlist_id):
    results = sp.user_playlist_tracks(username,playlist_id)
    tracks = results['items']
    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])

    return tracks

#Si l'id de la piste n'est pas dans la base de données, on récupère les audio_features de la piste pour les ajouter à la base de données
#On retourne ensuite les audio_features des pistes passées en paramètre (celles d'une playlist)
def get_audio_features(sp, tracks_ids, db):
    songs_to_get = []
    audio_features_to_return = []
    for i in range(0, len(tracks_ids)):
        if tracks_ids[i] not in db:
            songs_to_get.append(tracks_ids[i])
        else:
            audio_features_to_return.append(db[tracks_ids[i]])
    
    #On récupère ensuite 100 par 100 les audio_features des pistes à récupérer et on les ajoute à la base de données
    for i in range(0, len(songs_to_get), 100):
        audio_features = sp.audio_features(songs_to_get[i:i+100])
        for audio_feature in audio_features:
            db[audio_feature['id']] = audio_feature
            audio_features_to_return.append(audio_feature)

    #On enregistre la base de données
    save_database('data_songs', db)

    return audio_features_to_return

def get_artists_genre(sp, artists_ids, db):
    artists_to_get = []
    for i in range(0, len(artists_ids)):
        if artists_ids[i] not in db:
            artists_to_get.append(artists_ids[i])
    
    #On récupère ensuite 50 par 50 les genres des artistes à récupérer et on les ajoute à la base de données
    for i in range(0, len(artists_to_get), 50):
        artists = sp.artists(artists_to_get[i:i+50])
        for artist in artists['artists']:
            db[artist['id']] = artist['genres']

    #On enregistre la base de données
    save_database('data_artists', db)

def add_tracks(sp, playlist_id, tracks_ids):
    for i in range(0, len(tracks_ids), 100):
        sp.playlist_add_items(playlist_id, tracks_ids[i:i+100])

def create_playlist(sp, playlist_name):
    return sp.user_playlist_create(sp.current_user()['id'], playlist_name, public=False)

# On importe les noms de playlist et leurs seuils depuis config.json
def configLoad():
    with open('config.json', 'r') as f:
        return json.load(f)

# Ouverture et enregistrement de la base de données
def open_database(dbName): #Le fichier dbName ne contient pas l'extension .json
    if os.path.exists(f'{dbName}.json'):
        with open(f'{dbName}.json', 'r') as file:
            return json.load(file)
    else:
        return {}
def save_database(dbName, db):
    with open(f'{dbName}.json', 'w') as file:
        json.dump(db, file, indent=4)