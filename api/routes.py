import logging
import os
import secrets
import time
from functools import wraps
from typing import Optional

from flask import Blueprint, request, jsonify, redirect, session, Response, stream_with_context

from core.playlist import generate_playlist_stream, generate_multi_playlist_stream, sync_all_playlists_stream
from services.auth import (
    get_auth_url, exchange_code, save_token, get_valid_token,
    create_session_token, get_user_id_by_session_token, clear_session_token,
    save_generate, save_sync, get_history, get_history_decisions,
    save_playlist_prompt, get_playlist_prompt, get_playlist_anchors, get_playlist_source,
)
from services.spotify import SpotifyService
import config

logger = logging.getLogger(__name__)
bp     = Blueprint("api", __name__)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _current_user_id() -> Optional[str]:
    """Résout l'utilisateur via le bearer token envoyé par le front (pas de
    cookie — cross-site + Safari ITP ne le laisseraient pas survivre)."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    return get_user_id_by_session_token(auth_header.removeprefix("Bearer ").strip())


def _get_token() -> Optional[str]:
    user_id = _current_user_id()
    if not user_id:
        return None
    return get_valid_token(user_id)


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _get_token()
        if not token:
            return _err("Not authenticated. Please login via /auth/login", 401)
        return f(token, *args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _elapsed(start: float) -> str:
    return f"{round(time.time() - start, 2)}s"

def _ok(data, start: float = None) -> tuple:
    resp = {"error": None, "data": data}
    if start is not None:
        resp["execution_time"] = _elapsed(start)
    return jsonify(resp), 200

def _err(message: str, status: int = 400) -> tuple:
    return jsonify({"error": message, "data": None}), status


# ---------------------------------------------------------------------------
# ID parsing
# ---------------------------------------------------------------------------

def _parse_id(raw: str) -> str:
    if raw.strip().lower() == "liked":
        return "liked"
    try:
        return raw.split("playlist/")[1].split("?")[0]
    except (IndexError, AttributeError):
        return raw


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@bp.route("/auth/login")
def login():
    state = secrets.token_urlsafe(16)
    session["oauth_state"] = state
    return redirect(get_auth_url(state))


@bp.route("/auth/callback")
def callback():
    error = request.args.get("error")
    if error:
        return redirect(f"{config.FRONTEND_URL}?error={error}")

    state = request.args.get("state")
    if state != session.get("oauth_state"):
        return _err("Invalid state parameter", 403)

    code       = request.args.get("code")
    token_data = exchange_code(code)
    user_id    = SpotifyService.get_user_id(token_data["access_token"])

    if config.ALLOWED_USERS and user_id not in config.ALLOWED_USERS:
        logger.warning("Unauthorized login attempt by '%s'", user_id)
        return redirect(f"{config.FRONTEND_URL}?error=unauthorized")

    save_token(user_id, token_data)
    session_token = create_session_token(user_id)

    logger.info("User '%s' authenticated", user_id)
    # Le token part dans le fragment (#) : jamais envoyé au serveur / logs,
    # le front le récupère côté client et le stocke dans localStorage.
    return redirect(f"{config.FRONTEND_URL}#token={session_token}")


@bp.route("/auth/logout")
def logout():
    user_id = _current_user_id()
    if user_id:
        clear_session_token(user_id)
    return jsonify({"error": None, "data": {"message": "Logged out"}})


@bp.route("/auth/me")
def me():
    user_id = _current_user_id()
    if not user_id:
        return _err("Not authenticated", 401)
    return jsonify({"error": None, "data": {"user_id": user_id}})


# ---------------------------------------------------------------------------
# SSE — Generate
# ---------------------------------------------------------------------------

@bp.route("/generate", methods=["POST"])
@require_auth
def generate(access_token: str):
    body       = request.json or {}
    source_id  = body.get("source_id", "").strip()
    playlists  = body.get("playlists", [])
    multi_pass = body.get("multi_pass", True)

    if not source_id:
        return _err("Missing required parameter: source_id")
    if not playlists or not isinstance(playlists, list):
        return _err("Missing required parameter: playlists")
    if len(playlists) > 3:
        return _err("Maximum 3 playlists par génération")
    for i, pl in enumerate(playlists):
        if not pl.get("name") or not pl.get("prompt"):
            return _err(f"Playlist {i+1} : name and prompt are required")

    user_id = _current_user_id()
    start   = time.time()
    pid     = _parse_id(source_id)

    if len(playlists) == 1:
        pl = playlists[0]
        def stream_fn():
            return generate_playlist_stream(
                access_token, pid, pl["name"], pl["prompt"], user_id,
                anchors=pl.get("anchors", []), multi_pass=multi_pass,
            )
    else:
        def stream_fn():
            return generate_multi_playlist_stream(access_token, pid, playlists, user_id, multi_pass=multi_pass)

    def stream():
        import json as _json
        all_results = []
        for event in stream_fn():
            try:
                data = _json.loads(event.removeprefix("data: ").strip())
            except Exception:
                data = None

            if data and data.get("kind") == "done":
                all_results = data.get("results", [])
                # Le détail des décisions (GPT) reste côté serveur pour la persistance —
                # inutile de l'envoyer au client ici, il est récupéré à la demande via /history/<id>/decisions.
                slim = [{k: v for k, v in r.items() if k != "decisions"} for r in all_results]
                yield f"data: {_json.dumps({'kind': 'done', 'results': slim})}\n\n"
            else:
                yield event

        for pl_result in all_results:
            pidx    = pl_result.get("playlist_idx", 0)
            pl_spec = playlists[pidx] if pidx < len(playlists) else playlists[0]
            if pl_result.get("playlist_id"):
                save_generate(user_id, {
                    "playlist_id":    pl_result["playlist_id"],
                    "playlist_name":  pl_result["playlist_name"],
                    "prompt":         pl_spec.get("prompt", ""),
                    "checked_songs":  pl_result.get("checked_songs", 0),
                    "selected_songs": pl_result.get("selected_songs", 0),
                    "execution_time": _elapsed(start),
                    "decisions":      pl_result.get("decisions"),
                })

    return Response(
        stream_with_context(stream()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# SSE — Sync
# ---------------------------------------------------------------------------

@bp.route("/sync", methods=["POST"])
@require_auth
def sync(access_token: str):
    body        = request.json or {}
    source_id   = body.get("source_id")
    destructive = body.get("destructive", True)
    target_ids  = body.get("target_playlist_ids") or None

    if not source_id:
        return _err("Missing required parameter: source_id")

    user_id = _current_user_id()
    start   = time.time()

    def stream():
        import json as _json
        results = {}
        for event in sync_all_playlists_stream(
            access_token, _parse_id(source_id),
            destructive=destructive, target_ids=target_ids,
        ):
            yield event
            try:
                data = _json.loads(event.removeprefix("data: ").strip())
                if data.get("kind") == "done":
                    results.update(data.get("results", {}))
            except Exception:
                pass

        if results:
            save_sync(user_id, results, _elapsed(start))

    return Response(
        stream_with_context(stream()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Source tracks (anchor picker)
# ---------------------------------------------------------------------------

@bp.route("/source-tracks", methods=["GET"])
@require_auth
def source_tracks(access_token: str):
    source_id = request.args.get("source_id", "").strip()
    if not source_id:
        return _err("Missing required parameter: source_id")

    spotify = SpotifyService(access_token)
    try:
        tracks = spotify.get_tracks(_parse_id(source_id))
    except Exception:
        logger.exception("Failed to fetch source tracks for '%s'", source_id)
        return _err(f"Playlist source introuvable : « {source_id} ». Vérifie l'URL, ou tape « liked » pour tes titres likés.", 404)
    return _ok([{
        "id":        t.id,
        "title":     t.title,
        "artists":   t.artists,
        "cover_url": t.cover_url,
    } for t in tracks])


# ---------------------------------------------------------------------------
# Playlists
# ---------------------------------------------------------------------------

@bp.route("/playlists", methods=["GET"])
@require_auth
def playlists(access_token: str):
    spotify   = SpotifyService(access_token)
    generated = spotify.get_user_generated_playlists()
    result    = []

    for p in generated:
        pid       = p["id"]
        prompt    = get_playlist_prompt(pid) or ""
        tracks    = spotify.get_tracks(pid, extended=True)
        last_sync = max((t.added_at for t in tracks), default=None)
        result.append({
            "id":          pid,
            "name":        p["name"],
            "prompt":      prompt,
            "track_count": len(tracks),
            "last_sync":   last_sync,
        })

    return _ok(result)


@bp.route("/playlists/<playlist_id>/anchors", methods=["GET"])
@require_auth
def playlist_anchors(access_token: str, playlist_id: str):
    return _ok({
        "anchors":   get_playlist_anchors(playlist_id),
        "source_id": get_playlist_source(playlist_id),
    })


@bp.route("/playlists/<playlist_id>/prompt", methods=["PUT"])
@require_auth
def update_prompt(access_token: str, playlist_id: str):
    body   = request.json or {}
    prompt = body.get("prompt")

    if not prompt:
        return _err("Missing required parameter: prompt")

    user_id = _current_user_id()
    save_playlist_prompt(user_id, playlist_id, prompt)
    logger.info("Prompt updated for playlist '%s'", playlist_id)
    return _ok({"playlist_id": playlist_id, "prompt": prompt})


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

@bp.route("/history", methods=["GET"])
@require_auth
def history(access_token: str):
    user_id = _current_user_id()
    return _ok(get_history(user_id))


@bp.route("/history/<int:history_id>/decisions", methods=["GET"])
@require_auth
def history_decisions(access_token: str, history_id: int):
    user_id = _current_user_id()
    decisions = get_history_decisions(user_id, history_id)
    if decisions is None:
        return _err("Aucun détail de décision pour cette entrée", 404)
    return _ok(decisions)
