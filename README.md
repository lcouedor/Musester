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

- **Back** — Python / Flask, Spotipy, OpenAI SDK, gunicorn
- **Front** — HTML/CSS/JS vanilla, servi par Flask
- **Auth** — OAuth2 Spotify, sessions Flask
- **BDD** — SQLite en dev, PostgreSQL (Supabase) en prod

---

## Structure

```
musester/
├── api/
│   ├── app.py                  # Entry point Flask
│   ├── routes.py               # Endpoints
│   ├── config.py               # Variables et constantes
│   ├── db.py                   # Abstraction SQLite / PostgreSQL
│   ├── core/
│   │   ├── models.py           # Dataclasses Track, Decision
│   │   └── playlist.py         # Logique métier
│   ├── services/
│   │   ├── auth.py             # OAuth Spotify + gestion tokens/historique
│   │   ├── spotify.py          # Wrapper Spotipy
│   │   └── classifier.py       # Wrapper OpenAI
│   ├── tokens.db               # Base SQLite dev (gitignorée)
│   ├── history.db              # Historique SQLite dev (gitignorée)
│   ├── decisions.log           # Log des décisions GPT (gitignorée)
│   └── requirements.txt
├── web/
│   └── index.html              # Front
├── requirements.txt            # Délègue à api/requirements.txt (pour Render)
├── Procfile                    # Commande gunicorn pour Render
└── render.yaml                 # Config déploiement Render
```

---

## Dev local

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

Crée un fichier `.env` dans `api/` (voir `api/.env.example`) :

```env
SPOTIFY_ID=ton_client_id
SPOTIFY_SECRET=ton_client_secret
SPOTIFY_REDIRECT=http://127.0.0.1:5001/auth/callback
SPOTIFY_USERNAME=ton_username_spotify
GPT_KEY=ta_cle_openai
SECRET_KEY=une_chaine_aleatoire_longue
FRONTEND_URL=http://127.0.0.1:5001

# Laisser vide en dev = SQLite local
DATABASE_URL=

# Laisser vide en dev = tout le monde autorisé
ALLOWED_USERS=
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

### 4. Lancer

```bash
cd api
myenv/bin/python app.py
```

Puis ouvre [http://127.0.0.1:5001](http://127.0.0.1:5001)

---

## Déploiement (Render + Supabase)

### Base de données Supabase

1. Crée un projet sur [supabase.com](https://supabase.com)
2. Applique le schéma initial (tables `tokens`, `history`, `playlist_prompts`) via **SQL Editor** ou les migrations
3. Récupère la **connection string Transaction pooler** : Settings → Database → Transaction pooler
   ```
   postgresql://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres
   ```

### Render

1. Crée un **Web Service** sur [render.com](https://render.com), connecte le repo GitHub — Render détecte le `render.yaml` automatiquement
2. Configure les variables d'environnement :

| Variable | Valeur |
|---|---|
| `SPOTIFY_ID` | Client ID de ton app Spotify |
| `SPOTIFY_SECRET` | Client Secret de ton app Spotify |
| `SPOTIFY_USERNAME` | Ton username Spotify |
| `SPOTIFY_REDIRECT` | `https://TON-APP.onrender.com/auth/callback` |
| `GPT_KEY` | Clé API OpenAI |
| `FRONTEND_URL` | `https://TON-APP.onrender.com` |
| `DATABASE_URL` | Connection string Supabase (Transaction pooler) |
| `ALLOWED_USERS` | Spotify user IDs autorisés, séparés par des virgules |
| `SECRET_KEY` | Généré automatiquement par Render |

3. Ajoute l'URI de callback dans le dashboard Spotify Developer :
   ```
   https://TON-APP.onrender.com/auth/callback
   ```

### Whitelist (`ALLOWED_USERS`)

Pour restreindre l'accès à certains comptes Spotify, liste leurs IDs séparés par des virgules :
```
ALLOWED_USERS=id_user1,id_user2
```

Ton Spotify user ID se trouve dans l'URL de ton profil sur [open.spotify.com](https://open.spotify.com/user/) ou dans les logs Render après une première connexion.

Laisser vide = tout le monde peut se connecter (déconseillé en prod, ça consomme tes crédits OpenAI).

### Base de données

En local (`DATABASE_URL` vide) → SQLite (`tokens.db` + `history.db` dans `api/`)
En prod (`DATABASE_URL` défini) → PostgreSQL Supabase, les fichiers SQLite sont ignorés

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
Crée une ou plusieurs playlists à partir de prompts.

**Body**
```json
{
  "source_id": "https://open.spotify.com/playlist/XXX",
  "multi_pass": true,
  "playlists": [
    { "name": "Chill Soir", "prompt": "Musiques calmes pour la fin de soirée", "anchors": [] },
    { "name": "Focus", "prompt": "Sans paroles, pour travailler", "anchors": [] }
  ]
}
```
`source_id` accepte une URL complète, un ID brut, ou `"liked"` pour les titres likés. Maximum 3 playlists par appel.

**Réponse** (SSE)
Stream d'événements `progress` / `status` / `done`.

---

### `POST /sync`
Met à jour les playlists `IA-` : ajoute les nouveaux morceaux, supprime ceux retirés de la source (mode destructif) ou ajoute seulement (mode additif).

**Body**
```json
{
  "source_id": "https://open.spotify.com/playlist/XXX",
  "destructive": true,
  "target_playlist_ids": ["id1", "id2"]
}
```
`target_playlist_ids` est optionnel — si absent, toutes les playlists `IA-` sont synchronisées.

---

### `GET /source-tracks`
Retourne les morceaux d'une playlist source (utilisé pour le sélecteur d'anchors).

### `GET /playlists`
Retourne les playlists `IA-` de l'utilisateur avec leur prompt et date de dernier sync.

### `GET /history`
Retourne l'historique des générations et synchronisations.

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

- `decisions.log` est écrasé à chaque `/generate` — détail des décisions GPT (inclus/exclu + justification)
- Le `/sync` se base sur la date du dernier morceau ajouté pour ne traiter que les nouveaux morceaux
- En mode sync additif, la description de la playlist est mise à jour avec la date et la source utilisée
- `tokens.db`, `history.db` et `.env` sont gitignorés — ne jamais les committer
