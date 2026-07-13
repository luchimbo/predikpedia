"""
app/pages/audiencias.py — Página de Audiencias con wizard de 3 pasos.

Paso 1: Definir (nombre, descripción, cantidad)
Paso 2: Expandir (generar personas sintéticas)
Paso 3: Revisar (preview y guardar)
"""

import re
from datetime import datetime
from typing import List

import pandas as pd
import streamlit as st

from app.components.shell import render_empty_state, render_page_intro, render_section_title, render_soft_panel, render_stepper, render_stat_card
from app.domain.models import PerfilCliente, Universo
from app.services.universe_service import build_expansion_snapshot, expand_universe
from app.state import get, go_to_page, set
from app.storage.repository import find_latest_expansion, list_universes, save_expansion, save_universe


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


def _render_step_1_define():
    """Paso 1: Definir audiencia."""
    render_section_title("1. Definí tu audiencia")
    render_soft_panel(
        "Brief de audiencia",
        "Escribí una descripción suficientemente concreta para que el motor pueda generar respuestas coherentes. "
        "Incluí rol, contexto, necesidades, objeciones, canales y cualquier segmentación relevante en el mismo texto.",
    )

    if st.button("Cargar ejemplo guiado", key="aud_load_example"):
        st.session_state["aud_nombre"] = "panaderos_gonzalez_catan"
        st.session_state["aud_descripcion"] = (
            "Panaderos de González Catán que toman decisiones de compra para su local. "
            "Mayoría son dueños de panadería con muchos años de oficio, priorizan costo y confianza. "
            "Algunos están modernizando sus negocios y buscan diferenciarse. "
            "También hay comercios chicos que revenden productos y cuidan mucho el margen. "
            "Edad 25-60, compras semanales, usan WhatsApp y redes sociales."
        )
        st.session_state["aud_cantidad"] = 180
        st.rerun()

    nombre = st.text_input(
        "Nombre de la audiencia",
        value=st.session_state.get("aud_nombre_saved", ""),
        key="aud_nombre",
        placeholder="Ej: panaderos_gonzalez_catan",
    )
    descripcion = st.text_area(
        "¿Quiénes van a responder?",
        value=st.session_state.get("aud_descripcion_saved", ""),
        key="aud_descripcion",
        height=180,
        placeholder="Describe con detalle quiénes son las personas que van a responder. Incluí segmentos si los hay...",
    )
    cantidad = st.number_input(
        "¿Cuántas personas querés simular?",
        min_value=1,
        max_value=100000,
        value=int(st.session_state.get("aud_cantidad_saved", 100)),
        step=10,
        key="aud_cantidad",
    )

    if cantidad <= 80:
        st.info("Muestra rápida y económica para una primera lectura.")
    elif cantidad <= 300:
        st.info("Buen balance entre costo, tiempo y diversidad de respuestas.")
    else:
        st.warning("Muestra grande: va a requerir más tiempo y más créditos al ejecutar estudios.")

    if st.button("Continuar a Expandir", key="aud_step1_next", use_container_width=True):
        errors = _validate_universe(nombre, descripcion, int(cantidad))
        if errors:
            for err in errors:
                st.error(err)
        else:
            st.session_state["aud_nombre_saved"] = nombre
            st.session_state["aud_descripcion_saved"] = descripcion
            st.session_state["aud_cantidad_saved"] = int(cantidad)
            set("wiz_audience_step", 2)
            st.rerun()


def _render_step_2_expand():
    """Paso 2: Expandir en personas sintéticas."""
    render_section_title("2. Expandí en personas")
    render_soft_panel(
        "Generación de personas",
        "A partir del brief definido, se generarán personas sintéticas individuales "
        "con características enriquecidas (rol, industria, pain points, motivadores, etc.).",
    )

    nombre = st.session_state.get("aud_nombre_saved", "")
    descripcion = st.session_state.get("aud_descripcion_saved", "")
    cantidad = int(st.session_state.get("aud_cantidad_saved", 100))

    # Mostrar resumen antes de expandir
    st.markdown(f"**Audiencia:** {nombre}")
    st.markdown(f"**Personas:** {cantidad}")
    st.markdown(f"**Descripción:** {descripcion[:200]}...")

    if st.button("Generar personas sintéticas", key="aud_expand_btn", use_container_width=True, type="primary"):
        try:
            # Sin perfiles manuales: se usa un perfil genérico basado en la descripción
            universo = Universo(
                id=_new_universe_id(nombre),
                nombre=nombre.strip() or "Audiencia sin nombre",
                descripcion=descripcion.strip(),
                cantidad_personas=cantidad,
                prompt_perfil=descripcion.strip(),
                perfiles=[],  # Sin perfiles manuales, la expansión creará variedad automáticamente
            )

            personas = expand_universe(universo)
            snapshot = build_expansion_snapshot(universo, personas)

            # Guardar temporalmente
            st.session_state["aud_temp_universo"] = universo
            st.session_state["aud_temp_personas"] = personas
            st.session_state["aud_temp_snapshot"] = snapshot

            st.success(f"{len(personas)} personas generadas correctamente.")
            set("wiz_audience_step", 3)
            st.rerun()

        except Exception as exc:
            st.error(f"Error al expandir: {exc}")

    # Botón volver
    if st.button("← Volver", key="aud_step2_back", use_container_width=True):
        set("wiz_audience_step", 1)
        st.rerun()


def _render_step_3_review():
    """Paso 3: Revisar y guardar."""
    render_section_title("3. Revisá y guardá")

    universo = st.session_state.get("aud_temp_universo")
    personas = st.session_state.get("aud_temp_personas", [])
    snapshot = st.session_state.get("aud_temp_snapshot")

    if not universo or not personas:
        render_empty_state(
            "No hay expansión disponible",
            "Volvé al paso 2 para generar las personas sintéticas.",
            cta_text="Volver a Expandir",
            cta_key="aud_step3_back2",
            on_cta=lambda: (set("wiz_audience_step", 2), st.rerun()),
        )
        return

    # Métricas
    c1, c2, c3 = st.columns(3)
    with c1:
        render_stat_card("Personas generadas", str(len(personas)))
    with c2:
        render_stat_card("Perfiles", str(len({p.perfil for p in personas})))
    with c3:
        render_stat_card("Preview", str(min(25, len(personas))))

    # Resumen por perfil
    df_resumen = pd.DataFrame([
        {"Perfil": perfil, "Cantidad": len([p for p in personas if p.perfil == perfil])}
        for perfil in sorted({p.perfil for p in personas})
    ])
    st.dataframe(df_resumen, use_container_width=True, hide_index=True)

    # Preview de personas
    st.markdown("**Preview de personas (primeras 25):**")
    df_personas = pd.DataFrame([
        {
            "ID": p.persona_id,
            "Perfil": p.perfil,
            "Edad": p.edad_rango,
            "Rol": p.rol,
            "Industria": p.industria,
            "Pain": p.principal_pain,
            "Motivador": p.motivador,
        }
        for p in personas[:25]
    ])
    st.dataframe(df_personas, use_container_width=True, hide_index=True)

    # Guardar
    c1, c2 = st.columns(2)
    with c1:
        if st.button("← Volver", key="aud_step3_back", use_container_width=True):
            set("wiz_audience_step", 2)
            st.rerun()
    with c2:
        if st.button("💾 Guardar audiencia", key="aud_save", use_container_width=True, type="primary"):
            try:
                path_universe = save_universe(universo)
                path_snapshot = save_expansion(universo.id, snapshot)
                st.success(f"Audiencia guardada: {universo.nombre}")
                st.caption(f"Universo: {path_universe}")
                st.caption(f"Expansión: {path_snapshot}")

                # Limpiar estado temporal
                for key in ["aud_temp_universo", "aud_temp_personas", "aud_temp_snapshot"]:
                    if key in st.session_state:
                        del st.session_state[key]

                # Ofrecer ir a estudios
                if st.button("Ir a Estudios →", key="aud_go_studies", use_container_width=True):
                    go_to_page("Estudios")

            except Exception as exc:
                st.error(f"Error al guardar: {exc}")


def render_audiencias_page():
    """Renderiza la página completa de audiencias con wizard de 3 pasos."""
    render_page_intro(
        "Audiencias",
        "Creá y gestioná audiencias sintéticas",
        "Definí a quién querés investigar y generá personas revisables para tus estudios.",
    )

    step = get("wiz_audience_step", 1)
    step_labels = ["Definir", "Expandir", "Revisar"]
    render_stepper(step_labels, step, key_prefix="aud_wiz")
    st.divider()

    # Renderizar paso actual
    if step == 1:
        _render_step_1_define()
    elif step == 2:
        _render_step_2_expand()
    elif step == 3:
        _render_step_3_review()

    # Biblioteca de audiencias guardadas
    st.divider()
    render_section_title("Biblioteca de audiencias")
    universos = list_universes()

    if not universos:
        render_empty_state(
            "No hay audiencias guardadas",
            "Creá tu primera audiencia usando el wizard de arriba.",
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
