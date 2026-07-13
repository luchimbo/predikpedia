"""
app/pages/resultados.py — Página de Resultados con jerarquía ejecutiva.

1. Resumen ejecutivo
2. KPIs
3. Insights por perfil
4. Quotes destacadas
5. Tabla completa (al final)
"""

import json
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from app.components.shell import render_empty_state, render_page_intro, render_section_title, render_soft_panel, render_stat_card
from app.services.analysis_service import build_executive_report, insights_by_profile, representative_responses
from app.services.llm_service import LLMError, LLMService
from app.state import get, go_to_page
from app.storage.repository import list_studies, load_study_results


def _build_chunk_prompt(estudio, resultados_df: pd.DataFrame) -> str:
    """Genera el CSV con todas las respuestas para el prompt."""
    # Seleccionar columnas relevantes para el análisis
    cols = ["perfil", "respuesta", "sentiment", "intent", "main_objection", "main_driver"]
    cols_present = [c for c in cols if c in resultados_df.columns]
    csv_data = resultados_df[cols_present].to_csv(index=False)
    return csv_data


def _calcular_stats_cuantitativas(resultados_df: pd.DataFrame) -> str:
    """Calcula estadísticas cuantitativas del estudio para incluir en el prompt."""
    total = len(resultados_df)
    if total == 0:
        return "No hay respuestas para analizar."
    
    lineas = []
    lineas.append(f"Total de respuestas: {total}")
    
    # Distribución de intenciones
    if "intent" in resultados_df.columns:
        intent_counts = resultados_df["intent"].value_counts()
        if not intent_counts.empty:
            lineas.append("\nDistribución de intenciones:")
            for intent, count in intent_counts.items():
                pct = (count / total) * 100
                lineas.append(f"  - {intent}: {count} ({pct:.1f}%)")
    
    # Distribución de sentimientos
    if "sentiment" in resultados_df.columns:
        sentiment_counts = resultados_df["sentiment"].value_counts()
        if not sentiment_counts.empty:
            lineas.append("\nDistribución de sentimientos:")
            for sentiment, count in sentiment_counts.items():
                pct = (count / total) * 100
                lineas.append(f"  - {sentiment}: {count} ({pct:.1f}%)")
    
    # Distribución por perfil
    if "perfil" in resultados_df.columns:
        perfil_counts = resultados_df["perfil"].value_counts()
        if not perfil_counts.empty:
            lineas.append("\nDistribución por perfil:")
            for perfil, count in perfil_counts.items():
                pct = (count / total) * 100
                lineas.append(f"  - {perfil}: {count} ({pct:.1f}%)")
    
    # Top objeciones
    if "main_objection" in resultados_df.columns:
        obj_counts = resultados_df["main_objection"].value_counts().head(5)
        if not obj_counts.empty:
            lineas.append("\nPrincipales objeciones:")
            for obj, count in obj_counts.items():
                if obj and str(obj).strip():
                    pct = (count / total) * 100
                    lineas.append(f"  - {obj}: {count} ({pct:.1f}%)")
    
    # Top drivers
    if "main_driver" in resultados_df.columns:
        driver_counts = resultados_df["main_driver"].value_counts().head(5)
        if not driver_counts.empty:
            lineas.append("\nPrincipales motivadores:")
            for driver, count in driver_counts.items():
                if driver and str(driver).strip():
                    pct = (count / total) * 100
                    lineas.append(f"  - {driver}: {count} ({pct:.1f}%)")
    
    return "\n".join(lineas)


def _split_into_chunks(csv_data: str, max_chunk_size: int = 6000) -> List[str]:
    """Divide el CSV en chunks que quepan en el contexto del modelo."""
    lines = csv_data.split("\n")
    header = lines[0]
    data_lines = lines[1:]
    
    chunks = []
    current_chunk = header
    current_size = len(header)
    
    for line in data_lines:
        line_size = len(line) + 1  # +1 por el \n
        if current_size + line_size > max_chunk_size and current_chunk != header:
            chunks.append(current_chunk)
            current_chunk = header + "\n" + line
            current_size = len(header) + line_size
        else:
            current_chunk += "\n" + line
            current_size += line_size
    
    if current_chunk != header:
        chunks.append(current_chunk)
    
    return chunks if chunks else [csv_data]


def _build_analysis_prompt(estudio, csv_chunk: str, stats_text: str, chunk_num: int = 1, total_chunks: int = 1) -> str:
    """Construye el prompt para el análisis con IA."""
    chunk_info = f" (Chunk {chunk_num} de {total_chunks})" if total_chunks > 1 else ""
    
    prompt = f"""La pregunta que se les hizo a los clientes potenciales fue: {estudio.pregunta}
Contexto del estudio: {estudio.contexto or "No especificado"}
Audiencia: {estudio.universo_nombre}

DATOS CUANTITATIVOS DEL ESTUDIO:
{stats_text}

Acá están las respuestas en formato CSV{chunk_info}:
{csv_chunk}

Basándote en la pregunta específica que se hizo, determiná qué tipo de análisis es más relevante para este estudio. No uses un formato genérico rígido. Analizá las respuestas y presentá los hallazgos de la forma más útil para la toma de decisiones del negocio.

IMPORTANTE - USÁ LOS NÚMEROS:
- Cuando mencionés una tendencia, indicá cuántas respuestas la respaldan y qué porcentaje del total representan.
- Si la pregunta implica elegir entre opciones o categorías, contá cuántas respuestas apuntan a cada una usando los datos cuantitativos.
- Incluí números absolutos y porcentajes en tu análisis.
- No des opiniones sin respaldarlas con datos concretos.
"""
    return prompt


def _build_consolidation_prompt(estudio, partial_analyses: List[str], stats_text: str) -> str:
    """Construye el prompt para consolidar análisis parciales."""
    analyses_text = "\n\n---\n\n".join([f"ANÁLISIS PARCIAL {i+1}:\n{a}" for i, a in enumerate(partial_analyses)])
    
    prompt = f"""La pregunta que se les hizo a los clientes potenciales fue: {estudio.pregunta}
Contexto del estudio: {estudio.contexto or "No especificado"}

DATOS CUANTITATIVOS DEL ESTUDIO:
{stats_text}

Recibiste los siguientes análisis parciales de diferentes grupos de respuestas:

{analyses_text}

Tu tarea es consolidar todos estos análisis parciales en un único informe coherente y completo. Eliminá repeticiones, unificá hallazgos similares y presentá una visión integral. El formato y enfoque del análisis debe estar determinado por la pregunta específica del estudio, no por un template genérico.

IMPORTANTE - USÁ LOS NÚMEROS:
- Cuando mencionés una tendencia, indicá cuántas respuestas la respaldan y qué porcentaje del total representan.
- Si la pregunta implica elegir entre opciones o categorías, contá cuántas respuestas apuntan a cada una usando los datos cuantitativos.
- Incluí números absolutos y porcentajes en tu análisis.
- No des opiniones sin respaldarlas con datos concretos.

Respondé en español.
"""
    return prompt


def _run_ai_analysis(estudio, resultados_df: pd.DataFrame) -> str:
    """Ejecuta el análisis con IA usando todas las respuestas, dividiendo en chunks si es necesario."""
    try:
        engine = LLMService()
        if not engine.is_ready():
            return "Error: No hay API key configurada. Configurala en Configuración."
        
        system_prompt = "Sos un consultor senior de research de mercado especializado en producto y customer insights. Tu trabajo es analizar respuestas de clientes potenciales y extraer insights accionables para la toma de decisiones de negocio."
        
        # Calcular estadísticas cuantitativas
        stats_text = _calcular_stats_cuantitativas(resultados_df)
        
        # Generar CSV con todas las respuestas
        csv_data = _build_chunk_prompt(estudio, resultados_df)
        chunks = _split_into_chunks(csv_data, max_chunk_size=6000)
        total_chunks = len(chunks)
        
        if total_chunks == 1:
            # Si cabe en un solo chunk, analizar directamente
            user_prompt = _build_analysis_prompt(estudio, chunks[0], stats_text)
            with st.spinner("Analizando respuestas con IA..."):
                result = engine.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    agent_id="analysis",
                    max_retries=2,
                    timeout=120,
                )
            
            if isinstance(result, dict):
                return result.get("_raw", str(result))
            return str(result)
        
        else:
            # Dividir en chunks y analizar por partes
            partial_analyses = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, chunk in enumerate(chunks):
                status_text.text(f"Analizando chunk {i+1} de {total_chunks}...")
                progress_bar.progress((i) / total_chunks)
                
                user_prompt = _build_analysis_prompt(estudio, chunk, stats_text, chunk_num=i+1, total_chunks=total_chunks)
                result = engine.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    agent_id=f"analysis_chunk_{i+1}",
                    max_retries=2,
                    timeout=120,
                )
                
                if isinstance(result, dict):
                    partial_analyses.append(result.get("_raw", str(result)))
                else:
                    partial_analyses.append(str(result))
            
            # Consolidar análisis parciales
            status_text.text("Consolidando análisis...")
            progress_bar.progress(0.9)
            
            consolidation_prompt = _build_consolidation_prompt(estudio, partial_analyses, stats_text)
            final_result = engine.generate(
                system_prompt=system_prompt,
                user_prompt=consolidation_prompt,
                agent_id="analysis_consolidation",
                max_retries=2,
                timeout=120,
            )
            
            progress_bar.empty()
            status_text.empty()
            
            if isinstance(final_result, dict):
                return final_result.get("_raw", str(final_result))
            return str(final_result)
    
    except LLMError as e:
        return f"Error en el análisis: {e}"
    except Exception as e:
        return f"Error inesperado: {e}"


def render_resultados_page():
    """Renderiza la página de resultados con pestañas unificadas (Resultados, Preguntas, Comparar, Biblioteca)."""
    render_page_intro(
        "Resultados",
        "Visualización y Análisis de Estudios",
        "Analizá respuestas con IA, agrupá por preguntas, compará variantes o descargá reportes y datos.",
    )

    estudios = list_studies()
    if not estudios:
        render_empty_state(
            "No hay estudios ejecutados",
            "Cuando ejecutes un estudio, los resultados aparecerán acá.",
            cta_text="Ir a Estudios",
            cta_key="res_go_studies",
            on_cta=lambda: go_to_page("Estudios"),
        )
        return

    tab_analysis, tab_questions, tab_compare, tab_library = st.tabs([
        "📊 Análisis de Estudio",
        "❓ Respuestas por Pregunta",
        "⚖️ Comparar Estudios",
        "📂 Biblioteca / Descargas"
    ])

    with tab_analysis:
        _render_analysis_tab(estudios)

    with tab_questions:
        from app.pages.preguntas import render_preguntas_tab
        render_preguntas_tab()

    with tab_compare:
        from app.pages.reportes import render_reportes_tab
        render_reportes_tab()

    with tab_library:
        from app.pages.biblioteca import render_biblioteca_tab
        render_biblioteca_tab()


def _render_analysis_tab(estudios: List[Any]):
    """Renderiza la vista principal de análisis de un estudio."""

    # Selector de estudio
    def _fmt_option(e):
        titulo = e.titulo or "Sin título"
        return f"{titulo} · {e.universo_nombre} ({e.created_at})"

    options = {_fmt_option(e): e for e in estudios}
    selected = st.selectbox("Seleccionar estudio", list(options.keys()), key="res_study_select")
    estudio = options[selected]

    # Mostrar título del estudio
    if estudio.titulo:
        st.markdown(f"**Título:** {estudio.titulo}")
    st.caption(f"Pregunta: {estudio.pregunta}")

    # Cargar resultados
    resultados = load_study_results(estudio.id)
    if not resultados:
        render_empty_state(
            "Sin resultados guardados",
            f"El estudio '{estudio.id}' no tiene respuestas guardadas.",
        )
        return

    resultados_df = pd.DataFrame([r.to_dict() for r in resultados])

    # Métricas del estudio
    total_personas = len(set(resultados_df["persona_id"]))
    total_respuestas = len(resultados_df)
    metric_cols = st.columns(2)
    with metric_cols[0]:
        st.metric("Personas encuestadas", total_personas)
    with metric_cols[1]:
        st.metric("Respuestas totales", total_respuestas)
    st.divider()

    # Botón de descarga CSV prominente
    import re
    safe_titulo = re.sub(r'[<>\:"/\\|?*]', "_", estudio.titulo or estudio.id)
    csv_bytes = resultados_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Descargar CSV de respuestas",
        data=csv_bytes,
        file_name=f"{safe_titulo}.csv",
        mime="text/csv",
        use_container_width=True,
        type="primary",
    )
    st.divider()

    # ── Análisis con IA ───────────────────────────────────────────
    render_section_title("Análisis con IA")
    
    if st.button("🤖 Analizar respuestas con IA", key="res_ai_analyze", use_container_width=True, type="primary"):
        analisis = _run_ai_analysis(estudio, resultados_df)
        st.session_state["res_ai_result"] = analisis
        st.rerun()
    
    if "res_ai_result" in st.session_state:
        with st.container(border=True):
            st.markdown("### Análisis generado por IA")
            st.markdown(st.session_state["res_ai_result"])
            if st.button("🗑️ Cerrar análisis", key="res_ai_close"):
                del st.session_state["res_ai_result"]
                st.rerun()
    
    st.divider()

    # ── 1. Resumen Ejecutivo ──────────────────────────────────────
    report = build_executive_report(estudio, resultados_df)

    render_section_title("Resumen Ejecutivo")
    render_soft_panel("Conclusión principal", report["conclusion"])

    # ── 2. KPIs ──────────────────────────────────────────────────
    cols = st.columns(4)
    with cols[0]:
        render_stat_card("Personas", str(len(set(resultados_df["persona_id"]))))
    with cols[1]:
        render_stat_card("Respuestas", str(len(resultados_df)))
    with cols[2]:
        render_stat_card("Perfiles", str(len(resultados_df["perfil"].unique())))
    with cols[3]:
        render_stat_card("Template", estudio.template)

    # ── 3. Insights por Perfil ───────────────────────────────────
    render_section_title("Insights por perfil")
    insights_df = insights_by_profile(resultados_df)
    if not insights_df.empty:
        st.dataframe(insights_df, use_container_width=True, hide_index=True)
    else:
        st.caption("Sin datos suficientes para insights por perfil.")

    # ── 4. Quotes Destacadas ─────────────────────────────────────
    render_section_title("Quotes destacadas")
    quotes_df = representative_responses(resultados_df, limit_per_profile=2)
    if not quotes_df.empty:
        for _, row in quotes_df.iterrows():
            with st.container():
                st.markdown(f"**{row['Perfil']}** · {row['Persona']}")
                st.info(row['Respuesta'][:300])
    else:
        st.caption("Sin quotes destacadas.")

    # ── 5. Tabla Completa (al final) ─────────────────────────────
    render_section_title("Respuestas completas")
    with st.expander("Ver tabla completa", expanded=False):
        display_df = resultados_df[["persona_id", "perfil", "repeticion", "sentiment", "respuesta", "quote"]]
        st.dataframe(display_df, use_container_width=True, hide_index=True)

    # ── Exportes ─────────────────────────────────────────────────
    st.divider()
    render_section_title("Exportes")

    json_bytes = json.dumps([r.to_dict() for r in resultados], ensure_ascii=False, indent=2).encode("utf-8")

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "Descargar JSON",
            data=json_bytes,
            file_name=f"{safe_titulo}.json",
            mime="application/json",
            use_container_width=True,
        )
    with c2:
        st.download_button(
            "Descargar Informe MD",
            data=report["markdown"].encode("utf-8"),
            file_name=f"{safe_titulo}_informe.md",
            mime="text/markdown",
            use_container_width=True,
        )
