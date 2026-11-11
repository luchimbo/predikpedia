"""
app/storage/repository.py — CRUD de universos, estudios y resultados.

Usa Supabase Storage como backend persistente.
Fallback a filesystem local si SUPABASE_URL no está configurado (desarrollo).
"""

import json
import os
from contextvars import ContextVar
from tempfile import NamedTemporaryFile
from datetime import datetime, timezone
from typing import List, Optional

from app.domain.models import Benchmark, Estudio, ExpansionSnapshot, RespuestaEstudio, Universo

_SUPABASE_CONFIGURED = bool(
    os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
)

if _SUPABASE_CONFIGURED:
    from app.storage import supabase_storage as _sb

# ── Estado de sesión (user_id activo) ────────────────────────────────────────

_current_user = ContextVar("storage_user", default="")
_local_storage = ContextVar("local_storage", default=False)


def set_active_user(user_id: str) -> None:
    _current_user.set(user_id)


def use_local_storage() -> None:
    _local_storage.set(True)


def uses_supabase() -> bool:
    return _SUPABASE_CONFIGURED and not _local_storage.get()


def _uid() -> str:
    user_id = _current_user.get()
    if not user_id:
        raise RuntimeError("No active user set. Call set_active_user(uid) first.")
    return user_id


def _owned_remote_path(path: str) -> str:
    if not path.startswith("supabase://"):
        raise ValueError("Ruta de almacenamiento inválida.")
    owner, _, relative_path = path.removeprefix("supabase://").partition("/")
    if owner != _uid() or not relative_path or any(
        part in {"", ".", ".."} for part in relative_path.split("/")
    ) or chr(92) in relative_path:
        raise ValueError("Ruta de almacenamiento inválida.")
    return relative_path


# ── Fallback filesystem (desarrollo local) ───────────────────────────────────

from app.config import config


def _write_json_local(path: str, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=os.path.dirname(path), delete=False) as f:
        temporary = f.name
        try:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.close()
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                f.close()
                os.unlink(temporary)


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
    if uses_supabase():
        _sb.upload_json(_uid(), f"universos/{universo.id}.json", payload)
        return f"supabase://{_uid()}/universos/{universo.id}.json"
    path = os.path.join(str(config.universes_dir), f"{universo.id}.json")
    _write_json_local(path, payload)
    return path


def load_universe(path: str) -> Universo:
    if uses_supabase():
        data = _sb.download_json(_uid(), _owned_remote_path(path))
    else:
        data = _read_json_local(path)
    return Universo.from_dict(data)


def list_universes() -> List[Universo]:
    if uses_supabase():
        paths = _sb.list_files(_uid(), "universos")
        # exclude expansiones subfolder entries
        paths = [p for p in paths if not p.startswith("universos/expansiones")]
        paths = sorted(paths, reverse=True)
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
    if uses_supabase():
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
    if uses_supabase():
        _sb.upload_json(_uid(), f"universos/expansiones/{filename}", payload)
        return f"supabase://{_uid()}/universos/expansiones/{filename}"
    path = os.path.join(str(config.expansions_dir), filename)
    _write_json_local(path, payload)
    return path


def list_expansions(universe_id: Optional[str] = None) -> List[str]:
    if uses_supabase():
        paths = _sb.list_files(_uid(), "universos/expansiones")
        if universe_id:
            paths = [p for p in paths if os.path.basename(p).startswith(f"{universe_id}_")]
        paths = sorted(paths, reverse=True)
        return [f"supabase://{_uid()}/{p}" for p in paths]
    files = _sorted_json_files_local(str(config.expansions_dir))
    if not universe_id:
        return files
    return [p for p in files if os.path.basename(p).startswith(f"{universe_id}_")]


def load_expansion(path: str) -> ExpansionSnapshot:
    if uses_supabase():
        data = _sb.download_json(_uid(), _owned_remote_path(path))
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
    if uses_supabase():
        _sb.upload_json(_uid(), f"estudios/{estudio.id}.json", payload)
        return f"supabase://{_uid()}/estudios/{estudio.id}.json"
    path = os.path.join(str(config.studies_dir), f"{estudio.id}.json")
    _write_json_local(path, payload)
    return path


def load_study(path: str) -> Estudio:
    if uses_supabase():
        data = _sb.download_json(_uid(), _owned_remote_path(path))
    else:
        data = _read_json_local(path)
    return Estudio.from_dict(data)


def list_studies() -> List[Estudio]:
    if uses_supabase():
        paths = _sb.list_files(_uid(), "estudios")
        paths = sorted(paths, reverse=True)
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
    if uses_supabase():
        data = _sb.download_json(_uid(), f"estudios/{study_id}.json")
        return Estudio.from_dict(data) if data else None
    path = os.path.join(str(config.studies_dir), f"{study_id}.json")
    if not os.path.exists(path):
        return None
    return Estudio.from_dict(_read_json_local(path))


# ── Resultados ───────────────────────────────────────────────────────────────


def save_study_results(study_id: str, respuestas: List[RespuestaEstudio]) -> str:
    payload = [r.to_dict() for r in respuestas]
    if uses_supabase():
        _sb.upload_json(_uid(), f"resultados/{study_id}.json", payload)
        return f"supabase://{_uid()}/resultados/{study_id}.json"
    path = os.path.join(str(config.results_dir), f"{study_id}.json")
    _write_json_local(path, payload)
    return path


def load_study_results(study_id: str, *, strict: bool = False) -> List[RespuestaEstudio]:
    if uses_supabase():
        data = _sb.download_json(_uid(), f"resultados/{study_id}.json", strict=strict)
    else:
        path = os.path.join(str(config.results_dir), f"{study_id}.json")
        if not os.path.exists(path):
            return []
        data = _read_json_local(path)
    if not isinstance(data, list):
        if strict:
            raise ValueError("El archivo de respuestas no es válido.")
        return []
    return [RespuestaEstudio.from_dict(item) for item in data]


def list_results() -> List[str]:
    if uses_supabase():
        paths = _sb.list_files(_uid(), "resultados")
        paths = sorted(paths, reverse=True)
        return [f"supabase://{_uid()}/{p}" for p in paths]
    return _sorted_json_files_local(str(config.results_dir))


# ── Benchmarks (resultados reales para validar) ──────────────────────────────


def save_benchmark(benchmark: Benchmark) -> str:
    payload = benchmark.to_dict()
    if uses_supabase():
        _sb.upload_json(_uid(), f"benchmarks/{benchmark.id}.json", payload)
        return f"supabase://{_uid()}/benchmarks/{benchmark.id}.json"
    path = os.path.join(str(config.benchmarks_dir), f"{benchmark.id}.json")
    _write_json_local(path, payload)
    return path


def list_benchmarks() -> List[Benchmark]:
    if uses_supabase():
        results = []
        for rel in sorted(_sb.list_files(_uid(), "benchmarks"), reverse=True):
            data = _sb.download_json(_uid(), rel)
            if data:
                results.append(Benchmark.from_dict(data))
        return results
    return [
        Benchmark.from_dict(_read_json_local(p))
        for p in _sorted_json_files_local(str(config.benchmarks_dir))
    ]


def delete_benchmark(benchmark_id: str) -> None:
    if uses_supabase():
        _sb.delete_file(_uid(), f"benchmarks/{benchmark_id}.json")
        return
    path = os.path.join(str(config.benchmarks_dir), f"{benchmark_id}.json")
    if os.path.exists(path):
        os.remove(path)


def save_study_sample(study: Estudio, personas: list[dict]) -> None:
    payload = {"study": study.to_dict(), "personas": personas}
    relative = f"muestras/{study.id}.json"
    if uses_supabase():
        _sb.upload_json(_uid(), relative, payload)
    else:
        _write_json_local(str(config.data_dir / relative), payload)


def load_study_sample(study: Estudio) -> list[dict]:
    relative = f"muestras/{study.id}.json"
    if uses_supabase():
        payload = _sb.download_json(_uid(), relative, strict=True)
    else:
        payload = _read_json_local(str(config.data_dir / relative))
    if payload["study"] != study.to_dict():
        raise ValueError("La configuración del estudio cambió desde el guardado de la muestra.")
    return payload["personas"]
