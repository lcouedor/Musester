from flask import Flask, redirect, request
from flask_cors import CORS
from utils import getSecret
from dotenv import load_dotenv
from services.services_spotify import get_playlist_tracks_infos, get_matching_songs_ids, create_user_playlist, remove_songs_from_playlist, get_playlist_description, add_songs_to_playlist
from services.services_chatgpt import decision_handler_parallel as decision_handler
from flask import jsonify
from pprint import pprint
import json
import time

load_dotenv()

app = Flask(__name__)

CORS(app, resources={r"/*": {"origins": "*"}})

# Configurations de Spotify
SPOTIPY_CLIENT_ID = getSecret('SPOTIFY_ID')
SPOTIPY_CLIENT_SECRET = getSecret('SPOTIFY_SECRET')
SPOTIPY_REDIRECT_URI = getSecret('SPOTIFY_REDIRECT')

@app.route('/')
def home():
    return jsonify({'message': 'Welcome to the Playlist Generator API'})

@app.route('/generate', methods=['GET'])
def generate():
    """
    Generate a playlist based on user prompt and existing playlist tracks.
    """
    start_time = time.time()
    source_id = request.json['source_id']
    playlist_name = request.json['playlist_name']
    playlist_prompt = request.json['playlist_prompt']
    treshold_match_percentage = request.json['treshold_match_percentage']
    try:
        source_id = source_id.split('playlist/')[1].split('?')[0]
    except:
        return jsonify({'message': 'Invalid playlist id format'})

    tracks_info = get_playlist_tracks_infos(source_id)

    ia_decisions = decision_handler(playlist_prompt, tracks_info)

    selected_songs_ids = get_matching_songs_ids(tracks_info, ia_decisions, treshold_match_percentage)
    create_playlist = create_user_playlist(playlist_name, playlist_prompt, selected_songs_ids)
    
    execution_time = f"{round(time.time() - start_time, 2)}s"

    return {'message': 'Playlist created successfully', 'execution_time': execution_time, 'checked_songs': len(tracks_info), 'playlist_id': create_playlist, "songs_acceptance": ia_decisions}
    
@app.route('/update', methods=['GET'])
def update():
    """
    Update existing playlists based on user prompt and source playlist tracks.
    """
    start_time = time.time()
    source_id = request.json['source_id']
    target_ids = request.json['target_ids']
    treshold_match_percentage = request.json['treshold_match_percentage']
    try:
        source_id = source_id.split('playlist/')[1].split('?')[0]
    except:
        return jsonify({'message': 'Invalid playlist id format'})

    source_tracks_info = get_playlist_tracks_infos(source_id, extended=True)

    for target_id in target_ids:
        try:
            target_id = target_id.split('playlist/')[1].split('?')[0]
        except:
            return jsonify({'message': f'Invalid target playlist id format: {target_id}'})

        target_tracks_info = get_playlist_tracks_infos(target_id, extended=True)
        target_tracks_info.sort(key=lambda x: x['added_at'], reverse=True)
        last_added_date = target_tracks_info[0]['added_at']

        # récupérer la description de la playlist cible
        playlist_prompt = get_playlist_description(target_id)

        croped_source_tracks_info = [track for track in source_tracks_info if track['added_at'] > last_added_date]
        ia_decisions = decision_handler(playlist_prompt, croped_source_tracks_info)
        selected_songs_ids = get_matching_songs_ids(croped_source_tracks_info, ia_decisions, treshold_match_percentage)
        add_songs_to_playlist(target_id, selected_songs_ids)

    execution_time = f"{round(time.time() - start_time, 2)}s"

    return jsonify({'message': 'Playlists updated successfully', 'execution_time': execution_time})

@app.route('/sync', methods=['DELETE'])
def sync():
    """
    Remove from target playlists the songs that are no longer present in the source playlist.
    """
    start_time = time.time()
    source_id = request.json['source_id']
    targets_ids = request.json['target_ids']
    try:
        source_id = source_id.split('playlist/')[1].split('?')[0]
    except:
        return jsonify({'message': 'Invalid source playlist id format'})
    source_tracks_info = get_playlist_tracks_infos(source_id)
    
    #reduce source_tracks_info to only ids
    source_tracks_ids = [track['id'] for track in source_tracks_info]

    summary = {}

    for target_id in targets_ids:
        ids_to_remove = []
        try:
            target_id = target_id.split('playlist/')[1].split('?')[0]
        except:
            return jsonify({'message': f'Invalid target playlist id format: {target_id}'})
        target_tracks_info = get_playlist_tracks_infos(target_id, extended=True)
        
        for track in target_tracks_info:
            if track['id'] not in source_tracks_ids:
                ids_to_remove.append(track['id'])

        #remove tracks from target playlist
        remove_songs_from_playlist(target_id, ids_to_remove)
        summary[target_id] = len(ids_to_remove)

    return jsonify({'message': 'Playlists synchronized successfully', 'execution_time': f"{round(time.time() - start_time, 2)}s", 'summary': summary})


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5300)
