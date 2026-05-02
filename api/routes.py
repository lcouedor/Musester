import logging
import os
import secrets
import time
from functools import wraps
from typing import Optional

from flask import Blueprint, request, jsonify, redirect, session

from core.playlist import generate_playlist, sync_all_playlists
from services.auth import get_auth_url, exchange_code, save_token, get_valid_token
from services.spotify import SpotifyService

logger = logging.getLogger(__name__)
bp     = Blueprint('api', __name__)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _get_token() -> Optional[str]:
    user_id = session.get('user_id')
    if not user_id:
        return None
    return get_valid_token(user_id)


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _get_token()
        if not token:
            return _err('Not authenticated. Please login via /auth/login', 401)
        return f(token, *args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _elapsed(start: float) -> str:
    return f"{round(time.time() - start, 2)}s"

def _ok(data: dict, start: float) -> tuple:
    return jsonify({'error': None, 'data': data, 'execution_time': _elapsed(start)}), 200

def _err(message: str, status: int = 400) -> tuple:
    return jsonify({'error': message, 'data': None}), status


# ---------------------------------------------------------------------------
# ID parsing
# ---------------------------------------------------------------------------

def _parse_id(raw: str) -> str:
    if raw == "liked":
        return raw
    try:
        return raw.split('playlist/')[1].split('?')[0]
    except (IndexError, AttributeError):
        return raw


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@bp.route('/auth/login')
def login():
    state = secrets.token_urlsafe(16)
    session['oauth_state'] = state
    return redirect(get_auth_url(state))


@bp.route('/auth/callback')
def callback():
    error = request.args.get('error')
    if error:
        return _err(f'Spotify auth error: {error}')

    state = request.args.get('state')
    if state != session.get('oauth_state'):
        return _err('Invalid state parameter', 403)

    code       = request.args.get('code')
    token_data = exchange_code(code)

    # Récupérer l'id utilisateur Spotify
    user_id = SpotifyService.get_user_id(token_data['access_token'])
    save_token(user_id, token_data)
    session['user_id'] = user_id

    logger.info("User '%s' authenticated", user_id)
    return jsonify({'error': None, 'data': {'message': f'Logged in as {user_id}'}})


@bp.route('/auth/logout')
def logout():
    session.clear()
    return jsonify({'error': None, 'data': {'message': 'Logged out'}})


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@bp.route('/generate', methods=['GET'])
@require_auth
def generate(access_token: str):
    body      = request.json or {}
    source_id = body.get('source_id')
    name      = body.get('playlist_name')
    prompt    = body.get('playlist_prompt')

    if not all([source_id, name, prompt]):
        return _err('Missing required parameters: source_id, playlist_name, playlist_prompt')

    start  = time.time()
    result = generate_playlist(access_token, _parse_id(source_id), name, prompt)
    return _ok(result, start)


@bp.route('/sync', methods=['POST'])
@require_auth
def sync(access_token: str):
    body      = request.json or {}
    source_id = body.get('source_id')

    if not source_id:
        return _err('Missing required parameter: source_id')

    start  = time.time()
    result = sync_all_playlists(access_token, _parse_id(source_id))
    return _ok(result, start)
