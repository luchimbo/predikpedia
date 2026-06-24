"""
app/storage/repository.py — CRUD de universos, estudios y resultados.

Migrado desde storage_universos.py.
Usa app.config para rutas configurables.
"""

import json
import os
from datetime import datetime, timezone
from typing import List, Optional

from app.config import config
from app.domain.models import Estudio, ExpansionSnapshot, RespuestaEstudio, Universo


def _write_json(path: str, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def _read_json(path: str):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _sorted_json_files(directory: str) -> List[str]:
    if not os.path.exists(directory):
        return []
    files = [
        os.path.join(directory, name)
        for name in os.listdir(directory)
        if name.lower().endswith(".json")
    ]
    return sorted(files, key=os.path.getmtime, reverse=True)


# ── Universos ────────────────────────────────────────────────────────────────


def save_universe(universo: Universo) -> str:
    path = os.path.join(str(config.universes_dir), f"{universo.id}.json")
    _write_json(path, universo.to_dict())
    return path


def load_universe(path: str) -> Universo:
    return Universo.from_dict(_read_json(path))


def list_universes() -> List[Universo]:
    return [load_universe(path) for path in _sorted_json_files(str(config.universes_dir))]


def find_universe(universe_id: str) -> Optional[Universo]:
    path = os.path.join(str(config.universes_dir), f"{universe_id}.json")
    if not os.path.exists(path):
        return None
    return load_universe(path)


# ── Expansiones ─────────────────────────────────────────────────────────────


def save_expansion(universe_id: str, snapshot: ExpansionSnapshot) -> str:
    timestamp = str(snapshot.created_at).strip().replace(":", "-")
    if not timestamp:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    filename = f"{universe_id}_{timestamp}.json"
    path = os.path.join(str(config.expansions_dir), filename)
    _write_json(path, snapshot.to_dict())
    return path


def list_expansions(universe_id: Optional[str] = None) -> List[str]:
    files = _sorted_json_files(str(config.expansions_dir))
    if not universe_id:
        return files
    prefix = f"{universe_id}_"
    return [path for path in files if os.path.basename(path).startswith(prefix)]


def load_expansion(path: str) -> ExpansionSnapshot:
    return ExpansionSnapshot.from_dict(_read_json(path))


def find_latest_expansion(universe_id: str) -> Optional[dict]:
    files = list_expansions(universe_id)
    if not files:
        return None
    path = files[0]
    return {"path": path, "payload": load_expansion(path)}


# ── Estudios ────────────────────────────────────────────────────────────────


def save_study(estudio: Estudio) -> str:
    path = os.path.join(str(config.studies_dir), f"{estudio.id}.json")
    _write_json(path, estudio.to_dict())
    return path


def load_study(path: str) -> Estudio:
    return Estudio.from_dict(_read_json(path))


def list_studies() -> List[Estudio]:
    return [load_study(path) for path in _sorted_json_files(str(config.studies_dir))]


def find_study(study_id: str) -> Optional[Estudio]:
    path = os.path.join(str(config.studies_dir), f"{study_id}.json")
    if not os.path.exists(path):
        return None
    return load_study(path)


# ── Resultados ──────────────────────────────────────────────────────────────


def save_study_results(study_id: str, respuestas: List[RespuestaEstudio]) -> str:
    path = os.path.join(str(config.results_dir), f"{study_id}.json")
    payload = [r.to_dict() for r in respuestas]
    _write_json(path, payload)
    return path


def load_study_results(study_id: str) -> List[RespuestaEstudio]:
    path = os.path.join(str(config.results_dir), f"{study_id}.json")
    if not os.path.exists(path):
        return []
    data = _read_json(path)
    if isinstance(data, list):
        return [RespuestaEstudio.from_dict(item) for item in data]
    return []


def list_results() -> List[str]:
    return _sorted_json_files(str(config.results_dir))
