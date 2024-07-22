from pprint import pprint
import re

ACC_BORDER = 20 #Pourcentage de tolérance pour les critères

def definePlaylist(track, artists_genres, local_playlists, songs_data_db):
    inPlaylist = False
    playlists = []
    for playlist in local_playlists:
        # print(f"Playlist : {playlist['name']}")
        #On vérifie si la piste est déjà dans la playlist, si c'est le cas on passe à la suivante
        if track['id'] in playlist['exsisting_tracks']:
            inPlaylist = True
            continue

        if(checkGenres(artists_genres, playlist) and checkCriterias(track, playlist, songs_data_db)):
            playlists.append(playlist['name'])

    if len(playlists) == 0 and not inPlaylist:
        playlists.append("St - Mano")

    # print(f"Playlists : {playlists}")

    return playlists

def checkCriterias(track, playlist, songs_data_db):
    note = 0

    for criteria in playlist["filters"]["criterias"]:
        crit = criteria.split(" ")[0]
        extremum = ""
        if len(criteria.split(" ")) == 2:
            extremum = criteria.split(" ")[1]

        local_moy = playlist["filters"]["moyennes"][crit]

        lower_bound = local_moy * (1 - ACC_BORDER / 100)
        upper_bound = local_moy * (1 + ACC_BORDER / 100)

        if local_moy < 0.25 or extremum == "-":
            lower_bound = 0
            
        if (local_moy > 0.75 and local_moy <= 1) or (extremum == "+" and local_moy <= 1):
            upper_bound = 1

        if local_moy > 1 and extremum == "-": #Le cas du tempo
            lower_bound = 0

        if local_moy > 1 and extremum == "+": #Le cas du tempo
            upper_bound = 1000

        if lower_bound <= track[crit] <= upper_bound:
            note += 1
            # print(f"{crit} : [{lower_bound} ; {upper_bound}] - {track[crit]} (conforme)")
        else:
            note -= 2
            # print(f"{crit} : [{lower_bound} ; {upper_bound}] - {track[crit]} (non conforme)")

    # print(f"Note : {note}")

    return note >= 0

#On vérifie si les genres des artistes de la musique sont dans les filtres de la playlist (si il y a des filtres saisis)
def checkGenres(artists_genres, playlist):
    #Si l'entité genre n'est même pas présente dans les filtres, on retourne True
    if "genre" not in playlist["filters"]:
        return True

    #Si include et exclude sont présents mais vides, on retourne True
    if "include" in playlist["filters"]["genre"] and "exclude" in playlist["filters"]["genre"] and len(playlist["filters"]["genre"]["include"]) == 0 and len(playlist["filters"]["genre"]["exclude"]) == 0:
        return True
    
    note = 0

    #Si je n'avais pas de genres à inclure je mets la note à 1
    if "include" not in playlist["filters"]["genre"] or len(playlist["filters"]["genre"]["include"]) == 0:
        note = 1

    # print(f"Genres : {artists_genres}")
    for genre in artists_genres:
        #Si le genre est dans les genres à inclure, on ajoute 1
        if "include" in playlist["filters"]["genre"] and len(playlist["filters"]["genre"]["include"]) > 0 and genre in playlist["filters"]["genre"]["include"]:
            note += 1
        #Si le genre est dans les genres à exclure, on retire 1.5
        elif len(playlist["filters"]["genre"]["exclude"]) > 0 and genre in playlist["filters"]["genre"]["exclude"]:
            note -= 2

    # print(f"Note : {note}")

    return note > 0

def format_artists_genre(source_playlist, artists_genre_db):
    #On récupère les genres des artistes de la musique (il peut y avoir des doublons si il y a plusieurs artistes)
    artists_genres = []

    pre_filtered_genres = []
    #On met tous les genres de tous les artistes dans une même liste (avec des doublons possibles)
    for artist in source_playlist['track']['artists']:
        pre_filtered_genres.extend(artists_genre_db[artist['id']])

    #On split chaque genre par les espaces et les tirets
    filtered_genres = []
    for genre in pre_filtered_genres:
        genre.replace(':', ' ')
        genre.replace(';', ' ')
        genre.replace(',', ' ')
        genre.replace('/', ' ')
        genre.replace('-', ' ')
        filtered_genres.extend(genre.split(' '))

    #On les trie par nombre d'occurences
    filtered_genres = sorted(filtered_genres, key=filtered_genres.count, reverse=True)
    #On regarde combien d'éléments on un ou des doublons
    nb_doublons = 0
    for genre in filtered_genres:
        if filtered_genres.count(genre) > 1:
            nb_doublons += 1

    #Si je n'ai pas au moins 2 genres qui ont des doublons, je fais une liste sans doublons et je la retourne
    if nb_doublons < 2 and len(source_playlist['track']['artists']) > 1:
        artists_genres = list(dict.fromkeys(filtered_genres))
        return artists_genres

    artists_genres = filtered_genres
    
    #On retire les doublons
    artists_genres = list(dict.fromkeys(artists_genres))

    return artists_genres