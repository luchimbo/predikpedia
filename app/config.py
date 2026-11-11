"""
app/config.py — Configuración central de rutas y settings.

Prioridad de resolución de data_dir:
  1. Variable de entorno PREDIKPEDIA_DATA_DIR
  2. Archivo settings.json en la raíz del repo
  3. Default: ./data/ (relativo al repo)
"""

import json
import os
from contextvars import ContextVar
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent.resolve()
SETTINGS_FILE = REPO_ROOT / "settings.json"
DEFAULT_DATA_DIR = REPO_ROOT / "data"


_session_dir: ContextVar[Path | None] = ContextVar('data_dir', default=None)


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
            self._base_dir = Path(env_dir).resolve()
        # 2. Leer de settings.json
        elif SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                configured = settings.get("data_dir", "")
                if configured:
                    self._base_dir = Path(configured).resolve()
                else:
                    self._base_dir = DEFAULT_DATA_DIR
            except Exception:
                self._base_dir = DEFAULT_DATA_DIR
        # 3. Default
        else:
            self._base_dir = DEFAULT_DATA_DIR

    @property
    def data_dir(self):
        return _session_dir.get() or self._base_dir

    @property
    def universes_dir(self):
        return self.data_dir / "universos"

    @property
    def expansions_dir(self):
        return self.universes_dir / "expansiones"

    @property
    def studies_dir(self):
        return self.data_dir / "estudios"

    @property
    def results_dir(self):
        return self.data_dir / "resultados"

    @property
    def benchmarks_dir(self):
        return self.data_dir / "benchmarks"

    @property
    def ledger_file(self):
        return self.data_dir / "credits_ledger.json"

    def set_user(self, user_id: str, *, create: bool = True):
        """Bind the paths to the current execution context."""
        _session_dir.set(REPO_ROOT / "data" / user_id)
        if create:
            self.ensure_directories()

    def set_session_dir(self, path: str):
        _session_dir.set(Path(path).resolve())
        self.ensure_directories()

    def ensure_directories(self):
        """Crea los directorios de datos si no existen."""
        for path in (
            self.data_dir,
            self.universes_dir,
            self.expansions_dir,
            self.studies_dir,
            self.results_dir,
            self.benchmarks_dir,
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
