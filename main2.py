# ---------- IMPORTS ----------
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import cred
from pprint import pprint
import os
import re
import json
import datetime

clear = lambda: os.system('clear')

# ---------- VARIABLES ----------
# On importe les noms de playlist et leurs seuils depuis config.json
with open('config.json', 'r') as f:
    config = json.load(f)

#Ouvrir le fichier data_artists.json
if os.path.exists('data_artists.json'):
    with open('data_artists.json', 'r') as file:
        data_artists = json.load(file)
else:
    # Si le fichier n'existe pas, initialiser un dictionnaire vide
    data_artists = {} #La base de données des genres des artistes (la clé est l'id de l'artiste et la valeur est une liste de genres)

#Ouvrir le fichier data_songs.json
if os.path.exists('data_songs.json'):
    with open('data_songs.json', 'r') as file:
        data_songs = json.load(file)
else:
    # Si le fichier n'existe pas, initialiser un dictionnaire vide
    data_songs = {} #La base de données des données des musiques (la clé est l'id de la musique et la valeur est un dictionnaire de données)

# On initialise les listes de playlists de l'utilisateur 
user_playlists = []
# On initialise la liste des pistes de chaque playlist de l'utilisateur
playlist_tracks = {}
# Les musiques à ajouter dans les playlists
local_playlist = {}
#Dictionnaire des noms de playlists avec leur id
playlistsNamesId = {}

# ---------- FONCTIONS ----------

# Récupérer les pistes d'une playlist
def get_source_playlist_tracks(sp, username, playlist_id):
    results = sp.user_playlist_tracks(username,playlist_id)
    tracks = results['items']
    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])

    return tracks

#Récupérer les playlists de l'utilisateur et créer celles de la config si elles n'existent pas + préparer les variables globales
def preparePlaylists(sp):
    user_playlists = []
    for playlist in sp.current_user_playlists()['items']:
        if playlist['name'][:5] == 'Ge - ':
            user_playlists.append(playlist)
            musicsPlaylist = sp.playlist_tracks(playlist['id'], fields="items(track(id))")
            #J'ajoute les id des musiques de la playlist à la liste playlist_tracks
            playlist_tracks[playlist['id']] = [track['track']['id'] for track in musicsPlaylist['items']]
            playlistsNamesId[playlist['name']] = playlist['id']

    for playlist in config:
        playlist_name = f"Ge - {playlist['name'].capitalize()}"
        if playlist_name not in playlistsNamesId:
            new_playlist = sp.user_playlist_create(user=sp.current_user()['id'], name=playlist_name, public=True)
            user_playlists.append(new_playlist)
            playlist_tracks[new_playlist['id']] = []
            playlistsNamesId[playlist_name] = new_playlist['id']

    #J'ajoute aussi mano dans les playlists locales
    playlist_name = "Ge - Mano"
    if playlist_name not in playlistsNamesId:
        new_playlist = sp.user_playlist_create(user=sp.current_user()['id'], name=playlist_name, public=True)
        user_playlists.append(new_playlist)
        playlist_tracks[new_playlist['id']] = []
        playlistsNamesId[playlist_name] = new_playlist['id']

    #Je prépare les playlists locales
    for playlist_id in playlist_tracks:
        local_playlist[playlist_id] = []

# Définir les playlists auxquelles ajouter la piste
def definePlaylist(track, artists):
    playlist_add = [] # liste des playlist auxquelles ajouter la piste

    #Je récupère les genres des artistes de la musique
    local_genre = []
    for artist in artists:
        local_genre += data_artists[artist['id']]

    for playlist in config: #Pour chaque playlist de la config, je regarde si la musique correspond
        #Je regarde les filtres de la playlist dans le conf
        filters = playlist['filters']

        include_artists = False
        if 'artists' in filters:
            include_artists = any(artist['name'] in filters['artists'].get('include', []) for artist in artists)
            if any(artist['name'] in filters['artists'].get('exclude', []) for artist in artists):
                continue

        #Je regarde si le genre de la musique est dans les genres de la playlist
        if 'genre' in filters and not include_artists: #Si aucun artist n'a d'inclusion prioritaire, je regarde si le genre de la musique est dans les genres de la playlist
            # if 'exclude' in filters['genre'] and any(genre in local_genre for genre in filters['genre']['exclude']): #Si un des genres de la musique est dans les genres à exclure de la playlist
            #     continue
            # if 'include' in filters['genre'] and not any(genre in local_genre for genre in filters['genre']['include']): #Si aucun des genres de la musique n'est dans les genres de la playlist
            #     continue

            #Si un des genres de la musique est dans les genres à exclure de la playlist (j'utilise un substring pour matcher depuis rap par exemple aussi bien "rap" que "rap français" ou "pop rap", ...)
            if 'exclude' in filters['genre'] and any(re.search(genre, ' '.join(local_genre)) for genre in filters['genre']['exclude']):
                continue
            #Si aucun des genres de la musique n'est dans les genres de la playlist
            if 'include' in filters['genre'] and not any(re.search(genre, ' '.join(local_genre)) for genre in filters['genre']['include']):
                continue

        #Je regarde si les valeurs de la musique sont dans les valeurs de la playlist
        for key in filters:
            if key in ['genre', 'artists']:
                continue
            if key in ['valence', 'danceability', 'energy', 'acousticness', 'instrumentalness', 'tempo', 'speechiness']:
                if track[key] < filters[key]['min'] or track[key] > filters[key]['max']:
                    break
            elif key == 'mode':
                if (track['mode'] == 1 and filters[key] == 'mineur') or (track['mode'] == 0 and filters[key] == 'majeur'):
                    break
            elif key == 'releaseDate':
                #Si l'une des borne vaut "-", on ne la prend pas en compte
                if (filters[key]['min'] != "-" and int(track['releaseDate'].split('-')[0]) <= int(filters[key]['min'])) or (filters[key]['max'] != "-" and int(track['releaseDate'].split('-')[0]) >= int(filters[key]['max'])):
                    break
            elif key == 'likedDate':
                #On récupère le derner mot de la date (pour savoir si c'est days, months ou years)
                temporalite = filters[key].split(' ')[-1]
                #On récupère le nombre
                nombre = int(filters[key].split(' ')[0])
                #On récupère la date de like
                likedAt = track['likedDate'].split('T')[0]
                #On récupère la date actuelle
                now = datetime.datetime.now().strftime('%Y-%m-%d')
                #On récupère la différence entre les deux dates
                diff = datetime.datetime.strptime(now, '%Y-%m-%d') - datetime.datetime.strptime(likedAt, '%Y-%m-%d')
                #On récupère le nombre de jours de différence
                diff = diff.days
                #On regarde si la temporalité est en jours
                if temporalite == 'days':
                    if diff > nombre:
                        break
                #On regarde si la temporalité est en mois
                elif temporalite == 'months':
                    if diff > nombre*30:
                        break
                #On regarde si la temporalité est en années
                elif temporalite == 'years':
                    if diff > nombre*365:
                        break
            else:
                print('Erreur : clé inconnue')
                break
        else:
            playlist_add.append(playlist['name'])
            continue

    # Ajout d'une playlist si aucune ne convient
    if len(playlist_add) == 0:
        playlist_add.append('Mano')   

    #Suppression des doublons
    playlist_add = list(set(playlist_add))

    return playlist_add

# Pour chaque playlist à laquelle une musique doit être ajouté, je l'ajoute aux playlists locales
def fillLocalPlaylists(track, playlist_add):
    for playlist in playlist_add:
        playlist_name = f"Ge - {playlist.capitalize()}"
        playlist_id = playlistsNamesId[playlist_name]
        local_playlist[playlist_id].append(track['id'])

# Print iterations progress
def printProgressBar (iteration, total, prefix = '', suffix = '', decimals = 1, length = 100, fill = '█', printEnd = "\r"):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end = printEnd)
    # Print New Line on Complete
    if iteration == total: 
        print()

# Pour retirer des playlists locales les musiques déjà présentes dans les playlists spotify
def cleanAlreadyAdded():
    #Pour chaque playlist locale
    for playlist_id in local_playlist:
        #Pour toutes les musiques, je les ajoute à ma liste de musiques à ajouter si elles ne sont pas déjà dans la playlist spotify
        newTracks = []
        for track in local_playlist[playlist_id]:
            if track not in playlist_tracks[playlist_id]:
                newTracks.append(track)

        local_playlist[playlist_id] = newTracks

# Pour ajouter toutes les musiques des playlists locales aux playlists spotify
def addAllTracks(sp):
    for playlist_id in local_playlist:
        #Ajout 100 par 100 des musiques
        for i in range(0, len(local_playlist[playlist_id]), 100):
            sp.playlist_add_items(playlist_id, local_playlist[playlist_id][i:i+100])

def main():
    clear() #Retirer le warning ssl
    # ---------- AUTHENTIFICATION ----------
    # Création de l'objet SpotifyOAuth pour obtenir les informations d'identification de l'utilisateur
    scope = "playlist-read-private playlist-modify-private playlist-modify-public"
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope, redirect_uri=cred.redirect_url, client_id=cred.client_ID, client_secret=cred.client_SECRET, username='leocou'))

    # Identifiant de la playlist dont vous voulez récupérer les musiques
    playlist_id = cred.playlist_id
    # Récupération des musiques de la playlist source
    print("Récupération des musiques de la playlist source...")
    source_playlist = get_source_playlist_tracks(sp, sp.current_user()['id'], playlist_id)

    #Je prépare les playlists nouvelles et existantes
    print("Préparation des playlists...")
    preparePlaylists(sp)
    
    # ---------- FONCTIONS ----------

    # Supprimer des playlists les musiques qui ne sont plus dans la playlist source
    print("Nettoyage des playlists...")
    for p in playlist_tracks:
        for track in playlist_tracks[p]:
            if track not in [track['track']['id'] for track in source_playlist]: #Si la musique n'est plus dans la playlist source
                sp.playlist_remove_all_occurrences_of_items(p, [track])

    #Pour les playlists de la config qui ont le filtre "likedDate" on supprime les musiques qui ne correspondent plus
    # for playlist in config:
    #     if 'likedDate' in playlist['filters']:
    #         #On récupère les musiques de la playlist
    #         musicsPlaylist = sp.playlist_tracks(playlistsNamesId[f"Ge - {playlist['name'].capitalize()}"], fields="items(track(id, added_at))")
    #         toRemove = []
    #         #On parcourt les musiques
    #         for track in musicsPlaylist['items']:
    #             #On récupère la musique dans la playlist source (à ce stade on sait qu'elle y est forcément)
    #             trackSource = [track for track in source_playlist if track['track']['id'] == track['track']['id']][0]
    #             #On récupère la date de like
    #             if(track['added_at'] == None):
    #                 continue
    #             likedAt = track['added_at'].split('T')[0]
    #             #On récupère la date actuelle
    #             now = datetime.datetime.now().strftime('%Y-%m-%d')
    #             #On récupère la différence entre les deux dates
    #             diff = datetime.datetime.strptime(now, '%Y-%m-%d') - datetime.datetime.strptime(likedAt, '%Y-%m-%d')
    #             #On récupère le nombre de jours de différence
    #             diff = diff.days
    #             #On récupère le nombre
    #             nombre = int(playlist['filters']['likedDate'].split(' ')[0])
    #             #On récupère le dernier mot de la date (pour savoir si c'est days, months ou years)
    #             temporalite = playlist['filters']['likedDate'].split(' ')[-1]
    #             #On regarde si la temporalité est en jours
    #             if temporalite == 'days':
    #                 if diff > nombre:
    #                     toRemove.append(track['track']['id'])
    #             #On regarde si la temporalité est en mois
    #             elif temporalite == 'months':
    #                 if diff > nombre*30:
    #                     toRemove.append(track['track']['id'])
    #             #On regarde si la temporalité est en années
    #             elif temporalite == 'years':
    #                 if diff > nombre*365:
    #                     toRemove.append(track['track']['id'])
                
    #         #On supprime les musiques qui ne correspondent plus
    #         if len(toRemove) > 0:
    #             sp.playlist_remove_all_occurrences_of_items(playlistsNamesId[f"Ge - {playlist['name'].capitalize()}"], toRemove)

    #Je retire toutes les musiques de mano (elles seront réajoutées après si elles n'ont toujours pas de playlist)
    sp.playlist_remove_all_occurrences_of_items(playlistsNamesId["Ge - Mano"], playlist_tracks[playlistsNamesId["Ge - Mano"]])
                
    print("Récupérations des informations des musiques...")
    # Récupération des caractéristiques audio des musiques de la playlist source (100 par 100 pour l'API Spotify)
    track_ids = [track['track']['id'] for track in source_playlist]
    # audio_features = []
    # for i in range(0, len(track_ids), 100):
    #     audio_features += sp.audio_features(tracks=track_ids[i:i+100])

    # nbTitres = len(audio_features)
    songs_to_get_audio_features = []
    for i in range(0, len(track_ids)):
        if track_ids[i] not in data_songs:
            songs_to_get_audio_features.append(track_ids[i])

    audio_features = []
    for i in range(0, len(songs_to_get_audio_features), 100):
        audio_features += sp.audio_features(tracks=songs_to_get_audio_features[i:i+100])

    #Je récupère les données des musiques
    for i in range(0, len(audio_features)):
        data_songs[songs_to_get_audio_features[i]] = audio_features[i]

    # Sauvegarder les modifications dans le fichier data_songs.json
    with open('data_songs.json', 'w') as f:
        json.dump(data_songs, f, indent=4)

    nbTitres = len(audio_features)
    currentTitre = 0

    print("Classification des musiques...")
    # Parcours de toutes les pistes de la playlist
    for i in range(nbTitres):
        track = audio_features[i]
        #J'ajoute à track la date d'ajout de la musique à la playlist source
        track['likedDate'] = source_playlist[i]['added_at']
        #J'ajoute à track la date de sortie de l'album (si elle n'est pas renseignée, je mets 2021-01-01)
        track['releaseDate'] = sp.track(track_ids[i])['album']['release_date']
        if track['releaseDate'] == "":
            track['releaseDate'] = "2021-01-01"

        artists = source_playlist[i]['track']['artists']
        
        # On regarde si on a des artists que l'on ne connait pas déjà
        artists_to_search = []
        for artist in artists:
            #Si son id n'est pas déjà dans le fichier data_artists.json
            if artist['id'] not in data_artists:
                artists_to_search.append(artist['id'])

        #Je récupère les genres des artistes (par 50)
        for i in range(0, len(artists_to_search), 50):
            artists = sp.artists(artists_to_search[i:i+50])['artists']
            for artist in artists:
                #J'écris dans le fichier data_artists.json une ligne id: [genres]
                data_artists[artist['id']] = artist['genres']

        # Sauvegarder les modifications dans le fichier data_artists.json
        with open('data_artists.json', 'w') as f:
            json.dump(data_artists, f, indent=4)

        #Récupération des noms de playlists auxquelles ajouter la musique
        playlist_add = definePlaylist(track, artists)

        #Préparation des playlists
        fillLocalPlaylists(track, playlist_add)

        # Affichage de la progression
        clear()
        printProgressBar(currentTitre, nbTitres, prefix = 'Progression :', suffix = 'Complete', length = 50)
        print("\n")

        currentTitre += 1

    #Je clean les musiques déjà ajoutées
    print("Nettoyage des musiques déjà ajoutées...")
    cleanAlreadyAdded()

    #J'ajoute toutes les musiques des playlists locales aux playlists spotify
    print("Ajout des musiques aux playlists...")
    addAllTracks(sp)

    clear()
    printProgressBar(currentTitre, nbTitres, prefix = 'Progression :', suffix = 'Complete', length = 50)

if __name__ == "__main__":
    main()


















# ---------- UTILS ----------
# Afficher les données d'une piste
def voirDataTitre(audio_features, track_name):
    print('Titre :', track_name)
    print('Valence :', audio_features[0]['valence'])
    print('Danceability :', audio_features[0]['danceability'])
    print('Energy :', audio_features[0]['energy'])
    print('Acousticness :', audio_features[0]['acousticness'])
    print('Instrumentalness :', audio_features[0]['instrumentalness'])
    print('Tempo :', audio_features[0]['tempo'])
    print('Speechiness :', audio_features[0]['speechiness'])
    print('Mode :', 'Majeur' if audio_features[0]['mode'] == 1 else 'Mineur')
    print('\n')