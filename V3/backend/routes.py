from flask import Blueprint, jsonify, request
from services_bdd import getAllSongsService, patchSongService, getSongsByTagsService, getAllTagsService, addTagService, searchSongsByFilters
from services_spotify import syncService, createThemePlaylist
from services_chatgpt import getTagListForPrompt
from functools import wraps

import asyncio

from pprint import pprint

from utils import getSecret
from dotenv import load_dotenv
load_dotenv()

routes = Blueprint('routes', __name__)

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.headers.get('Authorization') != getSecret('MDP'):
            return jsonify({'message': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated
#------------Routes------------
#Home route
@routes.route('/')
@requires_auth
def home():
    return "Hello world"

#Get all songs
@routes.route('/songs/<page>', methods=['GET'])
@requires_auth
def getAllSongs(page):
    return jsonify(getAllSongsService(page))

#Get songs by filters
@routes.route('/filteredSongs', methods=['GET'])
@requires_auth
def getSongsByFilters():
    name = ''
    artist = ''
    tags = []

    if('name' in request.json):
        name = request.json['name']

    if('artists' in request.json):
        artist = request.json['artists']

    if('tags' in request.json):
        tags = request.json['tags']
    return jsonify(searchSongsByFilters(name, artist, tags))

#Get all tags
@routes.route('/tags', methods=['GET'])
@requires_auth
def getAllTags():
    return jsonify(getAllTagsService())

#Patch a song
@routes.route('/songs/<id>', methods=['PATCH'])
@requires_auth
def patchSong(id):
    song = request.json
    return jsonify(patchSongService(id, song))

#Add a tag
@routes.route('/tags/<name>', methods=['POST'])
@requires_auth
def addTag(name):
    return jsonify(addTagService(name))

#Get songs with matching tags
@routes.route('/songsByTags', methods=['GET'])
@requires_auth
def createPlaylistBySongsTags():
    result = getSongsByTagsService(request)
    return jsonify(result)

#Synchronize the database with the Spotify source playlist
@routes.route('/sync', methods=['GET'])
@requires_auth
def sync():
    playlistId = request.json['playlist_id']
    try:
        playlistId = playlistId.split('playlist/')[1].split('?')[0]
    except:
        return jsonify({'message': 'Invalid playlist id format'})
    return jsonify(asyncio.run(syncService(playlistId)))

@routes.route('/getProposalPlaylist', methods=['GET'])
@requires_auth
def getPlaylistProposalTags():
    prompt = request.json['prompt']
    playlist_name = request.json['playlist_name']
    tags = getTagListForPrompt(prompt)

    including_tags = tags.split('|')[0].split(',')
    excluding_tags = tags.split('|')[1].split(',')
    or_tags = tags.split('|')[2].split(',')

    #Pour chaque tag je retire les espaces
    including_tags = [tag.strip() for tag in including_tags]
    excluding_tags = [tag.strip() for tag in excluding_tags]
    or_tags = [tag.strip() for tag in or_tags]

    tagList = {
        'playlist_name': playlist_name,
        'including_tags': including_tags,
        'excluding_tags': excluding_tags,
        'or_tags': or_tags
    }

    songs = getSongsByTagsService(tagList, False)

    return jsonify(tagList)

@routes.route('/createPlaylistPrompt', methods=['GET'])
@requires_auth
def createPlaylistPrompt():
    #Me génère une playlist à partir des tags passés en paramètre
    #Je récupère les tags
    including_tags = request.json['including_tags']
    excluding_tags = request.json['excluding_tags']
    or_tags = request.json['or_tags']
    playlist_name = request.json['playlist_name']

    tagList = {
        'playlist_name': playlist_name,
        'including_tags': including_tags,
        'excluding_tags': excluding_tags,
        'or_tags': or_tags
    }

    songs = getSongsByTagsService(tagList, False)

    return jsonify(createThemePlaylist(songs, playlist_name))