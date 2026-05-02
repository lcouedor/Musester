from dotenv import load_dotenv

load_dotenv()

# Spotify
SPOTIFY_ID = os.getenv('SPOTIFY_ID')
SPOTIFY_SECRET = os.getenv('SPOTIFY_SECRET')
SPOTIFY_REDIRECT = os.getenv('SPOTIFY_REDIRECT')
SPOTIFY_USERNAME = os.getenv('SPOTIFY_USERNAME')
SPOTIFY_SCOPE = "playlist-read-private playlist-modify-private playlist-modify-public user-library-read"

# OpenAI
GPT_KEY = os.getenv('GPT_KEY')
GPT_MODEL = "gpt-4.1"

# Behaviour
BATCH_SIZE = 60
MAX_WORKERS = 3
PLAYLIST_PREFIX = "IA-"
