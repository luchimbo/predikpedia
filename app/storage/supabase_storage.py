"""
app/storage/supabase_storage.py — Capa de persistencia en Supabase Storage.

Cada usuario tiene sus archivos en:
  predikpedia-data/{user_id}/universos/*.json
  predikpedia-data/{user_id}/universos/expansiones/*.json
  predikpedia-data/{user_id}/estudios/*.json
  predikpedia-data/{user_id}/resultados/*.json
"""

import json
import os
from typing import Optional

from supabase import create_client, Client

BUCKET = "predikpedia-data"

_client: Optional[Client] = None


def _get_client() -> Client:
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")
        key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")
        if not url or not key:
            raise RuntimeError("Supabase credentials not set (SUPABASE_URL / SUPABASE_SERVICE_KEY)")
        _client = create_client(url, key)
    return _client


def upload_json(user_id: str, relative_path: str, data: dict | list) -> None:
    """Sube un objeto JSON a Supabase Storage."""
    client = _get_client()
    path = f"{user_id}/{relative_path}"
    content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    # upsert=True reemplaza si ya existe
    client.storage.from_(BUCKET).upload(
        path, content, {"content-type": "application/json", "upsert": "true"}
    )


def download_json(user_id: str, relative_path: str) -> Optional[dict | list]:
    """Descarga y parsea un JSON desde Supabase Storage. Retorna None si no existe."""
    client = _get_client()
    path = f"{user_id}/{relative_path}"
    try:
        response = client.storage.from_(BUCKET).download(path)
        return json.loads(response.decode("utf-8"))
    except Exception:
        return None


def list_files(user_id: str, folder: str) -> list[str]:
    """Lista los archivos .json de una carpeta del usuario. Retorna rutas relativas."""
    client = _get_client()
    prefix = f"{user_id}/{folder}"
    try:
        items = client.storage.from_(BUCKET).list(prefix)
        return [
            f"{folder}/{item['name']}"
            for item in items
            if item["name"].endswith(".json")
        ]
    except Exception:
        return []


def delete_file(user_id: str, relative_path: str) -> None:
    client = _get_client()
    path = f"{user_id}/{relative_path}"
    try:
        client.storage.from_(BUCKET).remove([path])
    except Exception:
        pass
