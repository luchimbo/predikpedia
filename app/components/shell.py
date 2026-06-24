"""
app/components/shell.py — Componentes visuales reutilizables.
"""

from typing import Any, Sequence

import pandas as pd
import streamlit as st


def render_page_intro(kicker: str, title: str, description: str):
    """Header de página con kicker, título y descripción."""
    st.markdown(
        f"""
        <div class="page-intro">
            <div class="page-intro-kicker">{kicker}</div>
            <div class="page-intro-title">{title}</div>
            <div class="page-intro-copy">{description}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_empty_state(
    title: str,
    description: str,
    cta_text: str = "",
    cta_key: str = "",
    on_cta=None,
    icon: str = "",
):
    """Estado vacío con diseño de producto."""
    icon_html = f'<div class="empty-state-icon">{icon}</div>' if icon else ""
    st.markdown(
        f"""
        <div class="empty-state">
            {icon_html}
            <div class="empty-state-title">{title}</div>
            <div class="empty-state-copy">{description}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if cta_text and on_cta:
        # Centrar el botón dentro del empty state
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button(cta_text, key=cta_key, use_container_width=True, type="primary"):
                on_cta()


def render_stat_card(label: str, value: str, detail: str = ""):
    """Tarjeta de métrica estilizada."""
    detail_html = f'<div class="stat-detail">{detail}</div>' if detail else ""
    st.markdown(
        f"""
        <div class="stat-card">
            <div class="stat-label">{label}</div>
            <div class="stat-value">{value}</div>
            {detail_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_title(title: str):
    """Título de sección estilizado."""
    st.markdown(f'<p class="section-title">{title}</p>', unsafe_allow_html=True)


def render_soft_panel(title: str, text: str):
    """Panel suave con título y texto."""
    st.markdown(
        f"""
        <div class='soft-panel'>
            <div class='soft-panel-title'>{title}</div>
            <div class='soft-panel-text'>{text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_stepper(steps: list[str], current_step: int, key_prefix: str = "stepper"):
    """
    Stepper visual horizontal.
    steps: lista de labels
    current_step: índice 1-based del paso activo
    """
    html_parts = ['<div class="stepper">']
    for i, label in enumerate(steps, 1):
        if i < current_step:
            state_class = "completed"
            circle_content = "&#10003;"
        elif i == current_step:
            state_class = "active"
            circle_content = str(i)
        else:
            state_class = ""
            circle_content = str(i)

        step_html = f'<div class="stepper-step {state_class}"><div class="stepper-circle">{circle_content}</div><div class="stepper-label">{label}</div></div>'
        html_parts.append(step_html)
    html_parts.append("</div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def recent_universes_df(universes: Sequence[Any]) -> pd.DataFrame:
    """DataFrame de universos recientes para tablas."""
    rows = []
    for universe in list(universes)[:5]:
        rows.append({
            "Nombre": getattr(universe, "nombre", "-"),
            "Personas": getattr(universe, "cantidad_personas", 0),
            "Perfiles": len(getattr(universe, "perfiles", []) or []),
            "Creado": getattr(universe, "created_at", "-"),
        })
    return pd.DataFrame(rows)


def recent_studies_df(studies: Sequence[Any]) -> pd.DataFrame:
    """DataFrame de estudios recientes para tablas."""
    rows = []
    for study in list(studies)[:5]:
        rows.append({
            "Audiencia": getattr(study, "universo_nombre", "-"),
            "Pregunta": str(getattr(study, "pregunta", ""))[:70],
            "RPP": getattr(study, "respuestas_por_persona", 0),
            "Creado": getattr(study, "created_at", "-"),
        })
    return pd.DataFrame(rows)
