import datetime
import re

#Récupérer les playlists de l'utilisateur et créer celles de la config si elles n'existent pas + préparer les variables globales
def preparePlaylists(sp, config, playlist_tracks, playlistsNamesId, local_playlist):
    user_playlists = []
    #Je récupère les playlists de l'utilisateur et les ajoute à la liste user_playlists (mirroir des playlists de l'utilisateur sur spotify)
    for playlist in sp.current_user_playlists()['items']:
        if playlist['name'][:5] == 'Ge - ':
            user_playlists.append(playlist)
            musicsPlaylist = sp.playlist_tracks(playlist['id'], fields="items(track(id))")
            #J'ajoute les id des musiques de la playlist à la liste playlist_tracks
            playlist_tracks[playlist['id']] = [track['track']['id'] for track in musicsPlaylist['items']]
            playlistsNamesId[playlist['name']] = playlist['id']

    #Je crée les playlists de la config si elles n'existent pas et les ajoute à la liste user_playlists
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

    #Je prépare les playlists locales (pour les ajouts)
    for playlist_id in playlist_tracks:
        local_playlist[playlist_id] = []

# Définir les playlists auxquelles ajouter la piste
def definePlaylist(track, artists, artists_genres, config, data_artists):
    playlist_add = [] # liste des playlist auxquelles ajouter la piste

    for playlist in config: #Pour chaque playlist de la config, je regarde si la musique correspond
        #Je regarde les filtres de la playlist dans le conf
        filters = playlist['filters']

        include_artists = False
        if 'artists' in filters: #Si il y a des artistes à inclure ou exclure
            include_artists = any(artist['name'] in filters['artists'].get('include', []) for artist in artists)
            if any(artist['name'] in filters['artists'].get('exclude', []) for artist in artists):
                continue

        flat_genres = [genre for sublist in artists_genres for genre in sublist]

        #Je regarde si le genre de la musique est dans les genres de la playlist
        if 'genre' in filters and not include_artists: #Si aucun artist n'a d'inclusion prioritaire, je regarde si le genre de la musique est dans les genres de la playlist
            #Si un des genres de la musique est dans les genres à exclure de la playlist 
            if 'exclude' in filters['genre'] and any(genre in flat_genres for genre in filters['genre']['exclude']):
                continue
            #Si aucun des genres de la musique n'est dans les genres de la playlist (on utilise un substrings pour les genres)
            if 'include' in filters['genre'] and not any(re.search(genre, ' '.join(flat_genres)) for genre in filters['genre']['include']):
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
                if not timeBetweenDates(track['likedDate'], filters[key]):
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
def fillLocalPlaylists(track, playlist_add, local_playlist, playlistsNamesId):
    for playlist in playlist_add:
        playlist_name = f"Ge - {playlist.capitalize()}"
        playlist_id = playlistsNamesId[playlist_name]
        local_playlist[playlist_id].append(track['id'])

# Pour retirer des playlists locales les musiques déjà présentes dans les playlists spotify
def cleanAlreadyAdded(local_playlist, playlist_tracks):
    #Pour chaque playlist locale
    for playlist_id in local_playlist:
        #Pour toutes les musiques, je les ajoute à ma liste de musiques à ajouter si elles ne sont pas déjà dans la playlist spotify
        newTracks = []
        for track in local_playlist[playlist_id]:
            if track not in playlist_tracks[playlist_id]:
                newTracks.append(track)

        local_playlist[playlist_id] = newTracks

#Fonction utile pour le temps entre now et une date donnée
def timeBetweenDates(likedDate, temporalite):
    #On récupère le nombre
    nombre = int(temporalite[0])
    #Et le derner mot de la temporalité (pour savoir si c'est days, months ou years)
    temporalite = temporalite[1]

    #On récupère la date actuelle
    now = datetime.datetime.now().strftime('%Y-%m-%d')
    #On récupère la date de la musique
    likedDate = likedDate.split('T')[0]

    #On convertit les dates en datetime
    now = datetime.datetime.strptime(now, '%Y-%m-%d')
    likedDate = datetime.datetime.strptime(likedDate, '%Y-%m-%d')

    #On calcule la différence
    if temporalite == 'days':
        return (now - likedDate).days < nombre
    elif temporalite == 'months':
        return (now.year - likedDate.year) * 12 + now.month - likedDate.month < nombre
    elif temporalite == 'years':
        return now.year - likedDate.year < nombre
    else:
        print('Erreur : temporalité inconnue')
        return False