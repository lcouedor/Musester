import logging
import time
from flask import Blueprint, request, jsonify
from core.playlist import generate_playlist, update_playlists, sync_playlists

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
    threshold = body.get('treshold_match_percentage')

    if not all([source_id, name, prompt, threshold is not None]):
        return _err('Missing required parameters: source_id, playlist_name, playlist_prompt, treshold_match_percentage')

    start = time.time()
    result = generate_playlist(_parse_id(source_id), name, prompt, threshold)
    return _ok(result, start)


@bp.route('/update', methods=['GET'])
def update():
    body       = request.json or {}
    source_id  = body.get('source_id')
    target_ids = body.get('target_ids', [])
    threshold  = body.get('treshold_match_percentage')

    if not all([source_id, target_ids, threshold is not None]):
        return _err('Missing required parameters: source_id, target_ids, treshold_match_percentage')

    start  = time.time()
    result = update_playlists(_parse_id(source_id), [_parse_id(i) for i in target_ids], threshold)
    return _ok(result, start)


@bp.route('/sync', methods=['DELETE'])
def sync():
    body       = request.json or {}
    source_id  = body.get('source_id')
    target_ids = body.get('target_ids', [])

    if not all([source_id, target_ids]):
        return _err('Missing required parameters: source_id, target_ids')

    start  = time.time()
    result = sync_playlists(_parse_id(source_id), [_parse_id(i) for i in target_ids])
    return _ok(result, start)
