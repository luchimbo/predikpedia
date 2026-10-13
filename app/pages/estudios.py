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
from app.services.study_response_service import normalize_option
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
# Con temperature 1 el muestreo respeta las probabilidades del modelo: bajarla homogeneiza
# las respuestas y achata la distribución que después se compara con una encuesta real.
STUDY_TEMPERATURE = 1.0
MAX_OPTIONS = 12
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


def _render_mode_options(sample_size: int) -> Dict[str, Any]:
    """Modalidad del estudio y sus opciones. Devuelve la configuración elegida."""
    choices = {"auto": "Automática", **MODES}
    selected = st.selectbox("Modalidad", list(choices), format_func=choices.get, key="est_mode")
    automatic = selected == "auto"
    mode = ("social" if sample_size >= 2 else "survey") if automatic else selected
    config: Dict[str, Any] = {"mode": mode, "automatic": automatic, "memory_enabled": False, "follow_up": [], "social_seed": 42}
    if mode == "survey":
        if automatic:
            st.caption("Con una sola persona, la respuesta es independiente. Con dos o más, se activa la interacción automáticamente.")
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
    if st.session_state.get("public_research_mode", False):
        from app.components.public_research import render_public_research
        render_public_research()
        return
    render_page_intro(
        "Estudios",
        "Hacé una pregunta a tu audiencia",
        "Elegí a quién preguntarle, escribí la pregunta y ejecutá. Al terminar vas directo a los resultados.",
    )

    if st.session_state.get("private_storage_available", False):
        if st.button("Preparar con evidencia pública", key="est_prepare_public"):
            st.session_state["public_research_mode"] = True
            st.rerun()

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
    research_snapshot_id = universo.research_snapshot_id
    if research_snapshot_id:
        store = session_store()
        if not store:
            st.warning("Esta audiencia requiere su expediente local. Iniciá scripts/start_private_app.ps1 en el equipo de origen.")
            return
        from app.storage.research_repository import ResearchRepository
        repo = ResearchRepository(store)
        if st.session_state.get("est_public_universe_id") == universo.id:
            research_snapshot_id = st.session_state.get("est_public_snapshot") or research_snapshot_id
        snapshot = repo.get_snapshot(research_snapshot_id)
        if not snapshot:
            st.error("Falta el expediente de evidencia de esta audiencia en este equipo.")
            return
        if st.session_state.get("est_public_previous_audience") != universo.id:
            from app.domain.research_models import ResearchBrief
            brief = ResearchBrief(**snapshot["project"]["brief"])
            st.session_state.update(est_pregunta=brief.question, est_contexto=brief.participant_stimulus,
                                    est_mode="survey", est_rpp=1, est_memory=False,
                                    est_tipo="cerrada" if brief.options else "abierta", est_opciones="\n".join(brief.options))
        engine = LLMService(local_only=True)
        llm_ready = engine.is_ready()
        st.caption("Esta audiencia usa evidencia pública guardada y responde exclusivamente con Ollama.")
    st.session_state["est_public_previous_audience"] = universo.id if research_snapshot_id else ""
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
    tipo = st.radio(
        "Tipo de respuesta",
        ["abierta", "cerrada"],
        format_func={"abierta": "Abierta (cada uno responde con sus palabras)",
                     "cerrada": "Cerrada (eligen una opción)"}.get,
        key="est_tipo",
        horizontal=True,
        help="Con opciones, el resultado es un % por opción y se puede comparar contra una encuesta real en Resultados → Validación.",
    )
    opciones: List[str] = []
    if tipo == "cerrada":
        raw_opciones = st.text_area(
            "Opciones (una por línea)",
            key="est_opciones",
            height=110,
            placeholder="Milei\nKicillof\nOtro\nNo sabe",
            help="Si vas a comparar con una encuesta real, usá las mismas opciones que tuvo, incluido 'No sabe' si estaba.",
        )
        # "No sabe" y "no sabé" son la misma opción para el modelo: se queda la primera.
        unicas: Dict[str, str] = {}
        for line in raw_opciones.splitlines():
            if normalize_option(line):
                unicas.setdefault(normalize_option(line), line.strip())
        opciones = list(unicas.values())
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
        max_personas = max(1, universo.cantidad_personas)
        limite = st.number_input(
            "Cantidad de personas que responden",
            min_value=1,
            max_value=max_personas,
            value=min(DEFAULT_SAMPLE, max_personas),
            key=f"est_limite_{universo.id}",
            help="Más personas = resultados más estables, pero tarda más.",
        )
        config = _render_mode_options(int(limite))
        rpp = 1
        if config["mode"] == "survey":
            rpp = int(st.number_input(
                "Respuestas por persona",
                min_value=1,
                max_value=5,
                value=None if "est_rpp" in st.session_state else 1,
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
    if mode == "social":
        st.caption("Cada participante responde, lee las opiniones iniciales de hasta dos vecinos y vuelve a responder. El resultado muestra la ronda final.")
    if not llm_ready:
        st.warning("No hay un modelo de IA disponible. Revisá la configuración antes de ejecutar.")

    if st.button("Ejecutar estudio", key="est_run", use_container_width=True, type="primary", disabled=not llm_ready):
        if not pregunta.strip():
            st.error("Escribí la pregunta del estudio.")
            return
        if tipo == "cerrada" and not 2 <= len(opciones) <= MAX_OPTIONS:
            st.error(f"Escribí entre 2 y {MAX_OPTIONS} opciones distintas, una por línea.")
            return
        if tipo == "cerrada" and mode == "interview":
            st.error("Las preguntas cerradas funcionan en encuesta o interacción. Cambiá la modalidad en Opciones avanzadas.")
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

        # El snapshot puede tener menos personas que la cantidad declarada.
        if config["automatic"] and len(personas) < 2:
            mode = plan.mode = "survey"

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
            memory_enabled=config["memory_enabled"] if mode != "survey" else False,
            follow_up_questions=config["follow_up"],
            social_seed=config["social_seed"],
            opciones=opciones,
            temperature=STUDY_TEMPERATURE,
            research_snapshot_id=research_snapshot_id,
            local_only=bool(research_snapshot_id),
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
