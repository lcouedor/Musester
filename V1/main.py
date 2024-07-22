from pprint import pprint
import os
import time
import cred
import utils.auth as auth
import utils.progress_bar as progress_bar
import utils.spotify_utils as spotify_utils
import utils.playlist_manager as playlist_manager

clear = lambda: os.system('clear')

# ---------- VARIABLES ----------
config = spotify_utils.configLoad() #Chargement de la config des playlists

data_artists = spotify_utils.open_database('data_artists') #Bdd perso des artistes
data_songs = spotify_utils.open_database('data_songs') #Bdd perso des musiques

user_playlists = [] #Liste des playlists de l'utilisateur
playlist_tracks = {} #Dictionnaire des noms de playlists avec leur liste de musiques
local_playlist = {} #Dictionnaire des noms de playlists avec leur liste de musiques (pour les ajouts)
playlistsNamesId = {} #Dictionnaire des noms de playlists avec leur id
start = time.time()

def timeInSecSince():
    return str(int(time.time() - start)) + "s"

def main():
    clear() #Retirer le warning ssl

    sp = auth.get_spotify_client() #Connexion à l'API Spotify

    playlist_id = cred.playlist_id # Identifiant de la playlist dont on veut récupérer les musiques

    # Récupération des musiques de la playlist source
    print("Récupération des musiques de la playlist source..." + timeInSecSince())
    source_playlist = spotify_utils.get_source_playlist_tracks(sp, sp.current_user()['id'], playlist_id)

    #On affiche dans la console tous les titres de musiques (titre - artistes) de la playlist source
    #print("Musiques de la playlist source :")
    #for track in source_playlist:
        #print(track['track']['name'] + " - " + ', '.join([artist['name'] for artist in track['track']['artists']]))

    # Préparation des playlists, récupération des musiques déjà présentes dans les playlists et ajout des playlists locales
    print("Préparation des playlists..." + timeInSecSince())
    playlist_manager.preparePlaylists(sp, config, playlist_tracks, playlistsNamesId, local_playlist)
    
    # Supprimer des playlists les musiques qui ne sont plus dans la playlist source
    print("Nettoyage des playlists..." + timeInSecSince())
    spotify_utils.clean_playlists(sp, playlist_tracks, source_playlist, playlistsNamesId)

    # Récupération des caractéristiques audio des musiques de la playlist source (100 par 100 pour l'API Spotify) et ajout dans la bdd
    print("Récupérations des informations des musiques..." + timeInSecSince())
    track_ids = [track['track']['id'] for track in source_playlist]
    audio_features = spotify_utils.get_audio_features(sp, track_ids, data_songs)

    nbTitres = len(audio_features)
    currentTitre = 0

    print("Classification des musiques..." + timeInSecSince())
    # Parcours de toutes les pistes de la playlist
    for i in range(nbTitres):
        track = audio_features[i]
        #J'ajoute à track la date d'ajout de la musique à la playlist source
        track['likedDate'] = source_playlist[i]['added_at']
        #J'ajoute à track la date de sortie de l'album (si elle n'est pas renseignée, je mets 2021-01-01)
        track['releaseDate'] = sp.track(track_ids[i])['album']['release_date']
        if track['releaseDate'] == "":
            track['releaseDate'] = "2021-01-01"

        #Récupération des genres des artistes de la musique
        artists = source_playlist[i]['track']['artists']
        artists_genres = spotify_utils.get_artists_genres(sp, source_playlist[i]['track']['artists'], data_artists)
        
        #Récupération des noms de playlists auxquelles ajouter la musique
        playlist_add = playlist_manager.definePlaylist(track, artists, artists_genres, config, data_artists)

        #Préparation des playlists
        playlist_manager.fillLocalPlaylists(track, playlist_add, local_playlist, playlistsNamesId)

        # Affichage de la progression
        progress_bar.printProgressBar(currentTitre, nbTitres, prefix = 'Progression :', suffix = 'Complete', length = 50)

        currentTitre += 1

    print("Nettoyage des musiques déjà ajoutées..." + timeInSecSince())
    playlist_manager.cleanAlreadyAdded(local_playlist, playlist_tracks)

    print("Ajout des musiques aux playlists..." + timeInSecSince())
    spotify_utils.addAllTracks(sp, local_playlist)

    progress_bar.printProgressBar(nbTitres, nbTitres, prefix = 'Progression :', suffix = 'Complete', length = 50)

    #On affiche le temps d'exécution (en minutes et secondes)
    excluded_time = time.time() - start
    print("Fin du programme")
    print("Temps d'exécution : " + str(int(excluded_time // 60)) + "m" + str(int(excluded_time % 60)))

if __name__ == "__main__":
    main()