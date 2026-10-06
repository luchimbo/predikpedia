"""Read-only source import, provisional support episodes and safe observations.

No LLM calls during import. Messages are data, never executable instructions.
"""

import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from app.domain.models import PerfilCliente, PersonaSintetica, Universo
from app.storage.evidence_repository import EvidenceRepository, canonical, identity_for, now_iso


THEMES = {
    "Conexión USB/MIDI/Bluetooth": r"\b(?:usb|midi|bluetooth|conectar|conectado|conexion)\b",
    "Software, instalación y drivers": r"\b(?:drivers?|asio|daw|ableton|cubase|reaper|fl\s*studio|instalar|instalacion)\b",
    "Audio, señal y latencia": r"\b(?:latencia|ruido|sonido|audio|senal|no\s+suena|no\s+se\s+escucha)\b",
    "Garantía y reparación": r"\b(?:garantia|reparar|reparacion|service|servicio\s+tecnico)\b",
    "Fuentes, cables y repuestos": r"\b(?:repuestos?|fuente|transformador|adaptador|cables?)\b",
    "Referencias a compra, precio o envío": r"\b(?:precio|comprar|compra|compre|envio|stock|cuotas|mercado\s*libre)\b",
}
_THEME_PATTERNS = {name: re.compile(pattern) for name, pattern in THEMES.items()}
PRODUCTS = {
    "MiniFuse": r"\bmini\s*fuse\b", "Medeli": r"\bmedeli\b", "AstroLab": r"\bastro\s*lab\b",
    "Arturia": r"\barturia\b", "Focusrite": r"\bfocusrite\b", "Scarlett": r"\bscarlett\b",
    "Novation": r"\bnovation\b", "M-Audio": r"\bm[-\s]?audio\b", "Behringer": r"\bbehringer\b",
    "Ableton": r"\bableton\b", "Cubase": r"\bcubase\b", "Reaper": r"\breaper\b",
    "FL Studio": r"\bfl\s*studio\b", "Windows": r"\bwindows\b", "macOS": r"\b(?:macos|mac\s*os)\b",
}
_PRODUCT_PATTERNS = {name: re.compile(pattern) for name, pattern in PRODUCTS.items()}
_RESOLUTION_CUE = re.compile(r"\b(?:ahora funciona|ya funciona|quedo solucionado|quedo resuelto|ya esta funcionando|se soluciono)\b")
_NEGATION = re.compile(r"\b(?:no|nunca|tampoco|todavia|aun|ojala|si|cuando)\b")


def fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


def present(text) -> bool:
    return text is not None and str(text).strip().lower() not in {"", "null", "none"}


def redact_contacts(text: str) -> str:
    """Best-effort aid for local review, NOT certification that free text is anonymous."""
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email]", text)
    text = re.sub(r"https?://\S+|www\.\S+", "[enlace]", text, flags=re.I)
    text = re.sub(r"(?<!\w)\+?\d[\d\s()./-]{6,}\d(?!\w)", "[número]", text)
    text = re.sub(r"\b[0-9a-f]{24,}\b", "[identificador]", text, flags=re.I)
    return text


def _timestamp(value: str) -> int | None:
    if not present(value):
        return None
    try:
        stamp = int(value)
        if stamp <= 0:
            return None
        datetime.fromtimestamp(stamp / 1000, timezone.utc)
        return stamp
    except (ValueError, OverflowError, OSError):
        raise ValueError("Hay fechas inválidas en el archivo. Revisá la columna timestamp.") from None


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def import_support_csv(store: EvidenceRepository, path: Path | str, account: str, *, gap_days: int = 7) -> dict:
    """Atomic and idempotent per owner/account/file. Account names identify a DB lineage.

    Stable key_id deduplicates messages. chat_row_id is only assumed stable inside
    that declared export lineage; it is never joined to reviews or a real person.
    """
    path = Path(path)
    if not account.strip() or len(account) > 120 or not 1 <= gap_days <= 90:
        raise ValueError("Definí el origen de la exportación y un intervalo entre 1 y 90 días.")
    digest = _file_hash(path)
    account_ref = store.opaque_id("account", account.strip())
    source_id = store.opaque_id("source", account_ref, digest)
    csv.field_size_limit(10_000_000)
    with store.connect() as db:
        existing = db.execute("SELECT stats_json FROM sources WHERE id=?", (source_id,)).fetchone()
        if existing:
            stats = json.loads(existing[0])
            if stats["gap_days"] != gap_days:
                raise ValueError("Ese archivo ya fue importado con otro intervalo. Conservá la segmentación existente.")
            return {"source_id": source_id, "already_imported": True, **stats,
                    "new_messages": 0, "duplicate_messages": 0, "content_conflicts": 0}
        db.execute("INSERT INTO sources VALUES (?, 'support_csv', ?, ?, ?, ?, '{}')",
                   (source_id, path.name, digest, account_ref, now_iso()))
        stats = Counter()
        chat_refs = set()
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"_id", "chat_row_id", "from_me", "timestamp", "text_data"}
            if not required.issubset(reader.fieldnames or []):
                raise ValueError("El CSV necesita _id, chat_row_id, from_me, timestamp y text_data. Exportá esos campos y volvé a importar.")
            for row_number, row in enumerate(reader, 2):
                stats["records"] += 1
                try:
                    chat_number = int(row["chat_row_id"])
                except (ValueError, TypeError):
                    raise ValueError(f"La fila {row_number} tiene un chat_row_id inválido.") from None
                if chat_number < 0:
                    stats["system_records"] += 1
                    continue
                if row["from_me"] not in {"0", "1"} or not present(row["_id"]):
                    raise ValueError(f"La fila {row_number} tiene dirección o identificador inválidos.")
                chat_ref = store.opaque_id("chat", account_ref, str(chat_number))
                chat_refs.add(chat_ref)
                direction = "incoming" if row["from_me"] == "0" else "outgoing"
                text = row["text_data"] if present(row["text_data"]) else ""
                timestamp = _timestamp(row["timestamp"])
                if timestamp is None:
                    stats["undated_records"] += 1
                if text:
                    stats["text_records"] += 1
                else:
                    stats["without_text"] += 1
                key = row.get("key_id")
                if not present(key) or key == "-1":
                    key = row["_id"]
                message_id = store.opaque_id("msg", account_ref, chat_ref, direction, key)
                sender = store.opaque_id("sender", account_ref, row.get("sender_jid_row_id") or "unknown")
                body_hash = hashlib.sha256(canonical([timestamp, direction, text, row.get("message_type", "")]).encode()).hexdigest()
                prior = db.execute("SELECT content_hash FROM messages WHERE id=?", (message_id,)).fetchone()
                if prior and prior[0] != body_hash:
                    # Preserve both versions instead of silently overwriting evidence.
                    message_id = store.opaque_id("msg", message_id, body_hash)
                    stats["content_conflicts"] += 1
                cursor = db.execute("INSERT OR IGNORE INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                    (message_id, account_ref, chat_ref, sender, timestamp, direction,
                                     row.get("message_type") or "unknown", text, body_hash))
                stats["new_messages"] += cursor.rowcount
                stats["duplicate_messages"] += 1 - cursor.rowcount
                db.execute("INSERT OR IGNORE INTO message_sources VALUES (?, ?, ?)", (message_id, source_id, row_number))
        cases = _build_cases(db, store, source_id, account_ref, gap_days)
        result = {**{key: stats[key] for key in ("records", "system_records", "text_records", "without_text", "undated_records",
                   "new_messages", "duplicate_messages", "content_conflicts")},
                  "chats": len(chat_refs), "cases": cases, "gap_days": gap_days,
                  "extractor_version": "support_mentions_v1", "identity_status": "conversation_unverified",
                  "episode_status": "provisional_time_gap_not_validated_case"}
        db.execute("UPDATE sources SET stats_json=? WHERE id=?", (canonical(result), source_id))
    return {"source_id": source_id, "already_imported": False, **result}


def _build_cases(db, store, source_id: str, account_ref: str, gap_days: int) -> int:
    rows = db.execute("""SELECT m.*, s.row_number FROM messages m JOIN message_sources s ON s.message_id=m.id
        WHERE s.source_id=? ORDER BY m.chat_ref, m.timestamp_ms IS NULL, m.timestamp_ms, s.row_number""", (source_id,))
    count, group, previous_chat, previous_stamp = 0, [], None, None
    for row in rows:
        stamp = row["timestamp_ms"]
        new = row["chat_ref"] != previous_chat or (
            group and ((stamp is None) != (previous_stamp is None) or
                       (stamp is not None and previous_stamp is not None and stamp - previous_stamp > gap_days * 86400000)))
        if new and group:
            _save_case(db, store, source_id, account_ref, group)
            count += 1
            group = []
        group.append(dict(row))
        previous_chat, previous_stamp = row["chat_ref"], stamp
    if group:
        _save_case(db, store, source_id, account_ref, group)
        count += 1
    return count


def _save_case(db, store, source_id: str, account_ref: str, messages: list[dict]) -> None:
    # Immutable membership protects saved panel bindings when a later export adds messages.
    case_id = store.opaque_id("case", account_ref, canonical([m["id"] for m in messages]))
    party_themes = {"incoming": set(), "outgoing": set()}
    products = {"incoming": set(), "outgoing": set()}
    refs, resolution_refs = {}, []
    for message in messages:
        folded = fold(message["text"])
        direction = message["direction"]
        for theme, pattern in _THEME_PATTERNS.items():
            if pattern.search(folded):
                party_themes[direction].add(theme)
                refs.setdefault(theme, []).append(message["id"])
        products[direction].update(name for name, pattern in _PRODUCT_PATTERNS.items() if pattern.search(folded))
        if direction == "incoming":
            for sentence in re.split(r"[.!?\n]", folded):
                if _RESOLUTION_CUE.search(sentence) and not _NEGATION.search(sentence):
                    resolution_refs.append(message["id"])
                    break
    observation = {
        "incoming_themes": sorted(party_themes["incoming"]), "support_themes": sorted(party_themes["outgoing"]),
        "incoming_product_mentions": sorted(products["incoming"]), "support_product_mentions": sorted(products["outgoing"]),
        "message_count": len(messages), "without_text": sum(not m["text"] for m in messages),
        "incoming_count": sum(m["direction"] == "incoming" for m in messages),
        "resolution": "unknown", "possible_resolution_message_refs": resolution_refs[:10],
        "theme_message_refs": {theme: ids[:5] for theme, ids in refs.items()},
        "identity_status": "conversation_unverified", "episode_status": "provisional",
        "evidence_level": "keyword_mentions_not_confirmed_problem",
        "extractor_version": "support_mentions_v1",
    }
    dated = [m["timestamp_ms"] for m in messages if m["timestamp_ms"] is not None]
    db.execute("INSERT OR IGNORE INTO cases(id, account_ref, chat_ref, kind, started_ms, ended_ms, observation_json) VALUES (?, ?, ?, 'support', ?, ?, ?)",
               (case_id, account_ref, messages[0]["chat_ref"], min(dated) if dated else None,
                max(dated) if dated else None, canonical(observation)))
    db.executemany("INSERT OR IGNORE INTO case_messages VALUES (?, ?, ?)", [(case_id, m["id"], i) for i, m in enumerate(messages)])
    db.execute("INSERT OR IGNORE INTO case_sources VALUES (?, ?)", (case_id, source_id))


def import_reviews_seed(store: EvidenceRepository, path: Path | str, *, privacy_reviewed: bool = False) -> dict:
    """Import the curated public seed separately; never merge identities with support."""
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "predikpedia.evidence_seed/v1" or payload.get("source_type") != "google_business_reviews":
        raise ValueError("El archivo no tiene el formato de reseñas de Predikpedia.")
    reviews = payload.get("reviews")
    if not isinstance(reviews, list) or not reviews:
        raise ValueError("El archivo no contiene reseñas.")
    source_hash = _file_hash(path)
    account_ref = store.opaque_id("account", "public-reviews", str(payload.get("business", "")))
    source_id = store.opaque_id("source", account_ref, source_hash)
    with store.connect() as db:
        old = db.execute("SELECT stats_json FROM sources WHERE id=?", (source_id,)).fetchone()
        if old:
            return {"source_id": source_id, "already_imported": True, **json.loads(old[0])}
        stats = {"reviews": len(reviews), "coverage": payload.get("coverage", "Muestra no aleatoria"),
                 "captured_on": payload.get("captured_on", ""), "privacy_reviewed": privacy_reviewed}
        db.execute("INSERT INTO sources VALUES (?, 'public_reviews', ?, ?, ?, ?, ?)",
                   (source_id, path.name, source_hash, account_ref, now_iso(), canonical(stats)))
        for review in reviews:
            customer = review.get("customer_report_summary")
            business = review.get("business_response_summary") or ""
            themes = review.get("themes") or []
            if not isinstance(customer, str) or not isinstance(business, str) or not isinstance(themes, list) or any(not isinstance(t, str) for t in themes):
                raise ValueError("Hay una reseña sin resumen o con campos inválidos.")
            if privacy_reviewed and (redact_contacts(customer) != customer or redact_contacts(business) != business):
                raise ValueError("Hay contactos en las reseñas. Anonimizalos antes de importarlas.")
            case_id = store.opaque_id("review", source_id, str(review.get("id", "")))
            observation = {"public_customer_report": customer, "business_response": business,
                           "themes": themes, "date_label": review.get("date_label", ""),
                           "captured_on": payload.get("captured_on", ""), "evidence_level": "public_unverified_report",
                           "scope": "general_context_not_personal_history"}
            checked = {"privacy_reviewed": privacy_reviewed}
            db.execute("INSERT INTO cases VALUES (?, ?, '', 'review', NULL, NULL, ?, ?)",
                       (case_id, account_ref, canonical(observation), canonical(checked)))
            db.execute("INSERT INTO case_sources VALUES (?, ?)", (case_id, source_id))
    return {"source_id": source_id, "already_imported": False, **stats}


def build_source_population(store: EvidenceRepository, universe: Universo, source_id: str) -> list[PersonaSintetica]:
    if not store.source(source_id) or store.source(source_id)["kind"] != "support_csv":
        raise ValueError("Elegí una fuente de soporte importada para generar la audiencia.")
    chats = store.eligible_chats(source_id)
    if not 1 <= universe.cantidad_personas <= len(chats):
        raise ValueError(f"La fuente tiene {len(chats)} chats con menciones temáticas. Reducí la cantidad de personas.")
    # Stable shuffled selection, without replacement; no multiplication of evidence.
    chats.sort(key=lambda chat: hashlib.sha256(f"{universe.id}:{chat}".encode()).hexdigest())
    personas, counts = [], Counter()
    for number, chat in enumerate(chats[:universe.cantidad_personas], 1):
        cases = store.cases_for_chat(chat, source_id)
        themes = sorted({theme for case in cases for theme in case["observation"]["incoming_themes"]})
        profile = themes[0] if themes else "Soporte sin tema especificado"
        counts[profile] += 1
        persona = PersonaSintetica(
            persona_id=store.opaque_id("synthetic", universe.id, chat), persona_numero=number,
            universo_id=universe.id, universo_nombre=universe.nombre,
            perfil=profile, perfil_descripcion="Escenario sintético inspirado en menciones de soporte; no representa al autor original.",
            perfil_porcentaje_objetivo=0,
            edad_rango="No especificado", rol="No especificado", industria="No especificado",
            objetivo="No especificado", principal_pain="Antecedentes de consulta: " + "; ".join(themes),
            motivador="No especificado", objecion_base="No especificado", sensibilidad_precio="No especificado",
            comportamiento="No especificado", canal_preferido="Mensajería de soporte (origen del escenario)",
            contexto_operativo=universe.descripcion, notas="Las menciones no prueban propiedad del equipo ni problema resuelto. No inferir biografía.",
            evidence_refs=[case["id"] for case in cases], evidence_source_ids=list(universe.evidence_source_ids),
        )
        persona.identity_id = identity_for(universe.id, persona.to_dict())
        personas.append(persona)
    universe.perfiles = [PerfilCliente(name, "Composición del panel seleccionado; no proporción de la clientela.", count * 100 / len(personas))
                         for name, count in sorted(counts.items())]
    for persona in personas:
        persona.perfil_porcentaje_objetivo = counts[persona.perfil] * 100 / len(personas)
    return personas


def evidence_for_persona(store: EvidenceRepository, persona: dict, *, limit: int = 6) -> list[dict]:
    """Only allowlisted observations and reviewed summaries can leave private storage."""
    evidence = []
    for case_ref in persona.get("evidence_refs", [])[:limit]:
        case = store.case(case_ref)
        if not case or case["kind"] != "support":
            continue
        data, review = case["observation"], case["review"]
        item = {"case_ref": case_ref, "scope": "assigned_synthetic_scenario_not_original_person",
                "incoming_mentions": data.get("incoming_themes", []), "support_mentions": data.get("support_themes", []),
                "incoming_product_mentions": data.get("incoming_product_mentions", []),
                "support_product_mentions": data.get("support_product_mentions", []),
                "evidence_level": data["evidence_level"], "resolution": "unknown",
                "started_ms": case["started_ms"], "ended_ms": case["ended_ms"],
                "missing_text_messages": data["without_text"]}
        if review.get("privacy_reviewed") and review.get("summary"):
            item.update({"reviewed_summary": review["summary"], "resolution": review["resolution"], "evidence_level": review["level"]})
        evidence.append(item)
    for source_id in persona.get("evidence_source_ids", []):
        source = store.source(source_id)
        if source and source["kind"] == "public_reviews":
            for case in store.list_cases(source_id, limit=3):
                if case["review"].get("privacy_reviewed"):
                    evidence.append({"case_ref": case["id"], **case["observation"]})
    return evidence[:limit]
