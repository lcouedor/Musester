# Structure du fichier de configuration JSON des playlists

[
    {
        "name": "playlist_name",
        "filters": {
            filter1,
            filter2,
            ...
        }
    }
]
## Filtres disponibles

### `genre`
- `include`: Si au moins l'un des artistes de la musique possède au moins l'un des genres donné, on passe au reste des vérifications
- `exclude`: Si au moins l'un des artistes de la musique possède au moins l'un des genres donné, on skip la musique

### `artists`
- `include`: Artistes à ajouter, indépendamment de leurs genres (la musique by-pass la vérification de genre, mais pas des autres caractéristiques)
- `exclude`: Artistes à exclure totalement de la playlist
- Les noms d'artistes doivent être orthographiés exactement comme sur spotify (Respectant également les majuscules)

### `valence`
- `min`: Valeur minimale (0.0 à 1.0).
- `max`: Valeur maximale (0.0 à 1.0).

### `danceability`
- `min`: Valeur minimale (0.0 à 1.0).
- `max`: Valeur maximale (0.0 à 1.0).
  
### `energy`
- `min`: Valeur minimale (0.0 à 1.0).
- `max`: Valeur maximale (0.0 à 1.0).

### `acousticness`
- `min`: Valeur minimale (0.0 à 1.0).
- `max`: Valeur maximale (0.0 à 1.0).

### `instrumentalness`
- `min`: Valeur minimale (0.0 à 1.0).
- `max`: Valeur maximale (0.0 à 1.0).

### `speechiness`
- `min`: Valeur minimale (0.0 à 1.0).
- `max`: Valeur maximale (0.0 à 1.0).

### `tempo`
- `min`
- `max`

### `releaseDate`
- `min`: Année minimale de sortie (par exemple, "2010").
- `max`: Année maximale de sortie 
- (ou "-" pour aucune limite dans min ou dans max)

### `likedDate`
- Durée relative depuis quand la chanson a été ajoutée à la playlist source (nombre days|months|years) -> ex : 2 days OU 2 months OU 2 years
  
### `mode`
- `majeur` ou `mineur`

Pour les filtres ayant un min/max, ces deux attributs sont obligatoires


# Structure du fichier cred.py
Le fichier `cred.py` donne les informations de credentials pour utiliser l'API de spotify, et l'ID de la playlist source
Il doit contenir quatre variables : 
- `client_ID`
- `client_SECRET`
- `redirect_url`
- `playlist_id`

Pour les 2 premières valeurs, créer un projet sur le site développeur Spotify : `https://developer.spotify.com/`