import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Generator

from spotipy.exceptions import SpotifyException

from core.models import Track, Decision
from core.scoring import score_against_anchors, fetch_track_context, prompt_cares_about_language
from services.spotify import SpotifyService
from services.classifier import ClassifierService, PREPROMPT_PASS1, PREPROMPT_PASS2
from services.auth import (
    save_playlist_prompt, get_playlist_prompt, get_playlist_anchors, get_playlist_source, save_sync, save_merge,
)
from services import jobs as _jobs

logger      = logging.getLogger(__name__)
_classifier = ClassifierService()


def _event(kind: str, **data) -> str:
    return f"data: {json.dumps({'kind': kind, **data})}\n\n"


def _filter(decisions: list) -> list:
    return [d.id for d in decisions if d.include]


def source_error_message(source_id: str, exc: Exception) -> str:
    if isinstance(exc, SpotifyException) and exc.http_status in (400, 404):
        return f"Playlist source introuvable : « {source_id} ». Vérifie l'URL, ou tape « liked » pour tes titres likés."
    logger.exception("Failed to fetch source tracks for '%s'", source_id)
    return f"Impossible de récupérer la playlist source « {source_id} »."


def _resolve_anchors(anchors_raw: list[dict], track_map: dict) -> list[Track]:
    result = []
    for a in (anchors_raw or []):
        t = track_map.get(a.get("id"))
        result.append(t or Track(id=a.get("id", ""), title=a.get("title", ""),
                                  artists=a.get("artists", ""), album=""))
    return result


# En dessous de ce score, un faux négatif (un morceau pertinent écarté à
# tort) est jugé assez improbable pour justifier un rejet direct plutôt que
# de payer GPT dessus — contrairement à la zone entre ce plancher et le
# seuil normal, où le doute profite au morceau (voir plus bas). Mesuré sur
# un cas réel (ancre Bring Me The Horizon, prompt metalcore) : seulement
# ~7% des morceaux scorés tombent sous ce plancher, donc ça n'allège pas
# énormément la passe GPT à soi seul — mais ce sont les cas les plus sûrs
# à écarter sans y regarder à deux fois.
HARD_REJECT_BELOW = 0.15

_wait_with_heartbeat = _jobs.wait_with_heartbeat


def _model_for(total_batches: int) -> str:
    """gpt-4.1 classe un lot ~2x plus vite que gpt-4.1-mini (mesuré : ~12.5s
    contre ~25s), mais son rate limit sur ce compte est ~7x plus serré (30k
    tokens/min contre 200k). Au-delà d'un petit nombre de lots, cette
    concurrence bridée le rend plus LENT globalement que le mini malgré sa
    vitesse par appel — et en pire cas, des lots entiers échouent après
    épuisement des tentatives (constaté : lots revenus vides, donc des
    morceaux jamais évalués, pas juste un ralentissement). gpt-4.1 ne vaut
    le coup que pour peu de lots (ex. génération avec ancres, où la plupart
    des morceaux sautent déjà GPT) — au-delà du seuil, le mini est le choix
    sûr, quelle que soit la vitesse par appel."""
    import config as _cfg
    return _cfg.GPT_MODEL_FAST if total_batches <= _cfg.SMALL_JOB_BATCH_THRESHOLD else _cfg.GPT_MODEL


def _decisions_payload(decisions: list[Decision], track_map: dict) -> list[dict]:
    out = []
    for d in decisions:
        t = track_map.get(d.id)
        out.append({
            "title": d.title, "include": d.include, "reason": d.reason,
            "cover_url": t.cover_url if t else None,
        })
    return out


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
    job_id: str = None,
) -> Generator[str, None, None]:

    import config as _cfg

    spotify   = SpotifyService(access_token)
    yield _event("status", message="Récupération des morceaux…")
    try:
        tracks = spotify.get_tracks(source_id)
    except Exception as e:
        yield _event("error", message=source_error_message(source_id, e))
        return
    track_map = {t.id: t for t in tracks}

    anchor_tracks = _resolve_anchors(anchors, track_map)
    decisions: list[Decision] = []

    # Quand des ancres sont fournies, la similarité d'embedding (prompt + tags
    # Last.fm) fait office de raccourci pour les morceaux qu'elle juge
    # clairement bons — inutile de payer un appel GPT pour eux. Mais elle ne
    # sert JAMAIS à exclure seule : les tags Last.fm et un extrait de paroles
    # captent le thème d'un morceau, pas sa production ni son énergie sonore,
    # donc deux morceaux du même sous-genre peuvent scorer bas l'un par
    # rapport à l'autre sur ce texte seul (cas réel : pour une ancre Bring Me
    # The Horizon, "From The Inside" à 0.37 et "Even If It Kills Me" à 0.28
    # — clairement pertinents pour un humain, mais qu'un cutoff pur aurait
    # silencieusement exclus sans jamais les soumettre à GPT). Tout ce qui
    # n'est pas confirmé par l'embedding — signal faible ou absent — passe
    # donc par la passe 1 GPT normale, qui a le dernier mot.
    embedding_approved: list[Track] = []
    pass1_pool = tracks
    if anchor_tracks:
        yield _event("status", message="Calcul de similarité aux ancres…")
        try:
            scoring   = None
            cancelled = False
            for kind, *rest in score_against_anchors(tracks, prompt, anchor_tracks, job_id=job_id):
                if kind == "progress":
                    done, total = rest
                    yield _event("progress", done=done, total=total)
                elif kind == "cancelled":
                    cancelled = True
                else:
                    scoring = rest[0]
            if cancelled:
                yield _event("error", message="Génération annulée")
                return
            embedding_approved = [t for t in tracks if scoring.passes(t.id)]
            approved_ids = {a.id for a in embedding_approved}

            hard_rejected: list[Track] = []
            pass1_pool = []
            for t in tracks:
                if t.id in approved_ids:
                    continue
                score = scoring.scores.get(t.id)
                if score is not None and score < HARD_REJECT_BELOW:
                    hard_rejected.append(t)
                else:
                    pass1_pool.append(t)

            for t in hard_rejected:
                score = scoring.scores.get(t.id)
                decisions.append(Decision(
                    id=t.id, title=t.title, include=False,
                    reason=f"[similarité] {score:.2f} — trop éloigné des ancres, aucun doute raisonnable",
                ))

            yield _event("status", message=(
                f"{len(embedding_approved)}/{len(tracks)} candidats retenus directement par similarité "
                f"({len(hard_rejected)} exclus directement, {len(pass1_pool)} évalués par GPT)"
            ))
        except Exception as e:
            logger.warning("Embedding scoring failed, falling back to full GPT pass: %s", e)
            pass1_pool = tracks

    if multi_pass:
        # --- Pass 1 : broad filter (uniquement sur ce que l'embedding n'a pas pu trancher) ---
        candidates = list(embedding_approved)
        if pass1_pool:
            pass1_batches = [pass1_pool[i:i+_cfg.BATCH_SIZE] for i in range(0, len(pass1_pool), _cfg.BATCH_SIZE)]
            total_p1      = len(pass1_batches)

            yield _event("status",   message=f"{len(pass1_pool)} morceaux — Passe 1 : filtrage large ({total_p1} batch(s))…")
            yield _event("progress", done=0, total=total_p1, phase=1)

            raw_p1: dict[int, list] = {}
            model_p1 = _model_for(total_p1)
            anch_p1  = anchor_tracks or None
            with ThreadPoolExecutor(max_workers=_cfg.MAX_WORKERS) as ex:
                futs = {ex.submit(_classifier._process_batch, prompt, b, i, total_p1, PREPROMPT_PASS1, anch_p1, None, model_p1): i
                        for i, b in enumerate(pass1_batches)}
                done = 0
                for kind, fut in _wait_with_heartbeat(futs, job_id=job_id):
                    if kind == "heartbeat":
                        yield _event("status", message=f"Passe 1 — toujours en cours… ({done}/{total_p1} lots terminés)")
                        continue
                    if kind == "cancelled":
                        yield _event("error", message="Génération annulée")
                        return
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

            candidates += [track_map[d.id] for d in pass1_decisions if d.include and d.id in track_map]

        yield _event("status", message=f"Passe 1 terminée — {len(candidates)}/{len(tracks)} candidats retenus")

        # --- Pass 2 : selective filter ---
        if candidates:
            context = {}
            yield _event("status", message="Analyse des morceaux (tags, paroles)…")
            for kind, *rest in fetch_track_context(candidates, job_id=job_id):
                if kind == "progress":
                    done, total = rest
                    yield _event("progress", done=done, total=total, phase="context")
                elif kind == "cancelled":
                    yield _event("error", message="Génération annulée")
                    return
                else:
                    context = rest[0]
            languages = (
                {tid: p["language"] for tid, p in context.items() if p.get("language")}
                if prompt_cares_about_language(prompt) else {}
            )

            pass2_batches = [candidates[i:i+_cfg.BATCH_SIZE] for i in range(0, len(candidates), _cfg.BATCH_SIZE)]
            total_p2      = len(pass2_batches)

            yield _event("status",   message=f"Passe 2 : sélection fine ({total_p2} batch(s))…")
            yield _event("progress", done=0, total=total_p2, phase=2)

            raw_p2: dict[int, list] = {}
            anch = anchor_tracks or None
            model_p2 = _model_for(total_p2)
            with ThreadPoolExecutor(max_workers=_cfg.MAX_WORKERS) as ex:
                futs = {ex.submit(_classifier._process_batch, prompt, b, i, total_p2, PREPROMPT_PASS2, anch, languages, model_p2, context): i
                        for i, b in enumerate(pass2_batches)}
                done = 0
                for kind, fut in _wait_with_heartbeat(futs, job_id=job_id):
                    if kind == "heartbeat":
                        yield _event("status", message=f"Passe 2 — toujours en cours… ({done}/{total_p2} lots terminés)")
                        continue
                    if kind == "cancelled":
                        yield _event("error", message="Génération annulée")
                        return
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
        # --- Single pass (pré-filtré par similarité si des ancres sont fournies) ---
        working = embedding_approved + pass1_pool if anchor_tracks else tracks

        context = {}
        yield _event("status", message="Analyse des morceaux (tags, paroles)…")
        for kind, *rest in fetch_track_context(working, job_id=job_id):
            if kind == "progress":
                done, total = rest
                yield _event("progress", done=done, total=total, phase="context")
            elif kind == "cancelled":
                yield _event("error", message="Génération annulée")
                return
            else:
                context = rest[0]
        languages = (
            {tid: p["language"] for tid, p in context.items() if p.get("language")}
            if prompt_cares_about_language(prompt) else {}
        )

        batches = [working[i:i+_cfg.BATCH_SIZE] for i in range(0, len(working), _cfg.BATCH_SIZE)]
        total_b = len(batches)

        yield _event("status",   message=f"{len(working)} morceaux — {total_b} batch(s) en cours…")
        yield _event("progress", done=0, total=total_b)

        anch    = anchor_tracks or None
        raw_sp: dict[int, list] = {}
        model_sp = _model_for(total_b)
        with ThreadPoolExecutor(max_workers=_cfg.MAX_WORKERS) as ex:
            futs = {ex.submit(_classifier._process_batch, prompt, b, i, total_b, None, anch, languages, model_sp, context): i
                    for i, b in enumerate(batches)}
            done = 0
            for kind, fut in _wait_with_heartbeat(futs, job_id=job_id):
                if kind == "heartbeat":
                    yield _event("status", message=f"Toujours en cours… ({done}/{total_b} lots terminés)")
                    continue
                if kind == "cancelled":
                    yield _event("error", message="Génération annulée")
                    return
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

    description   = _classifier.generate_description(prompt)
    playlist_id   = spotify.create_playlist(playlist_name, selected, description=description)
    saved_anchors = [{"id": t.id, "title": t.title, "artists": t.artists, "cover_url": t.cover_url}
                      for t in anchor_tracks] or None
    save_playlist_prompt(user_id, playlist_id, prompt, anchors=saved_anchors, source_id=source_id)
    _write_decisions_log([{"name": playlist_name, "prompt": prompt, "anchors": anchor_tracks, "decisions": decisions}])

    yield _event("done", results=[{
        "playlist_idx":   0,
        "playlist_id":    playlist_id,
        "playlist_name":  playlist_name,
        "checked_songs":  len(tracks),
        "selected_songs": len(selected),
        "decisions":      _decisions_payload(decisions, track_map),
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
    job_id: str = None,
) -> Generator[str, None, None]:
    """
    playlists: [{'name': str, 'prompt': str, 'anchors': list[dict]}]
    Single GPT pass evaluates each track against all playlist contexts simultaneously.
    With multi_pass: passe 1 broad single filter → passe 2 full multi-playlist eval.
    """
    import config as _cfg

    spotify   = SpotifyService(access_token)
    yield _event("status", message="Récupération des morceaux…")
    try:
        tracks = spotify.get_tracks(source_id)
    except Exception as e:
        yield _event("error", message=source_error_message(source_id, e))
        return
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
        # Les ancres sont propres à CHAQUE playlist — les passer telles quelles
        # au paramètre "anchors" de _process_batch (pensé pour une seule
        # playlist à la fois) mélangerait des morceaux de référence de
        # contextes différents et parfois contradictoires sous un seul jugement
        # "ça va avec toutes ces ancres". On les inline donc directement dans
        # le texte, scopées à leur propre playlist, pour que le filtre large
        # en tienne compte dès le départ sans ce risque de confusion.
        def _describe(spec: dict) -> str:
            desc = f'[{spec["name"]}] {spec["prompt"]}'
            if spec["anchors"]:
                examples = ", ".join(f'"{a.title}" by {a.artists}' for a in spec["anchors"])
                desc += f" (reference tracks for this playlist: {examples})"
            return desc

        combined_prompt = " / ".join(_describe(spec) for spec in playlists_spec)

        pass1_batches = [tracks[i:i+_cfg.BATCH_SIZE] for i in range(0, len(tracks), _cfg.BATCH_SIZE)]
        total_p1      = len(pass1_batches)

        yield _event("status",   message=f"{len(tracks)} morceaux — Passe 1 : filtrage large ({total_p1} batch(s))…")
        yield _event("progress", done=0, total=total_p1, phase=1)

        raw_p1: dict[int, list] = {}
        model_p1 = _model_for(total_p1)
        with ThreadPoolExecutor(max_workers=_cfg.MAX_WORKERS) as ex:
            futs = {ex.submit(_classifier._process_batch, combined_prompt, b, i, total_p1, PREPROMPT_PASS1, None, None, model_p1): i
                    for i, b in enumerate(pass1_batches)}
            done = 0
            for kind, fut in _wait_with_heartbeat(futs, job_id=job_id):
                if kind == "heartbeat":
                    yield _event("status", message=f"Passe 1 — toujours en cours… ({done}/{total_p1} lots terminés)")
                    continue
                if kind == "cancelled":
                    yield _event("error", message="Génération annulée")
                    return
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

    context = {}
    yield _event("status", message="Analyse des morceaux (tags, paroles)…")
    for kind, *rest in fetch_track_context(eval_tracks, job_id=job_id):
        if kind == "progress":
            done, total = rest
            yield _event("progress", done=done, total=total, phase="context")
        elif kind == "cancelled":
            yield _event("error", message="Génération annulée")
            return
        else:
            context = rest[0]

    # --- Passe finale : évaluation multi-playlist complète ---
    batches = [eval_tracks[i:i+_cfg.BATCH_SIZE] for i in range(0, len(eval_tracks), _cfg.BATCH_SIZE)]
    total_b = len(batches)
    phase   = 2 if multi_pass else None

    yield _event("status",   message=f"{'Passe 2 : sélection fine' if multi_pass else f'{len(tracks)} morceaux'} — {total_b} batch(s) — {len(playlists)} playlists…")
    yield _event("progress", done=0, total=total_b, **({} if phase is None else {"phase": phase}))

    raw_by_idx: dict[int, dict] = {}
    model_final = _model_for(total_b)
    with ThreadPoolExecutor(max_workers=_cfg.MAX_WORKERS) as ex:
        futs = {ex.submit(_classifier._process_batch_multi, playlists_spec, b, i, total_b, model_final, context): i
                for i, b in enumerate(batches)}
        done = 0
        for kind, fut in _wait_with_heartbeat(futs, job_id=job_id):
            if kind == "heartbeat":
                yield _event("status", message=f"Toujours en cours… ({done}/{total_b} lots terminés)")
                continue
            if kind == "cancelled":
                yield _event("error", message="Génération annulée")
                return
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

    results     = []
    log_entries = []
    for spec in playlists_spec:
        decisions     = decisions_by_playlist[spec["idx"]]
        selected      = _filter(decisions)
        description   = _classifier.generate_description(spec["prompt"])
        playlist_id   = spotify.create_playlist(spec["name"], selected, description=description)
        saved_anchors = [{"id": t.id, "title": t.title, "artists": t.artists, "cover_url": t.cover_url}
                          for t in spec["anchors"]] or None
        save_playlist_prompt(user_id, playlist_id, spec["prompt"], anchors=saved_anchors, source_id=source_id)
        results.append({
            "playlist_idx":   spec["idx"],
            "playlist_id":    playlist_id,
            "playlist_name":  spec["name"],
            "checked_songs":  len(tracks),
            "selected_songs": len(selected),
            "decisions":      _decisions_payload(decisions, track_map),
        })
        log_entries.append({
            "name":      spec["name"],
            "prompt":    spec["prompt"],
            "anchors":   spec["anchors"],
            "decisions": decisions,
        })

    _write_decisions_log(log_entries)
    yield _event("done", results=results)


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

def sync_all_playlists_stream(
    access_token: str,
    destructive: bool = True,
    target_ids: list | None = None,
) -> Generator[str, None, None]:
    """Chaque playlist est synchronisée contre SA PROPRE source enregistrée
    (jamais une source choisie au vol) — le calcul de "nouveaux morceaux
    depuis le dernier sync" compare les dates d'ajout des morceaux CIBLE à
    ceux de la source, ce qui n'a de sens que si c'est la même source depuis
    le début. Pointer un sync vers une autre playlist a été tenté et a
    silencieusement filtré tous les morceaux (leurs dates d'ajout, souvent
    plus anciennes que le dernier ajout côté cible, ne passaient jamais le
    test "> last_added"). Pour fusionner ponctuellement le contenu d'une
    autre playlist, voir merge_playlist_stream — un import complet, sans
    filtre par date. Pour changer durablement la source d'une playlist,
    voir PUT /playlists/<id>/prompt (accepte un nouveau source_id)."""
    import config as _cfg

    spotify = SpotifyService(access_token)

    yield _event("status", message="Récupération des playlists générées…")
    generated = spotify.get_user_generated_playlists()
    if target_ids:
        target_set = set(target_ids)
        generated  = [p for p in generated if p["id"] in target_set]
    total = len(generated)
    results   = {}

    if total == 0:
        yield _event("status", message="Aucune playlist IA- trouvée")
        yield _event("done", results={})
        return

    yield _event("status",   message=f"{total} playlist(s) à synchroniser")
    yield _event("progress", done=0, total=total)

    log_entries: list[dict] = []
    # Plusieurs playlists IA- peuvent partager la même source — ne la
    # retélécharger qu'une fois par source distincte rencontrée dans ce sync.
    source_cache: dict[str, tuple[list, set, str]] = {}

    for i, playlist in enumerate(generated):
        pid  = playlist["id"]
        name = playlist["name"]

        added     = 0
        checked   = 0
        to_remove = []

        source_id = get_playlist_source(pid)
        if not source_id:
            results[pid] = {"name": name, "removed": 0, "added": 0, "checked": 0, "reason": "no source linked"}
            yield _event("status", message=f"[{i+1}/{total}] {name} — aucune source enregistrée, ignorée")
            yield _event("playlist_done", name=name, removed=0, added=0, checked=0)
            yield _event("progress", done=i + 1, total=total)
            continue

        if source_id not in source_cache:
            yield _event("status", message=f"[{i+1}/{total}] {name} — récupération de sa source…")
            try:
                s_tracks = spotify.get_tracks(source_id, extended=True)
                s_name   = spotify.get_playlist_name(source_id)
            except Exception:
                results[pid] = {"name": name, "removed": 0, "added": 0, "checked": 0, "reason": "source introuvable"}
                yield _event("status", message=f"[{i+1}/{total}] {name} — playlist source introuvable, ignorée")
                yield _event("playlist_done", name=name, removed=0, added=0, checked=0)
                yield _event("progress", done=i + 1, total=total)
                continue
            source_cache[source_id] = (s_tracks, {t.id for t in s_tracks}, s_name)

        source_tracks, source_ids, source_name = source_cache[source_id]

        if destructive:
            yield _event("status", message=f"[{i+1}/{total}] {name} — suppression des morceaux retirés…")
        else:
            yield _event("status", message=f"[{i+1}/{total}] {name} — recherche des nouveaux morceaux…")

        # Une erreur sur une playlist (ex: supprimée de Spotify depuis) ne doit pas
        # faire mourir tout le flux — sinon aucun résultat n'est jamais persisté,
        # même pour les playlists déjà traitées avec succès.
        try:
            target_tracks = spotify.get_tracks(pid, extended=True)
            existing_ids  = {t.id for t in target_tracks}

            if destructive:
                to_remove = [t.id for t in target_tracks if t.id not in source_ids]
                if to_remove:
                    spotify.remove_from_playlist(pid, to_remove)

            # Calcul sûr de last_added — certains morceaux Spotify ont added_at = None
            if target_tracks:
                valid_dates = [t.added_at for t in target_tracks if t.added_at]
                last_added  = max(valid_dates) if valid_dates else None
            else:
                last_added = spotify.get_playlist_created_at(pid)

            if not last_added:
                logger.warning("No reference date for '%s', skipping update step", name)
                results[pid] = {"name": name, "removed": len(to_remove), "added": 0, "checked": 0, "reason": "no reference date"}
            else:
                # Filtre défensif : ignorer les morceaux source sans date
                new_tracks    = [
                    t for t in source_tracks
                    if t.added_at and t.added_at > last_added and t.id not in existing_ids
                ]
                new_track_map = {t.id: t for t in new_tracks}
                checked = len(new_tracks)

                yield _event("status", message=(
                    f"[{i+1}/{total}] {name} — "
                    f"{checked} nouveau(x) morceau(x) détecté(s) depuis le dernier sync"
                ))

                if new_tracks:
                    prompt = get_playlist_prompt(pid)
                    if not prompt:
                        logger.warning("No prompt in DB for '%s', skipping", name)
                        results[pid] = {"name": name, "removed": len(to_remove), "added": 0, "checked": checked, "reason": "no prompt in DB"}
                    else:
                        raw_anchors  = get_playlist_anchors(pid)
                        sync_anchors = [Track(id=a["id"], title=a["title"], artists=a["artists"], album="")
                                        for a in raw_anchors] or None

                        # Pas de progress ici : le sync traite plusieurs playlists
                        # d'affilée et son done/total suit "combien de playlists
                        # terminées", pas les morceaux d'une étape interne — mélanger
                        # les deux ferait sauter la barre de façon incohérente.
                        context = {}
                        yield _event("status", message=f"[{i+1}/{total}] {name} — analyse des morceaux (tags, paroles)…")
                        for kind, *rest in fetch_track_context(new_tracks):
                            if kind != "progress":
                                context = rest[0]
                        languages = (
                            {tid: p["language"] for tid, p in context.items() if p.get("language")}
                            if prompt_cares_about_language(prompt) else {}
                        )

                        total_b = -(-len(new_tracks) // _cfg.BATCH_SIZE)
                        batches = [new_tracks[j:j+_cfg.BATCH_SIZE] for j in range(0, len(new_tracks), _cfg.BATCH_SIZE)]

                        yield _event("status", message=f"[{i+1}/{total}] {name} — {total_b} batch(s) en cours…")

                        raw_sync: dict[int, list] = {}
                        sync_done = 0
                        model_sync = _model_for(total_b)
                        with ThreadPoolExecutor(max_workers=_cfg.MAX_WORKERS) as ex:
                            futs = {ex.submit(_classifier._process_batch, prompt, b, j, total_b, None, sync_anchors, languages, model_sync, context): j
                                    for j, b in enumerate(batches)}
                            for kind, fut in _wait_with_heartbeat(futs):
                                if kind == "heartbeat":
                                    yield _event("status", message=(
                                        f"[{i+1}/{total}] {name} — toujours en cours… "
                                        f"({sync_done}/{total_b} lots terminés)"
                                    ))
                                    continue
                                raw_sync[futs[fut]] = fut.result()
                                sync_done += 1

                        all_decisions: list[Decision] = []
                        for j in sorted(raw_sync):
                            for d in raw_sync[j]:
                                try:
                                    all_decisions.append(Decision(**d))
                                except (TypeError, ValueError):
                                    pass

                        log_entries.append({
                            "name":      name,
                            "prompt":    prompt,
                            "anchors":   [Track(id=a["id"], title=a["title"], artists=a["artists"], album="")
                                          for a in raw_anchors] if raw_anchors else [],
                            "decisions": all_decisions,
                        })

                        selected = _filter(all_decisions)
                        if selected:
                            spotify.add_to_playlist(pid, selected)
                            if not destructive:
                                from datetime import datetime
                                date_str = datetime.now().strftime("%d/%m/%Y")
                                spotify.prepend_playlist_description(pid, f"[Sync additif depuis \"{source_name}\" — {date_str}] ")
                        added     = len(selected)
                        results[pid] = {
                            "name": name, "removed": len(to_remove), "added": added, "checked": checked,
                            "decisions": _decisions_payload(all_decisions, new_track_map),
                        }
                else:
                    results[pid] = {"name": name, "removed": len(to_remove), "added": 0, "checked": 0}
        except Exception:
            logger.exception("Sync failed for playlist '%s' (%s)", name, pid)
            results[pid] = {"name": name, "removed": len(to_remove), "added": 0, "checked": 0, "reason": "error"}
            yield _event("status", message=f"[{i+1}/{total}] {name} — erreur, playlist ignorée")

        yield _event("playlist_done", name=name, removed=len(to_remove), added=added, checked=checked)
        yield _event("progress", done=i + 1, total=total)

    if log_entries:
        _write_decisions_log(log_entries)
    yield _event("done", results=results)


# ---------------------------------------------------------------------------
# Merge — importe ponctuellement TOUT le contenu d'une playlist quelconque
# dans une playlist IA-XX existante, jugé contre son prompt/ses ancres.
# Contrairement au sync (qui ne regarde que ce qui a été ajouté à LA source
# depuis le dernier passage, par date), le merge n'a pas de notion de "depuis
# la dernière fois" — il évalue tout ce qui n'est pas déjà présent, en une
# fois. Toujours additif, ne retire jamais rien.
# ---------------------------------------------------------------------------

def merge_playlist_stream(
    access_token: str,
    from_id: str,
    target_id: str,
    user_id: str,
) -> Generator[str, None, None]:
    import config as _cfg

    spotify = SpotifyService(access_token)

    yield _event("status", message="Récupération des morceaux à fusionner…")
    try:
        from_tracks = spotify.get_tracks(from_id)
    except Exception as e:
        yield _event("error", message=source_error_message(from_id, e))
        return
    from_name = spotify.get_playlist_name(from_id)

    target_name = spotify.get_playlist_name(target_id)
    prompt = get_playlist_prompt(target_id)
    if not prompt:
        yield _event("error", message=f"Aucun prompt enregistré pour « {target_name} ».")
        return

    yield _event("status", message=f"« {target_name} » — récupération des morceaux actuels…")
    try:
        target_tracks = spotify.get_tracks(target_id)
    except Exception as e:
        yield _event("error", message=source_error_message(target_id, e))
        return
    existing_ids = {t.id for t in target_tracks}

    candidates = [t for t in from_tracks if t.id not in existing_ids]
    if not candidates:
        yield _event("done", result={
            "name": target_name, "from_name": from_name, "checked": 0, "added": 0, "decisions": [],
        })
        return

    raw_anchors  = get_playlist_anchors(target_id)
    anchor_track = [Track(id=a["id"], title=a["title"], artists=a["artists"], album="")
                     for a in raw_anchors] or None

    context = {}
    yield _event("status", message="Analyse des morceaux (tags, paroles)…")
    for kind, *rest in fetch_track_context(candidates):
        if kind == "progress":
            done, ctx_total = rest
            yield _event("progress", done=done, total=ctx_total, phase="context")
        else:
            context = rest[0]
    languages = (
        {tid: p["language"] for tid, p in context.items() if p.get("language")}
        if prompt_cares_about_language(prompt) else {}
    )

    batches = [candidates[i:i+_cfg.BATCH_SIZE] for i in range(0, len(candidates), _cfg.BATCH_SIZE)]
    total_b = len(batches)
    yield _event("status",   message=f"{len(candidates)} morceaux — {total_b} batch(s) en cours…")
    yield _event("progress", done=0, total=total_b)

    raw: dict[int, list] = {}
    model_mg = _model_for(total_b)
    with ThreadPoolExecutor(max_workers=_cfg.MAX_WORKERS) as ex:
        futs = {ex.submit(_classifier._process_batch, prompt, b, i, total_b, None, anchor_track, languages, model_mg, context): i
                for i, b in enumerate(batches)}
        done = 0
        for kind, fut in _wait_with_heartbeat(futs):
            if kind == "heartbeat":
                yield _event("status", message=f"Toujours en cours… ({done}/{total_b} lots terminés)")
                continue
            raw[futs[fut]] = fut.result()
            done += 1
            yield _event("progress", done=done, total=total_b)

    decisions: list[Decision] = []
    for idx in sorted(raw):
        for d in raw[idx]:
            try:
                decisions.append(Decision(**d))
            except (TypeError, ValueError) as e:
                logger.warning("Skipping malformed decision %s: %s", d, e)

    selected = _filter(decisions)
    if selected:
        spotify.add_to_playlist(target_id, selected)
        from datetime import datetime
        date_str = datetime.now().strftime("%d/%m/%Y")
        spotify.prepend_playlist_description(target_id, f"[Fusion depuis \"{from_name}\" — {date_str}] ")

    track_map = {t.id: t for t in candidates}
    result = {
        "name": target_name, "from_name": from_name,
        "checked": len(candidates), "added": len(selected),
        "decisions": _decisions_payload(decisions, track_map),
    }
    _write_decisions_log([{"name": target_name, "prompt": prompt, "anchors": anchor_track or [], "decisions": decisions}])
    save_merge(user_id, target_id, target_name, from_name, result)
    yield _event("done", result=result)


# ---------------------------------------------------------------------------
# Re-filter — réévalue le contenu ACTUEL d'une playlist contre son prompt
# ACTUEL (utile après une édition de prompt : le sync normal ne réévalue
# jamais les morceaux déjà présents, seulement les nouveaux arrivants côté
# source). Ne touche jamais à la source — retire uniquement ce qui ne
# correspond plus.
# ---------------------------------------------------------------------------

def refilter_playlist_stream(
    access_token: str,
    playlist_id: str,
    user_id: str,
) -> Generator[str, None, None]:
    import time as _time
    import config as _cfg

    spotify = SpotifyService(access_token)
    name    = spotify.get_playlist_name(playlist_id)
    prompt  = get_playlist_prompt(playlist_id)

    if not prompt:
        yield _event("error", message=f"Aucun prompt enregistré pour « {name} ».")
        return

    yield _event("status", message=f"« {name} » — récupération des morceaux actuels…")
    try:
        tracks = spotify.get_tracks(playlist_id)
    except Exception as e:
        yield _event("error", message=source_error_message(playlist_id, e))
        return

    if not tracks:
        yield _event("done", result={"name": name, "checked": 0, "removed": 0, "decisions": []})
        return

    raw_anchors  = get_playlist_anchors(playlist_id)
    anchor_track = [Track(id=a["id"], title=a["title"], artists=a["artists"], album="")
                     for a in raw_anchors] or None

    context = {}
    yield _event("status", message="Analyse des morceaux (tags, paroles)…")
    for kind, *rest in fetch_track_context(tracks):
        if kind == "progress":
            done, total = rest
            yield _event("progress", done=done, total=total, phase="context")
        else:
            context = rest[0]
    languages = (
        {tid: p["language"] for tid, p in context.items() if p.get("language")}
        if prompt_cares_about_language(prompt) else {}
    )

    batches = [tracks[i:i+_cfg.BATCH_SIZE] for i in range(0, len(tracks), _cfg.BATCH_SIZE)]
    total_b = len(batches)
    yield _event("status",   message=f"{len(tracks)} morceaux — {total_b} batch(s) en cours…")
    yield _event("progress", done=0, total=total_b)

    start   = _time.time()
    raw: dict[int, list] = {}
    model_rf = _model_for(total_b)
    with ThreadPoolExecutor(max_workers=_cfg.MAX_WORKERS) as ex:
        futs = {ex.submit(_classifier._process_batch, prompt, b, i, total_b, None, anchor_track, languages, model_rf, context): i
                for i, b in enumerate(batches)}
        done = 0
        for kind, fut in _wait_with_heartbeat(futs):
            if kind == "heartbeat":
                yield _event("status", message=f"Toujours en cours… ({done}/{total_b} lots terminés)")
                continue
            raw[futs[fut]] = fut.result()
            done += 1
            yield _event("progress", done=done, total=total_b)

    decisions: list[Decision] = []
    for idx in sorted(raw):
        for d in raw[idx]:
            try:
                decisions.append(Decision(**d))
            except (TypeError, ValueError) as e:
                logger.warning("Skipping malformed decision %s: %s", d, e)

    to_remove = [d.id for d in decisions if not d.include]
    if to_remove:
        spotify.remove_from_playlist(playlist_id, to_remove)

    track_map = {t.id: t for t in tracks}
    result = {
        "name": name, "checked": len(tracks), "removed": len(to_remove),
        "decisions": _decisions_payload(decisions, track_map),
    }
    save_sync(user_id, {playlist_id: result}, f"{round(_time.time() - start, 2)}s")
    yield _event("done", result=result)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_decisions_log(entries: list[dict]):
    """
    entries: [{'name': str, 'prompt': str, 'anchors': list[Track], 'decisions': list[Decision]}]
    """
    log_path   = os.path.join(os.path.dirname(__file__), "..", "decisions.log")
    n          = len(entries)
    checked    = len(entries[0]["decisions"]) if entries else 0
    sep_heavy  = "═" * 62
    sep_light  = "─" * 62

    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"{sep_heavy}\n")
        f.write(f"  GÉNÉRATION — {n} playlist(s)\n")
        f.write(f"{sep_heavy}\n\n")

        for i, entry in enumerate(entries):
            name      = entry["name"]
            prompt    = entry["prompt"]
            anchors   = entry.get("anchors") or []
            decisions = entry["decisions"]
            included  = [d for d in decisions if d.include]
            excluded  = [d for d in decisions if not d.include]

            f.write(f"[{i+1}/{n}] IA-{name}\n")
            f.write(f"{sep_light}\n")
            f.write(f"PROMPT   : {prompt}\n")
            if anchors:
                anchor_str = ", ".join(f'"{a.title}" by {a.artists}' for a in anchors)
                f.write(f"ANCHORS  : {anchor_str}\n")
            f.write(f"RÉSULTAT : {len(included)} inclus / {len(excluded)} exclus / {len(decisions)} évalués\n\n")

            f.write("✓ INCLUS\n")
            for d in included:
                f.write(f"  {d.title} — {d.reason}\n")

            f.write("\n✗ EXCLUS\n")
            for d in excluded:
                f.write(f"  {d.title} — {d.reason}\n")

            if i < n - 1:
                f.write(f"\n{sep_heavy}\n\n")
