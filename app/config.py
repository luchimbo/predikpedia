"""
app/config.py — Configuración central de rutas y settings.

Prioridad de resolución de data_dir:
  1. Variable de entorno PREDIKPEDIA_DATA_DIR
  2. Archivo settings.json en la raíz del repo
  3. Default: ./data/ (relativo al repo)
"""

import json
import os
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent.resolve()
SETTINGS_FILE = REPO_ROOT / "settings.json"
DEFAULT_DATA_DIR = REPO_ROOT / "data"


class PredikpediaConfig:
    """Configuración singleton de rutas y settings de Predikpedia."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        # 1. Leer de ENV
        env_dir = os.getenv("PREDIKPEDIA_DATA_DIR", "")
        if env_dir:
            self.data_dir = Path(env_dir).resolve()
        # 2. Leer de settings.json
        elif SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                configured = settings.get("data_dir", "")
                if configured:
                    self.data_dir = Path(configured).resolve()
                else:
                    self.data_dir = DEFAULT_DATA_DIR
            except Exception:
                self.data_dir = DEFAULT_DATA_DIR
        # 3. Default
        else:
            self.data_dir = DEFAULT_DATA_DIR

        # Subdirectorios
        self.universes_dir = self.data_dir / "universos"
        self.expansions_dir = self.universes_dir / "expansiones"
        self.studies_dir = self.data_dir / "estudios"
        self.results_dir = self.data_dir / "resultados"
        self.ledger_file = self.data_dir / "credits_ledger.json"

    def ensure_directories(self):
        """Crea los directorios de datos si no existen."""
        for path in (
            self.data_dir,
            self.universes_dir,
            self.expansions_dir,
            self.studies_dir,
            self.results_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def save_settings(self, data_dir: str | None = None):
        """Guarda la configuración actual en settings.json."""
        settings = {}
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    settings = json.load(f)
            except Exception:
                pass
        if data_dir is not None:
            settings["data_dir"] = str(Path(data_dir).resolve())
        else:
            settings["data_dir"] = str(self.data_dir)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        self._load()


# Instancia pública
config = PredikpediaConfig()
