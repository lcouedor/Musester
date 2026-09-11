# Musester

Trie automatiquement les morceaux d'une playlist Spotify source (ou tes titres likés) dans de nouvelles playlists, en fonction d'un prompt décrivant une ambiance ou un contexte d'écoute. La classification est assurée par GPT-4.1-mini.

---

## Comment ça marche

1. Tu donnes une playlist source (ou `liked`) et un prompt ("musiques calmes pour travailler la nuit") — optionnellement, des **ancres** : des morceaux de la source qui correspondent exactement à ce que tu veux.
2. Chaque morceau passe par un filtrage en deux temps :
   - **Passe 1 (large)** — inclusive, garde tout ce qui a une chance raisonnable de coller.
   - **Passe 2 (sélective)** — ne garde que ce qui colle vraiment, parmi les candidats de la passe 1.
   Si des ancres sont fournies, la similarité d'embedding (texte du morceau — tags Last.fm + extrait de paroles — contre le prompt et les ancres) fait office de raccourci pour les morceaux qu'elle juge clairement bons : ils sautent directement la passe 1. Tout le reste (signal faible, absent, ou sous le seuil) passe par le filtrage GPT normal — l'embedding n'exclut jamais un morceau tout seul, il ne fait qu'accélérer les cas évidents.
   La langue réellement chantée (détectée depuis les paroles, pas supposée depuis la nationalité de l'artiste) est fournie à GPT comme signal supplémentaire.
3. Une nouvelle playlist préfixée `IA-` est créée dans ton Spotify avec les morceaux retenus, avec une description générée automatiquement à partir du prompt.
4. La **synchronisation** maintient les playlists à jour : nouveaux morceaux de la source évalués et ajoutés, morceaux retirés de la source supprimés (mode destructif) ou laissés en place (mode additif).
5. Le **ré-filtrage** réévalue le contenu *actuel* d'une playlist contre son prompt *actuel* — utile après avoir édité un prompt, puisque le sync normal ne réévalue jamais ce qui est déjà dans la playlist, seulement les nouveautés côté source.

La classification est déterministe (`temperature=0` + seed fixe) : la même playlist régénérée avec le même prompt redonne le même résultat, à la fiabilité près de ce qu'OpenAI garantit en best-effort.

---

## Stack

- **Back** — Python / Flask, Spotipy, OpenAI SDK (chat completions + embeddings), gunicorn — hébergé sur Render
- **Front** — HTML/CSS/JS vanilla, PWA mobile-first (3 écrans + nav du bas) — servi par Flask en dev, hébergé sur Vercel en prod
- **Auth** — OAuth2 Spotify ; sessions applicatives par **bearer token** (pas de cookie de session classique — Safari/ITP tue les cookies tiers cross-site entre le front Vercel et l'API Render). Le cookie Flask restant ne sert plus qu'au hand-off `oauth_state` pendant le flow OAuth lui-même.
- **BDD** — SQLite en dev, PostgreSQL (Neon) en prod
- **Signaux externes** — Last.fm (tags) et lrclib.net (paroles, pour la langue chantée réelle), tous deux optionnels : leur absence fait retomber le classement sur le filtrage GPT classique

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
│   │   ├── playlist.py         # Logique métier (generate / sync / refilter)
│   │   └── scoring.py          # Pré-filtre par similarité d'embedding (ancres)
│   ├── services/
│   │   ├── auth.py             # OAuth Spotify + gestion tokens/historique
│   │   ├── spotify.py          # Wrapper Spotipy
│   │   ├── classifier.py       # Wrapper OpenAI (chat completions, structured outputs)
│   │   ├── embeddings.py       # Wrapper OpenAI (embeddings, similarité cosinus)
│   │   ├── lastfm.py           # Tags Last.fm par morceau
│   │   └── lyrics.py           # Paroles (lrclib.net) + détection de langue
│   ├── tokens.db               # Base SQLite dev (gitignorée)
│   ├── history.db              # Historique SQLite dev (gitignorée)
│   ├── decisions.log           # Log des décisions GPT, écrasé à chaque run (gitignoré)
│   └── requirements.txt
├── web/
│   ├── index.html              # Structure — 3 écrans (Accueil / Générer / Historique) + nav du bas
│   ├── styles.css              # Design system (tokens, composants)
│   ├── app.js                  # Logique front, appels API, SSE
│   └── Logo.png
├── requirements.txt            # Délègue à api/requirements.txt (pour Render)
├── Procfile                    # Commande gunicorn pour Render
├── render.yaml                 # Config déploiement Render
└── .python-version             # Runtime Python pin pour Render (voir Déploiement)
```

---

## Dev local

### Prérequis
- Python 3.10+ (le SDK OpenAI utilisé l'exige — voir `.python-version`)
- Un compte [Spotify Developer](https://developer.spotify.com/dashboard) avec une app créée
- Une clé API OpenAI
- (Optionnel) Une clé API [Last.fm](https://www.last.fm/api) — sans elle, le pré-filtre par embedding est simplement désactivé

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

# Optionnel — sans ça, le pré-filtre par similarité d'embedding est désactivé
LASTFM_API_KEY=

# Laisser vide en dev = SQLite local
DATABASE_URL=
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

Pour restreindre qui peut se connecter, gère la liste directement dans **Users and Access** du dashboard Spotify — une app en Development Mode n'autorise de toute façon que les comptes que tu y ajoutes explicitement, inutile de dupliquer cette restriction côté app.

### 4. Lancer

```bash
cd api
myenv/bin/python app.py
```

Puis ouvre [http://127.0.0.1:5001](http://127.0.0.1:5001)

---

## Déploiement (Render + Vercel + Neon)

Le back (API) tourne sur Render, le front (statique) sur Vercel — deux domaines distincts, d'où l'auth par bearer token plutôt que par cookie de session (voir Stack).

### Base de données Neon

1. Crée un projet sur [neon.tech](https://neon.tech)
2. Applique le schéma initial (tables `tokens`, `history`, `playlist_prompts`) via le **SQL Editor** Neon ou les migrations
3. Récupère la **connection string pooled** : Dashboard → Connect → Pooled connection
   ```
   postgresql://USER:PASSWORD@ep-xxx-pooler.REGION.aws.neon.tech/neondb?sslmode=require&channel_binding=require
   ```

### Backend — Render

1. Crée un **Web Service** sur [render.com](https://render.com), connecte le repo GitHub — Render détecte le `render.yaml` automatiquement
2. Configure les variables d'environnement :

| Variable | Valeur |
|---|---|
| `SPOTIFY_ID` | Client ID de ton app Spotify |
| `SPOTIFY_SECRET` | Client Secret de ton app Spotify |
| `SPOTIFY_USERNAME` | Ton username Spotify |
| `SPOTIFY_REDIRECT` | `https://TON-API.onrender.com/auth/callback` (le backend Render — Spotify redirige ici, pas vers le front) |
| `GPT_KEY` | Clé API OpenAI |
| `FRONTEND_URL` | URL du front Vercel, ex. `https://musester.vercel.app` — sert à la fois de redirection post-login et d'origine CORS autorisée |
| `DATABASE_URL` | Connection string Neon (pooled connection) |
| `LASTFM_API_KEY` | Optionnel — clé API Last.fm pour le pré-filtre par embedding |
| `SECRET_KEY` | Généré automatiquement par Render |

3. Ajoute l'URI de callback dans le dashboard Spotify Developer :
   ```
   https://TON-API.onrender.com/auth/callback
   ```
4. `.python-version` à la racine du repo pin la version Python utilisée par Render — à garder synchronisé avec ce qu'exigent les dépendances de `requirements.txt` (le SDK OpenAI en particulier). Sans ce pin, un service existant peut rester bloqué sur un runtime plus ancien que ce que le build attend, et `pip install` échoue silencieusement — Render continue alors de servir le dernier build réussi sans signal clair que le déploiement suivant n'est jamais passé.

### Frontend — Vercel

1. Importe le repo GitHub sur [vercel.com/new](https://vercel.com/new)
2. **Root Directory** : `web` — **Framework Preset** : `Other` (site statique, pas de build command)
3. Déploie — le domaine stable du projet (ex. `musester.vercel.app`, pas l'URL de déploiement à hash aléatoire) est celui à renseigner dans `FRONTEND_URL` sur Render
4. Dans `web/app.js`, la constante `API` pointe vers l'URL Render en prod et bascule en relatif (`''`) en local/dev — à adapter si le domaine Render change

### Accès (qui peut se connecter)

Géré uniquement côté Spotify : Dashboard Spotify Developer → **Users and Access**. Une app en Development Mode n'autorise que les comptes explicitement ajoutés là — pas besoin d'une liste équivalente côté app, ça ne ferait que dupliquer la même restriction dans deux endroits différents.

### Base de données

En local (`DATABASE_URL` vide) → SQLite (`tokens.db` + `history.db` dans `api/`)
En prod (`DATABASE_URL` défini) → PostgreSQL Neon, les fichiers SQLite sont ignorés

---

## Endpoints

### `GET /auth/login`
Redirige vers la page d'autorisation Spotify.

### `GET /auth/callback`
Callback OAuth. Appelé automatiquement par Spotify après autorisation, redirige ensuite vers le front avec le bearer token dans le fragment d'URL (`#token=...`).

### `GET /auth/me`
Retourne l'utilisateur connecté (résolu depuis le header `Authorization: Bearer ...`).
```json
{ "error": null, "data": { "user_id": "..." } }
```

### `GET /auth/logout`
Invalide le bearer token courant.

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
`source_id` accepte une URL complète, un ID brut, ou `"liked"` pour les titres likés. Maximum 3 playlists par appel. `anchors` : liste de `{id, title, artists}` — morceaux de la source qui déclenchent le pré-filtre par embedding.

**Réponse** (SSE)
Stream d'événements `progress` / `status` / `done`.

---

### `POST /sync`
Met à jour les playlists `IA-` : évalue et ajoute les nouveaux morceaux de la source, supprime ceux retirés de la source (mode destructif) ou ajoute seulement (mode additif). Ne réévalue jamais ce qui est déjà dans la playlist.

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

### `POST /playlists/<id>/refilter`
Réévalue le contenu *actuel* de la playlist contre son prompt *actuel*, retire ce qui ne correspond plus. Utile après une édition de prompt. Réponse SSE (`progress` / `status` / `done`).

### `GET /source-tracks`
Retourne les morceaux d'une playlist source (utilisé pour le sélecteur d'ancres).

### `GET /playlists`
Retourne les playlists `IA-` de l'utilisateur (prompt, nombre de morceaux, date de dernier sync, cover Spotify).

### `GET /playlists/<id>/anchors`
Retourne les ancres et la source enregistrées pour une playlist.

### `PUT /playlists/<id>/prompt`
Met à jour le prompt d'une playlist (conserve ses ancres et sa source existantes).

### `GET /history`
Retourne l'historique des générations, synchronisations et ré-filtrages.

### `GET /history/<id>/decisions`
Retourne le détail des décisions GPT (inclus/exclu + justification) pour une entrée d'historique.

---

## Configuration

Paramètres ajustables dans `api/config.py` :

| Variable | Valeur par défaut | Description |
|---|---|---|
| `BATCH_SIZE` | `60` | Morceaux envoyés par requête GPT |
| `MAX_WORKERS` | `3` | Requêtes GPT parallèles max |
| `PLAYLIST_PREFIX` | `IA-` | Préfixe des playlists générées |
| `GPT_MODEL` | `gpt-4.1-mini` | Modèle OpenAI utilisé pour la classification |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Modèle utilisé pour le pré-filtre par similarité (ancres) |

---

## Notes

- `decisions.log` est écrasé à chaque `/generate` — détail des décisions GPT (inclus/exclu + justification)
- Le `/sync` se base sur la date du dernier morceau ajouté pour ne traiter que les nouveaux morceaux ; le `/refilter` réévalue tout le contenu actuel, sans toucher à la source
- En mode sync additif, la description de la playlist est mise à jour avec la date et la source utilisée
- La classification tourne à `temperature=0` avec un seed fixe — reproductible en best-effort, pas garanti bit-à-bit identique
- `tokens.db`, `history.db` et `.env` sont gitignorés — ne jamais les committer
