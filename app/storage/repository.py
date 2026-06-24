"""
app/storage/repository.py — CRUD de universos, estudios y resultados.

Usa Supabase Storage como backend persistente.
Fallback a filesystem local si SUPABASE_URL no está configurado (desarrollo).
"""

import json
import os
from datetime import datetime, timezone
from typing import List, Optional

from app.domain.models import Estudio, ExpansionSnapshot, RespuestaEstudio, Universo

_USE_SUPABASE = bool(
    os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
)

if _USE_SUPABASE:
    from app.storage import supabase_storage as _sb

# ── Estado de sesión (user_id activo) ────────────────────────────────────────

_current_user_id: Optional[str] = None


def set_active_user(user_id: str) -> None:
    global _current_user_id
    _current_user_id = user_id


def _uid() -> str:
    if not _current_user_id:
        raise RuntimeError("No active user set. Call set_active_user(uid) first.")
    return _current_user_id


# ── Fallback filesystem (desarrollo local) ───────────────────────────────────

from app.config import config


def _write_json_local(path: str, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _read_json_local(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _sorted_json_files_local(directory: str) -> List[str]:
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
    payload = universo.to_dict()
    if _USE_SUPABASE:
        _sb.upload_json(_uid(), f"universos/{universo.id}.json", payload)
        return f"supabase://{_uid()}/universos/{universo.id}.json"
    path = os.path.join(str(config.universes_dir), f"{universo.id}.json")
    _write_json_local(path, payload)
    return path


def load_universe(path: str) -> Universo:
    if _USE_SUPABASE and path.startswith("supabase://"):
        parts = path.replace("supabase://", "").split("/", 1)
        data = _sb.download_json(parts[0], parts[1])
    else:
        data = _read_json_local(path)
    return Universo.from_dict(data)


def list_universes() -> List[Universo]:
    if _USE_SUPABASE:
        paths = _sb.list_files(_uid(), "universos")
        # exclude expansiones subfolder entries
        paths = [p for p in paths if not p.startswith("universos/expansiones")]
        results = []
        for rel in paths:
            data = _sb.download_json(_uid(), rel)
            if data:
                results.append(Universo.from_dict(data))
        return results
    return [
        Universo.from_dict(_read_json_local(p))
        for p in _sorted_json_files_local(str(config.universes_dir))
    ]


def find_universe(universe_id: str) -> Optional[Universo]:
    if _USE_SUPABASE:
        data = _sb.download_json(_uid(), f"universos/{universe_id}.json")
        return Universo.from_dict(data) if data else None
    path = os.path.join(str(config.universes_dir), f"{universe_id}.json")
    if not os.path.exists(path):
        return None
    return Universo.from_dict(_read_json_local(path))


# ── Expansiones ──────────────────────────────────────────────────────────────


def save_expansion(universe_id: str, snapshot: ExpansionSnapshot) -> str:
    timestamp = str(snapshot.created_at).strip().replace(":", "-")
    if not timestamp:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    filename = f"{universe_id}_{timestamp}.json"
    payload = snapshot.to_dict()
    if _USE_SUPABASE:
        _sb.upload_json(_uid(), f"universos/expansiones/{filename}", payload)
        return f"supabase://{_uid()}/universos/expansiones/{filename}"
    path = os.path.join(str(config.expansions_dir), filename)
    _write_json_local(path, payload)
    return path


def list_expansions(universe_id: Optional[str] = None) -> List[str]:
    if _USE_SUPABASE:
        paths = _sb.list_files(_uid(), "universos/expansiones")
        if universe_id:
            paths = [p for p in paths if os.path.basename(p).startswith(f"{universe_id}_")]
        return [f"supabase://{_uid()}/{p}" for p in paths]
    files = _sorted_json_files_local(str(config.expansions_dir))
    if not universe_id:
        return files
    return [p for p in files if os.path.basename(p).startswith(f"{universe_id}_")]


def load_expansion(path: str) -> ExpansionSnapshot:
    if _USE_SUPABASE and path.startswith("supabase://"):
        parts = path.replace("supabase://", "").split("/", 1)
        data = _sb.download_json(parts[0], parts[1])
    else:
        data = _read_json_local(path)
    return ExpansionSnapshot.from_dict(data)


def find_latest_expansion(universe_id: str) -> Optional[dict]:
    files = list_expansions(universe_id)
    if not files:
        return None
    return {"path": files[0], "payload": load_expansion(files[0])}


# ── Estudios ─────────────────────────────────────────────────────────────────


def save_study(estudio: Estudio) -> str:
    payload = estudio.to_dict()
    if _USE_SUPABASE:
        _sb.upload_json(_uid(), f"estudios/{estudio.id}.json", payload)
        return f"supabase://{_uid()}/estudios/{estudio.id}.json"
    path = os.path.join(str(config.studies_dir), f"{estudio.id}.json")
    _write_json_local(path, payload)
    return path


def load_study(path: str) -> Estudio:
    if _USE_SUPABASE and path.startswith("supabase://"):
        parts = path.replace("supabase://", "").split("/", 1)
        data = _sb.download_json(parts[0], parts[1])
    else:
        data = _read_json_local(path)
    return Estudio.from_dict(data)


def list_studies() -> List[Estudio]:
    if _USE_SUPABASE:
        paths = _sb.list_files(_uid(), "estudios")
        results = []
        for rel in paths:
            data = _sb.download_json(_uid(), rel)
            if data:
                results.append(Estudio.from_dict(data))
        return results
    return [
        Estudio.from_dict(_read_json_local(p))
        for p in _sorted_json_files_local(str(config.studies_dir))
    ]


def find_study(study_id: str) -> Optional[Estudio]:
    if _USE_SUPABASE:
        data = _sb.download_json(_uid(), f"estudios/{study_id}.json")
        return Estudio.from_dict(data) if data else None
    path = os.path.join(str(config.studies_dir), f"{study_id}.json")
    if not os.path.exists(path):
        return None
    return Estudio.from_dict(_read_json_local(path))


# ── Resultados ───────────────────────────────────────────────────────────────


def save_study_results(study_id: str, respuestas: List[RespuestaEstudio]) -> str:
    payload = [r.to_dict() for r in respuestas]
    if _USE_SUPABASE:
        _sb.upload_json(_uid(), f"resultados/{study_id}.json", payload)
        return f"supabase://{_uid()}/resultados/{study_id}.json"
    path = os.path.join(str(config.results_dir), f"{study_id}.json")
    _write_json_local(path, payload)
    return path


def load_study_results(study_id: str) -> List[RespuestaEstudio]:
    if _USE_SUPABASE:
        data = _sb.download_json(_uid(), f"resultados/{study_id}.json")
    else:
        path = os.path.join(str(config.results_dir), f"{study_id}.json")
        if not os.path.exists(path):
            return []
        data = _read_json_local(path)
    if not data or not isinstance(data, list):
        return []
    return [RespuestaEstudio.from_dict(item) for item in data]


def list_results() -> List[str]:
    if _USE_SUPABASE:
        paths = _sb.list_files(_uid(), "resultados")
        return [f"supabase://{_uid()}/{p}" for p in paths]
    return _sorted_json_files_local(str(config.results_dir))
