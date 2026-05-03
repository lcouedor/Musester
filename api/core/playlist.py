import json
import logging
import os
from typing import Generator

from core.models import Track, Decision
from services.spotify import SpotifyService
from services.classifier import ClassifierService
from services.auth import save_playlist_prompt, get_playlist_prompt

logger      = logging.getLogger(__name__)
_classifier = ClassifierService()


def _event(kind: str, **data) -> str:
    return f"data: {json.dumps({'kind': kind, **data})}\n\n"


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------

def generate_playlist_stream(
    access_token: str,
    source_id: str,
    playlist_name: str,
    prompt: str,
    user_id: str,
) -> Generator[str, None, None]:

    spotify = SpotifyService(access_token)

    yield _event('status', message='Récupération des morceaux…')
    tracks = spotify.get_tracks(source_id)
    total_batches = -(-len(tracks) // __import__('config').BATCH_SIZE)
    yield _event('status', message=f'{len(tracks)} morceaux trouvés — {total_batches} batch(s) à analyser')
    yield _event('progress', done=0, total=total_batches)

    completed = {'n': 0}

    def on_batch_done(done: int, total: int):
        completed['n'] = done

    decisions = _classifier.classify(prompt, tracks, on_batch_done=on_batch_done)

    yield _event('progress', done=total_batches, total=total_batches)

    selected = _filter(decisions)
    yield _event('status', message=f'{len(selected)}/{len(tracks)} morceaux retenus — création de la playlist…')

    playlist_id = spotify.create_playlist(playlist_name, selected)

    # Prompt en DB
    save_playlist_prompt(user_id, playlist_id, prompt)

    _write_decisions_log(prompt, decisions)

    yield _event('done', **{
        'playlist_id':    playlist_id,
        'playlist_name':  playlist_name,
        'checked_songs':  len(tracks),
        'selected_songs': len(selected),
        'decisions':      [d.__dict__ for d in decisions],
    })


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

def sync_all_playlists_stream(
    access_token: str,
    source_id: str,
) -> Generator[str, None, None]:

    spotify = SpotifyService(access_token)

    yield _event('status', message='Récupération de la playlist source…')
    source_tracks = spotify.get_tracks(source_id, extended=True)
    source_ids    = {t.id for t in source_tracks}

    yield _event('status', message='Récupération des playlists générées…')
    generated = spotify.get_user_generated_playlists()
    total     = len(generated)
    results   = {}

    if total == 0:
        yield _event('done', results={})
        return

    yield _event('status', message=f'{total} playlist(s) à synchroniser')
    yield _event('progress', done=0, total=total)

    for i, playlist in enumerate(generated):
        pid  = playlist['id']
        name = playlist['name']

        yield _event('status', message=f'[{i+1}/{total}] {name} — suppression des morceaux retirés…')

        target_tracks = spotify.get_tracks(pid, extended=True)
        existing_ids  = {t.id for t in target_tracks}

        # 1. Suppression
        to_remove = [t.id for t in target_tracks if t.id not in source_ids]
        if to_remove:
            spotify.remove_from_playlist(pid, to_remove)

        # 2. Date de référence
        if target_tracks:
            last_added = max(t.added_at for t in target_tracks)
        else:
            last_added = spotify.get_playlist_created_at(pid)

        added   = 0
        checked = 0

        if not last_added:
            logger.warning("No reference date for '%s', skipping update step", name)
            results[pid] = {'name': name, 'removed': len(to_remove), 'added': 0, 'checked': 0, 'reason': 'no reference date'}
        else:
            new_tracks = [
                t for t in source_tracks
                if t.added_at > last_added and t.id not in existing_ids
            ]
            checked = len(new_tracks)

            if new_tracks:
                # Récupérer le prompt depuis la DB
                prompt = get_playlist_prompt(pid)
                if not prompt:
                    logger.warning("No prompt in DB for '%s', skipping", name)
                    results[pid] = {'name': name, 'removed': len(to_remove), 'added': 0, 'checked': checked, 'reason': 'no prompt in DB'}
                else:
                    batch_total = -(-len(new_tracks) // __import__('config').BATCH_SIZE)
                    yield _event('status', message=f'[{i+1}/{total}] {name} — classification de {checked} nouveaux morceaux ({batch_total} batch(s))…')
                    decisions = _classifier.classify(prompt, new_tracks)
                    selected  = _filter(decisions)
                    if selected:
                        spotify.add_to_playlist(pid, selected)
                    added = len(selected)
                    results[pid] = {'name': name, 'removed': len(to_remove), 'added': added, 'checked': checked}
            else:
                results[pid] = {'name': name, 'removed': len(to_remove), 'added': 0, 'checked': 0}

        yield _event('playlist_done', name=name, removed=len(to_remove), added=added, checked=checked)
        yield _event('progress', done=i + 1, total=total)

    yield _event('done', results=results)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _filter(decisions: list[Decision]) -> list[str]:
    return [d.id for d in decisions if d.include]


def _write_decisions_log(prompt: str, decisions: list[Decision]):
    log_path = os.path.join(os.path.dirname(__file__), '..', 'decisions.log')
    included = [d for d in decisions if d.include]
    excluded = [d for d in decisions if not d.include]
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write(f"PROMPT : {prompt}\n")
        f.write(f"TOTAL  : {len(decisions)} — INCLUS : {len(included)} — EXCLUS : {len(excluded)}\n")
        f.write("=" * 60 + "\n\n")
        f.write("✅ INCLUS\n")
        for d in included:
            f.write(f"  {d.title} — {d.reason}\n")
        f.write("\n❌ EXCLUS\n")
        for d in excluded:
            f.write(f"  {d.title} — {d.reason}\n")
