from services.spotify_api import get_spotify_client, get_playlist_tracks
from pprint import pprint

import requests
import re
import time

sourceUrl = 'https://tunebat.com/Info/'


playlist_id : str = '428dGuHpO7uB98groy1YhD'


def getTrackName(input_string):
    newString = re.sub(r'[^a-z]', '-', input_string.lower())
    #Si il y a 2 tirets consécutifs, on les remplace par un seul tiret
    newString = re.sub(r'-{2,}', '-', newString)
    #Si le dernier caractère est un tiret, on le supprime
    return newString[:-1] if newString[-1] == '-' else newString

def getArtistName(artists : list):
    #Retourner en une seule string les noms des artistes séparés par un tiret
    artistNames = ''
    for artist in artists:
        artistNames += artist['name'] + '-'
    return getTrackName(artistNames[:-1])

def main():
    # ---------- AUTHENTIFICATION ----------
    # Création de l'objet SpotifyOAuth pour obtenir les informations d'identification de l'utilisateur
    spotify = get_spotify_client()

    # ---------- RÉCUPÉRATION DES CARACTÉ DE LA PLAYLIST ----------
    playlist_tracks = get_playlist_tracks(spotify, playlist_id)

    trackId = playlist_tracks[0]['track']['id']
    trackName = playlist_tracks[0]['track']['name']
    formattedTrackName = getTrackName(trackName)
    formattedArtistName = getArtistName(playlist_tracks[0]['track']['artists'])

    urlFinal = sourceUrl + formattedTrackName + '-' + formattedArtistName + '/' + trackId


    #Je scrappe la page pour récupérer les informations
    # response = requests.get(urlFinal)

    # #Je récupère le code source de la page
    # sourceCode = response.text
    # print(sourceCode)

    #q: il semblerait que j'ai été bloqué en faisant la requête depuis python, comment faire ? (je ne suis pas bloqué en faisant la requête depuis mon navigateur)
    #a: il faut que je rajoute un header à ma requête pour simuler une requête depuis un navigateur
    #q: comment rajouter un header à ma requête ?
    #a: il faut que je rajoute un dictionnaire en paramètre de la méthode get() de requests
    #q: que dois-je mettre dans ce dictionnaire ?

    #La requête correcte :
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    #Il y a un léger temps de chargement dans la page pour avoir les infos que je veux, comment ne pas récupérer le code source trop tôt ?
    #Je peux utiliser la méthode sleep() du module time pour attendre un certain temps avant de récupérer le code source
    # Attendre 5 secondes avant de récupérer le code source
    time.sleep(5)
    response = requests.get(urlFinal, headers=headers)
    sourceCode = response.text
    print(sourceCode)




    

    # print(urlFinal)

if __name__ == '__main__':
    main()