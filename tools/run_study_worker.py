"""Process Predikpedia surveys independently of the Streamlit process."""
import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from app.config import config
from app.services.llm_service import LLMService
from app.services.study_queue import WORKER_LOCK, process_next, recover_interrupted
from app.services.study_recovery import study_lock
from app.storage.evidence_repository import EvidenceRepository
from app.storage.repository import set_active_user, use_local_storage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", default=os.getenv("PREDIKPEDIA_DEFAULT_USER", "demo_user"))
    parser.add_argument("--data-dir", help="Directorio local si cambiaste la ruta en Configuración.")
    args = parser.parse_args()
    use_local_storage()
    set_active_user(args.user)
    config.set_user(args.user)
    if args.data_dir:
        config.set_session_dir(args.data_dir)

    try:
        with study_lock(WORKER_LOCK):
            recover_interrupted()
            print(f"Worker activo en {config.data_dir}", flush=True)
            while True:
                worked = process_next(
                    lambda study: LLMService(local_only=study.local_only),
                    lambda study: EvidenceRepository(args.user) if study.local_only else None,
                )
                if not worked:
                    time.sleep(1)
    except KeyboardInterrupt:
        return
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
