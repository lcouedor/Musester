from flask import jsonify, request
from supabase import create_client, Client
from utils import getSecret
from dotenv import load_dotenv
import time
from pprint import pprint

import time

load_dotenv()

supabase: Client = create_client(getSecret('SUPABASE_URL'), getSecret('SUPABASE_KEY'))

def getTotalSongsCount():
    response = supabase.table("songs").select("id", count="exact").execute()
    return response.count  # Renvoie le nombre total de chansons

def getAllSongsService(page):
    #Je retire juste ce qu'il y a après le dernier / dans l'url
    BASE_URL = request.base_url.rsplit('/', 1)[0]
    # Convertir la page en entier
    try:
        page = int(page)
    except ValueError:
        return {"error": "Invalid page number"}, 400

    # Taille de page et indices
    page_size = 20
    #la page commence à 1 mais les indices commencent à 0
    start = (page-1) * page_size
    end = start + page_size

    # Récupérer les chansons
    response = supabase.table("songs").select("*").range(start, end - 1).execute()
    
    # Récupérer le nombre total de chansons
    total_count = getTotalSongsCount()
    total_pages = (total_count + page_size - 1) // page_size  # Arrondi vers le haut

    if(page > total_pages or page < 1):
        return {"error": "Page number out of range"}, 400

    # Remplacer les tag_ids par tag_names
    for song in response.data:
        tag_names = []
        song['tag_names'] = getTagNamesByIds(song['tag_ids'])
        del song['tag_ids']

    # Construire la réponse
    result = {
        "songs": response.data,
        "total_pages": total_pages,
        "current_page": page,
        "next_page_url": f"{BASE_URL}/{page + 1}" if page < total_pages else None
    }
    return result

def searchSongsByFilters(name='', artists='', tags=[]):
    # On crée une requête de base
    query = supabase.table('songs').select("*")

    # Ajouter les filtres un par un
    if name:
        query = query.ilike("song_name", f"%{name}%")  # Recherche insensible à la casse pour le nom
    if artists:
        query = query.ilike("song_artists", f"%{artists}%")  # Recherche insensible à la casse pour les artistes
    if tags:
        # On récupère les ids des tags à partir de leurs noms
        tags_id = []
        for tag in tags:
            tag_id_response = getTagIdByName(tag).json
            if 'error' not in tag_id_response:
                tags_id.append(tag_id_response['tag_id'])
        
        # Conversion des ids en chaîne de caractères
        tags_id = [str(tag_id) for tag_id in tags_id]
        
        # Application du filtre sur les tags
        query = query.cs("tag_ids", tags_id)  # Vérifie si tag_ids contient les tags_id spécifiés

    # Exécution de la requête
    response = query.execute()

    #Pour chaque chanson, je remplace les tag_ids par les tag_names
    for song in response.data:
        tag_names = []
        song['tag_names'] = getTagNamesByIds(song['tag_ids'])
        del song['tag_ids']
    return response.data

def patchSongService(id, song):
    #Je commence par récupérer la chanson
    existingSong = getSongById(id).json[0]

    #Si il y a la clé tag_names, je la remplace par tag_ids
    if 'tag_names' in song:
        tag_names = song['tag_names']
        tags_id = []
        for tag_name in tag_names:
            tag_id = getTagIdByName(tag_name).json
            if 'error' in tag_id:
                continue
            tags_id.append(tag_id['tag_id'])
        song['tag_ids'] = tags_id
        del song['tag_names']

    #Je modifie les champs de la chanson en fonction de ce qui a été envoyé
    for key in song:
        existingSong[key] = song[key]

    #Je mets à jour la chanson
    response = supabase.table("songs").update([existingSong]).eq("id", id).execute()
    return response.data

def getSongsByTagsService(request, type_request=True):
    if type_request:
        including_tags = request.json.get('including_tags')  # Tous les tags doivent être présents
        excluding_tags = request.json.get('excluding_tags')  # Aucun des tags ne doit être présent
        or_tags = request.json.get('or_tags')  # Au moins un des tags doit être présent
    else:
        including_tags = request['including_tags']  # Tous les tags doivent être présents
        excluding_tags = request['excluding_tags']  # Aucun des tags ne doit être présent
        or_tags = request['or_tags']  # Au moins un des tags doit être présent

    # Récupérer les id des tags
    including_tags_id, excluding_tags_id, or_tags_id = getAllTagsId(including_tags, excluding_tags, or_tags)

    songsIncluded = []
    songsOr = []
    songsExcluded = []
    finalSongs = []
    query = supabase.table("songs").select("*")

    if including_tags_id:
        query = supabase.table("songs").select("*").filter("tag_ids", "cs", f"{{{' ,'.join(map(str, including_tags_id))}}}")
        response = query.execute()
        songsIncluded = response.data

    #Je rajoute les chansons qui ont un des tags de or_tags
    if or_tags_id:
        for tag_id in or_tags_id:
            query = supabase.table("songs").select("*").filter("tag_ids", "cs", f"{{{tag_id}}}")
            response = query.execute()
            songsOr += response.data

    #Je fais un tableau des musiques exclues
    if excluding_tags_id:
        query = supabase.table("songs").select("*").filter("tag_ids", "cs", f"{{{' ,'.join(map(str, excluding_tags_id))}}}")
        response = query.execute()
        songsExcluded = response.data

    if not songsOr: 
        songsOr = songsIncluded

    for song in songsIncluded:
        if song in songsOr and song not in songsExcluded:
            if not song in finalSongs:
                finalSongs.append(song)
    if not songsIncluded:
        for song in songsOr:
            if song not in songsExcluded and song not in finalSongs:
                finalSongs.append(song)


    return finalSongs

def getAllTagsService():
    response = supabase.table("tags").select("*").execute()
    return response.data

def addTagService(name):
    tag = {"tag_name": name.lower()}
    response = supabase.table("tags").insert([tag]).execute()
    return response.data

#Get a song by its id
def getSongById(id):
    response = supabase.table("songs").select("*").eq("id", id).execute()
    return jsonify(response.data)

#Add a song
def addSong(song):
    response = supabase.table("songs").insert([song]).execute()
    return response.data

def addSongsBatch(songs):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = supabase.table("songs").insert(songs).execute()
            break
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)  # Attendre 1 seconde avant de réessayer
                continue
            else:
                raise e
    return response.data

def removeSong(id):
    response = supabase.table("songs").delete().eq("id", id).execute()
    return jsonify(response.data)

#Get a tag id by its name
def getTagIdByName(name):
    response = supabase.table("tags").select("*").eq("tag_name", name).execute()

    if len(response.data) == 0:
        return jsonify({"error": "Tag not found"})

    return jsonify({"tag_id": response.data[0]['id']})

def getTagNamesByIds(ids):
    #Je récupère tous les noms des tags de manière optimisée
    response = supabase.table("tags").select("tag_name").in_("id", ids).execute()
    return [tag['tag_name'] for tag in response.data]

#Get all tags names
def getAllTagsNames():
    tags = supabase.table("tags").select("*").execute()
    tagNames = []
    for tag in tags.data:
        tagNames.append(tag['tag_name'])
    return tagNames

#Récupérer les id des tags à partir de leur nom (s'ils existent)
def getAllTagsId(including_tags, excluding_tags, or_tags):
    # Je récupère les id des tags
    including_tags_id = []
    excluding_tags_id = []
    or_tags_id = []

    if including_tags:
        for tag in including_tags:
            tag_id = getTagIdByName(tag).json
            if 'error' in tag_id:
                continue
            including_tags_id.append(tag_id['tag_id'])

    if excluding_tags:
        for tag in excluding_tags:
            tag_id = getTagIdByName(tag).json
            if 'error' in tag_id:
                continue
            excluding_tags_id.append(tag_id['tag_id'])

    if or_tags:
        for tag in or_tags:
            tag_id = getTagIdByName(tag).json
            if 'error' in tag_id:
                continue
            or_tags_id.append(tag_id['tag_id'])

    # Si je n'ai qu'un seul tag dans or_tags, je le mets dans including_tags
    if len(or_tags_id) == 1:
        including_tags_id.append(or_tags_id[0])
        or_tags_id = []

    return including_tags_id, excluding_tags_id, or_tags_id

def isPlaylistSongInDb(spotify_id):
    response = supabase.table("songs").select("*").filter("song_spotify_id", "eq", spotify_id).execute()
    return len(response.data) > 0

def getTagIdByNameForSpotify(name):
    response = supabase.table("tags").select("*").eq("tag_name", name).execute()

    if len(response.data) == 0:
        return {"error": "Tag not found"}

    return {"tag_id": response.data[0]['id']}

def get_or_create_tag(tag_name):
    try:
        # Insère le tag
        response = supabase.table("tags").insert({"tag_name": tag_name.lower()}).execute()

        # Retourne l'ID si l'insertion réussit
        return response.data[0]["id"]
    except Exception as e:
        # Si une erreur survient (comme une violation d'unicité), récupère l'ID existant
        response = supabase.table("tags").select("*").eq("tag_name", tag_name.lower()).execute()
        if response.data:
            return response.data[0]["id"]
        else:
            raise Exception("Unexpected error while handling tags")