"""
predikpedia.py — Entrypoint Principal
"""

import os

from dotenv import load_dotenv
import streamlit as st

load_dotenv()

from app.config import config
from app.navigation import render_sidebar
from app.state import init_state
from app.storage.repository import (
    list_studies,
    list_universes,
    set_active_user,
    use_local_storage,
)
from app.theme import GLOBAL_CSS
from app.pages.home import render_home_page
from app.pages.audiencias import render_audiencias_page
from app.pages.estudios import render_estudios_page
from app.pages.resultados import render_resultados_page
from app.pages.configuracion import render_configuracion_page
from app.services.credits_service import CreditsService
from app.services.llm_service import LLMService

# ── Inicialización ──────────────────────────────────────────────────────────

# Leer user_id del query param (pasado desde Vercel al hacer redirect)
_params = st.query_params
_user_id = _params.get("uid", "")
if _user_id:
    config.set_user(_user_id)
else:
    # Al abrir Streamlit directamente, conservar los datos en este equipo y
    # aislarlos del storage remoto que usa el redirect autenticado de Vercel.
    _user_id = os.getenv("PREDIKPEDIA_DEFAULT_USER", "demo_user")
    config.set_user(_user_id)
    use_local_storage()

# El acceso directo a Streamlit no incluye el `uid` que agrega el redirect de
# Vercel. El repositorio usa ese identificador para el backend Supabase, por lo
# que siempre debe existir una identidad activa, incluso en modo local/demo.
set_active_user(_user_id)

init_state()
st.session_state["data_owner_id"] = _user_id
st.session_state["private_storage_available"] = (
    not bool(_params.get("uid", ""))
    and st.get_option("server.address") in {"127.0.0.1", "localhost", "::1"}
)

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

llm_engine = LLMService(api_key=saved_key or None)
provider_label = llm_engine.get_provider_label()
llm_ready = llm_engine.is_ready()

render_sidebar(
    balance_now=credits_engine.get_balance(),
    llm_ready=llm_ready,
    provider_label=provider_label,
)

# ── Routing ─────────────────────────────────────────────────────────────────

current_page = st.session_state.get("current_page", "Inicio")

if current_page == "Inicio":
    render_home_page(
        balance_now=credits_engine.get_balance(),
        has_api_key=llm_ready,
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
elif current_page == "Configuración":
    render_configuracion_page(credits_engine=credits_engine)
