import os
from dotenv import load_dotenv

load_dotenv()

REQUIRED_ENV_VARS = [
    'SPOTIFY_ID', 'SPOTIFY_SECRET', 'SPOTIFY_REDIRECT',
    'SPOTIFY_USERNAME', 'GPT_KEY',
]

def _check_env():
    missing = [k for k in REQUIRED_ENV_VARS if not os.getenv(k)]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")

_check_env()

# Spotify
SPOTIFY_ID       = os.getenv('SPOTIFY_ID')
SPOTIFY_SECRET   = os.getenv('SPOTIFY_SECRET')
SPOTIFY_REDIRECT = os.getenv('SPOTIFY_REDIRECT')
SPOTIFY_USERNAME = os.getenv('SPOTIFY_USERNAME')
SPOTIFY_SCOPE    = "playlist-read-private playlist-modify-private playlist-modify-public user-library-read"

# OpenAI
GPT_KEY         = os.getenv('GPT_KEY')
GPT_MODEL       = "gpt-4.1-mini"
EMBEDDING_MODEL = "text-embedding-3-small"

# Last.fm (tags — signal indépendant de ce que GPT "connaît" d'un morceau).
# Optionnel : en son absence, le classement retombe sur le comportement actuel.
LASTFM_API_KEY = os.getenv('LASTFM_API_KEY')

# Behaviour
BATCH_SIZE  = 60
# Mesuré en direct sur ce compte : 500 requêtes/min, 200k tokens/min pour
# gpt-4.1-mini — un lot de 60 morceaux tourne autour de 3-5k tokens et ~20s.
# À 3 workers, une grosse bibliothèque sans ancres (donc sans pré-filtre —
# tout part en GPT) attend l'essentiel de son temps sur de la concurrence
# inutilement bridée alors que le compte a une marge énorme (10 workers en
# continu reste largement sous les deux plafonds, avec de la marge).
MAX_WORKERS     = 10
PLAYLIST_PREFIX = "IA-"

# Server
PORT         = int(os.getenv('PORT', 5001))
FRONTEND_URL = os.getenv('FRONTEND_URL', f'http://127.0.0.1:{PORT}').strip().rstrip('/')
