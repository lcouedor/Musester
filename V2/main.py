from pprint import pprint
import os
import time
import cred
import utils.auth as auth
import utils.spotify_utils as spotify_utils
import utils.playlist_manager as playlist_manager
import utils.progress_bar as progress_bar

clear = lambda: os.system('clear')

# ---------- VARIABLES ----------
local_playlists = spotify_utils.configLoad() #Chargement de la config des playlists
artists_genre_db = [] #Bdd perso des artistes
songs_data_db = [] #Bdd perso des audio_features des musiques

music_add = {}

start = time.time()

def timeInSecSince():
    return str(int(time.time() - start)) + "s"

def main():
    #Retirer le warning ssl
    clear()

    #Ouverture des bases de données
    print("Ouverture des bases de données..." + timeInSecSince())
    songs_data_db = spotify_utils.open_database('data_songs')
    artists_genre_db = spotify_utils.open_database('data_artists')

    #Connexion à l'API Spotify
    print("Connexion à l'API Spotify..." + timeInSecSince())
    sp = auth.get_spotify_client()

    #On récupère les playlists sur spotify au nom des playlists locales
    print("Récupération des playlists Spotify depuis la configuration fournie et définition des critères..." + timeInSecSince())
    for playlist in local_playlists:
        moyennes = {}

        #On récupère l'id de la playlist spotify
        playlist_sp = spotify_utils.get_playlist(sp, playlist["name"])
        if playlist_sp is None:
            print(f"La playlist {playlist['name']} n'existe pas sur Spotify")
            continue

        #On récupère les pistes de la playlist spotify
        playlist_tracks = spotify_utils.get_source_playlist_tracks(sp, sp.current_user()['id'], playlist_sp['id'])

        #Si la playlist a moins de 5 pistes ce n'est pas suffisant pour faire une comparaison
        if len(playlist_tracks) < 5:
            print(f"La playlist {playlist['name']} a moins de 5 pistes")
            continue

        #TODO retirer des playlists les musiques qui ne sont plus dans la playlist source

        #On va chercher les audio_features des pistes de la playlist spotify
        audio_features = spotify_utils.get_audio_features(sp, [track['track']['id'] for track in playlist_tracks], songs_data_db)

        #On ouvre à nouveau la bdd si jamais on a ajouté des audio_features
        songs_data_db = spotify_utils.open_database('data_songs')

        #Pour chaque critère de la playlist locale, on récupère la médiane et l'écart type des valeurs de la playlist spotify
        for criteria in playlist["filters"]["criterias"]:
            values = []
            crit = criteria.split(" ")[0]
            for track in audio_features:
                values.append(track[crit])
            moyennes[crit] = sum(values) / len(values)

        #On ajoute les valeurs de médiane et d'écart type à la playlist locale
        playlist["filters"]["moyennes"] = moyennes

        #On ajoute aussi les id des pistes de la playlist spotify
        playlist["exsisting_tracks"] = [track['track']['id'] for track in playlist_tracks]

    #On récupère les musiques d'une playlist de référence
    print("Récupération des musiques de la playlist source..." + timeInSecSince())
    source_playlist = spotify_utils.get_source_playlist_tracks(sp, sp.current_user()['id'], cred.playlist_id)

    #On remplis la bdd des artistes avec ceux qui n'y sont pas déjà
    print("Récupération des genres des artistes..." + timeInSecSince())
    spotify_utils.get_artists_genre(sp, [track['track']['artists'][0]['id'] for track in source_playlist], artists_genre_db)
    #On ouvre à nouveau la bdd si jamais on a ajouté des genres
    artists_genre_db = spotify_utils.open_database('data_artists')

    #On va chercher les audio_features des pistes de la playlist de référence
    print("Récupération des audio_features des musiques de la playlist source..." + timeInSecSince())
    audio_features = spotify_utils.get_audio_features(sp, [track['track']['id'] for track in source_playlist], songs_data_db)

    currentTitre = 0

    print("Classification des musiques..." + timeInSecSince())
    for i in range(len(audio_features)):
        track = audio_features[i]

        artists_genres = playlist_manager.format_artists_genre(source_playlist[i], artists_genre_db)

        #On définit les playlists où la musique peut être ajoutée
        playlist_add = playlist_manager.definePlaylist(track, artists_genres, local_playlists, songs_data_db)

        for playlist in playlist_add:
            if playlist not in music_add:
                music_add[playlist] = []
            music_add[playlist].append(source_playlist[i]['track']['uri'])

        # Affichage de la progression
        progress_bar.printProgressBar(currentTitre, len(audio_features), prefix = 'Progression :', suffix = 'Complete', length = 50)

        currentTitre += 1

    print("Ajout des musiques..." + timeInSecSince())
    for playlist in music_add:
        playlist_sp = spotify_utils.get_playlist(sp, playlist)
        if playlist_sp is None:
            #Je crée la playlist si elle n'existe pas
            playlist_sp = spotify_utils.create_playlist(sp, playlist)

        spotify_utils.add_tracks(sp, playlist_sp['id'], music_add[playlist])

    progress_bar.printProgressBar(currentTitre, currentTitre, prefix = 'Progression :', suffix = 'Complete', length = 50)

    excluded_time = time.time() - start
    print("Temps d'exécution : " + str(int(excluded_time // 60)) + "m" + str(int(excluded_time % 60)))

if __name__ == "__main__":
    main()