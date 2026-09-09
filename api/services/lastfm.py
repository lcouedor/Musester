import logging

import requests

import config

logger = logging.getLogger(__name__)

LASTFM_API_URL = "https://ws.audioscrobbler.com/2.0/"


def get_track_tags(artist: str, title: str, limit: int = 6) -> list[str]:
    """Tags Last.fm les plus posés sur ce morceau (signal externe, indépendant
    de ce que GPT connaît). Liste vide si le morceau est inconnu de Last.fm,
    ou si aucune clé n'est configurée."""
    if not config.LASTFM_API_KEY:
        return []
    try:
        resp = requests.get(LASTFM_API_URL, params={
            "method":  "track.gettoptags",
            "artist":  artist,
            "track":   title,
            "api_key": config.LASTFM_API_KEY,
            "format":  "json",
        }, timeout=5)
        data = resp.json()
        tags = data.get("toptags", {}).get("tag") or []
        return [t["name"] for t in tags[:limit] if t.get("name")]
    except Exception as e:
        logger.warning("Last.fm tags failed for '%s - %s': %s", artist, title, e)
        return []
