"""
app/pages/estudios.py — Página de Estudios con wizard de 4 pasos.

Paso 1: Elegir audiencia
Paso 2: Configurar pregunta y contexto
Paso 3: Configurar muestra
Paso 4: Revisar costo y ejecutar
"""

from datetime import datetime
from typing import List
from uuid import uuid4

import pandas as pd
import streamlit as st

from app.components.shell import render_empty_state, render_page_intro, render_section_title, render_soft_panel, render_stepper, render_stat_card
from app.components.evidence import session_store
from app.domain.models import Estudio, RespuestaEstudio
from app.services.llm_service import LLMError, LLMService
from app.services.simulation_service import planned_tasks, run_simulation, social_graph
from app.state import get, go_to_page, set
from app.storage.repository import (
    find_latest_expansion,
    list_universes,
    save_study,
    save_study_results,
)


def _new_study_id(universe_id: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"study_{universe_id}_{ts}_{uuid4().hex[:8]}"


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
    if any(p.get("evidence_refs") for p in personas) and not st.session_state.get("private_storage_available", False):
        st.warning("Esta audiencia usa evidencia privada. Abrí la app en el equipo de origen con scripts/start_private_app.ps1 para continuar.")
        return
    st.success(f"Audiencia seleccionada: {universo.nombre} ({len(personas)} personas expandidas)")

    if st.button("Continuar →", key="est_step1_next", use_container_width=True):
        set("wiz_study_step", 2)
        st.rerun()


def _render_step_2_configure():
    """Paso 2: Configurar pregunta y contexto."""
    render_section_title("2. Configurá el estudio")
    modes = {"survey": "Encuesta independiente", "interview": "Entrevista con seguimiento", "social": "Interacción entre agentes"}
    saved_mode = st.session_state.get("est_mode_saved", "survey")
    mode = st.selectbox("Modalidad", list(modes), format_func=modes.get,
                        index=list(modes).index(saved_mode), key="est_mode")
    memory_enabled, follow_up, social_seed = False, [], 42
    if mode == "survey":
        st.caption("Cada repetición responde sin ver respuestas anteriores ni opiniones de otros agentes.")
    else:
        private_available = bool(st.session_state.get("private_storage_available", False))
        memory_enabled = st.checkbox("Conservar y recuperar historial de este participante", value=private_available,
                                     disabled=not private_available, key="est_memory",
                                     help="El historial queda separado por usuario, audiencia e identidad. Las respuestas simuladas no se convierten en hechos de origen.")
        if mode == "interview":
            raw_follow_up = st.text_area("Preguntas de seguimiento (una por línea, hasta cuatro)",
                                         value="\n".join(st.session_state.get("est_follow_up_saved", [])), key="est_follow_up")
            follow_up = [line.strip() for line in raw_follow_up.splitlines() if line.strip()]
            st.caption("Las preguntas del mismo estudio comparten historial, aunque no lo conserves para futuras entrevistas.")
        else:
            st.caption("Primero responde cada agente por separado. Después ve las opiniones iniciales de hasta dos vecinos y vuelve a responder.")
            with st.expander("Configuración de la red"):
                social_seed = int(st.number_input("Semilla para asignar vecinos", min_value=0, value=42, step=1, key="est_social_seed"))

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
            elif len(follow_up) > 4:
                st.error("La entrevista admite hasta cuatro preguntas de seguimiento. Reducí la lista para continuar.")
            else:
                st.session_state["est_titulo_saved"] = titulo.strip()
                st.session_state["est_pregunta_saved"] = pregunta.strip()
                st.session_state["est_contexto_saved"] = contexto.strip()
                st.session_state["est_mode_saved"] = mode
                st.session_state["est_memory_saved"] = memory_enabled
                st.session_state["est_follow_up_saved"] = follow_up
                st.session_state["est_social_seed_saved"] = social_seed
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
    mode = st.session_state.get("est_mode_saved", "survey")

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
        if mode == "survey":
            rpp = st.number_input("Respuestas por persona", min_value=1, max_value=5, value=1, key="est_rpp")
        else:
            rpp = 1
            if mode == "interview":
                render_stat_card("Preguntas por persona", str(1 + len(st.session_state.get("est_follow_up_saved", []))))
            else:
                render_stat_card("Rondas", "2")
    with c3:
        render_stat_card("Personas disponibles", str(total))

    rpp = int(rpp) if mode == "survey" else 1
    per_person = 2 if mode == "social" else (1 + len(st.session_state.get("est_follow_up_saved", [])) if mode == "interview" else rpp)
    total_respuestas = int(limite) * per_person
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
            if mode == "social" and int(limite) < 2:
                st.error("La interacción necesita al menos dos personas. Aumentá la muestra para continuar.")
                return
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
    mode = st.session_state.get("est_mode_saved", "survey")
    per_person = 2 if mode == "social" else (1 + len(st.session_state.get("est_follow_up_saved", [])) if mode == "interview" else rpp)
    total_tareas = len(personas) * per_person

    # Estimar costo (Bypassed)
    credits_engine = st.session_state.get("credits_engine")

    # Verificar API
    saved_key = st.session_state.get("saved_api_key", "")
    if not LLMService().is_ready():
        st.error("No hay API key configurada. Configurala en Configuración.")
        return

    st.markdown("**¿Ejecutar el estudio ahora?**")
    
    # Confirmación prominente de la muestra
    confirm_cols = st.columns(3)
    with confirm_cols[0]:
        render_stat_card("Personas a procesar", str(len(personas)))
    with confirm_cols[1]:
        render_stat_card("Tareas por persona", str(per_person))
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
    """Run through the UI-free simulation service, checkpointing every response."""
    try:
        engine = LLMService()
        if not engine.is_ready():
            st.error("No hay un modelo disponible. Revisá Configuración y volvé a ejecutar.")
            return
        personas = [p if isinstance(p, dict) else p.to_dict() for p in personas]
        mode = st.session_state.get("est_mode_saved", "survey")
        estudio = Estudio(
            id=_new_study_id(universo.id), universo_id=universo.id,
            universo_nombre=universo.nombre, titulo=titulo.strip(),
            pregunta=pregunta.strip(), contexto=contexto.strip(), template="custom",
            respuestas_por_persona=rpp if mode == "survey" else 1,
            simulation_version="realism_v2", mode=mode,
            memory_enabled=st.session_state.get("est_memory_saved", False) if mode != "survey" else False,
            follow_up_questions=st.session_state.get("est_follow_up_saved", []) if mode == "interview" else [],
            social_seed=st.session_state.get("est_social_seed_saved", 42),
        )
        if mode == "social":
            estudio.interaction_graph = social_graph([p["persona_id"] for p in personas], estudio.social_seed)
        save_study(estudio)
        respuestas: List[RespuestaEstudio] = []
        progress, status_text, stop_container = st.progress(0.0), st.empty(), st.empty()
        stop_checks = 0

        def should_stop():
            nonlocal stop_checks
            def mark_stopped():
                st.session_state["est_stop_flag"] = True
            if stop_container.button("Detener estudio", key=f"est_stop_{stop_checks}", use_container_width=True, on_click=mark_stopped):
                st.session_state["est_stop_flag"] = True
            stop_checks += 1
            return st.session_state.get("est_stop_flag", False)

        def on_response(answer, done, total):
            respuestas.append(answer)
            save_study_results(estudio.id, respuestas)
            progress.progress(done / total)
            status_text.markdown(f"Procesando: **{done} de {total}** tareas · {answer.phase}")
            if answer.respuesta.startswith("[ERROR:"):
                st.warning(f"{answer.persona_id}: no se obtuvo una respuesta válida.")

        run_simulation(estudio, personas, engine, store=session_store(),
                       on_response=on_response, should_stop=should_stop)
        total = planned_tasks(estudio, len(personas))
        if st.session_state.get("est_stop_flag", False):
            status_text.warning(f"Estudio detenido. Se guardaron {len(respuestas)} de {total} tareas.")
        else:
            valid = sum(not r.respuesta.startswith("[ERROR:") for r in respuestas)
            status_text.success(f"Estudio terminado: {valid} respuestas válidas de {total} tareas.")
        set("tmp_last_study", estudio)
        set("tmp_study_results", [r.to_dict() for r in respuestas])
        if credits_engine:
            credits_engine.consume("Simulación de estudio (1 agente)", quantity=len(respuestas))
        if st.button("Ver resultados →", key="est_go_results", use_container_width=True):
            go_to_page("Resultados")
    except Exception as exc:
        st.error(f"No se pudo completar el estudio: {exc}")


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
