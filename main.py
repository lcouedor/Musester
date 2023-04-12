# ---------- IMPORTS ----------
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import cred

# ---------- AUTHENTIFICATION ----------
# Création de l'objet SpotifyOAuth pour obtenir les informations d'identification de l'utilisateur
scope = "playlist-read-private playlist-modify-private playlist-modify-public"
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=cred.client_ID, client_secret= cred.client_SECRET, redirect_uri=cred.redirect_url, scope=scope))

# ---------- FONCTIONS ----------
# Identifiant de la playlist dont vous voulez récupérer les musiques
playlist_id = '7Lh0UtRMrJmZDh8lDdMSIG'
# Récupération des informations de la playlist
playlist = sp.playlist(playlist_id)

# Styles musicaux usuels
styles = ['pop', 'rock', 'hip hop', 'metal', 'reggae', 'soundtrack', 'indie', 'russian', 'soul', 'blues','country','dance','hard','ambiant','trance','anime','folk','jazz','bass','beach','beat','groove','house','melodic','electro','funk','alternative','R&b','rap','sad','happy','latin','party','modern rock']

# Parcours de toutes les pistes de la playlist
for track in playlist['tracks']['items']:
    # Affichage du compteur pour montrer la trace d'exécution
    # print(f"Processing track {track['track']['name']}...")

    # ---------- RÉCUPÉRATION DES IMFORMATIONS DE LA PISTE ----------
    track_id = track['track']['id']
    track_name = track['track']['name']
    track_album = sp.track(track_id)['album']

    # Récupération des artistes de la piste
    artists = track['track']['artists']

    # Récupération des genres de tous les artistes de la piste
    genres = []
    for artist in artists:
        artist_info = sp.artist(artist['id'])
        genres += artist_info['genres']

    # Parcours des genres des artistes pour trouver les genres présents dans le tableau styles
    track_genres = []
    for genre in genres:
        # Suppression des termes inutiles dans le genre (tels que "pop rock" -> "pop")
        for style in styles:
            if style in genre:
                track_genres.append(style)

    if len(track_genres) == 0:
        track_genres.append('mano')

    # Ajout de la piste aux playlists correspondantes
    for genre in track_genres:
        playlist_name = f"G - {genre.capitalize()} Playlist"
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
        for playlist_track in playlist_tracks['items']:
            if playlist_track['track']['id'] == track_id:
                track_exists = True
                break
        if not track_exists:
            sp.playlist_add_items(playlist_id, [track_id])

    
    # affichage du nom de l'artiste et de la liste des playlists auxquelles la piste a été ajoutée
    print(f"{track_name} - {list(dict.fromkeys(track_genres))}")

