"""
app/navigation.py — Sidebar y navegación principal.
"""

import streamlit as st

from app.services.llm_routing import LLMConfigurationError, load_llm_settings, resolve_provider


NAV_OPTIONS = [
    "Inicio",
    "Audiencias",
    "Estudios",
    "Resultados",
    "Configuración",
]


def render_sidebar(*, balance_now: float, llm_ready: bool, provider_label: str):
    """Renderiza el sidebar con navegación estilizada como producto."""
    with st.sidebar:
        # Header del sidebar en HTML para control total
        st.markdown(
            """
            <div style="padding: 0.5rem 0 1.5rem 0;">
                <div style="font-family: 'Manrope', sans-serif; font-size: 22px; font-weight: 800; color: #F1F5F9;">Predikpedia</div>
                <div style="font-size: 13px; color: #94A3B8; margin-top: 4px;">Research sintético</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        current_page = st.session_state.get("current_page", "Inicio")

        # Navegación: usar botones Streamlit pero estilizados vía CSS como nav items
        for page in NAV_OPTIONS:
            btn_type = "primary" if page == current_page else "secondary"
            if st.button(page, key=f"nav_{page}", use_container_width=True, type=btn_type):
                st.session_state["current_page"] = page
                st.rerun()

        # Footer con info operativa
        st.markdown(
            """
            <div style="margin-top: 2rem; padding-top: 1.5rem; border-top: 1px solid rgba(255,255,255,0.08);">
            """,
            unsafe_allow_html=True,
        )

        ia_status = f"Lista · {provider_label}" if llm_ready else "Sin configurar"
        st.markdown(
            f"""
            <div class="nav-footer-item">
                <span class="nav-footer-label">IA</span>
                <span class="nav-footer-value">{ia_status}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("</div>", unsafe_allow_html=True)


def resolve_provider_label(api_key: str) -> str:
    del api_key
    try:
        resolution = resolve_provider(load_llm_settings())
        return "Ollama local" if resolution.provider == "local" else "OpenRouter"
    except LLMConfigurationError:
        return "Sin configurar"
