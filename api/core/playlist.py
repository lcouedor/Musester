from core.models import Track, Decision
from services.spotify import SpotifyService
from services.classifier import ClassifierService

# Singletons — instanciés une seule fois au démarrage
_spotify    = SpotifyService()
_classifier = ClassifierService()


def generate_playlist(source_id: str, playlist_name: str, prompt: str, threshold: int) -> dict:
    tracks    = _spotify.get_tracks(source_id)
    decisions = _classifier.classify(prompt, tracks)
    selected  = _filter(tracks, decisions, threshold)
    playlist_id = _spotify.create_playlist(playlist_name, prompt, selected)
    return {
        'playlist_id':    playlist_id,
        'checked_songs':  len(tracks),
        'selected_songs': len(selected),
        'decisions':      [d.__dict__ for d in decisions],
    }


def update_playlists(source_id: str, target_ids: list[str], threshold: int) -> dict:
    source_tracks = _spotify.get_tracks(source_id, extended=True)
    results = {}

    for target_id in target_ids:
        target_tracks = _spotify.get_tracks(target_id, extended=True)
        last_added    = max(t.added_at for t in target_tracks)
        new_tracks    = [t for t in source_tracks if t.added_at > last_added]

        if not new_tracks:
            results[target_id] = {'added': 0, 'reason': 'no new tracks in source'}
            continue

        prompt    = _spotify.get_playlist_description(target_id)
        decisions = _classifier.classify(prompt, new_tracks)
        selected  = _filter(new_tracks, decisions, threshold)
        _spotify.add_to_playlist(target_id, selected)
        results[target_id] = {'added': len(selected)}

    return results


def sync_playlists(source_id: str, target_ids: list[str]) -> dict:
    source_ids = {t.id for t in _spotify.get_tracks(source_id)}
    summary    = {}

    for target_id in target_ids:
        target_tracks = _spotify.get_tracks(target_id)
        to_remove     = [t.id for t in target_tracks if t.id not in source_ids]
        _spotify.remove_from_playlist(target_id, to_remove)
        summary[target_id] = {'removed': len(to_remove)}

    return summary


def _filter(tracks: list[Track], decisions: list[Decision], threshold: int) -> list[str]:
    valid_ids = {t.id for t in tracks}
    return [d.id for d in decisions if d.id in valid_ids and d.match >= threshold]
