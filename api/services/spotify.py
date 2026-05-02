import logging
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from core.models import Track
import config

logger = logging.getLogger(__name__)

CREATED_SEPARATOR = "| created:"


def _format_description(prompt: str) -> str:
    ts = datetime.now(timezone.utc).isoformat()
    return f"{prompt} {CREATED_SEPARATOR}{ts}"


def _parse_description(raw: str) -> tuple:
    """Retourne (prompt_clean, created_at | None)"""
    if CREATED_SEPARATOR not in raw:
        return raw.strip(), None
    prompt, _, meta = raw.partition(CREATED_SEPARATOR)
    return prompt.strip(), meta.strip()


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
        return Track(
            id=t['id'],
            title=t['name'],
            artists='-'.join(a['name'] for a in t['artists']),
            album=t['album']['name'],
            added_at=item.get('added_at') if extended else None,
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

    def get_playlist_prompt(self, playlist_id: str) -> str:
        raw    = self._client.playlist(playlist_id)['description']
        prompt, _ = _parse_description(raw)
        return prompt

    def get_playlist_created_at(self, playlist_id: str) -> Optional[str]:
        raw = self._client.playlist(playlist_id)['description']
        _, created_at = _parse_description(raw)
        return created_at

    def create_playlist(self, name: str, prompt: str, track_ids: list) -> str:
        sp          = self._client
        user_id     = sp.current_user()['id']
        description = _format_description(prompt)
        playlist    = sp.user_playlist_create(
            user=user_id,
            name=config.PLAYLIST_PREFIX + name,
            public=False,
            description=description,
        )
        self._bulk_add(playlist['id'], track_ids)
        logger.info("Created playlist '%s' with %d tracks", name, len(track_ids))
        return playlist['id']

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
