from flask import Flask, redirect, request
from flask_cors import CORS
from utils import getSecret
from dotenv import load_dotenv
from services.services_spotify import get_playlist_tracks_infos, get_matching_songs_ids, create_user_playlist
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
def sync():
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
    
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5300)
