import json
import logging
import os
from typing import Generator

from core.models import Track, Decision
from services.spotify import SpotifyService
from services.classifier import ClassifierService, PREPROMPT, PREPROMPT_PASS1, PREPROMPT_PASS2
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
    anchors: list[dict] = None,
    multi_pass: bool = True,
) -> Generator[str, None, None]:

    import config as _cfg

    spotify = SpotifyService(access_token)

    yield _event('status', message='Récupération des morceaux…')
    tracks    = spotify.get_tracks(source_id)
    track_map = {t.id: t for t in tracks}

    anchor_tracks: list[Track] = []
    if anchors:
        for a in anchors:
            t = track_map.get(a.get('id'))
            if t:
                anchor_tracks.append(t)
            else:
                anchor_tracks.append(Track(
                    id=a.get('id', ''),
                    title=a.get('title', ''),
                    artists=a.get('artists', ''),
                    album='',
                ))

    decisions: list[Decision] = []

    if multi_pass:
        # --- Pass 1 : broad filter ---
        pass1_batches = [tracks[i:i+_cfg.BATCH_SIZE] for i in range(0, len(tracks), _cfg.BATCH_SIZE)]
        total_p1      = len(pass1_batches)

        yield _event('status',   message=f'{len(tracks)} morceaux — Passe 1 : filtrage large ({total_p1} batch(s))…')
        yield _event('progress', done=0, total=total_p1, phase=1)

        pass1_decisions: list[Decision] = []
        for idx, batch in enumerate(pass1_batches):
            yield _event('status', message=f'Passe 1 — batch {idx+1}/{total_p1}…')
            raw = _classifier._process_batch(prompt, batch, idx, total_p1, preprompt=PREPROMPT_PASS1)
            for d in raw:
                try:
                    pass1_decisions.append(Decision(**d))
                except (TypeError, ValueError) as e:
                    logger.warning("Skipping malformed decision %s: %s", d, e)
            yield _event('progress', done=idx+1, total=total_p1, phase=1)

        candidates = [track_map[d.id] for d in pass1_decisions if d.include and d.id in track_map]
        yield _event('status', message=f'Passe 1 terminée — {len(candidates)}/{len(tracks)} candidats retenus')

        # --- Pass 2 : selective filter ---
        if candidates:
            pass2_batches = [candidates[i:i+_cfg.BATCH_SIZE] for i in range(0, len(candidates), _cfg.BATCH_SIZE)]
            total_p2      = len(pass2_batches)

            yield _event('status',   message=f'Passe 2 : sélection fine ({total_p2} batch(s))…')
            yield _event('progress', done=0, total=total_p2, phase=2)

            for idx, batch in enumerate(pass2_batches):
                yield _event('status', message=f'Passe 2 — batch {idx+1}/{total_p2}…')
                raw = _classifier._process_batch(
                    prompt, batch, idx, total_p2,
                    preprompt=PREPROMPT_PASS2,
                    anchors=anchor_tracks or None,
                )
                for d in raw:
                    try:
                        decisions.append(Decision(**d))
                    except (TypeError, ValueError) as e:
                        logger.warning("Skipping malformed decision %s: %s", d, e)
                yield _event('progress', done=idx+1, total=total_p2, phase=2)
        else:
            yield _event('status', message='Aucun candidat retenu en passe 1')

    else:
        # --- Single pass ---
        batches  = [tracks[i:i+_cfg.BATCH_SIZE] for i in range(0, len(tracks), _cfg.BATCH_SIZE)]
        total_b  = len(batches)

        yield _event('status',   message=f'{len(tracks)} morceaux — {total_b} batch(s) à analyser')
        yield _event('progress', done=0, total=total_b)

        for idx, batch in enumerate(batches):
            yield _event('status', message=f'Batch {idx+1}/{total_b} — analyse de {len(batch)} morceaux…')
            raw = _classifier._process_batch(
                prompt, batch, idx, total_b,
                anchors=anchor_tracks or None,
            )
            for d in raw:
                try:
                    decisions.append(Decision(**d))
                except (TypeError, ValueError) as e:
                    logger.warning("Skipping malformed decision %s: %s", d, e)
            yield _event('progress', done=idx+1, total=total_b)

    selected = _filter(decisions)
    yield _event('status', message=f'{len(selected)}/{len(tracks)} morceaux retenus — création de la playlist…')

    playlist_id = spotify.create_playlist(playlist_name, selected)
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

    import config as _cfg

    spotify = SpotifyService(access_token)

    yield _event('status', message='Récupération de la playlist source…')
    source_tracks = spotify.get_tracks(source_id, extended=True)
    source_ids    = {t.id for t in source_tracks}

    yield _event('status', message='Récupération des playlists générées…')
    generated = spotify.get_user_generated_playlists()
    total     = len(generated)
    results   = {}

    if total == 0:
        yield _event('status', message='Aucune playlist IA- trouvée')
        yield _event('done', results={})
        return

    yield _event('status',   message=f'{total} playlist(s) à synchroniser')
    yield _event('progress', done=0, total=total)

    for i, playlist in enumerate(generated):
        pid  = playlist['id']
        name = playlist['name']

        yield _event('status', message=f'[{i+1}/{total}] {name} — suppression des morceaux retirés…')

        target_tracks = spotify.get_tracks(pid, extended=True)
        existing_ids  = {t.id for t in target_tracks}

        to_remove = [t.id for t in target_tracks if t.id not in source_ids]
        if to_remove:
            spotify.remove_from_playlist(pid, to_remove)

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
                prompt = get_playlist_prompt(pid)
                if not prompt:
                    logger.warning("No prompt in DB for '%s', skipping", name)
                    results[pid] = {'name': name, 'removed': len(to_remove), 'added': 0, 'checked': checked, 'reason': 'no prompt in DB'}
                else:
                    total_batches = -(-len(new_tracks) // _cfg.BATCH_SIZE)
                    batches       = [new_tracks[j:j+_cfg.BATCH_SIZE] for j in range(0, len(new_tracks), _cfg.BATCH_SIZE)]
                    all_decisions = []

                    for bidx, batch in enumerate(batches):
                        yield _event('status', message=f'[{i+1}/{total}] {name} — batch {bidx+1}/{total_batches}…')
                        raw = _classifier._process_batch(prompt, batch, bidx, total_batches)
                        for d in raw:
                            try:
                                all_decisions.append(Decision(**d))
                            except (TypeError, ValueError):
                                pass

                    selected = _filter(all_decisions)
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

def _filter(decisions: list) -> list:
    return [d.id for d in decisions if d.include]


def _write_decisions_log(prompt: str, decisions: list):
    log_path = os.path.join(os.path.dirname(__file__), '..', 'decisions.log')
    included = [d for d in decisions if d.include]
    excluded = [d for d in decisions if not d.include]
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write(f"PROMPT : {prompt}\n")
        f.write(f"TOTAL  : {len(decisions)} — INCLUS : {len(included)} — EXCLUS : {len(excluded)}\n")
        f.write("=" * 60 + "\n\n")
        f.write("INCLUS\n")
        for d in included:
            f.write(f"  {d.title} — {d.reason}\n")
        f.write("\nEXCLUS\n")
        for d in excluded:
            f.write(f"  {d.title} — {d.reason}\n")
