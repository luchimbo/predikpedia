"""Private, user-scoped evidence and agent memory. Never writes to tracked data/.

Raw messages stay in this SQLite database. Provider-facing evidence is built from
bounded structured observations or explicitly reviewed summaries, never raw text.
"""

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


PROFILE_KEYS = (
    "perfil", "perfil_descripcion", "arquetipo", "edad_rango", "rol", "industria",
    "objetivo", "principal_pain", "motivador", "objecion_base", "sensibilidad_precio",
    "comportamiento", "canal_preferido", "contexto_operativo", "notas", "evidence_refs",
)


def identity_for(universe_id: str, persona: dict) -> str:
    """Changed profiles get a new identity; P_000001 never collides across panels."""
    profile = {key: persona.get(key, "") for key in PROFILE_KEYS}
    fingerprint = hashlib.sha256(canonical(profile).encode()).hexdigest()
    return str(uuid5(NAMESPACE_URL, f"predikpedia:panel:{universe_id}:{persona['persona_id']}:{fingerprint}"))


class EvidenceRepository:
    def __init__(self, user_id: str, base_dir: Path | str | None = None):
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("Hace falta un usuario para guardar evidencia.")
        base = Path(base_dir or os.getenv("PREDIKPEDIA_PRIVATE_DIR") or (Path.home() / ".predikpedia" / "private"))
        # A UID is an opaque namespace, never a filesystem path.
        self.owner = hashlib.sha256(user_id.encode()).hexdigest()
        self.directory = base.resolve() / self.owner
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.directory / "evidence.sqlite3"
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, label TEXT NOT NULL,
                    file_hash TEXT NOT NULL, account_ref TEXT NOT NULL,
                    imported_at TEXT NOT NULL, stats_json TEXT NOT NULL,
                    UNIQUE(file_hash, account_ref)
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY, account_ref TEXT NOT NULL, chat_ref TEXT NOT NULL,
                    sender_ref TEXT NOT NULL, timestamp_ms INTEGER, direction TEXT NOT NULL,
                    message_type TEXT NOT NULL, text TEXT NOT NULL, content_hash TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS messages_chat ON messages(account_ref, chat_ref, timestamp_ms, id);
                CREATE TABLE IF NOT EXISTS message_sources (
                    message_id TEXT NOT NULL REFERENCES messages(id),
                    source_id TEXT NOT NULL REFERENCES sources(id), row_number INTEGER NOT NULL,
                    PRIMARY KEY(message_id, source_id)
                );
                CREATE TABLE IF NOT EXISTS cases (
                    id TEXT PRIMARY KEY, account_ref TEXT NOT NULL, chat_ref TEXT NOT NULL,
                    kind TEXT NOT NULL, started_ms INTEGER, ended_ms INTEGER,
                    observation_json TEXT NOT NULL, review_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS cases_chat ON cases(account_ref, chat_ref, started_ms, id);
                CREATE TABLE IF NOT EXISTS case_messages (
                    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                    message_id TEXT NOT NULL REFERENCES messages(id), ordinal INTEGER NOT NULL,
                    PRIMARY KEY(case_id, message_id)
                );
                CREATE TABLE IF NOT EXISTS case_sources (
                    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                    source_id TEXT NOT NULL REFERENCES sources(id), PRIMARY KEY(case_id, source_id)
                );
                CREATE TABLE IF NOT EXISTS agents (
                    identity_id TEXT PRIMARY KEY, universe_id TEXT NOT NULL,
                    persona_id TEXT NOT NULL, profile_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memory (
                    id TEXT PRIMARY KEY, identity_id TEXT NOT NULL REFERENCES agents(identity_id),
                    study_id TEXT NOT NULL, kind TEXT NOT NULL,
                    created_at TEXT NOT NULL, payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS memory_agent ON memory(identity_id, created_at, id);
                CREATE TABLE IF NOT EXISTS runs (
                    study_id TEXT PRIMARY KEY, plan_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS run_responses (
                    response_id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES runs(study_id),
                    payload_json TEXT NOT NULL
                );
            """)
            db.execute("INSERT OR IGNORE INTO metadata VALUES ('hmac_secret', ?)", (secrets.token_hex(32),))
            db.execute("INSERT OR IGNORE INTO metadata VALUES ('schema_version', '1')")
            self._secret = bytes.fromhex(db.execute("SELECT value FROM metadata WHERE key='hmac_secret'").fetchone()[0])

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def opaque_id(self, kind: str, *parts: str) -> str:
        digest = hmac.new(self._secret, canonical(list(parts)).encode(), hashlib.sha256).hexdigest()[:32]
        return f"{kind}_{digest}"

    def list_sources(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM sources ORDER BY imported_at DESC, id").fetchall()
        return [{**dict(row), "stats": json.loads(row["stats_json"])} for row in rows]

    def source(self, source_id: str) -> dict | None:
        return next((row for row in self.list_sources() if row["id"] == source_id), None)

    def list_cases(self, source_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("""SELECT c.* FROM cases c JOIN case_sources s ON s.case_id=c.id
                WHERE s.source_id=? ORDER BY c.started_ms DESC, c.id LIMIT ? OFFSET ?""",
                (source_id, min(max(int(limit), 1), 100), max(int(offset), 0))).fetchall()
        return [self._decode_case(row) for row in rows]

    @staticmethod
    def _decode_case(row) -> dict:
        return {**dict(row), "observation": json.loads(row["observation_json"]), "review": json.loads(row["review_json"])}

    def case(self, case_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
        return self._decode_case(row) if row else None

    def case_messages(self, case_id: str, limit: int = 30, offset: int = 0) -> list[dict]:
        """Local review only. Raw text must not enter provider-facing prompts."""
        with self.connect() as db:
            rows = db.execute("""SELECT m.*, cm.ordinal FROM messages m JOIN case_messages cm ON cm.message_id=m.id
                WHERE cm.case_id=? ORDER BY cm.ordinal LIMIT ? OFFSET ?""",
                (case_id, min(max(int(limit), 1), 100), max(int(offset), 0))).fetchall()
        return [dict(row) for row in rows]

    def review_case(self, case_id: str, summary: str, resolution: str, *, reviewed_privacy: bool) -> None:
        from app.services.evidence_service import redact_contacts
        if not reviewed_privacy or not summary.strip():
            raise ValueError("Revisá el caso y escribí un resumen sin datos personales antes de guardarlo.")
        if len(summary) > 1200 or redact_contacts(summary) != summary:
            raise ValueError("El resumen contiene contactos o es demasiado largo. Quitalos y volvé a guardar.")
        if resolution not in {"unknown", "client_confirmed", "client_reports_unresolved"}:
            raise ValueError("Elegí un estado de resolución válido.")
        with self.connect() as db:
            existing = db.execute("SELECT id FROM cases WHERE id=?", (case_id,)).fetchone()
            if not existing:
                raise ValueError("El caso ya no está disponible. Actualizá la lista.")
            review = {"summary": summary.strip(), "resolution": resolution, "reviewed_at": now_iso(),
                      "level": "human_reviewed_source_report", "privacy_reviewed": True}
            db.execute("UPDATE cases SET review_json=? WHERE id=?", (canonical(review), case_id))

    def eligible_chats(self, source_id: str) -> list[str]:
        """One source chat is an evidence scenario, not a verified individual."""
        with self.connect() as db:
            rows = db.execute("""SELECT DISTINCT c.chat_ref, c.observation_json FROM cases c
                JOIN case_sources s ON s.case_id=c.id WHERE s.source_id=? AND c.kind='support'""", (source_id,)).fetchall()
        return sorted({row["chat_ref"] for row in rows if json.loads(row["observation_json"]).get("incoming_themes")})

    def cases_for_chat(self, chat_ref: str, source_id: str, limit: int = 3) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("""SELECT c.* FROM cases c JOIN case_sources s ON s.case_id=c.id
                WHERE c.chat_ref=? AND s.source_id=? ORDER BY c.started_ms DESC, c.id LIMIT ?""",
                (chat_ref, source_id, limit)).fetchall()
        return [self._decode_case(row) for row in rows]

    def register_agent(self, universe_id: str, persona: dict) -> str:
        identity = identity_for(universe_id, persona)
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO agents VALUES (?, ?, ?, ?, ?)",
                       (identity, universe_id, persona["persona_id"], canonical(persona), now_iso()))
        return identity

    def history(self, identity_id: str, *, exclude_study: str = "", limit: int = 6) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("""SELECT * FROM memory WHERE identity_id=? AND study_id!=?
                ORDER BY created_at DESC, id DESC LIMIT ?""", (identity_id, exclude_study, limit)).fetchall()
        return [{"id": row["id"], "kind": row["kind"], "created_at": row["created_at"],
                 **json.loads(row["payload_json"])} for row in reversed(rows)]

    def start_run(self, study_id: str, plan: dict) -> None:
        with self.connect() as db:
            previous = db.execute("SELECT plan_json FROM runs WHERE study_id=?", (study_id,)).fetchone()
            if previous and previous[0] != canonical(plan):
                raise ValueError("Ese estudio ya tiene otro plan guardado. Creá una nueva corrida.")
            db.execute("INSERT OR IGNORE INTO runs VALUES (?, ?, ?)", (study_id, canonical(plan), now_iso()))

    def checkpoint(self, response: dict, *, remember: bool) -> None:
        """Response and simulated memory are committed together; errors never become memories."""
        from app.services.evidence_service import redact_contacts
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO run_responses VALUES (?, ?, ?)",
                       (response["response_id"], response["estudio_id"], canonical(response)))
            valid = bool(response["respuesta"].strip()) and not response["respuesta"].startswith("[ERROR:")
            if remember and valid:
                memory = {"question": redact_contacts(response["pregunta"])[:1000],
                          "response": redact_contacts(response["respuesta"])[:2000],
                          "phase": response["phase"], "exposure_ids": response["exposure_ids"],
                          "evidence_refs": response["evidence_refs"], "origin": "synthetic_output_not_source_fact"}
                db.execute("INSERT OR IGNORE INTO memory VALUES (?, ?, ?, ?, ?, ?)",
                           (response["response_id"], response["identity_id"], response["estudio_id"],
                            "social_response" if response["phase"] == "after_interaction" else "simulated_interview",
                            now_iso(), canonical(memory)))

    def run_responses(self, study_id: str) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT payload_json FROM run_responses WHERE study_id=? ORDER BY rowid", (study_id,)).fetchall()
        return [json.loads(row[0]) for row in rows]
