from flask import Flask, jsonify, request
from flask_cors import CORS
from supabase import create_client, Client

url: str = "https://vgyccwnlwsooyrdsswdz.supabase.co"
key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZneWNjd25sd3Nvb3lyZHNzd2R6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzMzMDY0ODgsImV4cCI6MjA0ODg4MjQ4OH0.j62OsNKJmP70tRB1PeLdYhvJ-x2mxu5szLShDt35fhk"
supabase: Client = create_client(url, key)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://musester.onrender.com"}})

# Routes
@app.route('/')
def home():
    return "Hello world"

#------------Routes songs------------
#Get all songs
@app.route('/songs', methods=['GET'])
def getAllSongs():
    response = supabase.table("songs").select("*").execute()
    return jsonify(response.data)

#Add a song
# @app.route('/songs', methods=['POST'])
# def addSong():
#     song = request.json
#     response = supabase.table("songs").insert([song]).execute()
#     return jsonify(response.data)
#------------Routes tags------------
#Get all tags
@app.route('/tags', methods=['GET'])
def getAllTags():
    response = supabase.table("tags").select("*").execute()
    return jsonify(response.data)

#Get a tag id by its name
@app.route('/tags/name/<name>', methods=['GET'])
def getTagIdByName(name):
    response = supabase.table("tags").select("*").eq("tag_name", name).execute()

    if len(response.data) == 0:
        return jsonify({"error": "Tag not found"})

    return jsonify({"tag_id": response.data[0]['id']})

#------------Routes songs_tags------------
#Get songs with matching tags
@app.route('/filtered_songs', methods=['GET'])
def getSongsByTags():
    including_tags = request.args.get('including_tags')  # Tous les tags doivent être présents
    excluding_tags = request.args.get('excluding_tags')  # Aucun des tags ne doit être présent
    or_tags = request.args.get('or_tags')  # Au moins un des tags doit être présent

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


    return jsonify(finalSongs)

#------------Fonctions utilitaires------------
#Récupérer les id des tags à partir de leur nom (s'ils existent)
def getAllTagsId(including_tags, excluding_tags, or_tags):
    # Je récupère les id des tags
    including_tags_id = []
    excluding_tags_id = []
    or_tags_id = []    

    if including_tags:
        including_tags = including_tags.split(';')
        for tag in including_tags:
            tag_id = getTagIdByName(tag).json
            if 'error' in tag_id:
                continue
            including_tags_id.append(tag_id['tag_id'])

    if excluding_tags:
        excluding_tags = excluding_tags.split(';')
        for tag in excluding_tags:
            tag_id = getTagIdByName(tag).json
            if 'error' in tag_id:
                continue
            excluding_tags_id.append(tag_id['tag_id'])

    if or_tags:
        or_tags = or_tags.split(';')
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

if __name__ == '__main__':
    # app.run(host='0.0.0.0', debug=True)
    app.run(debug=False)