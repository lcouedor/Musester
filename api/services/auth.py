import json
import logging
import os
import sqlite3
import time
from typing import Optional

import requests
import config

logger = logging.getLogger(__name__)

DB_PATH      = os.path.join(os.path.dirname(__file__), '..', 'tokens.db')
HISTORY_PATH = os.path.join(os.path.dirname(__file__), '..', 'history.db')

SPOTIFY_AUTH_URL  = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"


def _get_conn(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _get_conn(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                user_id       TEXT PRIMARY KEY,
                access_token  TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                expires_at    INTEGER NOT NULL
            )
        """)
    with _get_conn(HISTORY_PATH) as conn:
        # Table historique unifiée generate + sync
        conn.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id        TEXT NOT NULL,
                action         TEXT NOT NULL,
                created_at     TEXT NOT NULL,
                playlist_id    TEXT,
                playlist_name  TEXT,
                prompt         TEXT,
                checked_songs  INTEGER,
                selected_songs INTEGER,
                removed_songs  INTEGER,
                execution_time TEXT
            )
        """)
        # Table prompts — source de vérité pour les prompts GPT
        conn.execute("""
            CREATE TABLE IF NOT EXISTS playlist_prompts (
                playlist_id TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                prompt      TEXT NOT NULL,
                anchors     TEXT,
                source_id   TEXT,
                updated_at  TEXT NOT NULL
            )
        """)
        for col in ("anchors TEXT", "source_id TEXT"):
            try:
                conn.execute(f"ALTER TABLE playlist_prompts ADD COLUMN {col}")
            except sqlite3.OperationalError:
                pass
    logger.info("DBs ready")


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

def save_playlist_prompt(user_id: str, playlist_id: str, prompt: str,
                         anchors: list = None, source_id: str = None):
    anchors_json = json.dumps(anchors) if anchors else None
    with _get_conn(HISTORY_PATH) as conn:
        conn.execute("""
            INSERT INTO playlist_prompts (playlist_id, user_id, prompt, anchors, source_id, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(playlist_id) DO UPDATE SET
                prompt     = excluded.prompt,
                anchors    = excluded.anchors,
                source_id  = excluded.source_id,
                updated_at = excluded.updated_at
        """, (playlist_id, user_id, prompt, anchors_json, source_id))


def get_playlist_prompt(playlist_id: str) -> Optional[str]:
    with _get_conn(HISTORY_PATH) as conn:
        row = conn.execute(
            "SELECT prompt FROM playlist_prompts WHERE playlist_id = ?", (playlist_id,)
        ).fetchone()
    return row["prompt"] if row else None


def get_playlist_source(playlist_id: str) -> Optional[str]:
    with _get_conn(HISTORY_PATH) as conn:
        row = conn.execute(
            "SELECT source_id FROM playlist_prompts WHERE playlist_id = ?", (playlist_id,)
        ).fetchone()
    return row["source_id"] if row else None


def get_playlist_anchors(playlist_id: str) -> list:
    with _get_conn(HISTORY_PATH) as conn:
        row = conn.execute(
            "SELECT anchors FROM playlist_prompts WHERE playlist_id = ?", (playlist_id,)
        ).fetchone()
    if not row or not row["anchors"]:
        return []
    try:
        return json.loads(row["anchors"])
    except (json.JSONDecodeError, TypeError):
        return []


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

def save_generate(user_id: str, entry: dict):
    with _get_conn(HISTORY_PATH) as conn:
        conn.execute("""
            INSERT INTO history
                (user_id, action, created_at, playlist_id, playlist_name, prompt,
                 checked_songs, selected_songs, execution_time)
            VALUES (?, 'generate', datetime('now'), ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            entry['playlist_id'],
            entry['playlist_name'],
            entry['prompt'],
            entry['checked_songs'],
            entry['selected_songs'],
            entry['execution_time'],
        ))


def save_sync(user_id: str, results: dict, execution_time: str):
    with _get_conn(HISTORY_PATH) as conn:
        for pid, v in results.items():
            conn.execute("""
                INSERT INTO history
                    (user_id, action, created_at, playlist_id, playlist_name,
                     checked_songs, selected_songs, removed_songs, execution_time)
                VALUES (?, 'sync', datetime('now'), ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                pid,
                v.get('name', ''),
                v.get('checked', 0),
                v.get('added', 0),
                v.get('removed', 0),
                execution_time,
            ))


def get_history(user_id: str) -> list:
    with _get_conn(HISTORY_PATH) as conn:
        rows = conn.execute("""
            SELECT * FROM history WHERE user_id = ?
            ORDER BY created_at DESC LIMIT 100
        """, (user_id,)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# OAuth
# ---------------------------------------------------------------------------

def get_auth_url(state: str) -> str:
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
    data.setdefault("refresh_token", refresh_token)
    return data


def save_token(user_id: str, token_data: dict):
    expires_at = int(time.time()) + token_data["expires_in"]
    with _get_conn(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO tokens (user_id, access_token, refresh_token, expires_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                access_token  = excluded.access_token,
                refresh_token = excluded.refresh_token,
                expires_at    = excluded.expires_at
        """, (user_id, token_data["access_token"], token_data["refresh_token"], expires_at))


def get_valid_token(user_id: str) -> Optional[str]:
    with _get_conn(DB_PATH) as conn:
        row = conn.execute("SELECT * FROM tokens WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return None
    if row["expires_at"] - time.time() < 60:
        data = _refresh_token(user_id, row["refresh_token"])
        save_token(user_id, data)
        return data["access_token"]
    return row["access_token"]
