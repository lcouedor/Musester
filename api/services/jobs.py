import json
import logging
import os
import time
import uuid
from concurrent.futures import FIRST_COMPLETED, wait

from db import db_conn, PH

logger = logging.getLogger(__name__)

HEARTBEAT_SECONDS = 8

# Dans history.db (SQLite) / Neon (Postgres) — pas en mémoire. Un registre en
# mémoire ne survit pas à un redémarrage du process (déploiement, restart
# plateforme, recyclage de worker) : le thread qui tournait meurt avec lui, et
# n'importe quel poll en cours reçoit "job introuvable" pour un job qui, du
# point de vue de l'utilisateur, était juste en train de tourner. Une ligne en
# base survit à ça — seul le thread qui l'exécutait ne survit pas au restart
# lui-même (limite inhérente aux threads, indépendante d'où vit l'état).
HISTORY_PATH = os.path.join(os.path.dirname(__file__), '..', 'history.db')
_JOB_TTL_SECONDS = 15 * 60


def init_jobs_table():
    """Contrairement aux autres tables (voir services/auth.py), celle-ci est
    créée aussi en Postgres — pas de migration manuelle à faire dans Neon."""
    with db_conn(HISTORY_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id         TEXT PRIMARY KEY,
                status     TEXT NOT NULL,
                message    TEXT,
                progress   TEXT,
                result     TEXT,
                error      TEXT,
                cancelled  INTEGER NOT NULL DEFAULT 0,
                updated_at REAL NOT NULL
            )
        """)


def create_job() -> str:
    job_id = uuid.uuid4().hex
    with db_conn(HISTORY_PATH) as conn:
        conn.execute(f"""
            INSERT INTO jobs (id, status, message, progress, result, error, cancelled, updated_at)
            VALUES ({PH}, 'running', 'Connexion…', NULL, NULL, NULL, 0, {PH})
        """, (job_id, time.time()))
    _cleanup_stale()
    return job_id


def update_job(job_id: str, **fields):
    sets, params = [], []
    for key in ("status", "message", "error"):
        if key in fields:
            sets.append(f"{key} = {PH}")
            params.append(fields[key])
    if "progress" in fields:
        sets.append(f"progress = {PH}")
        params.append(json.dumps(fields["progress"]) if fields["progress"] is not None else None)
    if "result" in fields:
        sets.append(f"result = {PH}")
        params.append(json.dumps(fields["result"]) if fields["result"] is not None else None)
    if "cancelled" in fields:
        sets.append(f"cancelled = {PH}")
        params.append(1 if fields["cancelled"] else 0)
    if not sets:
        return
    sets.append(f"updated_at = {PH}")
    params.append(time.time())
    params.append(job_id)
    with db_conn(HISTORY_PATH) as conn:
        conn.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id = {PH}", params)


def get_job(job_id: str) -> dict | None:
    with db_conn(HISTORY_PATH) as conn:
        row = conn.execute(f"SELECT * FROM jobs WHERE id = {PH}", (job_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["progress"]  = json.loads(d["progress"]) if d.get("progress") else None
    d["result"]    = json.loads(d["result"]) if d.get("result") else None
    d["cancelled"] = bool(d.get("cancelled"))
    return d


def cancel_job(job_id: str):
    update_job(job_id, cancelled=True)


def is_cancelled(job_id: str | None) -> bool:
    if not job_id:
        return False
    job = get_job(job_id)
    return bool(job and job["cancelled"])


def wait_with_heartbeat(futs: dict, job_id: str = None, heartbeat_every: float = HEARTBEAT_SECONDS):
    """Comme as_completed(futs), mais émet aussi ('heartbeat', None) toutes
    les `heartbeat_every` secondes tant qu'aucun lot n'a terminé — ça donne
    au job un point régulier pour vérifier une éventuelle annulation, et ça
    tient le statut du job à jour pour qui le consulte (poll) même quand
    aucun lot n'a encore fini.

    Partagé entre core/playlist.py (lots GPT) et core/scoring.py (similarité
    aux ancres, détection de langue) — sans ça, annuler pendant ces deux
    étapes ne faisait rien tant qu'elles n'étaient pas allées à leur terme :
    la génération tourne dans un thread détaché (voir routes._run_generate_job),
    rien d'externe ne l'interrompt, seul un check explicite de is_cancelled()
    peut la faire s'arrêter en cours de route.

    Si `job_id` est annulé entre deux lots, yield ('cancelled', None) et
    s'arrête — les lots déjà lancés dans le ThreadPoolExecutor tournent à
    leur terme en arrière-plan (Python ne tue pas un thread en cours), mais
    on arrête d'en attendre le résultat et l'appelant peut couper court."""
    pending = set(futs)
    while pending:
        if job_id and is_cancelled(job_id):
            yield ("cancelled", None)
            return
        done, pending = wait(pending, timeout=heartbeat_every, return_when=FIRST_COMPLETED)
        if not done:
            yield ("heartbeat", None)
            continue
        for fut in done:
            yield ("done", fut)


def _cleanup_stale():
    cutoff = time.time() - _JOB_TTL_SECONDS
    with db_conn(HISTORY_PATH) as conn:
        conn.execute(f"DELETE FROM jobs WHERE updated_at < {PH}", (cutoff,))
