# ---------- IMPORTS ----------
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import cred
from pprint import pprint
import os

clear = lambda: os.system('clear')

# ---------- VARIABLES ----------
playlistName = ['Flow', 'ChillWork', 'Mid',  'Smile', 'SummerVibe', 'Motivation', 'Rap']

seuils = {
    #Flow
    playlistName[0]: {'valenceMin': 0.0,
                'valenceMax': 0.2,
                'danceabilityMin': 0.0,
                'danceabilityMax': 0.7,
                'energyMin': 0.0,
                'energyMax': 0.3,
                'acousticnessMin': 0.5,
                'acousticnessMax': 1.0,
                'instrumentalnessMin': 0.5,
                'instrumentalnessMax': 1.0,
                'tempoMin': 0,
                'tempoMax': 120,
                'speechinessMin': 0.0,
                'speechinessMax': 0.1,},

    #Chill Work
    playlistName[1]: {'valenceMin': 0.0,
                'valenceMax': 0.3,
                'danceabilityMin': 0.0,
                'danceabilityMax': 1.0,
                'energyMin': 0.0,
                'energyMax': 0.5,
                'acousticnessMin': 0.2,
                'acousticnessMax': 1.0,
                'instrumentalnessMin': 0.5,
                'instrumentalnessMax': 1.0,
                'tempoMin': 0,
                'tempoMax': 200,
                'speechinessMin': 0.0,
                'speechinessMax': 0.1,},
      
    #Mid
    playlistName[2]: {'valenceMin': 0.10,
                'valenceMax': 0.9,
                'danceabilityMin': 0.15,
                'danceabilityMax': 0.85,
                'energyMin': 0.15,
                'energyMax': 0.75,
                'acousticnessMin': 0.0,
                'acousticnessMax': 1.0,
                'instrumentalnessMin': 0.0,
                'instrumentalnessMax': 1.0,
                'tempoMin': 60,
                'tempoMax': 200,
                'speechinessMin': 0.0,
                'speechinessMax': 0.20,},
    
    #Smile
    playlistName[3]: {'valenceMin': 0.3,
                'valenceMax': 1.0,
                'danceabilityMin': 0.5,
                'danceabilityMax': 1.0,
                'energyMin': 0.5,
                'energyMax': 1.0,
                'acousticnessMin': 0.0,
                'acousticnessMax': 1.0,
                'instrumentalnessMin': 0.0,
                'instrumentalnessMax': 1.0,
                'tempoMin': 60,
                'tempoMax': 200,
                'speechinessMin': 0.0,
                'speechinessMax': 0.15,},

    #Summer Vibe
    playlistName[4]: {'valenceMin': 0.5,
                'valenceMax': 1.0,
                'danceabilityMin': 0.5,
                'danceabilityMax': 1.0,
                'energyMin': 0.7,
                'energyMax': 1.0,
                'acousticnessMin': 0.0,
                'acousticnessMax': 1.0,
                'instrumentalnessMin': 0.0,
                'instrumentalnessMax': 0.5,
                'tempoMin': 70,
                'tempoMax': 200,
                'speechinessMin': 0.0,
                'speechinessMax': 0.15,}, 

    #Motivation
    playlistName[5]: {'valenceMin': 0.0,
                'valenceMax': 1.0,
                'danceabilityMin': 0.2,
                'danceabilityMax': 0.65,
                'energyMin': 0.8,
                'energyMax': 1.0,
                'acousticnessMin': 0.0,
                'acousticnessMax': 0.2,
                'instrumentalnessMin': 0.0,
                'instrumentalnessMax': 0.3,
                'tempoMin': 100,
                'tempoMax': 200,
                'speechinessMin': 0.1,
                'speechinessMax': 1.0,},
    
    #Rap
    playlistName[6]: {'valenceMin': 0.0,
                'valenceMax': 1.0,
                'danceabilityMin': 0.25,
                'danceabilityMax': 1.0,
                'energyMin': 0.5,
                'energyMax': 1.0,
                'acousticnessMin': 0.0,
                'acousticnessMax': 1.0,
                'instrumentalnessMin': 0.0,
                'instrumentalnessMax': 1.0,
                'tempoMin': 70,
                'tempoMax': 200,
                'speechinessMin': 0.15,
                'speechinessMax': 1.0,}

}

# ---------- FONCTIONS ----------
# Définir les playlists auxquelles ajouter la piste
def definePlaylist(audio_features, group_genre):
    playlist_add = [] # liste des playlist auxquelles ajouter la piste

    # parcours de toutes les playlists possibles pour trouver lesquelles conviennent à la piste
    for i in range(len(playlistName)):
        if seuils[playlistName[i]]['valenceMin'] <= audio_features[0]['valence'] <= seuils[playlistName[i]]['valenceMax'] :
            if seuils[playlistName[i]]['danceabilityMin'] <= audio_features[0]['danceability'] <= seuils[playlistName[i]]['danceabilityMax'] :
                if seuils[playlistName[i]]['energyMin'] <= audio_features[0]['energy'] <= seuils[playlistName[i]]['energyMax'] :
                    if seuils[playlistName[i]]['acousticnessMin'] <= audio_features[0]['acousticness'] <= seuils[playlistName[i]]['acousticnessMax'] :
                        if seuils[playlistName[i]]['instrumentalnessMin'] <= audio_features[0]['instrumentalness'] <= seuils[playlistName[i]]['instrumentalnessMax'] :
                            if seuils[playlistName[i]]['tempoMin'] <= audio_features[0]['tempo'] <= seuils[playlistName[i]]['tempoMax'] :
                                if seuils[playlistName[i]]['speechinessMin'] <= audio_features[0]['speechiness'] <= seuils[playlistName[i]]['speechinessMax'] :
                                    playlist_add.append(playlistName[i])

    # ---------- CAS SPÉCIFIQUES ----------
    # Si l'un des genre du groupe est 'metal', on ajoute le mot 'metal' devant le nom de chaque playlist
    for genre in group_genre:
        if 'metal' in genre.lower():
            for i in range(len(playlist_add)):
                playlist_add[i] = f'Metal - {playlist_add[i]}'
            break

    # Si l'un des genre du groupe est 'russian', on ajoute le mot 'russian' devant le nom de la playlist
    for genre in group_genre:
        if 'russian' in genre.lower():
            for i in range(len(playlist_add)):
                playlist_add[i] = f'Russian - {playlist_add[i]}'
            break

    # Si l'un des genres du groupe est 'rap', on retire les playlists 'Summer Vibe' et 'Smile' s'ils existent
    for genre in group_genre:
        if 'rap' in genre.lower():
            if playlistName[4] in playlist_add:
                playlist_add.remove(playlistName[4])
            if playlistName[3] in playlist_add:
                playlist_add.remove(playlistName[3])
            break 

    # Si le tableau des playlists contient 'Summer Vibe', on retire 'Smile' et 'Mid' s'ils existent
    if playlistName[4] in playlist_add:
        if playlistName[3] in playlist_add:
            playlist_add.remove(playlistName[3])
        if playlistName[2] in playlist_add:
            playlist_add.remove(playlistName[2])

    # Si le tableau des playlists contient 'Flow', on retire 'ChillWork' s'il existe
    if playlistName[0] in playlist_add:
        if playlistName[1] in playlist_add:
            playlist_add.remove(playlistName[1])

    # Si aucun genre du groupe n'est 'rap', la playlist 'Rap' est retirée
    for genre in group_genre:
        if 'rap' not in genre.lower():
            if playlistName[6] in playlist_add:
                playlist_add.remove(playlistName[6])
                break

    # Ajout d'une playlist si aucune ne convient
    if len(playlist_add) == 0:
        playlist_add.append('Mano')    

    return playlist_add

# Ajouter une piste aux playlists
def ajoutPlaylist(sp, track_id, playlist_add):
    for playlist in playlist_add:
        playlist_name = f"Ge - {playlist.capitalize()}"
        playlists = sp.current_user_playlists()['items']
        playlist_exists = False
        for p in playlists:
            if p['name'] == playlist_name:
                playlist_exists = True
                playlist_id = p['id']
                break

        if not playlist_exists:
            new_playlist = sp.user_playlist_create(user=sp.current_user()['id'], name=playlist_name, public=True)
            playlist_id = new_playlist['id']
        # Vérification de la présence de la piste dans la playlist avant l'ajout
        playlist_tracks = sp.playlist_tracks(playlist_id, fields="items(track(id))")
        track_exists = False
        for t in playlist_tracks['items']:
            if t['track']['id'] == track_id:
                track_exists = True
                break
        if not track_exists:
            sp.playlist_add_items(playlist_id, [track_id])


def voirDataTitre(audio_features, track_name):
    print('Titre :', track_name)
    print('Valence :', audio_features[0]['valence'])
    print('Danceability :', audio_features[0]['danceability'])
    print('Energy :', audio_features[0]['energy'])
    print('Acousticness :', audio_features[0]['acousticness'])
    print('Instrumentalness :', audio_features[0]['instrumentalness'])
    print('Tempo :', audio_features[0]['tempo'])

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

def get_playlist_tracks(sp, username, playlist_id):
    results = sp.user_playlist_tracks(username,playlist_id)
    tracks = results['items']
    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])
    return tracks

def main():
    # ---------- AUTHENTIFICATION ----------
    # Création de l'objet SpotifyOAuth pour obtenir les informations d'identification de l'utilisateur
    scope = "playlist-read-private playlist-modify-private playlist-modify-public"
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=cred.client_ID, client_secret= cred.client_SECRET, redirect_uri=cred.redirect_url, scope=scope))

    # Identifiant de la playlist dont vous voulez récupérer les musiques
    playlist_id = '7Lh0UtRMrJmZDh8lDdMSIG'

    # Récupération des informations de la playlist
    playlist = get_playlist_tracks(sp, sp.current_user()['id'], playlist_id)

    # ---------- FONCTIONS ----------
    nbTitres = len(playlist)
    currentTitre = 0
    # Parcours de toutes les pistes de la playlist
    for i in range(nbTitres):
        track = playlist[i]

        #Récupération des informations de la piste
        track_id = track['track']['id']
        
        # Récupération des genres de tous les artistes de la piste
        group_genre = []
        for artist in track['track']['artists']:
            group_genre += sp.artist(artist['uri'])['genres']
        group_genre = list(set(group_genre)) # Suppression des doublons

        audio_features = sp.audio_features(tracks=[track_id])

        playlist_add = definePlaylist(audio_features, group_genre) # liste des playlist auxquelles ajouter la piste

        # Ajout de la piste aux playlist correspondantes
        ajoutPlaylist(sp, track_id, playlist_add)
        
        # Supprimer le titre traité de la playlist initiale
        # sp.playlist_remove_all_occurrences_of_items(playlist_id, [track_id])

        # Affichage de la progression
        clear()
        printProgressBar(currentTitre, nbTitres, prefix = 'Progression :', suffix = 'Complete', length = 50)
        print("\n")
        print(currentTitre, "/", nbTitres, "titres traités\n")
        print(track['track']['name'], "-", track['track']['artists'][0]['name'], "\n")

        currentTitre += 1

    clear()
    printProgressBar(currentTitre, nbTitres, prefix = 'Progression :', suffix = 'Complete', length = 50)


if __name__ == "__main__":
    main()