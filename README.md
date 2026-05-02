# Musester

Trie automatiquement les morceaux d'une playlist Spotify source dans de nouvelles playlists, en fonction d'un prompt décrivant une ambiance ou un contexte d'écoute. 
La classification est assurée par GPT-4.1.

---

## Comment ça marche

1. Tu donnes une playlist source (ou tes titres likés) et un prompt ("musiques calmes pour travailler la nuit")
2. GPT analyse chaque morceau et décide s'il correspond au contexte
3. Une nouvelle playlist préfixée `IA-` est créée dans ton Spotify avec les morceaux retenus
4. La synchronisation maintient les playlists à jour : nouveaux morceaux ajoutés, morceaux supprimés de la source retirés

---

## Stack

- **Back** — Python / Flask, Spotipy, OpenAI SDK
- **Front** — HTML/CSS/JS vanilla, servi par Flask
- **Auth** — OAuth2 Spotify, sessions Flask, SQLite pour les tokens

---

## Structure

```
musester/
├── api/
│   ├── app.py                  # Entry point Flask
│   ├── routes.py               # Endpoints
│   ├── config.py               # Variables et constantes
│   ├── core/
│   │   ├── models.py           # Dataclasses Track, Decision
│   │   └── playlist.py         # Logique métier
│   ├── services/
│   │   ├── auth.py             # OAuth Spotify + gestion tokens
│   │   ├── spotify.py          # Wrapper Spotipy
│   │   └── classifier.py       # Wrapper OpenAI
│   ├── tokens.db               # Base SQLite (gitignorée)
│   ├── decisions.log           # Log des décisions GPT (écrasé à chaque generate, gitignoré également)
│   └── requirements.txt
├── web/
│   └── index.html              # Front
└── start.sh                    # Script de lancement
```

---

## Installation

### Prérequis
- Python 3.10+
- Un compte [Spotify Developer](https://developer.spotify.com/dashboard) avec une app créée
- Une clé API OpenAI

### 1. Cloner et créer l'environnement virtuel

```bash
git clone https://github.com/ton-user/musester.git
cd musester/api
python3 -m venv myenv
myenv/bin/pip install -r requirements.txt
```

### 2. Variables d'environnement

Crée un fichier `.env` dans `api/` :

```env
SPOTIFY_ID=ton_client_id
SPOTIFY_SECRET=ton_client_secret
SPOTIFY_REDIRECT=http://127.0.0.1:5001/auth/callback
SPOTIFY_USERNAME=ton_username_spotify
GPT_KEY=ta_cle_openai
SECRET_KEY=une_chaine_aleatoire_longue
FRONTEND_URL=http://127.0.0.1:5001
```

Pour générer une `SECRET_KEY` :
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Dashboard Spotify

Dans ton app Spotify Developer → **Edit** → **Redirect URIs**, ajoute :
```
http://127.0.0.1:5001/auth/callback
```

Pour autoriser des proches à utiliser l'app (mode development, max 25 users) :
Dashboard → **User Management** → ajoute leur email Spotify.

---

## Lancer le projet

```bash
./start.sh
```

Puis ouvre [http://127.0.0.1:5001](http://127.0.0.1:5001)

---

## Endpoints

### `GET /auth/login`
Redirige vers la page d'autorisation Spotify.

### `GET /auth/callback`
Callback OAuth. Appelé automatiquement par Spotify après autorisation.

### `GET /auth/me`
Retourne l'utilisateur connecté.
```json
{ "error": null, "data": { "user_id": "..." } }
```

### `GET /auth/logout`
Supprime la session.

---

### `POST /generate`
Crée une nouvelle playlist à partir d'un prompt.

**Body**
```json
{
  "source_id": "https://open.spotify.com/playlist/XXX",
  "playlist_name": "Chill Soir",
  "playlist_prompt": "Musiques calmes et introspectives pour la fin de soirée"
}
```
`source_id` accepte une URL complète, un ID brut, ou `"liked"` pour les titres likés.

**Réponse**
```json
{
  "error": null,
  "execution_time": "18.4s",
  "data": {
    "playlist_id": "...",
    "checked_songs": 312,
    "selected_songs": 47,
    "decisions": [...]
  }
}
```

---

### `POST /sync`
Met à jour toutes les playlists `IA-` : ajoute les nouveaux morceaux de la source correspondant au prompt, supprime ceux qui ne sont plus dans la source.

**Body**
```json
{
  "source_id": "https://open.spotify.com/playlist/XXX"
}
```

**Réponse**
```json
{
  "error": null,
  "execution_time": "24.1s",
  "data": {
    "playlist_id_1": { "name": "IA-Chill Soir", "removed": 2, "added": 5, "checked": 12 },
    "playlist_id_2": { "name": "IA-Workout",    "removed": 0, "added": 3, "checked": 8  }
  }
}
```

---

## Configuration

Paramètres ajustables dans `api/config.py` :

| Variable | Valeur par défaut | Description |
|---|---|---|
| `BATCH_SIZE` | `60` | Morceaux envoyés par requête GPT |
| `MAX_WORKERS` | `3` | Requêtes GPT parallèles max |
| `PLAYLIST_PREFIX` | `IA-` | Préfixe des playlists générées |
| `GPT_MODEL` | `gpt-4.1` | Modèle OpenAI utilisé |

---

## Notes

- Le fichier `decisions.log` est écrasé à chaque `/generate` — il contient le détail des décisions GPT (morceau inclus/exclu + justification)
- Le `/sync` se base sur la date du dernier morceau ajouté à chaque playlist `IA-` pour ne traiter que les nouveaux morceaux de la source
- `tokens.db` et `.env` sont gitignorés — ne jamais les committer
