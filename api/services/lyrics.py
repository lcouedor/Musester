import logging
import threading

import requests
from langdetect import DetectorFactory, LangDetectException, detect

import config

logger = logging.getLogger(__name__)

LRCLIB_API_URL = "https://lrclib.net/api/get"

# langdetect n'est pas déterministe par défaut (échantillonnage aléatoire en
# interne) — on fixe la seed pour avoir des résultats reproductibles.
DetectorFactory.seed = 0

# ... et surtout pas thread-safe : son détecteur interne est un singleton
# partagé, donc l'appeler depuis plusieurs threads en parallèle (fetch_languages
# tourne dans un ThreadPoolExecutor) corrompt son état et renvoie des langues
# fantaisistes (constaté : "Papaoutai" détecté slovène au lieu de français).
# Le verrou ne sérialise QUE le calcul (quelques ms) — le fetch réseau, qui est
# le vrai coût, reste concurrent.
_detect_lock = threading.Lock()


def get_lyrics(artist: str, title: str) -> str | None:
    """Paroles complètes via lrclib.net (gratuit, sans clé). None si introuvable
    ou instrumental."""
    try:
        resp = requests.get(LRCLIB_API_URL, params={
            "artist_name": artist,
            "track_name":  title,
        }, timeout=6)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("instrumental"):
            return None
        return data.get("plainLyrics") or None
    except Exception as e:
        logger.warning("Lyrics lookup failed for '%s - %s': %s", artist, title, e)
        return None


def detect_language(text: str) -> str | None:
    """Code langue ISO 639-1 (ex. 'en', 'pl') détecté depuis un texte réel —
    un fait mesuré, pas une supposition depuis la nationalité de l'artiste."""
    if not text or len(text.strip()) < 12:
        return None
    try:
        with _detect_lock:
            return detect(text)
    except LangDetectException:
        return None
