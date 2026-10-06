"""
app/pages/estudios.py — Página de Estudios.

Una sola pantalla: elegir audiencia, escribir la pregunta y ejecutar.
El tamaño de la muestra y la modalidad viven en "Opciones avanzadas" con
defaults razonables. La ejecución usa simulation_service (sin UI); las
respuestas se guardan a medida que llegan, así que cortar la ejecución
(recargar, cambiar de página) no pierde lo ya respondido.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

import streamlit as st

from app.components.evidence import session_store
from app.components.shell import render_empty_state, render_page_intro, render_section_title, render_soft_panel
from app.domain.models import Estudio, RespuestaEstudio, Universo
from app.services.llm_service import LLMService
from app.services.simulation_service import planned_tasks, run_simulation
from app.services.universe_service import build_expansion_snapshot, expand_universe
from app.state import go_to_page
from app.storage.repository import (
    find_latest_expansion,
    list_universes,
    save_expansion,
    save_study,
    save_study_results,
)

DEFAULT_SAMPLE = 50
SAVE_EVERY = 10
MODES = {
    "survey": "Encuesta independiente",
    "interview": "Entrevista con seguimiento",
    "social": "Interacción entre agentes",
}


def _new_study_id(universe_id: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"study_{universe_id}_{ts}_{uuid4().hex[:8]}"


def _personas_for(universo: Universo) -> List[Dict[str, Any]]:
    """Personas de la audiencia. Si nunca se generaron, se generan ahora.

    La generación es determinista a partir de los segmentos guardados y no
    llama al modelo, así que no hace falta mandar al usuario a otra pantalla.
    """
    expansion = find_latest_expansion(universo.id)
    if expansion:
        return list(expansion["payload"].personas)
    if universo.origen == "datos_reales":
        # Regenerar con expand_universe inventaría atributos que no están en los datos.
        raise ValueError("No se encontraron las personas de esta audiencia. Volvé a cargar el archivo en Audiencias.")
    if universo.evidence_source_ids:
        # Las personas salen de chats de soporte; no se pueden reconstruir desde los segmentos.
        raise ValueError("No se encontraron las personas de esta audiencia. Volvé a generarla desde la fuente de soporte.")
    personas = expand_universe(universo)
    snapshot = build_expansion_snapshot(universo, personas)
    save_expansion(universo.id, snapshot)
    return list(snapshot.personas)


def _render_mode_options() -> Dict[str, Any]:
    """Modalidad del estudio y sus opciones. Devuelve la configuración elegida."""
    mode = st.selectbox("Modalidad", list(MODES), format_func=MODES.get, key="est_mode")
    config: Dict[str, Any] = {"mode": mode, "memory_enabled": False, "follow_up": [], "social_seed": 42}
    if mode == "survey":
        st.caption("Cada repetición responde sin ver respuestas anteriores ni opiniones de otros agentes.")
        return config

    private_available = bool(st.session_state.get("private_storage_available", False))
    config["memory_enabled"] = st.checkbox(
        "Conservar y recuperar historial de este participante",
        value=private_available,
        disabled=not private_available,
        key="est_memory",
        help="El historial queda separado por usuario, audiencia e identidad. Las respuestas simuladas no se convierten en hechos de origen.",
    )
    if mode == "interview":
        raw = st.text_area("Preguntas de seguimiento (una por línea, hasta cuatro)", key="est_follow_up")
        config["follow_up"] = [line.strip() for line in raw.splitlines() if line.strip()]
        st.caption("Las preguntas del mismo estudio comparten historial, aunque no lo conserves para futuras entrevistas.")
    else:
        st.caption("Primero responde cada agente por separado. Después ve las opiniones iniciales de hasta dos vecinos y vuelve a responder.")
        config["social_seed"] = int(st.number_input("Semilla para asignar vecinos", min_value=0, value=42, step=1, key="est_social_seed"))
    return config


def _execute_study(estudio: Estudio, personas: List[Dict[str, Any]], engine: LLMService) -> List[RespuestaEstudio]:
    """Ejecuta el estudio guardando las respuestas cada pocas tareas."""
    save_study(estudio)
    respuestas: List[RespuestaEstudio] = []

    progress = st.progress(0.0)
    status_text = st.empty()
    st.caption("Podés salir de esta pantalla cuando quieras: lo que ya se respondió queda guardado.")

    def on_response(answer: RespuestaEstudio, done: int, total: int):
        respuestas.append(answer)
        if done % SAVE_EVERY == 0:
            save_study_results(estudio.id, respuestas)
        progress.progress(done / total)
        status_text.markdown(f"Respuestas: **{done} de {total}** · último perfil: {answer.perfil}")

    run_simulation(estudio, personas, engine, store=session_store(), on_response=on_response)
    save_study_results(estudio.id, respuestas)
    return respuestas


def render_estudios_page():
    """Renderiza la página de estudios en una sola pantalla."""
    render_page_intro(
        "Estudios",
        "Hacé una pregunta a tu audiencia",
        "Elegí a quién preguntarle, escribí la pregunta y ejecutá. Al terminar vas directo a los resultados.",
    )

    universos = list_universes()
    if not universos:
        render_empty_state(
            "Todavía no tenés audiencias",
            "Primero creá una audiencia: es la gente a la que le vas a preguntar.",
            cta_text="Crear audiencia",
            cta_key="est_go_audiences",
            on_cta=lambda: go_to_page("Audiencias"),
        )
        return

    engine = LLMService(api_key=st.session_state.get("saved_api_key") or None)
    llm_ready = engine.is_ready()

    # ── 1. Audiencia ─────────────────────────────────────────────
    render_section_title("1. ¿A quién le preguntás?")
    ids = [u.id for u in universos]
    preselect: Optional[str] = st.session_state.pop("est_preselect_universe", None)
    if preselect in ids:
        st.session_state["est_audience_id"] = preselect
    if st.session_state.get("est_audience_id") not in ids:
        st.session_state["est_audience_id"] = ids[0]
    by_id = {u.id: u for u in universos}
    universe_id = st.selectbox(
        "Audiencia",
        ids,
        key="est_audience_id",
        format_func=lambda uid: f"{by_id[uid].nombre} · {by_id[uid].cantidad_personas} personas",
    )
    universo = by_id[universe_id]
    if universo.descripcion:
        st.caption(universo.descripcion[:240] + ("..." if len(universo.descripcion) > 240 else ""))
    if universo.evidence_source_ids and not st.session_state.get("private_storage_available", False):
        st.warning("Esta audiencia usa evidencia privada. Abrí la app en el equipo de origen con scripts/start_private_app.ps1 para continuar.")
        return

    # ── 2. Pregunta ──────────────────────────────────────────────
    render_section_title("2. ¿Qué querés saber?")
    pregunta = st.text_area(
        "Pregunta",
        key="est_pregunta",
        height=100,
        placeholder="Ej: ¿Qué te haría cambiar de proveedor de harina? ¿Qué te frena hoy?",
    )
    contexto = st.text_area(
        "Contexto (opcional)",
        key="est_contexto",
        height=80,
        placeholder="Datos que cambian la decisión: precio, alternativas que ya usan, situación del mercado...",
        help="Lo que más ayuda son datos concretos (precios, alternativas, coyuntura), no adjetivos.",
    )
    titulo = st.text_input(
        "Nombre del estudio (opcional)",
        key="est_titulo",
        placeholder="Si lo dejás vacío se usa la pregunta",
    )

    with st.expander("Opciones avanzadas"):
        config = _render_mode_options()
        max_personas = max(1, universo.cantidad_personas)
        limite = st.number_input(
            "Cantidad de personas que responden",
            min_value=1,
            max_value=max_personas,
            value=min(DEFAULT_SAMPLE, max_personas),
            key=f"est_limite_{universo.id}",
            help="Más personas = resultados más estables, pero tarda más.",
        )
        rpp = 1
        if config["mode"] == "survey":
            rpp = int(st.number_input(
                "Respuestas por persona",
                min_value=1,
                max_value=5,
                value=1,
                key="est_rpp",
                help="Pedirle más de una respuesta a cada persona sirve para ver cuánto varía.",
            ))

    mode = config["mode"]
    plan = Estudio(id="", universo_id=universo.id, universo_nombre=universo.nombre, titulo="", pregunta="",
                   contexto="", respuestas_por_persona=rpp, mode=mode, follow_up_questions=config["follow_up"])
    total = planned_tasks(plan, int(limite))

    # ── 3. Ejecutar ──────────────────────────────────────────────
    render_section_title("3. Ejecutar")
    render_soft_panel(
        "Resumen",
        f"Le vas a preguntar a **{int(limite)} personas** de **{universo.nombre}** "
        f"({total} respuestas en total · {MODES[mode].lower()}).",
    )
    if not llm_ready:
        st.warning("No hay un modelo de IA disponible. Revisá la configuración antes de ejecutar.")

    if st.button("Ejecutar estudio", key="est_run", use_container_width=True, type="primary", disabled=not llm_ready):
        if not pregunta.strip():
            st.error("Escribí la pregunta del estudio.")
            return
        if len(config["follow_up"]) > 4:
            st.error("La entrevista admite hasta cuatro preguntas de seguimiento. Reducí la lista para continuar.")
            return
        if mode == "social" and int(limite) < 2:
            st.error("La interacción necesita al menos dos personas. Aumentá la muestra para continuar.")
            return
        try:
            personas = _personas_for(universo)[: int(limite)]
        except Exception as exc:
            st.error(f"No se pudieron preparar las personas de la audiencia: {exc}")
            return

        estudio = Estudio(
            id=_new_study_id(universo.id),
            universo_id=universo.id,
            universo_nombre=universo.nombre,
            titulo=titulo.strip() or pregunta.strip()[:80],
            pregunta=pregunta.strip(),
            contexto=contexto.strip(),
            template="custom",
            respuestas_por_persona=rpp,
            respuestas_planeadas=planned_tasks(plan, len(personas)),
            simulation_version="realism_v2",
            mode=mode,
            memory_enabled=config["memory_enabled"],
            follow_up_questions=config["follow_up"],
            social_seed=config["social_seed"],
        )
        try:
            respuestas = _execute_study(estudio, personas, engine)
        except Exception as exc:
            st.error(f"Error al ejecutar el estudio: {exc}")
            return

        credits_engine = st.session_state.get("credits_engine")
        if credits_engine:
            credits_engine.consume("Simulación de estudio (1 agente)", quantity=len(respuestas))

        st.session_state["res_study_id"] = estudio.id
        go_to_page("Resultados")
