from dotenv import load_dotenv
from utils import getSecret

load_dotenv()

# Spotify
SPOTIFY_ID = getSecret('SPOTIFY_ID')
SPOTIFY_SECRET = getSecret('SPOTIFY_SECRET')
SPOTIFY_REDIRECT = getSecret('SPOTIFY_REDIRECT')
SPOTIFY_USERNAME = getSecret('SPOTIFY_USERNAME')
SPOTIFY_SCOPE = "playlist-read-private playlist-modify-private playlist-modify-public user-library-read"

# OpenAI
GPT_KEY = getSecret('GPT_KEY')
GPT_MODEL = "gpt-4.1"

# Behaviour
BATCH_SIZE = 60
MAX_WORKERS = 3
PLAYLIST_PREFIX = "IA-"
