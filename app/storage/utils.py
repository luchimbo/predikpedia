"""
app/storage/utils.py — Utilidades de I/O.

Migrado desde storage_utils.py.
"""

import glob
import json
import os
from typing import Any, Dict, List, Optional

import pandas as pd


def load_text_file(path: str, default: str = "") -> str:
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def save_text_file(path: str, content: str):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def safe_read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def safe_read_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def iter_data_files(directories: List[str]) -> List[str]:
    files: List[str] = []
    for directory in directories:
        if not directory or not os.path.exists(directory):
            continue
        for pattern in ["*.json", "*.csv"]:
            files.extend(glob.glob(os.path.join(directory, pattern)))
    return files


def is_ignored_filename(filename: str, ignored_terms: List[str]) -> bool:
    lower_name = filename.lower()
    return any(term in lower_name for term in ignored_terms)
