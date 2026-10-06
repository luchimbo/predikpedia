"""
Script one-time: sube la data local de un usuario a Supabase Storage.
Correr una sola vez: python migrate_to_supabase.py
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from supabase import create_client

BUCKET = "predikpedia-data"
USER_ID = "59fb43f0-ca12-4b5d-a2af-c0987c429ce6"
LOCAL_BASE = Path("data") / USER_ID

url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")

if not url or not key:
    print("ERROR: Faltan SUPABASE_URL o SUPABASE_SERVICE_KEY en .env")
    exit(1)

client = create_client(url, key)

uploaded = 0
errors = 0

for json_file in LOCAL_BASE.rglob("*.json"):
    relative = json_file.relative_to(LOCAL_BASE)
    remote_path = f"{USER_ID}/{relative.as_posix()}"

    with open(json_file, "r", encoding="utf-8") as f:
        content = f.read().encode("utf-8")

    try:
        client.storage.from_(BUCKET).upload(
            remote_path, content, {"content-type": "application/json", "upsert": "true"}
        )
        print(f"  OK {relative}")
        uploaded += 1
    except Exception as e:
        print(f"  ERR {relative} - {e}")
        errors += 1

print(f"\nDone: {uploaded} uploaded, {errors} errors.")
