import spotipy
from spotipy.oauth2 import SpotifyOAuth
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from config import playlist_prefix
from utils import getSecret
from dotenv import load_dotenv

load_dotenv()

_spotify_client = None

def get_spotify_client():
    global _spotify_client
    if _spotify_client is None:
        scope = "playlist-read-private playlist-modify-private playlist-modify-public user-library-read"
        _spotify_client = spotipy.Spotify(auth_manager=SpotifyOAuth(
            scope=scope,
            redirect_uri=getSecret('SPOTIFY_REDIRECT'),
            client_id=getSecret('SPOTIFY_ID'),
            client_secret=getSecret('SPOTIFY_SECRET'),
            username=getSecret('SPOTIFY_USERNAME'),
            open_browser=True,
        ))
    return _spotify_client


def _fetch_page(spotify, playlist_id, offset, limit=100):
    """Récupère une page de tracks."""
    return spotify.playlist_tracks(playlist_id, offset=offset, limit=limit)


def get_playlist_tracks_infos(playlist_id, extended=False):
    spotify = get_spotify_client()

    # Première page pour connaître le total
    first_page = spotify.playlist_tracks(playlist_id, limit=100, offset=0)
    total = first_page['total']
    all_items = list(first_page['items'])

    # Pages restantes en parallèle
    offsets = range(100, total, 100)
    if offsets:
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(_fetch_page, spotify, playlist_id, offset): offset for offset in offsets}
            pages = [None] * len(futures)
            for future in as_completed(futures):
                idx = (futures[future] - 100) // 100
                pages[idx] = future.result()['items']
        for page in pages:
            if page:
                all_items.extend(page)

    songs = []
    for item in all_items:
        track = item.get('track')
        if not track:
            continue
        song_info = {
            'id': track['id'],
            'title': track['name'],
            'artists': '-'.join(a['name'] for a in track['artists']),
            'album': track['album']['name'],
        }
        if extended:
            song_info['added_at'] = item['added_at']
        songs.append(song_info)

    return songs


def get_matching_songs_ids(songs, ia_decisions, treshold_match_percentage):
    """O(n) grâce à un set d'ids valides."""
    valid_ids = {song['id'] for song in songs}
    return [
        d['id']
        for d in ia_decisions
        if d['id'] in valid_ids and int(d['match']) >= treshold_match_percentage
    ]


def create_user_playlist(playlist_name: str, description: str, songs_ids: list):
    spotify = get_spotify_client()
    user_id = spotify.current_user()['id']
    playlist = spotify.user_playlist_create(
        user=user_id,
        name=playlist_prefix + playlist_name,
        public=False,
        description=description,
    )
    _bulk_add(spotify, playlist['id'], songs_ids)
    return playlist['id']


def add_songs_to_playlist(playlist_id: str, songs_ids: list):
    spotify = get_spotify_client()
    _bulk_add(spotify, playlist_id, songs_ids)


def remove_songs_from_playlist(playlist_id: str, songs_ids: list):
    spotify = get_spotify_client()
    for i in range(0, len(songs_ids), 100):
        spotify.playlist_remove_all_occurrences_of_items(
            playlist_id=playlist_id, items=songs_ids[i:i + 100]
        )


def get_playlist_description(playlist_id: str) -> str:
    return get_spotify_client().playlist(playlist_id)['description']


def _bulk_add(spotify, playlist_id: str, songs_ids: list):
    for i in range(0, len(songs_ids), 100):
        spotify.playlist_add_items(playlist_id=playlist_id, items=songs_ids[i:i + 100])
