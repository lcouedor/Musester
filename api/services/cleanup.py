import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone

from spotipy.exceptions import SpotifyException

from db import db_conn, PH, DATABASE_URL
from services.auth import HISTORY_PATH, get_valid_token
from services.spotify import SpotifyService

logger = logging.getLogger(__name__)

# Assez long pour couvrir un "rollback" de suppression côté Spotify (la ligne
# redevient utile si la playlist réapparaît — voir _sweep_once), assez court
# pour ne pas accumuler indéfiniment des prompts morts.
_GRACE_DAYS = 30
_STARTUP_DELAY_SECONDS = 20


def _ensure_missing_since_column():
    """playlist_prompts est une table existante gérée à la main dans Neon en
    prod (voir services/auth.py: init_db() n'y touche pas le schéma) — cette
    migration tourne ici de façon inconditionnelle et idempotente pour ne pas
    dépendre d'une étape manuelle côté Neon à chaque déploiement."""
    with db_conn(HISTORY_PATH) as conn:
        if DATABASE_URL:
            conn.execute("ALTER TABLE playlist_prompts ADD COLUMN IF NOT EXISTS missing_since TEXT")
        else:
            try:
                conn.execute("ALTER TABLE playlist_prompts ADD COLUMN missing_since TEXT")
            except sqlite3.OperationalError:
                pass


def _sweep_once():
    """Un prompt de playlist n'est nettoyé que si son ID Spotify ne répond
    plus DU TOUT — jamais sur la base du nom ou d'un filtre par préfixe, ce
    qui confondrait à tort un renommage avec une suppression (la playlist
    garde son ID en cas de renommage, donc ce contrôle ne se déclenche
    jamais pour ce cas)."""
    with db_conn(HISTORY_PATH) as conn:
        rows = conn.execute(
            "SELECT playlist_id, user_id, missing_since FROM playlist_prompts"
        ).fetchall()

    now     = datetime.now(timezone.utc)
    cutoff  = now - timedelta(days=_GRACE_DAYS)
    checked = flagged = cleared = deleted = 0

    for row in rows:
        playlist_id   = row["playlist_id"]
        user_id       = row["user_id"]
        missing_since = row["missing_since"]

        if missing_since:
            try:
                since = datetime.fromisoformat(missing_since)
            except ValueError:
                since = None
            if since and since < cutoff:
                with db_conn(HISTORY_PATH) as conn:
                    conn.execute(f"DELETE FROM playlist_prompts WHERE playlist_id = {PH}", (playlist_id,))
                deleted += 1
                continue

        try:
            token = get_valid_token(user_id)
            if not token:
                continue
            SpotifyService(token).get_playlist_name(playlist_id)
            checked += 1
            if missing_since:
                with db_conn(HISTORY_PATH) as conn:
                    conn.execute(
                        f"UPDATE playlist_prompts SET missing_since = NULL WHERE playlist_id = {PH}",
                        (playlist_id,),
                    )
                cleared += 1
        except SpotifyException as e:
            if e.http_status in (400, 404) and not missing_since:
                with db_conn(HISTORY_PATH) as conn:
                    conn.execute(
                        f"UPDATE playlist_prompts SET missing_since = {PH} WHERE playlist_id = {PH}",
                        (now.isoformat(), playlist_id),
                    )
                flagged += 1
        except Exception as e:
            # Erreur réseau / refresh token révoqué / rate-limit — jamais
            # traitée comme une preuve de suppression : un faux positif ici
            # supprimerait un prompt encore valide après 30 jours.
            logger.warning("Cleanup sweep: check failed for '%s': %s", playlist_id, e)

    if checked or flagged or cleared or deleted:
        logger.info(
            "Cleanup sweep terminé — %d vérifiées, %d marquées absentes, "
            "%d réapparues, %d supprimées définitivement",
            checked, flagged, cleared, deleted,
        )


def run_startup_sweep():
    """Lancé une fois au démarrage de l'app, en tâche de fond — jamais dans
    le chemin d'une requête utilisateur (l'alternative d'un Cron Job Render
    payant ou d'un throttle par-requête a été écartée pour ça). Le délai
    laisse le process finir de démarrer avant de solliciter Spotify pour
    chaque playlist en base."""
    def _run():
        time.sleep(_STARTUP_DELAY_SECONDS)
        try:
            _ensure_missing_since_column()
            _sweep_once()
        except Exception:
            logger.exception("Cleanup sweep failed")
    threading.Thread(target=_run, daemon=True).start()
