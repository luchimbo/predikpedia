"""
app/pages/estudios.py — Página de Estudios con wizard de 4 pasos.

Paso 1: Elegir audiencia
Paso 2: Configurar pregunta y contexto
Paso 3: Configurar muestra
Paso 4: Revisar costo y ejecutar
"""

from datetime import datetime
from typing import List

import pandas as pd
import streamlit as st

from app.components.shell import render_empty_state, render_page_intro, render_section_title, render_soft_panel, render_stepper, render_stat_card
from app.domain.models import Estudio, RespuestaEstudio
from app.services.llm_service import LLMError, LLMService
from app.state import get, go_to_page, set
from app.storage.repository import (
    find_latest_expansion,
    list_universes,
    save_study,
    save_study_results,
)


def _new_study_id(universe_id: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"study_{universe_id}_{ts}"


def _build_system_prompt(persona_profile: str, context: str = "") -> str:
    """Construye el system prompt genérico para una persona sintética."""
    ctx = f"\n\nContexto del estudio: {context}" if context else ""
    return (
        f"Actuá como la persona descrita en tu perfil. Respondé la pregunta "
        f"de forma abierta y honesta, en primera persona. Sé específico sobre tu contexto, "
        f"necesidades y limitaciones. No uses lenguaje corporativo genérico.{ctx}\n\n"
        f"Perfil: {persona_profile}\n\n"
        f"Respondé en primera persona, con realismo y consistencia con tu perfil. "
        f"Sé concreto y accionable en máximo 150 palabras."
    )


def _build_user_prompt(pregunta: str) -> str:
    """Construye el user prompt pidiendo salida estructurada."""
    return (
        f"{pregunta}\n\n"
        f"Respondé en formato JSON con exactamente estos campos:\n"
        f'{{\n'
        f'  "response_text": "Tu respuesta completa en primera persona",\n'
        f'  "sentiment": "positive | negative | neutral | mixed",\n'
        f'  "intent": "explorar | comprar | rechazar | comparar",\n'
        f'  "main_objection": "Principal objeción o fricción",\n'
        f'  "main_driver": "Principal motivador",\n'
        f'  "confidence": "high | medium | low",\n'
        f'  "quote": "Cita destacada de tu respuesta"\n'
        f'}}'
    )


def _render_step_1_select_audience():
    """Paso 1: Seleccionar audiencia."""
    render_section_title("1. Elegí una audiencia")
    render_soft_panel(
        "Audiencia del estudio",
        "Seleccioná una audiencia que ya haya sido expandida en personas sintéticas.",
    )

    universos = list_universes()
    if not universos:
        render_empty_state(
            "No hay audiencias disponibles",
            "Primero creá y expandí una audiencia en la página de Audiencias.",
            cta_text="Ir a Audiencias",
            cta_key="est_go_audiences",
            on_cta=lambda: go_to_page("Audiencias"),
        )
        return

    options = {f"{u.nombre} ({u.cantidad_personas} personas)": u for u in universos}
    selected = st.selectbox("Audiencia", list(options.keys()), key="est_audience_select")
    universo = options[selected]

    # Verificar que tenga expansión
    expansion = find_latest_expansion(universo.id)
    if not expansion:
        st.warning("Esta audiencia no tiene una expansión reciente. Expandila primero en Audiencias.")
        if st.button("Ir a Audiencias", key="est_expand_first", use_container_width=True):
            go_to_page("Audiencias")
        return

    st.session_state["est_selected_universe"] = universo
    st.session_state["est_expansion"] = expansion

    personas = expansion["payload"].personas
    st.success(f"Audiencia seleccionada: {universo.nombre} ({len(personas)} personas expandidas)")

    if st.button("Continuar →", key="est_step1_next", use_container_width=True):
        set("wiz_study_step", 2)
        st.rerun()


def _render_step_2_configure():
    """Paso 2: Configurar pregunta y contexto."""
    render_section_title("2. Configurá el estudio")

    titulo = st.text_input(
        "Título del estudio",
        key="est_titulo",
        placeholder="Ej: Propuesta de valor Q3 2024",
    )
    pregunta = st.text_area(
        "Pregunta principal del estudio",
        key="est_pregunta",
        height=100,
        placeholder="Ej: ¿Qué propuesta de valor te haría elegir esta opción sobre las alternativas?",
    )
    contexto = st.text_area(
        "Contexto del estudio (opcional)",
        key="est_contexto",
        height=80,
        placeholder="Ej: Mercado competitivo, inflación alta y alta desconfianza en promesas de marca.",
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("← Volver", key="est_step2_back", use_container_width=True):
            set("wiz_study_step", 1)
            st.rerun()
    with c2:
        if st.button("Continuar →", key="est_step2_next", use_container_width=True):
            if not titulo.strip():
                st.error("El título del estudio es obligatorio.")
            elif not pregunta.strip():
                st.error("La pregunta del estudio es obligatoria.")
            else:
                st.session_state["est_titulo_saved"] = titulo.strip()
                st.session_state["est_pregunta_saved"] = pregunta.strip()
                st.session_state["est_contexto_saved"] = contexto.strip()
                set("wiz_study_step", 3)
                st.rerun()


def _render_step_3_sample():
    """Paso 3: Configurar muestra."""
    render_section_title("3. Configurá la muestra")

    expansion = st.session_state.get("est_expansion")
    if not expansion:
        st.error("No hay expansión seleccionada.")
        return

    personas = expansion["payload"].personas
    total = len(personas)

    c1, c2, c3 = st.columns(3)
    with c1:
        limite = st.number_input(
            "Personas a procesar",
            min_value=1,
            max_value=total,
            value=min(120, total),
            key="est_limite",
        )
    with c2:
        rpp = st.number_input(
            "Respuestas por persona",
            min_value=1,
            max_value=5,
            value=1,
            key="est_rpp",
        )
    with c3:
        render_stat_card("Personas disponibles", str(total))

    total_respuestas = int(limite) * int(rpp)
    render_soft_panel(
        "Resumen",
        f"**Personas a procesar:** {int(limite)}\n\n"
        f"**Respuestas esperadas:** {total_respuestas}\n\n"
        f"**Audiencia:** {st.session_state.get('est_selected_universe', {}).nombre if st.session_state.get('est_selected_universe') else 'N/A'}",
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("← Volver", key="est_step3_back", use_container_width=True):
            set("wiz_study_step", 2)
            st.rerun()
    with c2:
        if st.button("Continuar →", key="est_step3_next", use_container_width=True):
            st.session_state["est_limite_saved"] = int(limite)
            st.session_state["est_rpp_saved"] = int(rpp)
            set("wiz_study_step", 4)
            st.rerun()


def _render_step_4_execute():
    """Paso 4: Revisar costo y ejecutar."""
    render_section_title("4. Ejecutar estudio")

    universo = st.session_state.get("est_selected_universe")
    expansion = st.session_state.get("est_expansion")
    titulo = st.session_state.get("est_titulo_saved", "")
    pregunta = st.session_state.get("est_pregunta_saved", "")
    contexto = st.session_state.get("est_contexto_saved", "")
    limite = int(st.session_state.get("est_limite_saved", 120))
    rpp = int(st.session_state.get("est_rpp_saved", 1))

    if not universo or not expansion:
        st.error("Faltan datos del estudio.")
        return

    personas = expansion["payload"].personas[:limite]
    total_tareas = len(personas) * rpp

    # Estimar costo (Bypassed)
    credits_engine = st.session_state.get("credits_engine")

    # Verificar API
    saved_key = st.session_state.get("saved_api_key", "")
    if not saved_key:
        st.error("No hay API key configurada. Configurala en Configuración.")
        return

    st.markdown("**¿Ejecutar el estudio ahora?**")
    
    # Confirmación prominente de la muestra
    confirm_cols = st.columns(3)
    with confirm_cols[0]:
        render_stat_card("Personas a procesar", str(len(personas)))
    with confirm_cols[1]:
        render_stat_card("Respuestas por persona", str(rpp))
    with confirm_cols[2]:
        render_stat_card("Total de tareas", str(total_tareas))
    
    st.info(f"Se procesarán **{len(personas)}** personas de la audiencia '{universo.nombre}'.")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("← Volver", key="est_step4_back", use_container_width=True):
            set("wiz_study_step", 3)
            st.rerun()
    with c2:
        if st.button("Ejecutar estudio", key="est_run", use_container_width=True, type="primary"):
            st.session_state["est_stop_flag"] = False
            _execute_study(universo, personas, titulo, pregunta, contexto, rpp, credits_engine)


def _execute_study(universo, personas, titulo, pregunta, contexto, rpp, credits_engine):
    """Ejecuta el estudio con progreso."""
    try:
        engine = LLMService()
        if not engine.is_ready():
            st.error("API key inválida o no configurada.")
            return

        estudio = Estudio(
            id=_new_study_id(universo.id),
            universo_id=universo.id,
            universo_nombre=universo.nombre,
            titulo=titulo.strip(),
            pregunta=pregunta.strip(),
            contexto=contexto.strip(),
            template="custom",
            respuestas_por_persona=rpp,
        )
        save_study(estudio)

        respuestas: List[RespuestaEstudio] = []
        total = len(personas) * rpp
        completadas = 0

        progress = st.progress(0.0)
        status_text = st.empty()
        stop_container = st.empty()

        for idx, persona_dict in enumerate(personas):
            # Botón de detener (se recrea cada iteración para que sea clickeable)
            if stop_container.button("⛔ Detener estudio", key=f"est_stop_{idx}", use_container_width=True):
                st.session_state["est_stop_flag"] = True
                st.warning("Deteniendo estudio...")

            if st.session_state.get("est_stop_flag", False):
                status_text.error("Estudio detenido por el usuario")
                break

            if isinstance(persona_dict, dict):
                persona = persona_dict
            else:
                persona = persona_dict.to_dict() if hasattr(persona_dict, 'to_dict') else {}

            persona_id = str(persona.get("persona_id", "")) or f"P_{len(respuestas) + 1:06d}"
            perfil = str(persona.get("perfil", "")).strip() or "General"

            # Construir perfil para system prompt
            perfil_desc = f"Perfil: {perfil}. {persona.get('perfil_descripcion', '')}"
            detalles = []
            for campo in ["edad_rango", "rol", "industria", "principal_pain", "motivador", "objecion_base", "comportamiento", "canal_preferido"]:
                val = persona.get(campo, "")
                if val:
                    detalles.append(f"{campo}: {val}")
            perfil_completo = f"{perfil_desc}. " + "; ".join(detalles) if detalles else perfil_desc

            system_prompt = _build_system_prompt(perfil_completo, contexto)

            for rep in range(1, rpp + 1):
                user_prompt = _build_user_prompt(pregunta)

                try:
                    result = engine.generate(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        agent_id=persona_id,
                        expect_json=True,
                    )

                    # Parsear resultado
                    if isinstance(result, dict):
                        respuesta_txt = str(result.get("response_text", result.get("_raw", ""))).strip()
                        sentiment = str(result.get("sentiment", "")).strip()
                        intent = str(result.get("intent", "")).strip()
                        main_objection = str(result.get("main_objection", "")).strip()
                        main_driver = str(result.get("main_driver", "")).strip()
                        confidence = str(result.get("confidence", "")).strip()
                        price_sensitivity = str(result.get("price_sensitivity", "")).strip()
                        quote = str(result.get("quote", "")).strip()
                    else:
                        respuesta_txt = str(result).strip()
                        sentiment = intent = main_objection = main_driver = confidence = price_sensitivity = quote = ""

                    respuestas.append(RespuestaEstudio(
                        estudio_id=estudio.id,
                        persona_id=persona_id,
                        perfil=perfil,
                        repeticion=rep,
                        pregunta=pregunta,
                        contexto=contexto,
                        respuesta=respuesta_txt,
                        sintesis=respuesta_txt[:180],
                        sentiment=sentiment,
                        intent=intent,
                        main_objection=main_objection,
                        main_driver=main_driver,
                        confidence=confidence,
                        price_sensitivity=price_sensitivity,
                        quote=quote or respuesta_txt[:120],
                    ))

                    completadas += 1
                    progress.progress(completadas / total)

                except LLMError as e:
                    st.warning(f"Error en {persona_id}: {e}")
                    respuestas.append(RespuestaEstudio(
                        estudio_id=estudio.id,
                        persona_id=persona_id,
                        perfil=perfil,
                        repeticion=rep,
                        pregunta=pregunta,
                        contexto=contexto,
                        respuesta=f"[ERROR: {e}]",
                        sintesis="Error de LLM",
                    ))
                    completadas += 1

            status_text.markdown(f"🤖 **Procesando perfiles:** `{completadas}` de `{total}` respuestas (`{persona_id}` · `{perfil}`)...")

        # Guardar resultados (parciales o completos)
        save_study_results(estudio.id, respuestas)

        detenido = st.session_state.get("est_stop_flag", False)
        if detenido:
            status_text.error(f"Estudio detenido. Se guardaron {len(respuestas)} respuestas de {total} planificadas.")
        else:
            status_text.success(f"¡Estudio completado! Se procesaron {len(personas)} personas.")

        set("tmp_last_study", estudio)
        set("tmp_study_results", [r.to_dict() for r in respuestas])

        if credits_engine:
            credits_engine.consume("Simulación de estudio (1 agente)", quantity=len(respuestas))

        if st.button("Ver resultados →", key="est_go_results", use_container_width=True):
            go_to_page("Resultados")

    except Exception as exc:
        st.error(f"Error al ejecutar el estudio: {exc}")


def render_estudios_page():
    """Renderiza la página completa de estudios con wizard de 4 pasos."""
    render_page_intro(
        "Estudios",
        "Configurá y ejecutá estudios",
        "Elegí una audiencia, escribí tu pregunta y corré simulaciones con seguimiento de progreso.",
    )

    step = get("wiz_study_step", 1)
    step_labels = ["Audiencia", "Pregunta", "Muestra", "Ejecutar"]
    render_stepper(step_labels, step, key_prefix="est_wiz")
    st.divider()

    if step == 1:
        _render_step_1_select_audience()
    elif step == 2:
        _render_step_2_configure()
    elif step == 3:
        _render_step_3_sample()
    elif step == 4:
        _render_step_4_execute()
