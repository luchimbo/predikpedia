"""
app/pages/biblioteca.py — Biblioteca de estudios para descarga rápida.

Muestra un listado de todos los estudios con sus títulos y permite
descargar resultados individualmente.
"""

import json
import re
from typing import Sequence

import pandas as pd
import streamlit as st

from app.components.shell import render_empty_state, render_page_intro, render_section_title
from app.domain.models import Estudio
from app.services.analysis_service import build_executive_report
from app.state import go_to_page
from app.storage.repository import list_studies, load_study_results


def _safe_filename(titulo: str, estudio_id: str) -> str:
    base = titulo.strip() or estudio_id
    return re.sub(r'[<>:"/\\|?*]', "_", base)


def _render_study_row(estudio: Estudio, idx: int):
    """Renderiza una fila de estudio con info y botones de descarga."""
    resultados = load_study_results(estudio.id)
    cantidad = len(resultados)
    
    with st.container(border=True):
        cols = st.columns([3, 1, 1, 1, 1])
        
        with cols[0]:
            titulo = estudio.titulo or "Sin título"
            st.markdown(f"**{titulo}**")
            st.caption(f"Audiencia: {estudio.universo_nombre} · {estudio.created_at}")
            st.caption(f"Pregunta: {estudio.pregunta[:80]}...")
        
        with cols[1]:
            st.markdown(f"**{cantidad}** respuestas")
        
        with cols[2]:
            if cantidad > 0:
                resultados_df = pd.DataFrame([r.to_dict() for r in resultados])
                csv_bytes = resultados_df.to_csv(index=False).encode("utf-8")
                safe = _safe_filename(estudio.titulo, estudio.id)
                st.download_button(
                    "CSV",
                    data=csv_bytes,
                    file_name=f"{safe}.csv",
                    mime="text/csv",
                    key=f"bib_csv_{idx}",
                    use_container_width=True,
                )
        
        with cols[3]:
            if cantidad > 0:
                json_bytes = json.dumps([r.to_dict() for r in resultados], ensure_ascii=False, indent=2).encode("utf-8")
                safe = _safe_filename(estudio.titulo, estudio.id)
                st.download_button(
                    "JSON",
                    data=json_bytes,
                    file_name=f"{safe}.json",
                    mime="application/json",
                    key=f"bib_json_{idx}",
                    use_container_width=True,
                )
        
        with cols[4]:
            if cantidad > 0:
                resultados_df = pd.DataFrame([r.to_dict() for r in resultados])
                report = build_executive_report(estudio, resultados_df)
                md_bytes = report["markdown"].encode("utf-8")
                safe = _safe_filename(estudio.titulo, estudio.id)
                st.download_button(
                    "Informe",
                    data=md_bytes,
                    file_name=f"{safe}_informe.md",
                    mime="text/markdown",
                    key=f"bib_md_{idx}",
                    use_container_width=True,
                )


def render_biblioteca_tab():
    """Renderiza el tab de biblioteca de estudios."""
    estudios = list_studies()
    if not estudios:
        render_empty_state(
            "No hay estudios",
            "Cuando ejecutes un estudio, aparecerá acá para descargar.",
            cta_text="Ir a Estudios",
            cta_key="bib_go_studies",
            on_cta=lambda: go_to_page("Estudios"),
        )
        return

    # Resumen
    total_estudios = len(estudios)
    total_respuestas = sum(len(load_study_results(e.id)) for e in estudios)
    
    summary_cols = st.columns(2)
    with summary_cols[0]:
        st.metric("Estudios", total_estudios)
    with summary_cols[1]:
        st.metric("Respuestas totales", total_respuestas)
    
    st.divider()
    render_section_title("Listado de estudios")
    
    for idx, estudio in enumerate(estudios):
        _render_study_row(estudio, idx)
