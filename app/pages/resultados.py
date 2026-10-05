"""
app/pages/resultados.py — Página de Resultados con jerarquía ejecutiva.

1. Resumen del estudio (números, reacciones, motivos, grupos y citas)
2. Informe con IA (a pedido)
3. Respuestas completas y descargas
4. Más vistas: por pregunta, comparación y biblioteca
"""

import json
import re
from typing import Dict, List

import pandas as pd
import streamlit as st

from app.components.shell import render_empty_state, render_page_intro, render_section_title, render_soft_panel, render_stat_card
from app.services.analysis_service import (
    build_executive_report,
    error_mask,
    insights_by_profile,
    representative_responses,
    valid_responses,
)
from app.services.llm_service import LLMError, LLMService
from app.state import go_to_page
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


SENTIMENT_LABELS = {
    "positive": "Positiva",
    "negative": "Negativa",
    "neutral": "Neutral",
    "mixed": "Mixta",
}
INTENT_LABELS = {
    "comprar": "Compraría",
    "rechazar": "Rechazaría",
    "explorar": "Quiere saber más",
    "comparar": "Compararía opciones",
}


def _distribution(series: pd.Series, labels: Dict[str, str]) -> pd.DataFrame:
    """Porcentaje por categoría, con etiquetas en español."""
    values = series.fillna("").astype(str).str.strip().str.lower()
    values = values[values != ""]
    if values.empty:
        return pd.DataFrame()
    pct = (values.map(lambda v: labels.get(v, v.capitalize())).value_counts(normalize=True) * 100).round(1)
    return pct.rename("%").to_frame()


def _top_reasons(series: pd.Series, limit: int = 5) -> List[str]:
    values = series.fillna("").astype(str).str.strip()
    values = values[values != ""]
    if values.empty:
        return []
    counts = values.str.rstrip(".").value_counts().head(limit)
    total = len(values)
    return [f"{texto} ({count} de {total})" for texto, count in counts.items()]


def render_resultados_page():
    """Página de resultados: primero el resumen del estudio, después el detalle."""
    render_page_intro(
        "Resultados",
        "¿Qué respondió tu audiencia?",
        "Arriba tenés el resumen; más abajo, las respuestas completas, descargas y comparaciones.",
    )

    estudios = list_studies()
    if not estudios:
        render_empty_state(
            "Todavía no hay estudios",
            "Cuando ejecutes un estudio, los resultados aparecen acá.",
            cta_text="Hacer un estudio",
            cta_key="res_go_studies",
            on_cta=lambda: go_to_page("Estudios"),
        )
        return

    by_id = {e.id: e for e in estudios}
    if st.session_state.get("res_study_id") not in by_id:
        st.session_state["res_study_id"] = estudios[0].id
    study_id = st.selectbox(
        "Estudio",
        list(by_id.keys()),
        key="res_study_id",
        format_func=lambda sid: f"{by_id[sid].titulo or by_id[sid].pregunta[:60] or 'Sin título'} · {by_id[sid].universo_nombre}",
    )
    _render_study_summary(by_id[study_id])

    st.divider()
    render_section_title("Más vistas")
    tab_questions, tab_compare, tab_library = st.tabs([
        "Respuestas por pregunta",
        "Comparar estudios",
        "Todos los estudios y descargas",
    ])
    with tab_questions:
        from app.pages.preguntas import render_preguntas_tab
        render_preguntas_tab()
    with tab_compare:
        from app.pages.reportes import render_reportes_tab
        render_reportes_tab()
    with tab_library:
        from app.pages.biblioteca import render_biblioteca_tab
        render_biblioteca_tab()


def _render_study_summary(estudio):
    """Resumen de un estudio: números, reacciones, motivos, grupos y citas."""
    st.markdown(f"**Pregunta:** {estudio.pregunta}")
    st.caption(f"Audiencia: {estudio.universo_nombre} · {estudio.created_at}")

    resultados = load_study_results(estudio.id)
    if not resultados:
        render_empty_state(
            "Este estudio no tiene respuestas",
            "Puede que se haya cortado antes de recibir la primera respuesta. Probá ejecutarlo de nuevo.",
        )
        return

    all_df = pd.DataFrame([r.to_dict() for r in resultados])
    errores = int(error_mask(all_df).sum())
    resultados_df = valid_responses(all_df)

    planeadas = int(getattr(estudio, "respuestas_planeadas", 0) or 0)
    if planeadas and len(all_df) < planeadas:
        st.warning(
            f"El estudio quedó incompleto: se guardaron {len(all_df)} de {planeadas} respuestas "
            "(se cortó antes de terminar)."
        )
    if errores:
        st.warning(
            f"{errores} respuesta(s) fallaron por un error del modelo y no se cuentan en el análisis."
        )
    if resultados_df.empty:
        render_empty_state(
            "No hay respuestas válidas",
            "Todas las llamadas al modelo fallaron. Revisá la configuración del modelo y ejecutá de nuevo.",
        )
        return

    # ── Números ──────────────────────────────────────────────────
    cols = st.columns(3)
    with cols[0]:
        render_stat_card("Personas", str(resultados_df["persona_id"].nunique()))
    with cols[1]:
        render_stat_card("Respuestas válidas", str(len(resultados_df)))
    with cols[2]:
        render_stat_card("Grupos", str(resultados_df["perfil"].nunique()))

    report = build_executive_report(estudio, resultados_df)
    render_soft_panel("En pocas palabras", report["conclusion"])

    # ── Reacciones ───────────────────────────────────────────────
    sentiment_df = _distribution(resultados_df.get("sentiment", pd.Series(dtype=str)), SENTIMENT_LABELS)
    intent_df = _distribution(resultados_df.get("intent", pd.Series(dtype=str)), INTENT_LABELS)
    if not sentiment_df.empty or not intent_df.empty:
        c1, c2 = st.columns(2)
        with c1:
            render_section_title("¿Cómo reaccionaron?")
            if sentiment_df.empty:
                st.caption("Sin datos.")
            else:
                st.bar_chart(sentiment_df, horizontal=True, x_label="", y_label="% de respuestas")
        with c2:
            render_section_title("¿Qué harían?")
            if intent_df.empty:
                st.caption("Sin datos.")
            else:
                st.bar_chart(intent_df, horizontal=True, x_label="", y_label="% de respuestas")

    # ── Motivos ──────────────────────────────────────────────────
    objeciones = _top_reasons(resultados_df.get("main_objection", pd.Series(dtype=str)))
    motivos = _top_reasons(resultados_df.get("main_driver", pd.Series(dtype=str)))
    if objeciones or motivos:
        c1, c2 = st.columns(2)
        with c1:
            render_section_title("Lo que más frena")
            st.markdown("\n".join(f"- {o}" for o in objeciones) or "Sin datos.")
        with c2:
            render_section_title("Lo que más mueve")
            st.markdown("\n".join(f"- {m}" for m in motivos) or "Sin datos.")

    # ── Por grupo ────────────────────────────────────────────────
    render_section_title("Por grupo")
    insights_df = insights_by_profile(resultados_df)
    if not insights_df.empty:
        st.dataframe(
            insights_df.rename(columns={"Perfil": "Grupo", "Temas clave": "Palabras más usadas"})
            .drop(columns=["Largo promedio"], errors="ignore"),
            use_container_width=True,
            hide_index=True,
        )

    # ── Citas ────────────────────────────────────────────────────
    render_section_title("Algunas respuestas")
    quotes_df = representative_responses(resultados_df, limit_per_profile=2)
    for _, row in quotes_df.iterrows():
        st.markdown(f"**{row['Perfil']}**")
        st.info(row["Respuesta"][:300])

    # ── Análisis con IA ──────────────────────────────────────────
    render_section_title("Informe con IA")
    ai_results: Dict[str, str] = st.session_state.setdefault("res_ai_results", {})
    if estudio.id in ai_results:
        with st.container(border=True):
            st.markdown(ai_results[estudio.id])
            if st.button("Cerrar informe", key=f"res_ai_close_{estudio.id}"):
                ai_results.pop(estudio.id, None)
                st.rerun()
    else:
        st.caption("Un consultor virtual lee todas las respuestas y escribe un informe. Tarda un poco.")
        if st.button("Generar informe con IA", key=f"res_ai_analyze_{estudio.id}", use_container_width=True):
            ai_results[estudio.id] = _run_ai_analysis(estudio, resultados_df)
            st.rerun()

    # ── Detalle y descargas ──────────────────────────────────────
    safe_titulo = re.sub(r'[<>\:"/\\|?*]', "_", estudio.titulo or estudio.id)
    with st.expander("Ver todas las respuestas y descargar"):
        display_df = all_df[["perfil", "sentiment", "intent", "respuesta", "error"]].rename(columns={
            "perfil": "Grupo", "sentiment": "Reacción", "intent": "Qué haría",
            "respuesta": "Respuesta", "error": "Error",
        })
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.download_button(
                "Descargar CSV",
                data=all_df.to_csv(index=False).encode("utf-8"),
                file_name=f"{safe_titulo}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with c2:
            st.download_button(
                "Descargar JSON",
                data=json.dumps([r.to_dict() for r in resultados], ensure_ascii=False, indent=2).encode("utf-8"),
                file_name=f"{safe_titulo}.json",
                mime="application/json",
                use_container_width=True,
            )
        with c3:
            st.download_button(
                "Descargar informe (MD)",
                data=report["markdown"].encode("utf-8"),
                file_name=f"{safe_titulo}_informe.md",
                mime="text/markdown",
                use_container_width=True,
            )
