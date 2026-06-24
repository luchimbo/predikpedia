"""
app/theme.py — Sistema visual de Predikpedia.
CSS completo para shell, componentes, sidebar y stepper.
"""

from typing import Dict


COLORS: Dict[str, str] = {
    "bg_app": "#F6F4EF",
    "bg_surface": "#FFFFFF",
    "bg_surface_alt": "#FAF8F3",
    "border_subtle": "#DED8CB",
    "text_primary": "#141414",
    "text_secondary": "#5F665F",
    "text_muted": "#98A2B3",
    "accent_primary": "#0E6F5C",
    "accent_light": "#17977E",
    "accent_soft": "#DDF3EE",
    "accent_glow": "#8CE1D0",
    "success": "#16835F",
    "warning": "#B7791F",
    "danger": "#C2413B",
    "info": "#3B82F6",
    "steel": "#667085",
    "steel_light": "#98A2B3",
    "sidebar_bg": "#151A17",
    "sidebar_text": "#C9D2CB",
    "sidebar_active": "#21372F",
    "sidebar_hover": "#202923",
}


GLOBAL_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Manrope:wght@500;600;700;800&family=Source+Sans+3:wght@400;500;600;700&display=swap');

:root {{
    --bg-app: {COLORS["bg_app"]};
    --bg-surface: {COLORS["bg_surface"]};
    --bg-surface-alt: {COLORS["bg_surface_alt"]};
    --border-subtle: {COLORS["border_subtle"]};
    --text-primary: {COLORS["text_primary"]};
    --text-secondary: {COLORS["text_secondary"]};
    --text-muted: {COLORS["text_muted"]};
    --accent-primary: {COLORS["accent_primary"]};
    --accent-primary-soft: {COLORS["accent_soft"]};
    --accent-light: {COLORS["accent_light"]};
    --success: {COLORS["success"]};
    --warning: {COLORS["warning"]};
    --danger: {COLORS["danger"]};
    --info: {COLORS["info"]};
}}

html, body {{
    font-family: 'Source Sans 3', sans-serif;
}}

.stApp {{
    background: var(--bg-app);
}}

/* ── Header ───────────────────────────────────────────────── */
[data-testid="stHeader"] {{
    background: rgba(246, 244, 239, 0.82);
    border-bottom: 1px solid rgba(222, 216, 203, 0.72);
}}

/* ── Contenedor principal ─────────────────────────────────── */
.block-container {{
    max-width: 1200px;
    padding-top: 1.5rem;
    padding-bottom: 3rem;
}}

/* ── Sidebar ──────────────────────────────────────────────── */
/* Forzar fondo NEGRO PURO en el sidebar y sus capas internas */
section[data-testid="stSidebar"] {{
    background: #000000 !important;
    background-color: #000000 !important;
    min-width: 280px;
    max-width: 280px;
}}

section[data-testid="stSidebar"] * {{
    background-color: transparent !important;
}}

section[data-testid="stSidebar"] > div {{
    background: #000000 !important;
    background-color: #000000 !important;
}}

section[data-testid="stSidebar"] .block-container {{
    background: #000000 !important;
    background-color: #000000 !important;
    padding: 1.5rem 1rem;
}}

/* Los botones del sidebar ya tienen su propio color de texto definido arriba.
   No forzamos color global en el sidebar para no romper la legibilidad
   sobre el fondo nativo de Streamlit. */

/* Navegación custom del sidebar */
.nav-sidebar {{
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-top: 1.5rem;
}}

.nav-item {{
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    border-radius: 10px;
    color: {COLORS["sidebar_text"]};
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
    text-decoration: none;
    border: none;
    background: transparent;
    width: 100%;
}}

.nav-item:hover {{
    background: {COLORS["sidebar_hover"]};
    color: #FFFFFF;
}}

.nav-item.active {{
    background: {COLORS["sidebar_active"]};
    color: #FFFFFF;
    font-weight: 600;
}}

.nav-item.active .nav-indicator {{
    background: {COLORS["accent_light"]};
}}

.nav-indicator {{
    width: 4px;
    height: 4px;
    border-radius: 50%;
    background: {COLORS["sidebar_text"]};
    opacity: 0.5;
    flex-shrink: 0;
}}

.nav-item.active .nav-indicator {{
    opacity: 1;
}}

.nav-footer {{
    margin-top: auto;
    padding-top: 1.5rem;
    border-top: 1px solid rgba(255,255,255,0.08);
}}

.nav-footer-item {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 0;
    font-size: 13px;
    color: {COLORS["sidebar_text"]};
}}

.nav-footer-label {{
    opacity: 0.9;
    color: rgba(255,255,255,0.8);
}}

.nav-footer-value {{
    font-family: 'IBM Plex Mono', monospace;
    font-weight: 500;
}}

/* ── Sidebar Buttons (Nav Items) ─────────────────────────── */
/* IMPORTANTE: Streamlit pone el fondo en el <button>, no en el div contenedor.
   Hay que targetear el button interno para que el fondo se vea. */

/* ── Sidebar Buttons (Nav Items) ─────────────────────────── */
/* Estrategia: fondo SÓLIDO oscuro en los botones para que se vean
   como "islas oscuras" independientemente del fondo del sidebar. */

/* Aumentar especificidad duplicando selectores */
[data-testid="stSidebar"][data-testid="stSidebar"] [data-testid="stBaseButton-secondary"][data-testid="stBaseButton-secondary"] button {{
    background: #1F1F1F !important;
    background-color: #1F1F1F !important;
    border: 1px solid #333333 !important;
    box-shadow: none !important;
    color: #FFFFFF !important;
    text-align: left !important;
    padding: 12px 16px !important;
    border-radius: 10px !important;
    font-size: 15px !important;
    font-weight: 600 !important;
    width: 100% !important;
    margin: 3px 0 !important;
    transition: all 0.15s ease !important;
    line-height: 1.4 !important;
}}

[data-testid="stSidebar"][data-testid="stSidebar"] [data-testid="stBaseButton-secondary"][data-testid="stBaseButton-secondary"] button:hover {{
    background: #333333 !important;
    background-color: #333333 !important;
    border-color: #444444 !important;
    color: #FFFFFF !important;
}}

/* Botón ACTIVO: verde fuerte */
[data-testid="stSidebar"][data-testid="stSidebar"] [data-testid="stBaseButton-primary"][data-testid="stBaseButton-primary"] button {{
    background: #0E6F5C !important;
    background-color: #0E6F5C !important;
    border: 1px solid #1A8A73 !important;
    box-shadow: 0 0 0 1px rgba(14,111,92,0.5) !important;
    color: #FFFFFF !important;
    text-align: left !important;
    padding: 12px 16px !important;
    border-radius: 10px !important;
    font-size: 15px !important;
    font-weight: 700 !important;
    width: 100% !important;
    margin: 3px 0 !important;
    transition: all 0.15s ease !important;
    line-height: 1.4 !important;
}}

[data-testid="stSidebar"][data-testid="stSidebar"] [data-testid="stBaseButton-primary"][data-testid="stBaseButton-primary"] button:hover {{
    background: #0B5D4E !important;
    background-color: #0B5D4E !important;
    border-color: #15A085 !important;
}}

/* Fallback con máxima especificidad */
[data-testid="stSidebar"][data-testid="stSidebar"] .stButton.stButton > button {{
    background: #1F1F1F !important;
    background-color: #1F1F1F !important;
    border: 1px solid #333333 !important;
    color: #FFFFFF !important;
    text-align: left !important;
    padding: 12px 16px !important;
    border-radius: 10px !important;
    font-size: 15px !important;
    font-weight: 600 !important;
    width: 100% !important;
    margin: 3px 0 !important;
}}

[data-testid="stSidebar"][data-testid="stSidebar"] .stButton.stButton > button:hover {{
    background: #333333 !important;
    background-color: #333333 !important;
    border-color: #444444 !important;
    color: #FFFFFF !important;
}}

[data-testid="stSidebar"][data-testid="stSidebar"] .stButton.stButton > button[kind="primary"] {{
    background: #0E6F5C !important;
    background-color: #0E6F5C !important;
    border: 1px solid #1A8A73 !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
}}

/* ── Botones generales ────────────────────────────────────── */
.stButton > button {{
    background: var(--accent-primary);
    color: #FFFFFF;
    border-radius: 12px;
    font-weight: 600;
    border: none;
    padding: 0.5rem 1.25rem;
    transition: background 0.15s ease;
}}

.stButton > button:hover {{
    background: #0B5D4E;
}}

.stButton > button[kind="secondary"] {{
    background: transparent;
    color: var(--text-primary);
    border: 1px solid var(--border-subtle);
}}

.stButton > button[kind="secondary"]:hover {{
    background: var(--bg-surface-alt);
}}

/* ── Inputs ───────────────────────────────────────────────── */
.stTextInput input, .stTextArea textarea, .stNumberInput input {{
    border-radius: 12px;
    border: 1px solid var(--border-subtle);
    background: var(--bg-surface);
    padding: 0.625rem 0.875rem;
    font-size: 14px;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
}}

.stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {{
    border-color: var(--accent-primary);
    box-shadow: 0 0 0 3px rgba(14,111,92,0.08);
}}

/* ── Page Intro ───────────────────────────────────────────── */
.page-intro {{
    margin-bottom: 2rem;
    max-width: 720px;
}}

.page-intro-kicker {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--accent-primary);
    margin-bottom: 0.5rem;
}}

.page-intro-title {{
    font-family: 'Manrope', sans-serif;
    font-size: 28px;
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1.2;
    margin-bottom: 0.75rem;
}}

.page-intro-copy {{
    font-size: 15px;
    color: var(--text-secondary);
    line-height: 1.6;
}}

/* ── Section Title ────────────────────────────────────────── */
.section-title {{
    font-family: 'Manrope', sans-serif;
    font-size: 16px;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 1rem;
    margin-top: 1.5rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border-subtle);
}}

/* ── Soft Panel ───────────────────────────────────────────── */
.soft-panel {{
    background: var(--bg-surface-alt);
    border: 1px solid var(--border-subtle);
    border-radius: 14px;
    padding: 1.25rem;
    margin-bottom: 1.5rem;
}}

.soft-panel-title {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--accent-primary);
    margin-bottom: 0.5rem;
}}

.soft-panel-text {{
    font-size: 14px;
    color: var(--text-secondary);
    line-height: 1.6;
}}

/* ── Stat Card ────────────────────────────────────────────── */
.stat-card {{
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: 16px;
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}}

.stat-label {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-muted);
}}

.stat-value {{
    font-family: 'Manrope', sans-serif;
    font-size: 28px;
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1.2;
}}

.stat-detail {{
    font-size: 13px;
    color: var(--text-secondary);
    margin-top: 0.25rem;
}}

/* ── Empty State ──────────────────────────────────────────── */
.empty-state {{
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: 3rem 2rem;
    background: var(--bg-surface);
    border: 1px dashed var(--border-subtle);
    border-radius: 20px;
    margin: 1.5rem 0;
}}

.empty-state-icon {{
    width: 48px;
    height: 48px;
    border-radius: 14px;
    background: var(--bg-surface-alt);
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 1rem;
    font-size: 20px;
    color: var(--text-muted);
}}

.empty-state-title {{
    font-family: 'Manrope', sans-serif;
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 0.5rem;
}}

.empty-state-copy {{
    font-size: 14px;
    color: var(--text-secondary);
    line-height: 1.5;
    max-width: 400px;
    margin-bottom: 1.25rem;
}}

/* ── Stepper ──────────────────────────────────────────────── */
.stepper {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin: 1.5rem 0 2rem 0;
    padding: 0 0.5rem;
}}

.stepper-step {{
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    flex: 1;
    position: relative;
}}

.stepper-step:not(:last-child)::after {{
    content: '';
    position: absolute;
    top: 14px;
    left: 50%;
    width: 100%;
    height: 2px;
    background: var(--border-subtle);
    z-index: 0;
}}

.stepper-step.completed:not(:last-child)::after {{
    background: var(--accent-primary);
}}

.stepper-circle {{
    width: 30px;
    height: 30px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    font-weight: 600;
    border: 2px solid var(--border-subtle);
    background: var(--bg-surface);
    color: var(--text-muted);
    position: relative;
    z-index: 1;
    transition: all 0.2s ease;
}}

.stepper-step.active .stepper-circle {{
    border-color: var(--accent-primary);
    background: var(--accent-primary);
    color: #FFFFFF;
    box-shadow: 0 0 0 4px rgba(14,111,92,0.12);
}}

.stepper-step.completed .stepper-circle {{
    border-color: var(--accent-primary);
    background: var(--accent-primary);
    color: #FFFFFF;
}}

.stepper-label {{
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    text-align: center;
    white-space: nowrap;
}}

.stepper-step.active .stepper-label {{
    color: var(--text-primary);
}}

.stepper-step.completed .stepper-label {{
    color: var(--accent-primary);
}}

/* ── Metrics nativos de Streamlit ─────────────────────────── */
[data-testid="stMetric"] {{
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: 16px;
    padding: 1rem;
}}

[data-testid="stMetricLabel"] {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-muted);
}}

[data-testid="stMetricValue"] {{
    font-family: 'Manrope', sans-serif;
    font-size: 24px;
    font-weight: 700;
    color: var(--text-primary);
}}

/* ── DataFrames ───────────────────────────────────────────── */
.stDataFrame {{
    border: 1px solid var(--border-subtle);
    border-radius: 16px;
}}

/* ── Tabs ─────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab"] {{
    border-radius: 20px;
    font-weight: 500;
    font-size: 14px;
}}

.stTabs [data-baseweb="tab-list"] {{
    gap: 8px;
}}

/* ── Selectbox / Dropdowns ────────────────────────────────── */
[data-testid="stSelectbox"] > div > div {{
    border-radius: 12px;
    border: 1px solid var(--border-subtle);
}}

/* ── Info / Warning / Error boxes ─────────────────────────── */
[data-testid="stAlert"] {{
    border-radius: 12px;
    border: 1px solid var(--border-subtle);
}}

/* ── Expander ─────────────────────────────────────────────── */
[data-testid="stExpander"] {{
    border: 1px solid var(--border-subtle);
    border-radius: 14px;
    overflow: hidden;
}}

[data-testid="stExpander"] > details > summary {{
    padding: 0.75rem 1rem;
    font-weight: 600;
    font-size: 14px;
}}

/* ── Divider ──────────────────────────────────────────────── */
hr {{
    border: none;
    border-top: 1px solid var(--border-subtle);
    margin: 2rem 0;
}}
</style>
"""
