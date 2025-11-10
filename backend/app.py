from flask import Flask, redirect, request
from flask_cors import CORS
from utils import getSecret
from dotenv import load_dotenv
from services.services_spotify import get_playlist_tracks_infos, get_matching_songs_ids, create_user_playlist, remove_songs_from_playlist
from services.services_chatgpt import decisionHandler_parallel as decisionHandler
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
    playlistId = request.json['playlist_id']
    playlistName = request.json['playlist_name']
    playlistPrompt = request.json['playlist_prompt']
    treshold_match_percentage = request.json['treshold_match_percentage']
    try:
        playlistId = playlistId.split('playlist/')[1].split('?')[0]
    except:
        return jsonify({'message': 'Invalid playlist id format'})

    tracks_info = get_playlist_tracks_infos(playlistId)

    iaDecisions = decisionHandler(playlistPrompt, tracks_info)

    selected_songs_ids = get_matching_songs_ids(tracks_info, iaDecisions, treshold_match_percentage)
    createPlaylist = create_user_playlist(playlistName, playlistPrompt, selected_songs_ids)
    
    execution_time = f"{round(time.time() - start_time, 2)}s"

    return {'message': 'Playlist created successfully', 'execution_time': execution_time, 'checked_songs': len(tracks_info), 'playlist_id': createPlaylist, "songs_acceptance": iaDecisions}
    
@app.route('/sync', methods=['DELETE'])
def sync():
    """
    Remove from target playlists the songs that are no longer present in the source playlist.
    """
    start_time = time.time()
    source_id = request.json['source_id']
    targets_ids = request.json['targets_ids']
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
