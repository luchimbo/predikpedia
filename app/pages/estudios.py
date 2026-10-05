"""
app/pages/estudios.py — Página de Estudios.

Una sola pantalla: elegir audiencia, escribir la pregunta y ejecutar.
El tamaño de la muestra vive en "Opciones avanzadas" con defaults razonables.
Las respuestas se guardan a medida que llegan, así que cortar la ejecución
(recargar, cambiar de página) no pierde lo ya respondido.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

import streamlit as st

from app.components.shell import render_empty_state, render_page_intro, render_section_title, render_soft_panel
from app.domain.models import Estudio, RespuestaEstudio, Universo
from app.services.llm_service import LLMError, LLMService
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
PERSONA_FIELDS = [
    "edad_rango", "rol", "industria", "objetivo", "principal_pain", "motivador",
    "objecion_base", "sensibilidad_precio", "comportamiento", "canal_preferido",
]


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


def _persona_profile(persona: Dict[str, Any]) -> str:
    perfil = str(persona.get("perfil", "")).strip() or "General"
    perfil_desc = f"Perfil: {perfil}. {persona.get('perfil_descripcion', '')}"
    detalles = [f"{campo}: {persona[campo]}" for campo in PERSONA_FIELDS if persona.get(campo)]
    return f"{perfil_desc}. " + "; ".join(detalles) if detalles else perfil_desc


def _personas_for(universo: Universo) -> List[Dict[str, Any]]:
    """Personas de la audiencia. Si nunca se generaron, se generan ahora.

    La generación es determinista a partir de los segmentos guardados y no
    llama al modelo, así que no hace falta mandar al usuario a otra pantalla.
    """
    expansion = find_latest_expansion(universo.id)
    if expansion:
        return list(expansion["payload"].personas)
    personas = expand_universe(universo)
    snapshot = build_expansion_snapshot(universo, personas)
    save_expansion(universo.id, snapshot)
    return list(snapshot.personas)


def _parse_result(result: Any) -> Dict[str, str]:
    if isinstance(result, dict):
        texto = str(result.get("response_text", result.get("_raw", ""))).strip()
        campos = {
            k: str(result.get(k, "")).strip()
            for k in ["sentiment", "intent", "main_objection", "main_driver", "confidence", "price_sensitivity", "quote"]
        }
    else:
        texto = str(result).strip()
        campos = {k: "" for k in ["sentiment", "intent", "main_objection", "main_driver", "confidence", "price_sensitivity", "quote"]}
    campos["respuesta"] = texto
    campos["quote"] = campos["quote"] or texto[:120]
    return campos


def _execute_study(estudio: Estudio, personas: List[Dict[str, Any]], engine: LLMService) -> List[RespuestaEstudio]:
    """Ejecuta el estudio guardando las respuestas cada pocas llamadas."""
    save_study(estudio)
    respuestas: List[RespuestaEstudio] = []
    total = len(personas) * estudio.respuestas_por_persona

    progress = st.progress(0.0)
    status_text = st.empty()
    st.caption("Podés salir de esta pantalla cuando quieras: lo que ya se respondió queda guardado.")

    user_prompt = _build_user_prompt(estudio.pregunta)
    for idx, persona in enumerate(personas, start=1):
        persona_id = str(persona.get("persona_id", "")) or f"P_{idx:06d}"
        perfil = str(persona.get("perfil", "")).strip() or "General"
        system_prompt = _build_system_prompt(_persona_profile(persona), estudio.contexto)

        for rep in range(1, estudio.respuestas_por_persona + 1):
            base = dict(
                estudio_id=estudio.id,
                persona_id=persona_id,
                perfil=perfil,
                repeticion=rep,
                pregunta=estudio.pregunta,
                contexto=estudio.contexto,
            )
            try:
                result = engine.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    agent_id=persona_id,
                    expect_json=True,
                )
                campos = _parse_result(result)
                respuestas.append(RespuestaEstudio(**base, sintesis=campos["respuesta"][:180], **campos))
            except LLMError as exc:
                respuestas.append(RespuestaEstudio(**base, respuesta="", sintesis="Error del modelo", error=str(exc)))

            progress.progress(len(respuestas) / total)
            status_text.markdown(f"Respuestas: **{len(respuestas)} de {total}** · último perfil: {perfil}")
            if len(respuestas) % SAVE_EVERY == 0:
                save_study_results(estudio.id, respuestas)

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
        max_personas = max(1, universo.cantidad_personas)
        limite = st.number_input(
            "Cantidad de personas que responden",
            min_value=1,
            max_value=max_personas,
            value=min(DEFAULT_SAMPLE, max_personas),
            key=f"est_limite_{universo.id}",
            help="Más personas = resultados más estables, pero tarda más.",
        )
        rpp = st.number_input(
            "Respuestas por persona",
            min_value=1,
            max_value=5,
            value=1,
            key="est_rpp",
            help="Pedirle más de una respuesta a cada persona sirve para ver cuánto varía.",
        )

    total = int(limite) * int(rpp)

    # ── 3. Ejecutar ──────────────────────────────────────────────
    render_section_title("3. Ejecutar")
    render_soft_panel(
        "Resumen",
        f"Le vas a preguntar a **{int(limite)} personas** de **{universo.nombre}** "
        f"({total} respuestas en total).",
    )
    if not llm_ready:
        st.warning("No hay un modelo de IA disponible. Revisá la configuración antes de ejecutar.")

    if st.button("Ejecutar estudio", key="est_run", use_container_width=True, type="primary", disabled=not llm_ready):
        if not pregunta.strip():
            st.error("Escribí la pregunta del estudio.")
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
            respuestas_por_persona=int(rpp),
            respuestas_planeadas=len(personas) * int(rpp),
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
