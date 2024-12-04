from flask import Blueprint, jsonify, request
from services_bdd import getAllSongsService, patchSongService, getSongsByTagsService, getAllTagsService, addTagService
from services_spotify import syncService, createThemePlaylist
from supabase import create_client, Client
from cred import url, key
from config import sourcePlaylistId

supabase: Client = create_client(url, key)

routes = Blueprint('routes', __name__)

#------------Routes------------
#Home route
@routes.route('/')
def home():
    return "Hello world"

#Get all songs
@routes.route('/songs', methods=['GET'])
def getAllSongs():
    return jsonify(getAllSongsService())

#Get all tags
@routes.route('/tags', methods=['GET'])
def getAllTags():
    return jsonify(getAllTagsService())

#Patch a song
@routes.route('/songs/<id>', methods=['PATCH'])
def patchSong(id):
    song = request.json
    return jsonify(patchSongService(id, song))

#Add a tag
@routes.route('/tags/<name>', methods=['POST'])
def addTag(name):
    return jsonify(addTagService(name))

#Get songs with matching tags
@routes.route('/filtered_songs', methods=['GET'])
def createPlaylistBySongsTags():
    result = getSongsByTagsService(request)
    createThemePlaylist(result, request.json['playlist_name'])
    return jsonify(result)

#Synchronize the database with the Spotify source playlist
@routes.route('/sync', methods=['GET'])
def sync():
    return jsonify(syncService(sourcePlaylistId))