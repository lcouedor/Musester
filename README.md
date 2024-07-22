# Objectif du projet
Répartir les musiques d'une playlist spotify "source" dans d'autres playlists en fonction de divers attributs (genres des artistes, valence, energy) d'en le but d'en déduire un mood et un genre d'écoute

## V1
Version initiale, incluant la suppression automatique dans les playlists enfants les musiques qui ne sont plus dans la source
La définition des bornes des critères est manuelles
La non conformité à un critère est éliminatoire
Permet de partir de 0 afin de créer l'ensemble des playlists souhaitée

## V2
Version n'incluant pas la suppression automatique dans les playlists enfants des musiques absentes de la playlist source, le filtre par date de sortie, et la date d'ajout à la playlist
Version plus précise nécessitant cependant la création des playlists manuellement sur spotify ainsi qu'un échantillonnage préalable (au moins 5 titres dans une playlist pour qu'elle puisse être échantillonnée)
Une moyenne pour chaque critère d'importance (renseigné dans la configuration) est établie.
Version plus flexible car la non conformité à un seul critère n'entraine pas nécessairement la non conformité à la playlist (plus précise par la même occasion, permettant d'ajuster sur les cas d'erreurs de valeurs récupérées par l'API Spotify).
Vérification des critères et des genres distincte. Chacun est flexible à son niveau, mais les deux doivent être validés pour valider l'ajout d'une musique à une playlist.
