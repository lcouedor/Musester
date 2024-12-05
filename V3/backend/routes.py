from flask import Blueprint, jsonify, request
from services_bdd import getAllSongsService, patchSongService, getSongsByTagsService, getAllTagsService, addTagService
from services_spotify import syncService, createThemePlaylist
from services_chatgpt import getTagListForPrompt
from config import sourcePlaylistId
import asyncio

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
    return jsonify(asyncio.run(syncService(sourcePlaylistId)))

@routes.route('/createPlaylist', methods=['GET'])
def getPlaylistProposalTags():
    prompt = request.json['prompt']
    playlist_name = request.json['playlist_name']
    tags = getTagListForPrompt(prompt)

    including_tags = tags.split('-')[0].split(',')
    excluding_tags = tags.split('-')[1].split(',')
    or_tags = tags.split('-')[2].split(',')

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

    return jsonify(tagList)

    # songs = getSongsByTagsService(tagList, False)

    # return jsonify(createThemePlaylist(songs, playlist_name))
    # # return jsonify({'message': 'Playlist created'})