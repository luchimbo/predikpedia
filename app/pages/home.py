"""
app/pages/home.py — Página de inicio.
"""

from typing import Sequence

import streamlit as st

from app.components.shell import render_page_intro, render_stat_card
from app.navigation import resolve_provider_label


def render_home_page(
    *,
    balance_now: float,
    has_api_key: bool,
    provider_label: str,
    universes: Sequence,
    studies: Sequence,
):
    """Renderiza la página de inicio."""
    total_universes = len(universes)
    total_studies = len(studies)

    # Determinar siguiente paso recomendado
    if not has_api_key:
        next_action = "Configurar API key"
        next_copy = "Cargá OpenRouter o Gemini para poder ejecutar respuestas sintéticas."
        next_page = "Configuración"
    elif total_universes == 0:
        next_action = "Crear audiencia"
        next_copy = "Empezá definiendo a quién querés investigar."
        next_page = "Audiencias"
    else:
        next_action = "Nuevo estudio"
        next_copy = "Usá una audiencia guardada, escribí una pregunta y ejecutá el estudio."
        next_page = "Estudios"

    # Header
    render_page_intro(
        "Workspace de research sintético",
        "Investigá audiencias, corré estudios y leé decisiones sin ruido técnico.",
        "Predikpedia organiza el flujo en tres momentos: crear audiencia, ejecutar un estudio y convertir respuestas en lectura accionable.",
    )

    # Stats
    c1, c2, c3 = st.columns(3)
    with c1:
        render_stat_card("Audiencias", str(total_universes))
    with c2:
        render_stat_card("Estudios", str(total_studies))
    with c3:
        render_stat_card("Proveedor", provider_label)

    # Siguiente paso
    st.divider()
    action_col, context_col = st.columns(2)

    with action_col:
        st.subheader("Siguiente paso recomendado")
        st.write(f"**{next_action}**")
        st.caption(next_copy)
        if st.button(next_action, key="home_primary_cta", use_container_width=True, type="primary"):
            st.session_state.current_page = next_page
            st.rerun()

    with context_col:
        st.subheader("Estado operativo")
        status_text = "Lista" if has_api_key else "Falta configurar API key"
        st.write(f"**API:** {status_text}")

    # Accesos rápidos
    st.divider()
    st.subheader("Accesos rápidos")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Crear audiencia", key="home_sec_universos", use_container_width=True):
            st.session_state.current_page = "Audiencias"
            st.rerun()
    with c2:
        if st.button("Ver resultados", key="home_sec_results", use_container_width=True):
            st.session_state.current_page = "Resultados"
            st.rerun()
    with c3:
        if st.button("Configuración", key="home_sec_settings", use_container_width=True):
            st.session_state.current_page = "Configuración"
            st.rerun()

    # Tablas recientes
    st.divider()
    if universes:
        st.subheader("Audiencias recientes")
        st.dataframe(recent_universes_df(universes), use_container_width=True, hide_index=True)
    else:
        st.info("No hay audiencias guardadas. Creá una audiencia para empezar el flujo principal.")
        if st.button("Crear audiencia", key="home_empty_cta", use_container_width=True):
            st.session_state.current_page = "Audiencias"
            st.rerun()

    if studies:
        st.subheader("Estudios recientes")
        st.dataframe(recent_studies_df(studies), use_container_width=True, hide_index=True)
    else:
        st.info("Cuando ejecutes estudios, van a aparecer acá.")


def recent_universes_df(universes):
    """DataFrame de universos recientes para tablas."""
    import pandas as pd
    rows = []
    for universe in list(universes)[:5]:
        rows.append({
            "Nombre": getattr(universe, "nombre", "-"),
            "Personas": getattr(universe, "cantidad_personas", 0),
            "Perfiles": len(getattr(universe, "perfiles", []) or []),
            "Creado": getattr(universe, "created_at", "-"),
        })
    return pd.DataFrame(rows)


def recent_studies_df(studies):
    """DataFrame de estudios recientes para tablas."""
    import pandas as pd
    rows = []
    for study in list(studies)[:5]:
        rows.append({
            "Audiencia": getattr(study, "universo_nombre", "-"),
            "Pregunta": str(getattr(study, "pregunta", ""))[:70],
            "RPP": getattr(study, "respuestas_por_persona", 0),
            "Creado": getattr(study, "created_at", "-"),
        })
    return pd.DataFrame(rows)
