"""
app/pages/reportes.py — Página de Reportes con historial y comparación.

1. Lista de estudios guardados
2. Filtros por audiencia, fecha, template
3. Comparación entre estudios
4. Exportes presentables
"""

import json
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from app.components.shell import render_empty_state, render_page_intro, render_section_title, render_stat_card
from app.services.analysis_service import build_executive_report
from app.state import get, go_to_page
from app.storage.repository import list_studies, load_study_results


def render_reportes_tab():
    """Renderiza el tab de comparación de estudios."""
    estudios = list_studies()
    if not estudios:
        render_empty_state(
            "No hay estudios guardados",
            "Cuando ejecutes estudios, van a aparecer acá.",
            cta_text="Ir a Estudios",
            cta_key="rep_go_studies",
            on_cta=lambda: go_to_page("Estudios"),
        )
        return

    # ── Filtros ──────────────────────────────────────────────────
    render_section_title("Biblioteca de estudios")

    universos = sorted({e.universo_nombre for e in estudios})
    templates = sorted({e.template for e in estudios})

    c1, c2 = st.columns(2)
    with c1:
        filtro_universo = st.selectbox("Filtrar por audiencia", ["Todos"] + universos, key="rep_filter_univ")
    with c2:
        filtro_template = st.selectbox("Filtrar por template", ["Todos"] + templates, key="rep_filter_tmpl")

    filtrados = estudios
    if filtro_universo != "Todos":
        filtrados = [e for e in filtrados if e.universo_nombre == filtro_universo]
    if filtro_template != "Todos":
        filtrados = [e for e in filtrados if e.template == filtro_template]

    # ── Tabla de estudios ────────────────────────────────────────
    if filtrados:
        df = pd.DataFrame([
            {
                "ID": e.id,
                "Audiencia": e.universo_nombre,
                "Pregunta": e.pregunta[:60] + "..." if len(e.pregunta) > 60 else e.pregunta,
                "Template": e.template,
                "RPP": e.respuestas_por_persona,
                "Creado": e.created_at,
            }
            for e in filtrados
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No hay estudios para los filtros seleccionados.")

    # ── Comparación ──────────────────────────────────────────────
    st.divider()
    render_section_title("Comparar estudios")

    if len(filtrados) >= 2:
        estudio_options = {f"{e.universo_nombre}: {e.pregunta[:40]}... ({e.template})": e for e in filtrados}

        c1, c2 = st.columns(2)
        with c1:
            sel_a = st.selectbox("Estudio A", list(estudio_options.keys()), key="rep_cmp_a")
        with c2:
            sel_b = st.selectbox("Estudio B", list(estudio_options.keys()), key="rep_cmp_b", index=min(1, len(estudio_options)-1))

        if sel_a != sel_b:
            est_a = estudio_options[sel_a]
            est_b = estudio_options[sel_b]

            res_a = load_study_results(est_a.id)
            res_b = load_study_results(est_b.id)

            if res_a and res_b:
                df_a = pd.DataFrame([r.to_dict() for r in res_a])
                df_b = pd.DataFrame([r.to_dict() for r in res_b])

                report_a = build_executive_report(est_a, df_a)
                report_b = build_executive_report(est_b, df_b)

                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**{est_a.template}**")
                    st.caption(report_a["conclusion"])
                    render_stat_card("Respuestas", str(len(df_a)))
                    if report_a["insights"]:
                        st.markdown("**Top insight:**")
                        st.info(report_a["insights"][0]["hallazgo"])

                with c2:
                    st.markdown(f"**{est_b.template}**")
                    st.caption(report_b["conclusion"])
                    render_stat_card("Respuestas", str(len(df_b)))
                    if report_b["insights"]:
                        st.markdown("**Top insight:**")
                        st.info(report_b["insights"][0]["hallazgo"])
            else:
                st.warning("Uno o ambos estudios no tienen resultados cargados.")
        else:
            st.info("Seleccioná dos estudios distintos para comparar.")
    else:
        st.info("Necesitás al menos 2 estudios para comparar.")
