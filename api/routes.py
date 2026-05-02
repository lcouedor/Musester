import logging
import time
from flask import Blueprint, request, jsonify
from core.playlist import generate_playlist, update_all_playlists, sync_all_playlists

logger = logging.getLogger(__name__)
bp     = Blueprint('api', __name__)


def _parse_id(raw: str) -> str:
    if raw == "liked":
        return raw
    try:
        return raw.split('playlist/')[1].split('?')[0]
    except (IndexError, AttributeError):
        return raw

def _elapsed(start: float) -> str:
    return f"{round(time.time() - start, 2)}s"

def _ok(data: dict, start: float) -> tuple:
    return jsonify({'error': None, 'data': data, 'execution_time': _elapsed(start)}), 200

def _err(message: str, status: int = 400) -> tuple:
    return jsonify({'error': message, 'data': None}), status


@bp.route('/generate', methods=['GET'])
def generate():
    body      = request.json or {}
    source_id = body.get('source_id')
    name      = body.get('playlist_name')
    prompt    = body.get('playlist_prompt')

    if not all([source_id, name, prompt]):
        return _err('Missing required parameters: source_id, playlist_name, playlist_prompt')

    start  = time.time()
    result = generate_playlist(_parse_id(source_id), name, prompt)
    return _ok(result, start)


@bp.route('/update', methods=['GET'])
def update():
    body      = request.json or {}
    source_id = body.get('source_id')

    if not source_id:
        return _err('Missing required parameter: source_id')

    start  = time.time()
    result = update_all_playlists(_parse_id(source_id))
    return _ok(result, start)


@bp.route('/sync', methods=['DELETE'])
def sync():
    body      = request.json or {}
    source_id = body.get('source_id')

    if not source_id:
        return _err('Missing required parameter: source_id')

    start  = time.time()
    result = sync_all_playlists(_parse_id(source_id))
    return _ok(result, start)
