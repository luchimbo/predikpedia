"""
app/state.py — Capa central de estado de la aplicación.
"""

from typing import Any

import streamlit as st


STATE_KEYS = {
    "current_page": "Inicio",
    "active_universe_id": "",
    "active_study_id": "",
    "active_results_id": "",
    "saved_api_key": "",
    "settings_user_id": "demo_user",
    "settings_data_dir": "",
    "run_status": "idle",
    "last_error": "",
    "credits_engine": None,
    "wiz_audience_step": 1,
    "wiz_audience_universe_id": "",
    "wiz_study_step": 1,
    "wiz_study_template": "",
    "tmp_expansion_personas": [],
    "tmp_study_results": [],
    "tmp_last_study": None,
}


def init_state():
    """Inicializa todas las claves de estado con sus valores por defecto."""
    for key, default in STATE_KEYS.items():
        if key not in st.session_state:
            st.session_state[key] = default


def get(key: str, default: Any = None) -> Any:
    return st.session_state.get(key, default)


def set(key: str, value: Any):
    st.session_state[key] = value


def go_to_page(page: str):
    """Cambia la página actual y fuerza rerun."""
    st.session_state["current_page"] = page
    st.rerun()
