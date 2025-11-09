from flask import Flask, redirect, request
from flask_cors import CORS
from utils import getSecret
from dotenv import load_dotenv
from services.services_spotify import get_playlist_tracks_infos, get_matching_songs_ids, create_user_playlist
from services.services_chatgpt import decisionHandler
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

@app.route('/generate', methods=['GET'])
def sync():
    start_time = time.time()
    playlistId = request.json['playlist_id']
    playlistName = request.json['playlist_name']
    playlistPrompt = request.json['playlist_prompt']
    try:
        playlistId = playlistId.split('playlist/')[1].split('?')[0]
    except:
        return jsonify({'message': 'Invalid playlist id format'})

    tracks_info = get_playlist_tracks_infos(playlistId)
    iaDecisions = decisionHandler(playlistPrompt, tracks_info)
    # iaDecisions = '[{"id": "6YB9jhzVEzw8CKeXD7Vx8j", "title": "What Could Have Been (from the series Arcane League of Legends)", "match":"60"},{"id": "6ZFbXIJkuI1dVNWvzJzown", "title": "Time", "match": "85"},{"id": "2LSsSV7V33wM9EKQA2xjGS", "title": "Con La Brisa", "match": "90"},{"id": "4VnDmjYCZkyeqeb0NIKqdA", "title": "Can You Hear The Music", "match": "40"},{"id": "7sXDYdXmR2PnafjkpfdCYv", "title": "Experience", "match": "90"},{"id": "1qpGMJi0ippCaMUOs7cz2q", "title": "Let You Down", "match": "55"},{"id": "4ExVFhrJqFqgKSUAqDM5AZ", "title": "Summer of Farewells - From Up On Poppy Hill (Vocals by Aoi Teshima)","match": "95"},{"id": "1tNI51sYVgEkEKC3r7skcn", "title": "Спи", "match": "90"},{"id": "28cnXtME493VX9NOw9cIUh", "title": "Hurt", "match": "40"},{"id": "0IMJjZtStHUsUz26Ymlcj2", "title": "Guns for Hire (From the series Arcane League of Legends)", "match": "30"},{"id": "6k41naacsmD4L3i9AzCFom", "title": "Now We Are Free", "match": "80"},{"id": "4c7AiatyOtwNmeUuKswBkY", "title": "White Sparrows", "match": "20"},{"id": "47sP9utcdOeL1zD6mEeFiU", "title": "I Love You - Acoustic", "match": "75"},{"id": "7w5AOd6HrDIHewHfpABEss", "title": "Wicked Game", "match": "85"},{"id": "4a4UrMYz1oLrdF1CzLcsGZ", "title": "Ascend", "match": "65"},{"id": "5HNCy40Ni5BZJFw1TKzRsC", "title": "Comfortably Numb", "match": "75"}]'
    iaDecisions = json.loads(iaDecisions)

    selected_songs_ids = get_matching_songs_ids(tracks_info, iaDecisions)
    createPlaylist = create_user_playlist(playlistName, playlistPrompt, selected_songs_ids)
    
    execution_time = f"{round(time.time() - start_time, 2)}s"

    return {'message': 'Playlist created successfully', 'execution_time': execution_time, 'checked_songs': len(tracks_info), 'playlist_id': createPlaylist, "songs_acceptance": iaDecisions}
    
if __name__ == '__main__':
    app.run(debug=True)
