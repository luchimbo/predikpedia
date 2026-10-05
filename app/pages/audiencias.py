"""
app/pages/audiencias.py — Página de Audiencias con wizard de 2 pasos.

Paso 1: Describir la audiencia y generar las personas
Paso 2: Revisar y guardar
"""

import re
from datetime import datetime
from typing import List

import pandas as pd
import streamlit as st

from app.components.shell import render_empty_state, render_page_intro, render_section_title, render_stepper, render_stat_card
from app.domain.models import PerfilCliente, Universo
from app.services.audience_design_service import AudienceDesignError, design_segments
from app.services.llm_service import LLMService
from app.services.universe_service import build_expansion_snapshot, expand_universe
from app.state import get, go_to_page, set
from app.storage.repository import list_universes, save_expansion, save_universe


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "universo"


def _new_universe_id(nombre: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"universe_{_slugify(nombre)}_{ts}"


def _validate_universe(nombre: str, descripcion: str, cantidad: int) -> List[str]:
    errors = []
    if not descripcion.strip():
        errors.append("La descripción de quiénes van a responder es obligatoria.")
    if cantidad <= 0:
        errors.append("La cantidad de personas debe ser mayor a 0.")
    return errors


EXAMPLE = {
    "aud_nombre": "Panaderos de González Catán",
    "aud_descripcion": (
        "Panaderos de González Catán que toman decisiones de compra para su local. "
        "Mayoría son dueños de panadería con muchos años de oficio, priorizan costo y confianza. "
        "Algunos están modernizando sus negocios y buscan diferenciarse. "
        "También hay comercios chicos que revenden productos y cuidan mucho el margen. "
        "Edad 25-60, compras semanales, usan WhatsApp y redes sociales."
    ),
    "aud_cantidad": 180,
}


def _render_just_saved():
    """Confirmación después de guardar, dibujada fuera del handler del botón."""
    saved = st.session_state.get("aud_just_saved")
    if not saved:
        return
    with st.container(border=True):
        st.success(f"Audiencia guardada: **{saved['nombre']}**")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Hacerle una pregunta →", key="aud_go_studies", use_container_width=True, type="primary"):
                st.session_state.pop("aud_just_saved", None)
                st.session_state["est_preselect_universe"] = saved["id"]
                go_to_page("Estudios")
        with c2:
            if st.button("Crear otra audiencia", key="aud_new_another", use_container_width=True):
                st.session_state.pop("aud_just_saved", None)
                st.rerun()


def _generate(nombre: str, descripcion: str, cantidad: int, usar_ia: bool):
    """Diseña los segmentos (1 llamada al modelo) y genera las personas."""
    perfiles: List[PerfilCliente] = []
    if usar_ia:
        with st.spinner("Armando los segmentos de tu audiencia..."):
            try:
                perfiles = design_segments(descripcion)
            except AudienceDesignError as exc:
                st.session_state["aud_design_warning"] = (
                    f"No se pudieron diseñar los segmentos con IA ({exc}). "
                    "Se usaron atributos genéricos."
                )

    universo = Universo(
        id=_new_universe_id(nombre),
        nombre=nombre.strip() or "Audiencia sin nombre",
        descripcion=descripcion.strip(),
        cantidad_personas=cantidad,
        prompt_perfil=descripcion.strip(),
        perfiles=perfiles,  # Vacío = perfil "General" con atributos genéricos
    )
    personas = expand_universe(universo)
    st.session_state["aud_temp_universo"] = universo
    st.session_state["aud_temp_personas"] = personas
    st.session_state["aud_temp_snapshot"] = build_expansion_snapshot(universo, personas)


def _render_step_1_define():
    """Paso 1: describir la audiencia y generar las personas."""
    _render_just_saved()

    render_section_title("1. Describí a quién querés preguntarle")

    if st.button("Cargar un ejemplo", key="aud_load_example"):
        st.session_state.update(EXAMPLE)
        st.rerun()

    # Streamlit borra el estado de los widgets que no se dibujan, así que al
    # volver desde "Revisar" se restauran desde la copia guardada en aud_form.
    form = st.session_state.get("aud_form", {})
    for key, default in (("aud_nombre", ""), ("aud_descripcion", ""), ("aud_cantidad", 100)):
        if key not in st.session_state:
            st.session_state[key] = form.get(key, default)

    nombre = st.text_input(
        "Nombre de la audiencia",
        key="aud_nombre",
        placeholder="Ej: Panaderos de González Catán",
    )
    descripcion = st.text_area(
        "¿Quiénes son?",
        key="aud_descripcion",
        height=180,
        placeholder=(
            "Quiénes son, dónde están, a qué se dedican, qué les preocupa, cómo compran. "
            "Si hay grupos distintos, contalos con su proporción aproximada."
        ),
    )
    cantidad = st.number_input(
        "¿Cuántas personas?",
        min_value=1,
        max_value=100000,
        step=10,
        key="aud_cantidad",
        help="Es el tamaño de la audiencia. Al hacer un estudio podés preguntarle a una parte.",
    )

    llm_ready = LLMService(api_key=st.session_state.get("saved_api_key") or None).is_ready()
    usar_ia = llm_ready
    if not llm_ready:
        st.caption("No hay un modelo de IA disponible: las personas se van a generar con atributos genéricos.")

    if st.button("Generar personas", key="aud_generate", use_container_width=True, type="primary"):
        errors = _validate_universe(nombre, descripcion, int(cantidad))
        if errors:
            for err in errors:
                st.error(err)
            return
        try:
            _generate(nombre, descripcion, int(cantidad), usar_ia)
        except Exception as exc:
            st.error(f"No se pudieron generar las personas: {exc}")
            return
        st.session_state["aud_form"] = {
            "aud_nombre": nombre, "aud_descripcion": descripcion, "aud_cantidad": int(cantidad),
        }
        st.session_state.pop("aud_just_saved", None)
        set("wiz_audience_step", 2)
        st.rerun()


def _render_step_2_review():
    """Paso 2: revisar y guardar."""
    render_section_title("2. Revisá y guardá")

    universo = st.session_state.get("aud_temp_universo")
    personas = st.session_state.get("aud_temp_personas", [])
    snapshot = st.session_state.get("aud_temp_snapshot")

    if not universo or not personas:
        set("wiz_audience_step", 1)
        st.rerun()

    warning = st.session_state.pop("aud_design_warning", "")
    if warning:
        st.warning(warning)

    c1, c2 = st.columns(2)
    with c1:
        render_stat_card("Personas", str(len(personas)))
    with c2:
        render_stat_card("Grupos", str(len({p.perfil for p in personas})))

    descripciones = {perfil.nombre: perfil.descripcion for perfil in universo.perfiles}
    df_resumen = pd.DataFrame([
        {
            "Grupo": perfil,
            "Personas": len([p for p in personas if p.perfil == perfil]),
            "Quiénes son": descripciones.get(perfil, ""),
        }
        for perfil in sorted({p.perfil for p in personas})
    ])
    st.dataframe(df_resumen, use_container_width=True, hide_index=True)

    with st.expander("Ver algunas personas de ejemplo"):
        df_personas = pd.DataFrame([
            {
                "Grupo": p.perfil,
                "Edad": p.edad_rango,
                "Rol": p.rol,
                "Rubro": p.industria,
                "Le preocupa": p.principal_pain,
                "Lo mueve": p.motivador,
                "Objeción": p.objecion_base,
                "Sensibilidad al precio": p.sensibilidad_precio,
                "Canal": p.canal_preferido,
            }
            for p in personas[:25]
        ])
        st.dataframe(df_personas, use_container_width=True, hide_index=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("← Cambiar la descripción", key="aud_step2_back", use_container_width=True):
            set("wiz_audience_step", 1)
            st.rerun()
    with c2:
        if st.button("Guardar audiencia", key="aud_save", use_container_width=True, type="primary"):
            try:
                save_universe(universo)
                save_expansion(universo.id, snapshot)
            except Exception as exc:
                st.error(f"Error al guardar: {exc}")
                return
            for key in ["aud_temp_universo", "aud_temp_personas", "aud_temp_snapshot",
                        "aud_form", "aud_nombre", "aud_descripcion", "aud_cantidad"]:
                st.session_state.pop(key, None)
            st.session_state["aud_just_saved"] = {"id": universo.id, "nombre": universo.nombre}
            set("wiz_audience_step", 1)
            st.rerun()


def render_audiencias_page():
    """Renderiza la página completa de audiencias con wizard de 2 pasos."""
    render_page_intro(
        "Audiencias",
        "¿A quién querés preguntarle?",
        "Describí a tu público con tus palabras. La app arma los grupos y las personas que después van a responder tus preguntas.",
    )

    step = get("wiz_audience_step", 1)
    if step not in (1, 2):
        step = 1
    render_stepper(["Describir", "Revisar y guardar"], step, key_prefix="aud_wiz")
    st.divider()

    if step == 1:
        _render_step_1_define()
    else:
        _render_step_2_review()

    # Biblioteca de audiencias guardadas
    st.divider()
    render_section_title("Tus audiencias")
    universos = list_universes()

    if not universos:
        render_empty_state(
            "No hay audiencias guardadas",
            "Creá tu primera audiencia con el formulario de arriba.",
        )
    else:
        df = pd.DataFrame([
            {
                "Nombre": u.nombre,
                "Descripción": u.descripcion[:80] + "..." if len(u.descripcion) > 80 else u.descripcion,
                "Personas": u.cantidad_personas,
                "Creado": u.created_at,
            }
            for u in universos
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)
