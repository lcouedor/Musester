import logging
from core.models import Track, Decision
from services.spotify import SpotifyService
from services.classifier import ClassifierService

logger = logging.getLogger(__name__)

_spotify    = SpotifyService()
_classifier = ClassifierService()


def generate_playlist(source_id: str, playlist_name: str, prompt: str) -> dict:
    tracks      = _spotify.get_tracks(source_id)
    decisions   = _classifier.classify(prompt, tracks)
    selected    = _filter(decisions)
    playlist_id = _spotify.create_playlist(playlist_name, prompt, selected)
    return {
        'playlist_id':    playlist_id,
        'checked_songs':  len(tracks),
        'selected_songs': len(selected),
        'decisions':      [d.__dict__ for d in decisions],
    }


def update_all_playlists(source_id: str) -> dict:
    """
    Met à jour toutes les playlists générées (préfixe IA-) avec les nouveaux
    morceaux de la source ajoutés depuis le dernier ajout à chaque playlist.
    """
    source_tracks    = _spotify.get_tracks(source_id, extended=True)
    source_ids       = {t.id for t in source_tracks}
    generated        = _spotify.get_user_generated_playlists()
    results          = {}

    for playlist in generated:
        pid  = playlist['id']
        name = playlist['name']

        # Déterminer la date de référence
        target_tracks = _spotify.get_tracks(pid, extended=True)
        existing_ids  = {t.id for t in target_tracks}

        if target_tracks:
            last_added = max(t.added_at for t in target_tracks)
        else:
            # Playlist vide — utiliser la date de création stockée dans la description
            last_added = _spotify.get_playlist_created_at(pid)

        if not last_added:
            logger.warning("No reference date for '%s', skipping", name)
            results[pid] = {'added': 0, 'reason': 'no reference date found'}
            continue

        # Morceaux de la source ajoutés après last_added, pas déjà dans la playlist
        new_tracks = [
            t for t in source_tracks
            if t.added_at > last_added and t.id not in existing_ids
        ]

        if not new_tracks:
            results[pid] = {'added': 0, 'reason': 'no new tracks in source'}
            continue

        prompt    = _spotify.get_playlist_prompt(pid)
        decisions = _classifier.classify(prompt, new_tracks)
        selected  = _filter(decisions)
        _spotify.add_to_playlist(pid, selected)

        logger.info("Updated '%s': +%d tracks", name, len(selected))
        results[pid] = {'name': name, 'added': len(selected), 'checked': len(new_tracks)}

    return results


def sync_all_playlists(source_id: str) -> dict:
    """
    Supprime de toutes les playlists générées (préfixe IA-) les morceaux
    qui ne sont plus dans la playlist source.
    """
    source_ids = {t.id for t in _spotify.get_tracks(source_id)}
    generated  = _spotify.get_user_generated_playlists()
    summary    = {}

    for playlist in generated:
        pid          = playlist['id']
        name         = playlist['name']
        target_tracks = _spotify.get_tracks(pid)
        to_remove    = [t.id for t in target_tracks if t.id not in source_ids]

        _spotify.remove_from_playlist(pid, to_remove)
        logger.info("Synced '%s': -%d tracks", name, len(to_remove))
        summary[pid] = {'name': name, 'removed': len(to_remove)}

    return summary


def _filter(decisions: list[Decision]) -> list[str]:
    return [d.id for d in decisions if d.include]
