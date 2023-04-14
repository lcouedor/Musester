# ---------- IMPORTS ----------
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import cred
from pprint import pprint

# ---------- VARIABLES ----------
playlistName = ['ChillWork', 'Flow', 'SummerVibe', 'Smile', 'Mid', 'Motivation', 'Rap']

#TODO improve : 
# - nightcall : playlist dans ce style ? 
# - supprimer auto les musiques ajoutées
# - relancer auto le script pour nb musiques par bloc de 100
# - tri par origine de la musique (playlist russian par exemple, mettre les fr à part si possible ?)
# - Ajouter plein de musiques

seuils = {
    #Chill Work
    playlistName[0]: {'valenceMin': 0.0, 
                'valenceMax': 0.5, 
                'danceabilityMin': 0.0, 
                'danceabilityMax': 1.0, 
                'energyMin': 0.0, 
                'energyMax': 0.5, 
                'acousticnessMin': 0.0, 
                'acousticnessMax': 1.0, 
                'instrumentalnessMin': 0.3, 
                'instrumentalnessMax': 1.0,
                'tempoMin': 0,
                'tempoMax': 200,
                'speechinessMin': 0.0,
                'speechinessMax': 1.0,},
    #Flow
    playlistName[1]: {'valenceMin': 0.0,
                'valenceMax': 1.0,
                'danceabilityMin': 0.0,
                'danceabilityMax': 0.4,
                'energyMin': 0.0,
                'energyMax': 0.3,
                'acousticnessMin': 0.6,
                'acousticnessMax': 1.0,
                'instrumentalnessMin': 0.0,
                'instrumentalnessMax': 1.0,
                'tempoMin': 0,
                'tempoMax': 120,
                'speechinessMin': 0.0,
                'speechinessMax': 1.0,},
    #Summer Vibe
    playlistName[2]: {'valenceMin': 0.35,
                'valenceMax': 1.0,
                'danceabilityMin': 0.60,
                'danceabilityMax': 1.0,
                'energyMin': 0.6,
                'energyMax': 1.0,
                'acousticnessMin': 0.0,
                'acousticnessMax': 1.0,
                'instrumentalnessMin': 0.0,
                'instrumentalnessMax': 1.0,
                'tempoMin': 70,
                'tempoMax': 140,
                'speechinessMin': 0.0,
                'speechinessMax': 0.2,}, 
    #Smile
    playlistName[3]: {'valenceMin': 0.15,
                'valenceMax': 1.0,
                'danceabilityMin': 0.4,
                'danceabilityMax': 1.0,
                'energyMin': 0.5,
                'energyMax': 1.0,
                'acousticnessMin': 0.0,
                'acousticnessMax': 1.0,
                'instrumentalnessMin': 0.0,
                'instrumentalnessMax': 1.0,
                'tempoMin': 0,
                'tempoMax': 160,
                'speechinessMin': 0.0,
                'speechinessMax': 0.2,},
    #Mid
    playlistName[4]: {'valenceMin': 0.10,
                'valenceMax': 0.85,
                'danceabilityMin': 0.15,
                'danceabilityMax': 0.85,
                'energyMin': 0.15,
                'energyMax': 0.85,
                'acousticnessMin': 0.0,
                'acousticnessMax': 1.0,
                'instrumentalnessMin': 0.0,
                'instrumentalnessMax': 1.0,
                'tempoMin': 60,
                'tempoMax': 200,
                'speechinessMin': 0.0,
                'speechinessMax': 1.0,},
    #Motivation
    playlistName[5]: {'valenceMin': 0.0,
                'valenceMax': 1.0,
                'danceabilityMin': 0.3,
                'danceabilityMax': 0.9,
                'energyMin': 0.7,
                'energyMax': 1.0,
                'acousticnessMin': 0.0,
                'acousticnessMax': 0.3,
                'instrumentalnessMin': 0.0,
                'instrumentalnessMax': 0.3,
                'tempoMin': 100,
                'tempoMax': 200,
                'speechinessMin': 0.0,
                'speechinessMax': 1.0,},
    #Rap
    playlistName[6]: {'valenceMin': 0.0,
                'valenceMax': 1.0,
                'danceabilityMin': 0.3,
                'danceabilityMax': 1.0,
                'energyMin': 0.6,
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
def definePlaylist(audio_features):
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

    if len(playlist_add) == 0:
        playlist_add.append('mano')

    return playlist_add

# Ajouter une piste aux playlists
def ajoutPlaylist(sp, track_id, playlist_add):
    for playlist in playlist_add:
        playlist_name = f"G - {playlist.capitalize()} Playlist"
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


def main():
    # ---------- AUTHENTIFICATION ----------
    # Création de l'objet SpotifyOAuth pour obtenir les informations d'identification de l'utilisateur
    scope = "playlist-read-private playlist-modify-private playlist-modify-public"
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=cred.client_ID, client_secret= cred.client_SECRET, redirect_uri=cred.redirect_url, scope=scope))

    # Identifiant de la playlist dont vous voulez récupérer les musiques
    playlist_id = '7Lh0UtRMrJmZDh8lDdMSIG'
    # Récupération des informations de la playlist
    playlist = sp.playlist(playlist_id)

    # ---------- FONCTIONS ----------
    # Parcours de toutes les pistes de la playlist
    for track in playlist['tracks']['items']:
        #Récupération des informations de la piste
        track_id = track['track']['id']
        track_name = track['track']['name']
        audio_features = sp.audio_features(tracks=[track_id])
        voirDataTitre(audio_features, track_name)
        playlist_add = definePlaylist(audio_features) # liste des playlist auxquelles ajouter la piste

        # Ajout de la piste aux playlist correspondantes
        ajoutPlaylist(sp, track_id, playlist_add)
        print('------------------------')

if __name__ == "__main__":
    main()