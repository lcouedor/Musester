import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import spotipy

from core.models import Track
import config

logger = logging.getLogger(__name__)


class SpotifyService:

    def __init__(self, access_token: str):
        self._client = spotipy.Spotify(auth=access_token)

    @staticmethod
    def get_user_id(access_token: str) -> str:
        sp = spotipy.Spotify(auth=access_token)
        return sp.current_user()['id']

    def get_tracks(self, playlist_id: str, extended: bool = False) -> list:
        sp       = self._client
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
        images = t['album'].get('images', [])
        cover_url = images[0]['url'] if images else None
        return Track(
            id=t['id'],
            title=t['name'],
            artists='-'.join(a['name'] for a in t['artists']),
            album=t['album']['name'],
            added_at=item.get('added_at') if extended else None,
            cover_url=cover_url,
        )

    def get_user_generated_playlists(self) -> list:
        sp      = self._client
        user_id = sp.current_user()['id']
        results = sp.current_user_playlists(limit=50)
        items   = list(results['items'])
        while results['next']:
            results = sp.next(results)
            items.extend(results['items'])

        generated = [
            p for p in items
            if p['owner']['id'] == user_id and p['name'].startswith(config.PLAYLIST_PREFIX)
        ]
        logger.info("Found %d generated playlists", len(generated))
        return generated

    def get_playlist_created_at(self, playlist_id: str) -> Optional[str]:
        """Retourne la date du morceau ajouté en dernier, ou None."""
        tracks = self.get_tracks(playlist_id, extended=True)
        if not tracks:
            return None
        return min(t.added_at for t in tracks)

    def create_playlist(self, name: str, track_ids: list) -> str:
        """Crée une playlist sans description — le prompt est en DB."""
        sp      = self._client
        user_id = sp.current_user()['id']
        playlist = sp.user_playlist_create(
            user=user_id,
            name=config.PLAYLIST_PREFIX + name,
            public=False,
            description='',
        )
        self._bulk_add(playlist['id'], track_ids)
        logger.info("Created playlist '%s' with %d tracks", name, len(track_ids))
        return playlist['id']

    def clear_playlist(self, playlist_id: str):
        """Vide complètement une playlist."""
        tracks = self.get_tracks(playlist_id)
        if tracks:
            self.remove_from_playlist(playlist_id, [t.id for t in tracks])

    def add_to_playlist(self, playlist_id: str, track_ids: list):
        self._bulk_add(playlist_id, track_ids)
        logger.info("Added %d tracks to '%s'", len(track_ids), playlist_id)

    def remove_from_playlist(self, playlist_id: str, track_ids: list):
        sp = self._client
        for i in range(0, len(track_ids), 100):
            sp.playlist_remove_all_occurrences_of_items(
                playlist_id=playlist_id,
                items=track_ids[i:i+100],
            )
        logger.info("Removed %d tracks from '%s'", len(track_ids), playlist_id)

    def _bulk_add(self, playlist_id: str, track_ids: list):
        sp = self._client
        for i in range(0, len(track_ids), 100):
            sp.playlist_add_items(playlist_id=playlist_id, items=track_ids[i:i+100])
