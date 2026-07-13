"""
app/pages/configuracion.py — Página de Configuración.

Migrado desde ui_settings.py, sin presets electorales ni triangulación micro.
"""

import os

import streamlit as st

from app.components.shell import render_page_intro, render_section_title, render_stat_card
from app.config import config
from app.navigation import resolve_provider_label
from app.services.credits_service import CreditsService
from app.state import go_to_page


def render_configuracion_page(*, credits_engine):
    render_page_intro(
        "Configuración",
        "Sistema y acceso",
        "Gestioná API, créditos y rutas de datos fuera del flujo principal de investigación.",
    )

    balance = credits_engine.get_balance()
    balance_usd = credits_engine.get_balance_usd_equiv()
    saved_key = st.session_state.get("saved_api_key", "")
    provider_label = resolve_provider_label(saved_key)

    # Métricas rápidas
    c1, c2, c4 = st.columns(3)
    with c1:
        render_stat_card("Proveedor", provider_label)
    with c2:
        render_stat_card("API key", "Cargada" if saved_key else "Falta")
    with c4:
        render_stat_card("Data dir", str(config.data_dir))

    tab_access, tab_paths = st.tabs(["Acceso", "Rutas"])

    with tab_access:
        render_section_title("Acceso al modelo")
        st.caption("La app utiliza OpenRouter (debe empezar con sk-or).")

        api_key_input = st.text_input(
            "API key",
            type="password",
            value=saved_key,
            key="cfg_api_key",
            placeholder="sk-or-...",
        )
        if api_key_input != saved_key:
            st.session_state["saved_api_key"] = api_key_input
            os.environ["OPENROUTER_API_KEY"] = api_key_input
            st.rerun()

        m1, m2 = st.columns(2)
        with m1:
            render_stat_card("Proveedor detectado", resolve_provider_label(saved_key))
        with m2:
            render_stat_card("Clave cargada", "Sí" if saved_key else "No")

        with st.expander("Ayuda técnica"):
            st.caption("OpenRouter debe empezar con sk-or.")

    with tab_paths:
        render_section_title("Rutas de datos")
        st.caption("Configurá dónde se guardan los datos de la aplicación.")

        current_dir = str(config.data_dir)
        new_dir = st.text_input("Directorio de datos", value=current_dir, key="cfg_data_dir")

        if new_dir != current_dir:
            config.save_settings(data_dir=new_dir)
            st.success(f"Ruta actualizada: {new_dir}")
            st.rerun()

        st.info(f"Ruta actual: {current_dir}")
        st.caption("Podés usar una variable de entorno PREDIKPEDIA_DATA_DIR para sobreescribir esto.")
