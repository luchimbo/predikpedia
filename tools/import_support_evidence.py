"""Import support privately and optionally create a source-backed synthetic panel.

Run with the repository Python. No model requests and no remote storage writes.
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from app.config import config
from app.domain.models import Universo
from app.services.evidence_service import build_source_population, import_reviews_seed, import_support_csv
from app.services.universe_service import build_expansion_snapshot
from app.storage.evidence_repository import EvidenceRepository
from app.storage.repository import find_latest_expansion, find_universe, save_expansion, save_universe, set_active_user, use_local_storage


def main():
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--user-id", default=os.getenv("PREDIKPEDIA_DEFAULT_USER", "demo_user"))
    parser.add_argument("--account", default="pc-midi-soporte-db")
    parser.add_argument("--gap-days", type=int, default=7)
    parser.add_argument("--reviews", type=Path, help="Curated, already anonymized public seed")
    parser.add_argument("--create-panel", action="store_true")
    parser.add_argument("--panel-size", type=int, default=100)
    args = parser.parse_args()
    store = EvidenceRepository(args.user_id)
    result = import_support_csv(store, args.csv, args.account, gap_days=args.gap_days)
    source_ids = [result["source_id"]]
    if args.reviews:
        reviews = import_reviews_seed(store, args.reviews, privacy_reviewed=True)
        result["reviews_import"] = reviews
        source_ids.append(reviews["source_id"])
    result["eligible_source_chats"] = len(store.eligible_chats(source_ids[0]))
    if args.create_panel:
        # Force local even when .env configures Supabase for the portal.
        use_local_storage()
        set_active_user(args.user_id)
        config.set_user(args.user_id)
        universe_id = "universe_pcmidi_support_" + result["source_id"][-12:]
        existing = find_universe(universe_id)
        if existing and find_latest_expansion(universe_id):
            result["panel"] = {"id": existing.id, "personas": existing.cantidad_personas, "already_saved": True}
        else:
            universe = Universo(universe_id, "PC MIDI Center · escenarios de soporte",
                                "Agentes sintéticos inspirados en escenarios del soporte técnico de PC MIDI Center. "
                                "No son los clientes originales. Datos biográficos desconocidos quedan sin especificar.",
                                args.panel_size, evidence_source_ids=source_ids)
            personas = build_source_population(store, universe, source_ids[0])
            snapshot = build_expansion_snapshot(universe, personas)
            for persona in personas:
                store.register_agent(universe.id, persona.to_dict())
            save_universe(universe)
            save_expansion(universe.id, snapshot)
            result["panel"] = {"id": universe.id, "personas": len(personas), "already_saved": False}
    result["private_database"] = str(store.path)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
