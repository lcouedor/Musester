import json
import logging
import os
import sqlite3
import time
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'tokens.db')

SPOTIFY_AUTH_URL  = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                user_id       TEXT PRIMARY KEY,
                access_token  TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                expires_at    INTEGER NOT NULL
            )
        """)
    logger.info("Token DB ready")


# ---------------------------------------------------------------------------
# OAuth helpers
# ---------------------------------------------------------------------------

def get_auth_url(state: str) -> str:
    logger.info("Using redirect_uri: %s", config.SPOTIFY_REDIRECT)
    params = {
        "client_id":     config.SPOTIFY_ID,
        "response_type": "code",
        "redirect_uri":  config.SPOTIFY_REDIRECT,
        "scope":         config.SPOTIFY_SCOPE,
        "state":         state,
        "show_dialog":   "true",
    }
    query = "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params.items())
    return f"{SPOTIFY_AUTH_URL}?{query}"


def exchange_code(code: str) -> dict:
    """Échange le code OAuth contre access_token + refresh_token."""
    resp = requests.post(SPOTIFY_TOKEN_URL, data={
        "grant_type":   "authorization_code",
        "code":         code,
        "redirect_uri": config.SPOTIFY_REDIRECT,
    }, auth=(config.SPOTIFY_ID, config.SPOTIFY_SECRET))
    resp.raise_for_status()
    return resp.json()


def _refresh_token(user_id: str, refresh_token: str) -> dict:
    resp = requests.post(SPOTIFY_TOKEN_URL, data={
        "grant_type":    "refresh_token",
        "refresh_token": refresh_token,
    }, auth=(config.SPOTIFY_ID, config.SPOTIFY_SECRET))
    resp.raise_for_status()
    data = resp.json()
    # Spotify ne retourne pas toujours un nouveau refresh_token
    data.setdefault("refresh_token", refresh_token)
    return data


# ---------------------------------------------------------------------------
# Token storage
# ---------------------------------------------------------------------------

def save_token(user_id: str, token_data: dict):
    expires_at = int(time.time()) + token_data["expires_in"]
    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO tokens (user_id, access_token, refresh_token, expires_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                access_token  = excluded.access_token,
                refresh_token = excluded.refresh_token,
                expires_at    = excluded.expires_at
        """, (user_id, token_data["access_token"], token_data["refresh_token"], expires_at))
    logger.info("Token saved for user '%s'", user_id)


def get_valid_token(user_id: str) -> Optional[str]:
    """Retourne un access_token valide, rafraîchi si nécessaire."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM tokens WHERE user_id = ?", (user_id,)
        ).fetchone()

    if not row:
        return None

    # Refresh si expiré dans moins de 60s
    if row["expires_at"] - time.time() < 60:
        logger.info("Refreshing token for user '%s'", user_id)
        data = _refresh_token(user_id, row["refresh_token"])
        save_token(user_id, data)
        return data["access_token"]

    return row["access_token"]
