"""
predikpedia.py — Entrypoint Principal
"""

import os

from dotenv import load_dotenv
import streamlit as st

load_dotenv()

from app.config import config
from app.navigation import render_sidebar, resolve_provider_label
from app.state import init_state
from app.storage.repository import list_studies, list_universes, set_active_user
from app.theme import GLOBAL_CSS
from app.pages.home import render_home_page
from app.pages.audiencias import render_audiencias_page
from app.pages.estudios import render_estudios_page
from app.pages.resultados import render_resultados_page
from app.pages.preguntas import render_preguntas_page
from app.pages.biblioteca import render_biblioteca_page
from app.pages.reportes import render_reportes_page
from app.pages.configuracion import render_configuracion_page
from app.services.credits_service import CreditsService

# ── Inicialización ──────────────────────────────────────────────────────────

# Leer user_id del query param (pasado desde Vercel al hacer redirect)
_params = st.query_params
_user_id = _params.get("uid", "")
if _user_id:
    config.set_user(_user_id)
    set_active_user(_user_id)
else:
    config.ensure_directories()

init_state()

saved_key = st.session_state.get("saved_api_key", "")
if not saved_key:
    saved_key = os.getenv("OPENROUTER_API_KEY", "")
    st.session_state["saved_api_key"] = saved_key

if saved_key:
    os.environ["OPENROUTER_API_KEY"] = saved_key

if st.session_state.get("credits_engine") is None:
    st.session_state["credits_engine"] = CreditsService(
        user_id=st.session_state.get("settings_user_id", "demo_user")
    )

credits_engine = st.session_state["credits_engine"]

# ── Configuración de página ─────────────────────────────────────────────────

st.set_page_config(
    page_title="Predikpedia",
    layout="wide",
    page_icon="⬡",
    initial_sidebar_state="expanded",
)

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ── Sidebar ─────────────────────────────────────────────────────────────────

render_sidebar(
    balance_now=credits_engine.get_balance(),
    saved_api_key=saved_key,
)

# ── Routing ─────────────────────────────────────────────────────────────────

current_page = st.session_state.get("current_page", "Inicio")
provider_label = resolve_provider_label(saved_key)

if current_page == "Inicio":
    render_home_page(
        balance_now=credits_engine.get_balance(),
        has_api_key=bool(saved_key),
        provider_label=provider_label,
        universes=list_universes(),
        studies=list_studies(),
    )
elif current_page == "Audiencias":
    render_audiencias_page()
elif current_page == "Estudios":
    render_estudios_page()
elif current_page == "Resultados":
    render_resultados_page()
elif current_page == "Preguntas":
    render_preguntas_page()
elif current_page == "Biblioteca":
    render_biblioteca_page()
elif current_page == "Reportes":
    render_reportes_page()
elif current_page == "Configuración":
    render_configuracion_page(credits_engine=credits_engine)
