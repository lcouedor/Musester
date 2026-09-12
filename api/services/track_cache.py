import json
import logging
import os
import re
import time

from db import db_conn, PH
from services.lastfm import get_track_tags
from services.lyrics import get_lyrics, detect_language

logger = logging.getLogger(__name__)

# Table partagée entre TOUS les utilisateurs, volontairement — les tags et
# paroles d'un morceau ne dépendent de personne, deux comptes qui ont le même
# morceau en bibliothèque profitent du même appel réseau une seule fois pour
# tous. Dans history.db / Neon comme le reste, pas de fichier séparé. Clé par
# artiste+titre normalisés (pas par ID Spotify) : c'est déjà ce que Last.fm et
# lrclib utilisent pour chercher, donc ça capte aussi les cas "même morceau,
# éditions Spotify différentes" (single vs album, remaster...) que l'ID
# Spotify seul manquerait.
HISTORY_PATH = os.path.join(os.path.dirname(__file__), '..', 'history.db')

# Paroles jamais stockées en entier — seul l'extrait qu'on utilise réellement
# (assez pour capter le thème pour l'embedding, et largement assez pour une
# détection de langue fiable). Ordre de grandeur mesuré : ~30-35 Mo pour
# 50 000 morceaux uniques en cache, sur un quota Neon gratuit de 500 Mo.
_LYRICS_EXCERPT_LEN = 400


def init_track_cache_table():
    with db_conn(HISTORY_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS track_cache (
                cache_key  TEXT PRIMARY KEY,
                tags       TEXT,
                lyrics     TEXT,
                language   TEXT,
                fetched_at REAL NOT NULL
            )
        """)


def _normalize_key(artist: str, title: str) -> str:
    norm = lambda s: re.sub(r'\s+', ' ', (s or '').strip().lower())
    return f"{norm(artist)}|||{norm(title)}"


def get_profile(artist: str, title: str) -> dict:
    """{'tags': list[str], 'lyrics': str|None, 'language': str|None} — lu du
    cache partagé si déjà connu ; sinon interroge Last.fm + lrclib UNE fois
    et met en cache (même un résultat vide, pour ne pas réinterroger sans fin
    un morceau introuvable sur ces APIs à chaque génération)."""
    key = _normalize_key(artist, title)
    with db_conn(HISTORY_PATH) as conn:
        row = conn.execute(f"SELECT tags, lyrics, language FROM track_cache WHERE cache_key = {PH}", (key,)).fetchone()
    if row is not None:
        return {
            "tags":     json.loads(row["tags"]) if row["tags"] else [],
            "lyrics":   row["lyrics"],
            "language": row["language"],
        }

    tags        = get_track_tags(artist, title)
    lyrics_full = get_lyrics(artist, title)
    lyrics      = lyrics_full[:_LYRICS_EXCERPT_LEN].strip() if lyrics_full else None
    language    = detect_language(lyrics_full) if lyrics_full else None

    try:
        with db_conn(HISTORY_PATH) as conn:
            conn.execute(f"""
                INSERT INTO track_cache (cache_key, tags, lyrics, language, fetched_at)
                VALUES ({PH}, {PH}, {PH}, {PH}, {PH})
                ON CONFLICT (cache_key) DO NOTHING
            """, (key, json.dumps(tags) if tags else None, lyrics, language, time.time()))
    except Exception:
        # Deux requêtes concurrentes sur le même morceau jamais vu peuvent se
        # doubler — l'écriture perdante n'est qu'un appel réseau gâché, pas
        # une incohérence de données (le DO NOTHING gère déjà le cas propre).
        logger.warning("Failed to cache profile for '%s - %s'", artist, title)

    return {"tags": tags, "lyrics": lyrics, "language": language}
