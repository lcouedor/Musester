from flask import Blueprint, jsonify, request
from services_bdd import getAllSongsService, patchSongService, getSongsByTagsService, getAllTagsService, addTagService, searchSongsByFilters
from services_spotify import syncService, createThemePlaylist
from services_chatgpt import getTagListForPrompt
import asyncio

from pprint import pprint

routes = Blueprint('routes', __name__)

#------------Routes------------
#Home route
@routes.route('/')
def home():
    return "Hello world"

#Get all songs
@routes.route('/songs/<page>', methods=['GET'])
def getAllSongs(page):
    return jsonify(getAllSongsService(page))

#Get songs by filters
@routes.route('/songs', methods=['GET'])
def getSongsByFilters():
    name = request.json['name']
    artist = request.json['artist']
    tags = request.json['tags']
    return jsonify(searchSongsByFilters)

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
    return jsonify(result)

#Synchronize the database with the Spotify source playlist
@routes.route('/sync', methods=['GET'])
def sync():
    playlistId = request.json['playlist_id']
    try:
        playlistId = playlistId.split('playlist/')[1].split('?')[0]
    except:
        return jsonify({'message': 'Invalid playlist id format'})
    return jsonify(asyncio.run(syncService(playlistId)))

@routes.route('/getProposalPlaylist', methods=['GET'])
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

    # return jsonify(createThemePlaylist(songs, playlist_name))
    # # return jsonify({'message': 'Playlist created'})

@routes.route('/createPlaylistPrompt', methods=['GET'])
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