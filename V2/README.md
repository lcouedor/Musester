# Structure du fichier de configuration JSON des playlists

[
    {
        "name": "playlist_name",
        "filters": {
            genre,
            criterias: ['criteria1', 'criteria2', ...]
        }
    }
]
## Filtres disponibles

### `genre` => champ optionnel
- `include` => champ optionnel : Si au moins l'un des artistes de la musique possède au moins l'un des genres donné, on passe au reste des vérifications
- `exclude` => champ optionnel : Si au moins l'un des artistes de la musique possède au moins l'un des genres donné, on skip la musique

### `valence`
A measure from 0.0 to 1.0 describing the musical positiveness conveyed by a track

### `danceability`
Danceability describes how suitable a track is for dancing
  
### `energy`
Energy is a measure from 0.0 to 1.0 and represents a perceptual measure of intensity and activity

### `acousticness`
A confidence measure from 0.0 to 1.0 of whether the track is acoustic

### `instrumentalness`
Predicts whether a track contains no vocals. "Ooh" and "aah" sounds are treated as instrumental in this context. Rap or spoken word tracks are clearly "vocal"

### `speechiness`
Speechiness detects the presence of spoken words in a track. The more exclusively speech-like the recording

### `tempo`
The overall estimated tempo of a track in beats per minute (BPM)

Chaque champ peut se suivre du symbole "+" ou "-" selon la tendance que l'on veut obtenir (ex: pour une playlist "chill" on veut plutôt une énergie faible -> on ajoute donc le filtre "energy -" aux critères, cela abaissera la limite basse qui ne sera pas calculée par rapport aux autres musiques de la playlist)

Pour chacun des critères spécifiés, des moyennes sont calculées, et des seuils à la hausse et à la baisse sont définis (selon un pourcentage d'écart)
(C'est ces seuils qui sont modifiées selon la présence de "+" et "-" après les critères)

La non conformité d'un critère n'est pas éliminatoire, mais fait baisser une note globale
Une note trop faible entraine la non-conformité de la musique à rejoindre une playlist donnée

Pour les genres des artistes, s'il y a plusieurs artistes sur une musique, et qu'au moins 2 mots clés sont présents en double au minimum, ces mots clés dupliqués sont les genres de la musique. S'il n'y a qu'un seul artistes, les genres sont tous les mots clés des genres (les mots clés sont l'ensemble des genres splités, ex : le genre "rap rock" entraine les genres "rap" et "rock", ou encore le genre "hard metal", entraine les genres "hard" et "metal")
Si un genre présent dans la configuration est présent dans les genres de l'artiste, c'est un match (dont l'effet dépend si le match est dans un genre include ou exclude)



# Structure du fichier cred.py
Le fichier `cred.py` donne les informations de credentials pour utiliser l'API de spotify, et l'ID de la playlist source
Il doit contenir quatre variables : 
- `client_ID`
- `client_SECRET`
- `redirect_url`
- `playlist_id`
- `username`

Pour les 2 premières valeurs, créer un projet sur le site développeur Spotify : `https://developer.spotify.com/`
Pour la dernière, il faut ajouter un user dans 'User Management' sur la page du projet dans le dashboard de l'API spotify