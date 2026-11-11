"""Durable local FIFO for independent surveys."""
import sqlite3
from contextlib import contextmanager, closing
from dataclasses import dataclass

from app.config import config
from app.services.study_recovery import continue_survey, response_is_valid, study_lock
from app.storage.repository import find_study, load_study_results, uses_supabase

WORKER_LOCK = "local_study_queue_worker"


@dataclass(frozen=True)
class Job:
    study_id: str
    action: str
    status: str


@contextmanager
def _database():
    if uses_supabase():
        raise ValueError("La cola solo está disponible en modo local.")
    config.data_dir.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(config.data_dir / "study_queue.sqlite3")) as db, db:
        db.execute("""CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            study_id TEXT NOT NULL UNIQUE,
            action TEXT NOT NULL,
            status TEXT NOT NULL
        )""")
        yield db


def enqueue(study_ids, *, retry_errors=False):
    """Insert a pair in one transaction and coalesce repeated submissions."""
    study_ids = tuple(study_ids)
    action = "retry" if retry_errors else "resume"
    if any(not (study := find_study(study_id)) or not study.resumable for study_id in study_ids):
        raise ValueError("La cola requiere estudios preparados de una respuesta por persona.")
    with _database() as db:
        db.executemany(
            """INSERT INTO jobs (study_id, action, status) VALUES (?, ?, 'queued')
               ON CONFLICT(study_id) DO UPDATE SET id=excluded.id, action=excluded.action, status='queued'
               WHERE jobs.status NOT IN ('queued', 'running')""",
            [(study_id, action) for study_id in study_ids],
        )


def study_jobs():
    if uses_supabase() or not (config.data_dir / "study_queue.sqlite3").exists():
        return {}
    with _database() as db:
        return {row[0]: Job(*row) for row in db.execute("SELECT study_id, action, status FROM jobs ORDER BY id")}


def worker_online():
    try:
        with study_lock(WORKER_LOCK):
            return False
    except ValueError:
        return True


def recover_interrupted():
    """Call only while holding the exclusive worker lock."""
    with _database() as db:
        db.execute("UPDATE jobs SET status='queued' WHERE status='running'")


def process_next(engine_factory, store_factory):
    """Process one task while the caller holds the exclusive worker lock."""
    with _database() as db:
        row = db.execute("SELECT study_id, action FROM jobs WHERE status='queued' ORDER BY id LIMIT 1").fetchone()
        if not row:
            return False
        study_id, action = row
        db.execute("UPDATE jobs SET status='running' WHERE study_id=?", (study_id,))

    try:
        study = find_study(study_id)
        if study is None:
            raise ValueError("No se encontró el estudio.")
        engine = engine_factory(study)
        if not engine.is_ready():
            raise ValueError("El worker no tiene un modelo configurado.")
        answers = continue_survey(study, engine, store=store_factory(study), retry_errors=action == "retry")
        status = "failed" if any(not response_is_valid(a) for a in answers) else "done"
        if len(answers) != study.respuestas_planeadas and status == "done":
            status = "failed"
    except Exception as exc:
        # Exception details can include local paths and provider configuration.
        print(f"Estudio {study_id}: {type(exc).__name__}", flush=True)
        status = "failed"
    with _database() as db:
        db.execute("UPDATE jobs SET status=? WHERE study_id=?", (status, study_id))
    return True


def progress_for(study):
    answers = load_study_results(study.id)
    return sum(response_is_valid(a) for a in answers), len(answers)
