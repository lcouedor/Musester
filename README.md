# Musester (Music sorter)

# Objectif du projet
Répartir les musiques d'une playlist spotify "source" dans d'autres playlists en fonction de leur mood d'écoute.

# Fonctionnement
La description est envoyée à l'API chatGPT  avec la liste des musiques de la playlist source. Il est demandé à l'IA de retourner pour chaque musique un taux de correspondance entre la musique et la description souhaitée.

# Endpoints
- GET "/generate" pour lancer le tri automatique.
Paramètres : 
    - playlist_id -> l'id de la playlist source
    - playlist_name -> le nom à donner à la nouvelle playlist créée automatiquement
    - playlist_prompt -> la description donnée à la playlist, détermine l'affectation des musiques
    - treshold_match_percentage -> seuil d'acceptation d'une musique, explication ci-dessous

- DELETE "/sync" pour supprimer de playlists de destination toutes les musiques qui ne sont plus dans la source.
Paramètres :
  - source_id -> l'id de la playlist source
  - targets_ids -> tableau d'ids de playlists de destination

# Utilisation
- Activer l'environnement virtuel :
  - >source myenv/bin/activate
- Lancer l'API :
  - >./myenv/bin/python backend/app.py
- Requêter l'endpoint de génération
- Le programme traitera les musiques par batch de 20 et créera automatiquement la playlist souhaitée avec les musiques adaptées issues de la playlist source

# Déploiement
-- Work in progress --
> vercel --cwd backend to update prod
