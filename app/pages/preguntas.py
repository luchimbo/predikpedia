"""
app/pages/preguntas.py — Vista de resultados crudos agrupados por pregunta.

A diferencia de la página Resultados (centrada en un estudio), acá se agrupan
los estudios por su texto de pregunta y se muestran juntas todas las respuestas
crudas de todas las corridas que usaron esa misma pregunta.
"""

import json
import re
from collections import OrderedDict
from typing import Dict, List

import pandas as pd
import streamlit as st

from app.components.shell import render_empty_state, render_page_intro, render_section_title, render_stat_card
from app.domain.models import Estudio
from app.state import go_to_page
from app.storage.repository import list_studies, load_study_results


def _safe_filename(base: str, fallback: str) -> str:
    base = (base or "").strip() or fallback
    return re.sub(r'[<>:"/\\|?*]', "_", base)


def _truncar(texto: str, limite: int = 70) -> str:
    texto = texto.strip()
    return texto if len(texto) <= limite else texto[:limite] + "..."


def _agrupar_por_pregunta(estudios: List[Estudio]) -> "OrderedDict[str, List[Estudio]]":
    """Agrupa estudios por el texto de su pregunta (preserva orden de aparición)."""
    grupos: "OrderedDict[str, List[Estudio]]" = OrderedDict()
    for estudio in estudios:
        clave = estudio.pregunta.strip()
        grupos.setdefault(clave, []).append(estudio)
    return grupos


def _construir_df(estudios: List[Estudio]) -> pd.DataFrame:
    """Concatena las respuestas de varias corridas agregando columnas de contexto."""
    filas = []
    for estudio in estudios:
        etiqueta_estudio = estudio.titulo or estudio.id
        for respuesta in load_study_results(estudio.id):
            fila = respuesta.to_dict()
            fila["Estudio"] = etiqueta_estudio
            fila["Audiencia"] = estudio.universo_nombre
            fila["Creado"] = estudio.created_at
            filas.append(fila)
    return pd.DataFrame(filas)


def render_preguntas_page():
    """Renderiza la página de resultados agrupados por pregunta."""
    render_page_intro(
        "Preguntas",
        "Todas las respuestas hechas con una pregunta",
        "Elegí una pregunta y mirá juntas todas las respuestas crudas de cada corrida que la usó.",
    )

    estudios = list_studies()
    if not estudios:
        render_empty_state(
            "No hay estudios ejecutados",
            "Cuando ejecutes un estudio, sus respuestas aparecerán acá.",
            cta_text="Ir a Estudios",
            cta_key="preg_go_studies",
            on_cta=lambda: go_to_page("Estudios"),
        )
        return

    grupos = _agrupar_por_pregunta(estudios)

    # ── Selector de pregunta ─────────────────────────────────────────
    def _fmt_pregunta(pregunta: str) -> str:
        n = len(grupos[pregunta])
        sufijo = "corrida" if n == 1 else "corridas"
        return f"{_truncar(pregunta)} · {n} {sufijo}"

    opciones = {_fmt_pregunta(p): p for p in grupos.keys()}
    seleccion = st.selectbox("Seleccionar pregunta", list(opciones.keys()), key="preg_select")
    pregunta = opciones[seleccion]
    corridas = grupos[pregunta]

    st.markdown(f"**Pregunta:** {pregunta or '(sin texto)'}")

    df = _construir_df(corridas)
    if df.empty:
        render_empty_state(
            "Sin respuestas guardadas",
            "Las corridas de esta pregunta todavía no tienen respuestas guardadas.",
        )
        return

    # ── Métricas de cabecera ─────────────────────────────────────────
    total_respuestas = len(df)
    total_personas = df["persona_id"].nunique() if "persona_id" in df.columns else 0
    total_audiencias = df["Audiencia"].nunique()

    cols = st.columns(4)
    with cols[0]:
        render_stat_card("Corridas", str(len(corridas)))
    with cols[1]:
        render_stat_card("Audiencias", str(total_audiencias))
    with cols[2]:
        render_stat_card("Respuestas", str(total_respuestas))
    with cols[3]:
        render_stat_card("Personas", str(total_personas))

    st.divider()

    # ── Filtros ──────────────────────────────────────────────────────
    render_section_title("Filtros")
    f1, f2, f3 = st.columns(3)
    with f1:
        audiencias = ["Todas"] + sorted(df["Audiencia"].dropna().unique().tolist())
        filtro_audiencia = st.selectbox("Audiencia", audiencias, key="preg_filtro_aud")
    with f2:
        perfiles = ["Todos"] + sorted(df["perfil"].dropna().unique().tolist()) if "perfil" in df.columns else ["Todos"]
        filtro_perfil = st.selectbox("Perfil", perfiles, key="preg_filtro_perfil")
    with f3:
        estudios_opts = ["Todas"] + sorted(df["Estudio"].dropna().unique().tolist())
        filtro_estudio = st.selectbox("Corrida", estudios_opts, key="preg_filtro_estudio")

    df_filtrado = df
    if filtro_audiencia != "Todas":
        df_filtrado = df_filtrado[df_filtrado["Audiencia"] == filtro_audiencia]
    if filtro_perfil != "Todos" and "perfil" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["perfil"] == filtro_perfil]
    if filtro_estudio != "Todas":
        df_filtrado = df_filtrado[df_filtrado["Estudio"] == filtro_estudio]

    # ── Tabla combinada ──────────────────────────────────────────────
    st.divider()
    render_section_title(f"Respuestas ({len(df_filtrado)})")

    cols_mostrar = ["Estudio", "Audiencia", "perfil", "persona_id", "repeticion", "respuesta", "quote"]
    cols_presentes = [c for c in cols_mostrar if c in df_filtrado.columns]
    st.dataframe(df_filtrado[cols_presentes], use_container_width=True, hide_index=True)

    # ── Descarga combinada ───────────────────────────────────────────
    st.divider()
    render_section_title("Descargar")

    safe = _safe_filename(pregunta, "pregunta")[:60]
    csv_bytes = df_filtrado.to_csv(index=False).encode("utf-8")
    json_bytes = json.dumps(
        df_filtrado.to_dict(orient="records"), ensure_ascii=False, indent=2
    ).encode("utf-8")

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "📥 Descargar CSV",
            data=csv_bytes,
            file_name=f"{safe}.csv",
            mime="text/csv",
            use_container_width=True,
            type="primary",
            key="preg_dl_csv",
        )
    with c2:
        st.download_button(
            "Descargar JSON",
            data=json_bytes,
            file_name=f"{safe}.json",
            mime="application/json",
            use_container_width=True,
            key="preg_dl_json",
        )

    # ── Detalle por corrida ──────────────────────────────────────────
    if len(corridas) > 1:
        st.divider()
        render_section_title("Detalle por corrida")
        for estudio in corridas:
            etiqueta = estudio.titulo or estudio.id
            df_corrida = df[df["Estudio"] == etiqueta]
            with st.expander(f"{etiqueta} · {estudio.universo_nombre} ({len(df_corrida)} respuestas)"):
                cols_c = [c for c in cols_mostrar if c in df_corrida.columns and c != "Estudio"]
                st.dataframe(df_corrida[cols_c], use_container_width=True, hide_index=True)
