import logging
from core.models import Track, Decision
from services.spotify import SpotifyService
from services.classifier import ClassifierService

logger     = logging.getLogger(__name__)
_classifier = ClassifierService()


def generate_playlist(access_token: str, source_id: str, playlist_name: str, prompt: str) -> dict:
    spotify     = SpotifyService(access_token)
    tracks      = spotify.get_tracks(source_id)
    decisions   = _classifier.classify(prompt, tracks)
    selected    = _filter(decisions)
    playlist_id = spotify.create_playlist(playlist_name, prompt, selected)
    return {
        'playlist_id':    playlist_id,
        'checked_songs':  len(tracks),
        'selected_songs': len(selected),
        'decisions':      [d.__dict__ for d in decisions],
    }


def sync_all_playlists(access_token: str, source_id: str) -> dict:
    spotify       = SpotifyService(access_token)
    source_tracks = spotify.get_tracks(source_id, extended=True)
    source_ids    = {t.id for t in source_tracks}
    generated     = spotify.get_user_generated_playlists()
    results       = {}

    for playlist in generated:
        pid  = playlist['id']
        name = playlist['name']

        target_tracks = spotify.get_tracks(pid, extended=True)
        existing_ids  = {t.id for t in target_tracks}

        # 1. Suppression des morceaux absents de la source
        to_remove = [t.id for t in target_tracks if t.id not in source_ids]
        if to_remove:
            spotify.remove_from_playlist(pid, to_remove)

        # 2. Déterminer la date de référence
        if target_tracks:
            last_added = max(t.added_at for t in target_tracks)
        else:
            last_added = spotify.get_playlist_created_at(pid)

        if not last_added:
            logger.warning("No reference date for '%s', skipping update step", name)
            results[pid] = {'name': name, 'removed': len(to_remove), 'added': 0, 'reason': 'no reference date'}
            continue

        # 3. Nouveaux morceaux de la source
        new_tracks = [
            t for t in source_tracks
            if t.added_at > last_added and t.id not in existing_ids
        ]

        added = 0
        if new_tracks:
            prompt    = spotify.get_playlist_prompt(pid)
            decisions = _classifier.classify(prompt, new_tracks)
            selected  = _filter(decisions)
            if selected:
                spotify.add_to_playlist(pid, selected)
            added = len(selected)

        logger.info("Synced '%s': -%d / +%d tracks", name, len(to_remove), added)
        results[pid] = {'name': name, 'removed': len(to_remove), 'added': added, 'checked': len(new_tracks)}

    return results


def _filter(decisions: list) -> list:
    return [d.id for d in decisions if d.include]
