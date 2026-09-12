import logging
import threading
import time
import uuid

logger = logging.getLogger(__name__)

# En mémoire, pas en base : ces jobs ne survivent qu'à la durée d'une
# génération (quelques minutes), inutile de payer une table Postgres pour
# ça. Ça suppose un seul process gunicorn (voir render.yaml — worker_class
# gthread + workers=1) : avec plusieurs process, un job créé sur l'un serait
# invisible pour une requête de poll qui atterrit sur l'autre.
_JOB_TTL_SECONDS = 15 * 60

_lock = threading.Lock()
_jobs: dict[str, dict] = {}


def create_job() -> str:
    job_id = uuid.uuid4().hex
    with _lock:
        _jobs[job_id] = {
            "status":     "running",  # running | done | error
            "message":    "Connexion…",
            "progress":   None,
            "result":     None,
            "error":      None,
            "cancelled":  False,
            "updated_at": time.time(),
        }
    _cleanup_stale()
    return job_id


def update_job(job_id: str, **fields):
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return
        job.update(fields)
        job["updated_at"] = time.time()


def get_job(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def cancel_job(job_id: str):
    with _lock:
        job = _jobs.get(job_id)
        if job:
            job["cancelled"] = True


def is_cancelled(job_id: str | None) -> bool:
    if not job_id:
        return False
    with _lock:
        job = _jobs.get(job_id)
        return bool(job and job["cancelled"])


def _cleanup_stale():
    cutoff = time.time() - _JOB_TTL_SECONDS
    with _lock:
        for jid in [j for j, v in _jobs.items() if v["updated_at"] < cutoff]:
            del _jobs[jid]
