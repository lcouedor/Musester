import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Generator

from core.models import Track, Decision
from services.spotify import SpotifyService
from services.classifier import ClassifierService, PREPROMPT_PASS1, PREPROMPT_PASS2
from services.auth import save_playlist_prompt, get_playlist_prompt, get_playlist_anchors

logger      = logging.getLogger(__name__)
_classifier = ClassifierService()


def _event(kind: str, **data) -> str:
    return f"data: {json.dumps({'kind': kind, **data})}\n\n"


def _filter(decisions: list) -> list:
    return [d.id for d in decisions if d.include]


def _resolve_anchors(anchors_raw: list[dict], track_map: dict) -> list[Track]:
    result = []
    for a in (anchors_raw or []):
        t = track_map.get(a.get("id"))
        result.append(t or Track(id=a.get("id", ""), title=a.get("title", ""),
                                  artists=a.get("artists", ""), album=""))
    return result


def _run_parallel_batches(batches, submit_fn, total, phase=None):
    """
    Yields (progress_event, raw_results_dict) pairs as batches complete.
    submit_fn(batch, idx, total) → Future
    Returns ordered dict: {idx: raw_result}
    """
    raw_by_idx = {}
    with ThreadPoolExecutor(max_workers=__import__("config").MAX_WORKERS) as ex:
        futures = {ex.submit(submit_fn, b, i, total): i for i, b in enumerate(batches)}
        done = 0
        for fut in as_completed(futures):
            raw_by_idx[futures[fut]] = fut.result()
            done += 1
            kwargs = dict(done=done, total=total)
            if phase is not None:
                kwargs["phase"] = phase
            yield _event("progress", **kwargs)
    return raw_by_idx


# ---------------------------------------------------------------------------
# Generate — single playlist
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

    spotify   = SpotifyService(access_token)
    yield _event("status", message="Récupération des morceaux…")
    tracks    = spotify.get_tracks(source_id)
    track_map = {t.id: t for t in tracks}

    anchor_tracks = _resolve_anchors(anchors, track_map)
    decisions: list[Decision] = []

    if multi_pass:
        # --- Pass 1 : broad filter ---
        pass1_batches = [tracks[i:i+_cfg.BATCH_SIZE] for i in range(0, len(tracks), _cfg.BATCH_SIZE)]
        total_p1      = len(pass1_batches)

        yield _event("status",   message=f"{len(tracks)} morceaux — Passe 1 : filtrage large ({total_p1} batch(s))…")
        yield _event("progress", done=0, total=total_p1, phase=1)

        raw_p1: dict[int, list] = {}
        with ThreadPoolExecutor(max_workers=_cfg.MAX_WORKERS) as ex:
            futs = {ex.submit(_classifier._process_batch, prompt, b, i, total_p1, PREPROMPT_PASS1): i
                    for i, b in enumerate(pass1_batches)}
            done = 0
            for fut in as_completed(futs):
                raw_p1[futs[fut]] = fut.result()
                done += 1
                yield _event("progress", done=done, total=total_p1, phase=1)

        pass1_decisions: list[Decision] = []
        for idx in sorted(raw_p1):
            for d in raw_p1[idx]:
                try:
                    pass1_decisions.append(Decision(**d))
                except (TypeError, ValueError) as e:
                    logger.warning("Skipping malformed decision %s: %s", d, e)

        candidates = [track_map[d.id] for d in pass1_decisions if d.include and d.id in track_map]
        yield _event("status", message=f"Passe 1 terminée — {len(candidates)}/{len(tracks)} candidats retenus")

        # --- Pass 2 : selective filter ---
        if candidates:
            pass2_batches = [candidates[i:i+_cfg.BATCH_SIZE] for i in range(0, len(candidates), _cfg.BATCH_SIZE)]
            total_p2      = len(pass2_batches)

            yield _event("status",   message=f"Passe 2 : sélection fine ({total_p2} batch(s))…")
            yield _event("progress", done=0, total=total_p2, phase=2)

            raw_p2: dict[int, list] = {}
            anch = anchor_tracks or None
            with ThreadPoolExecutor(max_workers=_cfg.MAX_WORKERS) as ex:
                futs = {ex.submit(_classifier._process_batch, prompt, b, i, total_p2, PREPROMPT_PASS2, anch): i
                        for i, b in enumerate(pass2_batches)}
                done = 0
                for fut in as_completed(futs):
                    raw_p2[futs[fut]] = fut.result()
                    done += 1
                    yield _event("progress", done=done, total=total_p2, phase=2)

            for idx in sorted(raw_p2):
                for d in raw_p2[idx]:
                    try:
                        decisions.append(Decision(**d))
                    except (TypeError, ValueError) as e:
                        logger.warning("Skipping malformed decision %s: %s", d, e)
        else:
            yield _event("status", message="Aucun candidat retenu en passe 1")

    else:
        # --- Single pass ---
        batches = [tracks[i:i+_cfg.BATCH_SIZE] for i in range(0, len(tracks), _cfg.BATCH_SIZE)]
        total_b = len(batches)

        yield _event("status",   message=f"{len(tracks)} morceaux — {total_b} batch(s) en cours…")
        yield _event("progress", done=0, total=total_b)

        anch    = anchor_tracks or None
        raw_sp: dict[int, list] = {}
        with ThreadPoolExecutor(max_workers=_cfg.MAX_WORKERS) as ex:
            futs = {ex.submit(_classifier._process_batch, prompt, b, i, total_b, None, anch): i
                    for i, b in enumerate(batches)}
            done = 0
            for fut in as_completed(futs):
                raw_sp[futs[fut]] = fut.result()
                done += 1
                yield _event("progress", done=done, total=total_b)

        for idx in sorted(raw_sp):
            for d in raw_sp[idx]:
                try:
                    decisions.append(Decision(**d))
                except (TypeError, ValueError) as e:
                    logger.warning("Skipping malformed decision %s: %s", d, e)

    selected    = _filter(decisions)
    yield _event("status", message=f"{len(selected)}/{len(tracks)} morceaux retenus — création de la playlist…")

    playlist_id   = spotify.create_playlist(playlist_name, selected)
    saved_anchors = [{"id": t.id, "title": t.title, "artists": t.artists} for t in anchor_tracks] or None
    save_playlist_prompt(user_id, playlist_id, prompt, anchors=saved_anchors)
    _write_decisions_log(prompt, decisions)

    yield _event("done", results=[{
        "playlist_idx":   0,
        "playlist_id":    playlist_id,
        "playlist_name":  playlist_name,
        "checked_songs":  len(tracks),
        "selected_songs": len(selected),
    }])


# ---------------------------------------------------------------------------
# Generate — multi-playlist (single GPT pass, multiple prompts)
# ---------------------------------------------------------------------------

def generate_multi_playlist_stream(
    access_token: str,
    source_id: str,
    playlists: list[dict],
    user_id: str,
    multi_pass: bool = False,
) -> Generator[str, None, None]:
    """
    playlists: [{'name': str, 'prompt': str, 'anchors': list[dict]}]
    Single GPT pass evaluates each track against all playlist contexts simultaneously.
    With multi_pass: passe 1 broad single filter → passe 2 full multi-playlist eval.
    """
    import config as _cfg

    spotify   = SpotifyService(access_token)
    yield _event("status", message="Récupération des morceaux…")
    tracks    = spotify.get_tracks(source_id)
    track_map = {t.id: t for t in tracks}

    playlists_spec = []
    for i, pl in enumerate(playlists):
        playlists_spec.append({
            "idx":     i,
            "name":    pl["name"],
            "prompt":  pl["prompt"],
            "anchors": _resolve_anchors(pl.get("anchors", []), track_map),
        })

    decisions_by_playlist: dict[int, list[Decision]] = {i: [] for i in range(len(playlists))}

    if multi_pass:
        # --- Passe 1 : filtre large sur une description combinée ---
        combined_prompt = " / ".join(f'[{spec["name"]}] {spec["prompt"]}' for spec in playlists_spec)

        pass1_batches = [tracks[i:i+_cfg.BATCH_SIZE] for i in range(0, len(tracks), _cfg.BATCH_SIZE)]
        total_p1      = len(pass1_batches)

        yield _event("status",   message=f"{len(tracks)} morceaux — Passe 1 : filtrage large ({total_p1} batch(s))…")
        yield _event("progress", done=0, total=total_p1, phase=1)

        raw_p1: dict[int, list] = {}
        with ThreadPoolExecutor(max_workers=_cfg.MAX_WORKERS) as ex:
            futs = {ex.submit(_classifier._process_batch, combined_prompt, b, i, total_p1, PREPROMPT_PASS1): i
                    for i, b in enumerate(pass1_batches)}
            done = 0
            for fut in as_completed(futs):
                raw_p1[futs[fut]] = fut.result()
                done += 1
                yield _event("progress", done=done, total=total_p1, phase=1)

        pass1_decisions: list[Decision] = []
        for idx in sorted(raw_p1):
            for d in raw_p1[idx]:
                try:
                    pass1_decisions.append(Decision(**d))
                except (TypeError, ValueError) as e:
                    logger.warning("Skipping malformed decision %s: %s", d, e)

        candidates = [track_map[d.id] for d in pass1_decisions if d.include and d.id in track_map]
        yield _event("status", message=f"Passe 1 terminée — {len(candidates)}/{len(tracks)} candidats retenus")

        if not candidates:
            yield _event("status", message="Aucun candidat retenu en passe 1")
            yield _event("done", results=[])
            return

        eval_tracks = candidates
    else:
        eval_tracks = tracks

    # --- Passe finale : évaluation multi-playlist complète ---
    batches = [eval_tracks[i:i+_cfg.BATCH_SIZE] for i in range(0, len(eval_tracks), _cfg.BATCH_SIZE)]
    total_b = len(batches)
    phase   = 2 if multi_pass else None

    yield _event("status",   message=f"{'Passe 2 : sélection fine' if multi_pass else f'{len(tracks)} morceaux'} — {total_b} batch(s) — {len(playlists)} playlists…")
    yield _event("progress", done=0, total=total_b, **({} if phase is None else {"phase": phase}))

    raw_by_idx: dict[int, dict] = {}
    with ThreadPoolExecutor(max_workers=_cfg.MAX_WORKERS) as ex:
        futs = {ex.submit(_classifier._process_batch_multi, playlists_spec, b, i, total_b): i
                for i, b in enumerate(batches)}
        done = 0
        for fut in as_completed(futs):
            raw_by_idx[futs[fut]] = fut.result()
            done += 1
            evt = {"done": done, "total": total_b}
            if phase is not None:
                evt["phase"] = phase
            yield _event("progress", **evt)

    for idx in sorted(raw_by_idx):
        for pidx, raw_decisions in raw_by_idx[idx].items():
            for d in raw_decisions:
                try:
                    decisions_by_playlist[pidx].append(Decision(**d))
                except (TypeError, ValueError) as e:
                    logger.warning("Skipping malformed decision %s: %s", d, e)

    yield _event("status", message=f"Création de {len(playlists)} playlist(s)…")

    results = []
    for spec in playlists_spec:
        selected      = _filter(decisions_by_playlist[spec["idx"]])
        playlist_id   = spotify.create_playlist(spec["name"], selected)
        saved_anchors = [{"id": t.id, "title": t.title, "artists": t.artists} for t in spec["anchors"]] or None
        save_playlist_prompt(user_id, playlist_id, spec["prompt"], anchors=saved_anchors)
        results.append({
            "playlist_idx":   spec["idx"],
            "playlist_id":    playlist_id,
            "playlist_name":  spec["name"],
            "checked_songs":  len(tracks),
            "selected_songs": len(selected),
        })

    yield _event("done", results=results)


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

def sync_all_playlists_stream(
    access_token: str,
    source_id: str,
) -> Generator[str, None, None]:

    import config as _cfg

    spotify = SpotifyService(access_token)

    yield _event("status", message="Récupération de la playlist source…")
    source_tracks = spotify.get_tracks(source_id, extended=True)
    source_ids    = {t.id for t in source_tracks}

    yield _event("status", message="Récupération des playlists générées…")
    generated = spotify.get_user_generated_playlists()
    total     = len(generated)
    results   = {}

    if total == 0:
        yield _event("status", message="Aucune playlist IA- trouvée")
        yield _event("done", results={})
        return

    yield _event("status",   message=f"{total} playlist(s) à synchroniser")
    yield _event("progress", done=0, total=total)

    for i, playlist in enumerate(generated):
        pid  = playlist["id"]
        name = playlist["name"]

        yield _event("status", message=f"[{i+1}/{total}] {name} — suppression des morceaux retirés…")

        target_tracks = spotify.get_tracks(pid, extended=True)
        existing_ids  = {t.id for t in target_tracks}

        to_remove = [t.id for t in target_tracks if t.id not in source_ids]
        if to_remove:
            spotify.remove_from_playlist(pid, to_remove)

        last_added = max((t.added_at for t in target_tracks), default=None) if target_tracks else spotify.get_playlist_created_at(pid)

        added   = 0
        checked = 0

        if not last_added:
            logger.warning("No reference date for '%s', skipping update step", name)
            results[pid] = {"name": name, "removed": len(to_remove), "added": 0, "checked": 0, "reason": "no reference date"}
        else:
            new_tracks = [t for t in source_tracks if t.added_at > last_added and t.id not in existing_ids]
            checked    = len(new_tracks)

            if new_tracks:
                prompt = get_playlist_prompt(pid)
                if not prompt:
                    logger.warning("No prompt in DB for '%s', skipping", name)
                    results[pid] = {"name": name, "removed": len(to_remove), "added": 0, "checked": checked, "reason": "no prompt in DB"}
                else:
                    raw_anchors  = get_playlist_anchors(pid)
                    sync_anchors = [Track(id=a["id"], title=a["title"], artists=a["artists"], album="")
                                    for a in raw_anchors] or None
                    total_b  = -(-len(new_tracks) // _cfg.BATCH_SIZE)
                    batches  = [new_tracks[j:j+_cfg.BATCH_SIZE] for j in range(0, len(new_tracks), _cfg.BATCH_SIZE)]

                    yield _event("status", message=f"[{i+1}/{total}] {name} — {total_b} batch(s) en cours…")

                    raw_sync: dict[int, list] = {}
                    with ThreadPoolExecutor(max_workers=_cfg.MAX_WORKERS) as ex:
                        futs = {ex.submit(_classifier._process_batch, prompt, b, j, total_b, None, sync_anchors): j
                                for j, b in enumerate(batches)}
                        for fut in as_completed(futs):
                            raw_sync[futs[fut]] = fut.result()

                    all_decisions = []
                    for j in sorted(raw_sync):
                        for d in raw_sync[j]:
                            try:
                                all_decisions.append(Decision(**d))
                            except (TypeError, ValueError):
                                pass

                    selected = _filter(all_decisions)
                    if selected:
                        spotify.add_to_playlist(pid, selected)
                    added     = len(selected)
                    results[pid] = {"name": name, "removed": len(to_remove), "added": added, "checked": checked}
            else:
                results[pid] = {"name": name, "removed": len(to_remove), "added": 0, "checked": 0}

        yield _event("playlist_done", name=name, removed=len(to_remove), added=added, checked=checked)
        yield _event("progress", done=i + 1, total=total)

    yield _event("done", results=results)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_decisions_log(prompt: str, decisions: list):
    log_path = os.path.join(os.path.dirname(__file__), "..", "decisions.log")
    included = [d for d in decisions if d.include]
    excluded = [d for d in decisions if not d.include]
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"PROMPT : {prompt}\n")
        f.write(f"TOTAL  : {len(decisions)} — INCLUS : {len(included)} — EXCLUS : {len(excluded)}\n")
        f.write("=" * 60 + "\n\n")
        f.write("INCLUS\n")
        for d in included:
            f.write(f"  {d.title} — {d.reason}\n")
        f.write("\nEXCLUS\n")
        for d in excluded:
            f.write(f"  {d.title} — {d.reason}\n")
