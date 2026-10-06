"""Source import and case review, embedded in Audiencias without new navigation."""

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from app.services.evidence_service import import_support_csv, redact_contacts
from app.storage.evidence_repository import EvidenceRepository


def session_store() -> EvidenceRepository | None:
    # The existing portal's uid query is not proof of authentication. Private
    # source review is enabled only on an explicitly loopback-bound server.
    if not st.session_state.get("private_storage_available", False):
        return None
    return EvidenceRepository(st.session_state["data_owner_id"])


def render_evidence_panel(store: EvidenceRepository) -> None:
    with st.expander("Fuentes de soporte y revisión de casos"):
        st.caption("Importá el CSV una sola vez. Los mensajes quedan en este equipo; los agentes reciben menciones estructuradas o resúmenes revisados.")
        uploaded = st.file_uploader("Exportación de soporte", type=["csv"], key="evidence_upload")
        account = st.text_input("Origen de la exportación", value="pc-midi-soporte-db", key="evidence_account",
                                help="Usá el mismo nombre solo para exportaciones de la misma base. Los IDs de chat pueden cambiar entre bases.")
        if st.button("Importar soporte", key="evidence_import", disabled=uploaded is None):
            try:
                with tempfile.TemporaryDirectory(prefix="predikpedia-source-") as directory:
                    path = Path(directory) / Path(uploaded.name).name
                    path.write_bytes(uploaded.getvalue())
                    with st.spinner("Importando mensajes y preparando episodios…"):
                        result = import_support_csv(store, path, account)
                st.session_state["evidence_import_result"] = result
            except (ValueError, OSError) as exc:
                st.error(f"No se pudo importar el archivo: {exc}")
        result = st.session_state.get("evidence_import_result")
        if result:
            action = "Archivo ya importado" if result["already_imported"] else "Fuente importada"
            st.success(f"{action}: {result['chats']} chats y {result['cases']} episodios provisionales")
        sources = [s for s in store.list_sources() if s["kind"] == "support_csv"]
        if not sources:
            st.info("Importá una exportación de soporte para crear audiencias con antecedentes de origen.")
            return
        source_id = st.selectbox("Fuente a revisar", [s["id"] for s in sources],
                                 format_func=lambda sid: next(s["label"] for s in sources if s["id"] == sid), key="evidence_review_source")
        source = store.source(source_id)
        stats = source["stats"]
        st.caption(f"{stats['text_records']} registros con texto · {stats['without_text']} sin texto · intervalo de {stats['gap_days']} días para proponer episodios")
        page = int(st.number_input("Página de casos", min_value=1, value=1, step=1, key=f"evidence_page_{source_id}"))
        cases = store.list_cases(source_id, limit=30, offset=(page - 1) * 30)
        if not cases:
            st.info("No hay casos en esta página. Volvé a una página anterior.")
            return
        case_id = st.selectbox("Episodio provisional", [c["id"] for c in cases], key=f"evidence_case_{source_id}_{page}",
                               format_func=lambda cid: "; ".join(next(c for c in cases if c["id"] == cid)["observation"]["incoming_themes"])[:110] or cid[:20])
        case = store.case(case_id)
        st.json(case["observation"], expanded=False)
        st.caption("Las menciones y posibles frases de resolución necesitan revisión. No confirman identidad individual ni solución.")
        message_page = int(st.number_input("Página de mensajes del caso", min_value=1, value=1, step=1, key=f"evidence_messages_{case_id}"))
        messages = store.case_messages(case_id, limit=30, offset=(message_page - 1) * 30)
        st.caption("Vista local con contactos ocultos automáticamente. Revisá también nombres, direcciones y cualquier otro dato identificable antes de resumir.")
        st.dataframe(pd.DataFrame([{"Referencia": m["id"], "Dirección": m["direction"], "Fecha Unix ms": m["timestamp_ms"],
                                   "Texto para revisión local": redact_contacts(m["text"])} for m in messages]),
                     use_container_width=True, hide_index=True)
        with st.form(f"evidence_review_{case_id}"):
            summary = st.text_area("Resumen revisado sin datos personales", value=case["review"].get("summary", ""), max_chars=1200,
                                   help="Separá el problema declarado, los intentos y la respuesta del soporte. No agregues datos que el chat no sustenta.")
            options = {"unknown": "Resolución desconocida", "client_confirmed": "El cliente confirma la solución",
                       "client_reports_unresolved": "El cliente informa que sigue sin resolver"}
            current = case["review"].get("resolution", "unknown")
            resolution = st.selectbox("Estado del caso", list(options), format_func=options.get,
                                      index=list(options).index(current))
            checked = st.checkbox("Revisé el contexto y quité los datos que identifican a las personas")
            if st.form_submit_button("Guardar revisión"):
                try:
                    store.review_case(case_id, summary, resolution, reviewed_privacy=checked)
                    st.success("Revisión guardada. El resumen podrá usarse como evidencia del escenario sintético.")
                except ValueError as exc:
                    st.error(str(exc))
