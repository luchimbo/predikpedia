"""Persistence and recovery for one-response independent surveys."""
import hashlib
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from tempfile import gettempdir

from app.config import config
from app.domain.models import Estudio, RespuestaEstudio
from app.services.simulation_service import run_simulation
from app.storage.repository import (
    load_study_results,
    load_study_sample,
    save_study,
    save_study_results,
    save_study_sample,
)


def response_is_valid(answer: RespuestaEstudio) -> bool:
    return bool(answer.respuesta.strip()) and not answer.error and not answer.respuesta.strip().startswith("[ERROR:")


@contextmanager
def study_lock(study_id: str):
    # A SQLite transaction releases the lock if a worker exits mid-run.
    scope = f"{config.data_dir.resolve()}:{study_id}"
    name = hashlib.sha256(scope.encode()).hexdigest()
    root = Path(gettempdir()) / "predikpedia-study-locks"
    root.mkdir(exist_ok=True)
    with closing(sqlite3.connect(root / f"{name}.db", timeout=0)) as db:
        try:
            db.execute("BEGIN EXCLUSIVE")
        except sqlite3.OperationalError as exc:
            if exc.sqlite_errorcode == sqlite3.SQLITE_BUSY:
                raise ValueError("Este estudio ya se está ejecutando en otra sesión.") from exc
            raise
        yield


def prepare_survey(study: Estudio, personas: list[dict]) -> None:
    if not study.resumable or study.mode != "survey" or study.respuestas_por_persona != 1:
        raise ValueError("La recuperación requiere una encuesta de una respuesta por persona.")
    ids = {p.get("persona_id") for p in personas}
    if len(personas) != study.respuestas_planeadas or not ids or None in ids or "" in ids or len(ids) != len(personas):
        raise ValueError("La muestra necesita identificadores únicos y debe coincidir con el total previsto.")
    with study_lock(study.id):
        save_study_sample(study, personas)
        save_study_results(study.id, [])
        save_study(study)


def continue_survey(study: Estudio, engine, *, store=None, retry_errors=False, on_progress=None):
    with study_lock(study.id):
        personas = load_study_sample(study)
        ids = [p["persona_id"] for p in personas]
        if study.local_only and (store is None or not engine.local_only):
            raise ValueError("Abrí el expediente en el equipo de origen y ejecutá con Ollama.")
        saved = load_study_results(study.id, strict=True)
        answers = {a.persona_id: a for a in saved}
        if len(answers) != len(saved):
            raise ValueError("El estudio tiene respuestas duplicadas.")
        if store:
            # The private evidence database commits before the portable results file.
            for row in store.run_responses(study.id):
                answer = RespuestaEstudio.from_dict(row)
                if answer.persona_id not in answers or not response_is_valid(answers[answer.persona_id]):
                    answers[answer.persona_id] = answer
        if any(a.estudio_id != study.id or pid not in ids for pid, a in answers.items()):
            raise ValueError("Las respuestas guardadas no coinciden con la muestra del estudio.")

        pending = ({pid for pid, a in answers.items() if not response_is_valid(a)}
                   if retry_errors else set(ids).difference(answers))

        def persist():
            save_study_results(study.id, [answers[pid] for pid in ids if pid in answers])

        def checkpoint(answer, done, total):
            answers[answer.persona_id] = answer
            persist()
            if on_progress:
                on_progress(done, total)

        if pending:
            run_simulation(study, personas, engine, store=store,
                           survey_pending_ids=pending, on_response=checkpoint)
        elif len(answers) != len(saved) or answers != {a.persona_id: a for a in saved}:
            persist()
        return [answers[pid] for pid in ids if pid in answers]
