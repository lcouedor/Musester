from flask import Blueprint, request, jsonify
from core.playlist import generate_playlist, update_playlists, sync_playlists
import time

bp = Blueprint('api', __name__)


def _parse_id(raw: str) -> str:
    if raw == "liked":
        return raw
    try:
        return raw.split('playlist/')[1].split('?')[0]
    except (IndexError, AttributeError):
        return raw

def _elapsed(start: float) -> str:
    return f"{round(time.time() - start, 2)}s"


@bp.route('/generate', methods=['GET'])
def generate():
    body = request.json or {}
    source_id = body.get('source_id')
    playlist_name = body.get('playlist_name')
    prompt = body.get('playlist_prompt')
    threshold = body.get('treshold_match_percentage')

    if not all([source_id, playlist_name, prompt, threshold is not None]):
        return jsonify({'error': 'Missing required parameters'}), 400

    start = time.time()
    result = generate_playlist(_parse_id(source_id), playlist_name, prompt, threshold)
    return jsonify({**result, 'execution_time': _elapsed(start)})


@bp.route('/update', methods=['GET'])
def update():
    body = request.json or {}
    source_id = body.get('source_id')
    target_ids = body.get('target_ids', [])
    threshold = body.get('treshold_match_percentage')

    if not all([source_id, target_ids, threshold is not None]):
        return jsonify({'error': 'Missing required parameters'}), 400

    start = time.time()
    result = update_playlists(_parse_id(source_id), [_parse_id(i) for i in target_ids], threshold)
    return jsonify({'results': result, 'execution_time': _elapsed(start)})


@bp.route('/sync', methods=['DELETE'])
def sync():
    body = request.json or {}
    source_id = body.get('source_id')
    target_ids = body.get('target_ids', [])

    if not all([source_id, target_ids]):
        return jsonify({'error': 'Missing required parameters'}), 400

    start = time.time()
    result = sync_playlists(_parse_id(source_id), [_parse_id(i) for i in target_ids])
    return jsonify({'summary': result, 'execution_time': _elapsed(start)})
