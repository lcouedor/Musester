import logging
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.models import Track
import config

logger = logging.getLogger(__name__)


class SpotifyService:
    _client = None

    def _get_client(self) -> spotipy.Spotify:
        if not self._client:
            self._client = spotipy.Spotify(auth_manager=SpotifyOAuth(
                scope=config.SPOTIFY_SCOPE,
                redirect_uri=config.SPOTIFY_REDIRECT,
                client_id=config.SPOTIFY_ID,
                client_secret=config.SPOTIFY_SECRET,
                username=config.SPOTIFY_USERNAME,
            ))
        return self._client

    def get_tracks(self, playlist_id: str, extended: bool = False) -> list[Track]:
        sp = self._get_client()
        is_liked = playlist_id == "liked"
        limit    = 50 if is_liked else 100

        def fetch(offset: int) -> dict:
            if is_liked:
                return sp.current_user_saved_tracks(limit=limit, offset=offset)
            return sp.playlist_tracks(playlist_id, limit=limit, offset=offset)

        first_page = fetch(0)
        total      = first_page['total']
        all_items  = list(first_page['items'])

        offsets = range(limit, total, limit)
        if offsets:
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(fetch, o): o for o in offsets}
                pages   = {}
                for future in as_completed(futures):
                    idx        = (futures[future] - limit) // limit
                    pages[idx] = future.result()['items']
            for i in sorted(pages):
                all_items.extend(pages[i])

        tracks = [self._parse_track(item, extended) for item in all_items if item.get('track')]
        logger.info("Fetched %d tracks from '%s'", len(tracks), playlist_id)
        return tracks

    def _parse_track(self, item: dict, extended: bool) -> Track:
        t = item['track']
        return Track(
            id=t['id'],
            title=t['name'],
            artists='-'.join(a['name'] for a in t['artists']),
            album=t['album']['name'],
            added_at=item.get('added_at') if extended else None,
        )

    def create_playlist(self, name: str, description: str, track_ids: list[str]) -> str:
        sp      = self._get_client()
        user_id = sp.current_user()['id']
        playlist = sp.user_playlist_create(
            user=user_id,
            name=config.PLAYLIST_PREFIX + name,
            public=False,
            description=description,
        )
        self._bulk_add(playlist['id'], track_ids)
        logger.info("Created playlist '%s' with %d tracks", name, len(track_ids))
        return playlist['id']

    def add_to_playlist(self, playlist_id: str, track_ids: list[str]):
        self._bulk_add(playlist_id, track_ids)
        logger.info("Added %d tracks to '%s'", len(track_ids), playlist_id)

    def remove_from_playlist(self, playlist_id: str, track_ids: list[str]):
        sp = self._get_client()
        for i in range(0, len(track_ids), 100):
            sp.playlist_remove_all_occurrences_of_items(
                playlist_id=playlist_id,
                items=track_ids[i:i+100],
            )
        logger.info("Removed %d tracks from '%s'", len(track_ids), playlist_id)

    def get_playlist_description(self, playlist_id: str) -> str:
        return self._get_client().playlist(playlist_id)['description']

    def _bulk_add(self, playlist_id: str, track_ids: list[str]):
        sp = self._get_client()
        for i in range(0, len(track_ids), 100):
            sp.playlist_add_items(playlist_id=playlist_id, items=track_ids[i:i+100])
