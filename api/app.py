from flask import Flask, request, jsonify
from flask_cors import CORS
from utils import getSecret
from dotenv import load_dotenv
from services.services_spotify import (
    get_playlist_tracks_infos,
    get_matching_songs_ids,
    create_user_playlist,
    remove_songs_from_playlist,
    get_playlist_description,
    add_songs_to_playlist,
)
from services.services_chatgpt import decision_handler_parallel as decision_handler
import time

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})


def _parse_playlist_id(raw_id: str):
    """Extrait l'id propre depuis une URL ou un id direct. Lève ValueError si invalide."""
    try:
        return raw_id.split('playlist/')[1].split('?')[0]
    except (IndexError, AttributeError):
        return raw_id  # déjà un id brut


def _elapsed(start: float) -> str:
    return f"{round(time.time() - start, 2)}s"


@app.route('/')
def home():
    return jsonify({'message': 'Welcome to the Playlist Generator API'})


@app.route('/generate', methods=['GET'])
def generate():
    body = request.json or {}
    source_id = body.get('source_id')
    playlist_name = body.get('playlist_name')
    playlist_prompt = body.get('playlist_prompt')
    treshold = body.get('treshold_match_percentage')

    if not all([source_id, playlist_name, playlist_prompt, treshold is not None]):
        return jsonify({'message': 'Missing required parameters'}), 400

    start = time.time()
    source_id = _parse_playlist_id(source_id)

    tracks_info = get_playlist_tracks_infos(source_id)
    ia_decisions = decision_handler(playlist_prompt, tracks_info)
    selected_ids = get_matching_songs_ids(tracks_info, ia_decisions, treshold)
    playlist_id = create_user_playlist(playlist_name, playlist_prompt, selected_ids)

    return jsonify({
        'message': 'Playlist created successfully',
        'execution_time': _elapsed(start),
        'checked_songs': len(tracks_info),
        'playlist_id': playlist_id,
        'songs_acceptance': ia_decisions,
    })


@app.route('/update', methods=['GET'])
def update():
    body = request.json or {}
    source_id = body.get('source_id')
    target_ids = body.get('target_ids', [])
    treshold = body.get('treshold_match_percentage')

    if not all([source_id, target_ids, treshold is not None]):
        return jsonify({'message': 'Missing required parameters'}), 400

    start = time.time()
    source_id = _parse_playlist_id(source_id)
    source_tracks_info = get_playlist_tracks_infos(source_id, extended=True)

    for raw_id in target_ids:
        target_id = _parse_playlist_id(raw_id)

        target_tracks = get_playlist_tracks_infos(target_id, extended=True)
        last_added = max(t['added_at'] for t in target_tracks)

        playlist_prompt = get_playlist_description(target_id)
        new_tracks = [t for t in source_tracks_info if t['added_at'] > last_added]

        if not new_tracks:
            continue

        ia_decisions = decision_handler(playlist_prompt, new_tracks)
        selected_ids = get_matching_songs_ids(new_tracks, ia_decisions, treshold)
        add_songs_to_playlist(target_id, selected_ids)

    return jsonify({'message': 'Playlists updated successfully', 'execution_time': _elapsed(start)})


@app.route('/sync', methods=['DELETE'])
def sync():
    body = request.json or {}
    source_id = body.get('source_id')
    targets_ids = body.get('target_ids', [])

    if not all([source_id, targets_ids]):
        return jsonify({'message': 'Missing required parameters'}), 400

    start = time.time()
    source_id = _parse_playlist_id(source_id)
    source_ids_set = {t['id'] for t in get_playlist_tracks_infos(source_id)}

    summary = {}
    for raw_id in targets_ids:
        target_id = _parse_playlist_id(raw_id)
        target_tracks = get_playlist_tracks_infos(target_id, extended=True)
        to_remove = [t['id'] for t in target_tracks if t['id'] not in source_ids_set]
        remove_songs_from_playlist(target_id, to_remove)
        summary[target_id] = len(to_remove)

    return jsonify({
        'message': 'Playlists synchronized successfully',
        'execution_time': _elapsed(start),
        'summary': summary,
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5300)
