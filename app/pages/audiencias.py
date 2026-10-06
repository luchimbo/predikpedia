"""
app/pages/audiencias.py — Página de Audiencias con wizard de 2 pasos.

Paso 1: Describir la audiencia y generar las personas
Paso 2: Revisar y guardar
"""

import re
from dataclasses import replace
from datetime import datetime
from typing import List

import pandas as pd
import streamlit as st

from app.components.evidence import render_evidence_panel, session_store
from app.components.shell import render_empty_state, render_page_intro, render_section_title, render_stepper, render_stat_card
from app.domain.models import PerfilCliente, Universo
from app.services.audience_design_service import AudienceDesignError, design_segments
from app.services.evidence_service import build_source_population
from app.services.llm_service import LLMService
from app.services.population_import_service import (
    ROLE_ATTRIBUTE,
    ROLE_GROUP,
    ROLES,
    PopulationImportError,
    build_population,
    is_personal_column,
    read_table,
    suggest_mapping,
)
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


MODE_DESCRIBE = "Describir con palabras"
MODE_UPLOAD = "Subir datos reales"
MODE_SUPPORT = "Chats de soporte"


def _restore_form(defaults):
    """Restaura widgets desde aud_form.

    Streamlit borra el estado de los widgets que no se dibujan, así que al
    volver desde "Revisar" se restauran desde la copia guardada en aud_form.
    """
    form = st.session_state.get("aud_form", {})
    for key, default in defaults:
        if key not in st.session_state:
            st.session_state[key] = form.get(key, default)


def _finish_step_1(form: dict):
    st.session_state["aud_form"] = form
    st.session_state.pop("aud_just_saved", None)
    set("wiz_audience_step", 2)
    st.rerun()


def _render_step_1_define():
    """Paso 1: describir la audiencia (o subir datos reales) y generar las personas."""
    _render_just_saved()

    render_section_title("1. ¿A quién querés preguntarle?")
    store = session_store()
    if store:
        render_evidence_panel(store)
    support_sources = [s for s in store.list_sources() if s["kind"] == "support_csv"] if store else []
    modos = [MODE_DESCRIBE, MODE_UPLOAD] + ([MODE_SUPPORT] if support_sources else [])
    _restore_form([("aud_modo", MODE_DESCRIBE), ("aud_nombre", ""), ("aud_descripcion", ""), ("aud_cantidad", 100)])
    if st.session_state.get("aud_modo") not in modos:
        st.session_state["aud_modo"] = MODE_DESCRIBE
    modo = st.radio(
        "¿Cómo querés armar la audiencia?",
        modos,
        key="aud_modo",
        horizontal=True,
        help=(
            "Con palabras, la IA arma los grupos a partir de tu descripción. "
            "Con datos reales, cada persona es una fila de tu archivo (encuesta, clientes, padrón)."
        ),
    )
    if modo == MODE_UPLOAD:
        _render_upload_form()
    elif modo == MODE_SUPPORT:
        _render_support_form(store, support_sources)
    else:
        _render_describe_form()


def _render_describe_form():
    if st.button("Cargar un ejemplo", key="aud_load_example"):
        st.session_state.update(EXAMPLE)
        st.rerun()

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
        _finish_step_1({
            "aud_modo": MODE_DESCRIBE, "aud_nombre": nombre,
            "aud_descripcion": descripcion, "aud_cantidad": int(cantidad),
        })


def _render_upload_form():
    st.caption(
        "Subí un CSV o Excel con **una fila por persona real** (por ejemplo una encuesta o tu base de clientes). "
        "Cada persona de la audiencia va a ser una de esas filas, con todos sus datos juntos."
    )
    uploaded = st.file_uploader("Archivo", type=["csv", "xlsx", "xls"], key="aud_file")
    is_new_file = False
    if uploaded is not None:
        previous = st.session_state.get("aud_upload") or {}
        is_new_file = previous.get("name") != uploaded.name or previous.get("data") != uploaded.getvalue()
        st.session_state["aud_upload"] = {"name": uploaded.name, "data": uploaded.getvalue()}
    upload = st.session_state.get("aud_upload")
    if not upload:
        return

    try:
        df = read_table(upload["data"], upload["name"])
    except PopulationImportError as exc:
        st.error(str(exc))
        return
    if is_new_file:
        # Por defecto, una persona por fila real.
        st.session_state["aud_cantidad"] = len(df)
    st.markdown(f"**{upload['name']}** · {len(df)} filas · {len(df.columns)} columnas")

    # ── Para qué sirve cada columna ──────────────────────────────
    form = st.session_state.get("aud_form", {})
    saved_mapping = form.get("mapping") if form.get("archivo") == upload["name"] else None
    mapping = saved_mapping or suggest_mapping(df)
    editor_df = pd.DataFrame([
        {
            "Columna": col,
            "Ejemplo": next((str(v) for v in df[col].dropna().head(3) if str(v).strip()), ""),
            "Uso": mapping.get(col, ROLE_ATTRIBUTE),
        }
        for col in df.columns
    ])
    st.markdown("**¿Para qué sirve cada columna?**")
    edited = st.data_editor(
        editor_df,
        key=f"aud_mapping_{upload['name']}_{len(upload['data'])}",
        hide_index=True,
        use_container_width=True,
        disabled=["Columna", "Ejemplo"],
        column_config={
            "Uso": st.column_config.SelectboxColumn("Uso", options=ROLES, required=True),
        },
    )
    mapping = dict(zip(edited["Columna"], edited["Uso"]))
    st.caption(
        "**atributo**: dato de la persona que ve la IA · **grupo**: segmento para leer resultados · "
        "**peso**: ponderador de la encuesta · **respuesta real**: lo que la gente contestó a tu pregunta; "
        "no se le muestra a la IA (si la ve, copia la respuesta) · **ignorar**: no se usa."
    )
    personales = [c for c, rol in mapping.items() if rol in (ROLE_ATTRIBUTE, ROLE_GROUP) and is_personal_column(c)]
    if personales:
        st.warning(
            "Estas columnas parecen datos personales y se van a mandar a la IA: "
            + ", ".join(personales) + ". Marcalas como **ignorar** salvo que estés seguro."
        )

    nombre = st.text_input(
        "Nombre de la audiencia",
        key="aud_nombre",
        placeholder="Ej: Clientes encuesta 2025",
    )
    descripcion = st.text_area(
        "Contexto de esta población (opcional)",
        key="aud_descripcion",
        height=100,
        placeholder="Ej: Encuesta a clientes de panaderías de GBA, marzo 2025.",
    )
    cantidad = st.number_input(
        "¿Cuántas personas?",
        min_value=1,
        max_value=100000,
        step=10,
        key="aud_cantidad",
        help=(
            f"El archivo tiene {len(df)} filas. Si pedís más personas que filas, algunas filas se repiten "
            "(cada una responde por su cuenta). Si hay columna de peso, las filas salen según su peso."
        ),
    )

    if st.button("Generar personas", key="aud_generate_real", use_container_width=True, type="primary"):
        try:
            universo, personas = build_population(
                df,
                mapping,
                int(cantidad),
                universe_id=_new_universe_id(nombre or upload["name"]),
                nombre=nombre or upload["name"].rsplit(".", 1)[0],
                descripcion=descripcion,
                fuente=f"{upload['name']} ({len(df)} filas)",
            )
        except PopulationImportError as exc:
            st.error(str(exc))
            return
        st.session_state["aud_temp_universo"] = universo
        st.session_state["aud_temp_personas"] = personas
        st.session_state["aud_temp_snapshot"] = build_expansion_snapshot(universo, personas)
        _finish_step_1({
            "aud_modo": MODE_UPLOAD, "aud_nombre": nombre, "aud_descripcion": descripcion,
            "aud_cantidad": int(cantidad), "archivo": upload["name"], "mapping": mapping,
        })


def _render_support_form(store, sources):
    """Panel sintético cuyos antecedentes salen de chats de soporte importados en este equipo."""
    source_id = st.selectbox("Fuente de soporte", [s["id"] for s in sources], key="aud_source",
                             format_func=lambda sid: next(s["label"] for s in sources if s["id"] == sid))
    maximum = len(store.eligible_chats(source_id))
    st.caption(f"{maximum} chats con menciones disponibles. Cada agente usa un escenario de origen distinto; no reproduce a la persona real.")
    if maximum < 1:
        st.warning("La fuente no tiene texto entrante con temas reconocibles. Importá otra fuente o describí la audiencia con palabras.")
        return
    public = [s for s in store.list_sources() if s["kind"] == "public_reviews" and s["stats"].get("privacy_reviewed")]
    additional_sources = st.multiselect(
        "Reseñas como contexto general (opcional)", [s["id"] for s in public], key="aud_public_sources",
        format_func=lambda sid: next(s["label"] for s in public if s["id"] == sid),
    ) if public else []

    nombre = st.text_input("Nombre de la audiencia", key="aud_nombre", placeholder="Ej: Clientes de soporte")
    descripcion = st.text_area("Contexto de esta población", key="aud_descripcion", height=100,
                               placeholder="Ej: Personas que consultaron al soporte técnico de la tienda.")
    st.session_state["aud_cantidad"] = min(int(st.session_state.get("aud_cantidad", 100)), maximum)
    cantidad = st.number_input("¿Cuántas personas?", min_value=1, max_value=maximum, step=10, key="aud_cantidad")
    st.caption("Los datos biográficos desconocidos quedan sin especificar; esta generación no consulta a la IA.")

    if st.button("Generar personas", key="aud_generate_support", use_container_width=True, type="primary"):
        errors = _validate_universe(nombre, descripcion, int(cantidad))
        if errors:
            for err in errors:
                st.error(err)
            return
        universo = Universo(
            id=_new_universe_id(nombre),
            nombre=nombre.strip() or "Audiencia sin nombre",
            descripcion=descripcion.strip(),
            cantidad_personas=int(cantidad),
            prompt_perfil=descripcion.strip(),
            evidence_source_ids=[source_id, *additional_sources],
        )
        try:
            personas = build_source_population(store, universo, source_id)
        except ValueError as exc:
            st.error(str(exc))
            return
        st.session_state["aud_temp_universo"] = universo
        st.session_state["aud_temp_personas"] = personas
        st.session_state["aud_temp_snapshot"] = build_expansion_snapshot(universo, personas)
        _finish_step_1({
            "aud_modo": MODE_SUPPORT, "aud_nombre": nombre,
            "aud_descripcion": descripcion, "aud_cantidad": int(cantidad),
        })


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
    if universo.origen == "datos_reales" or universo.evidence_source_ids or not universo.perfiles:
        # Con datos reales o fuentes de soporte, los porcentajes salen de los datos y no se editan.
        st.dataframe(df_resumen, use_container_width=True, hide_index=True)
    else:
        _render_editable_shares(universo, personas)

    if universo.origen == "datos_reales":
        st.caption(f"Cada persona es una fila real de **{universo.fuente}**.")
        with st.expander("Ver algunas personas de ejemplo"):
            st.dataframe(
                pd.DataFrame([{"Grupo": p.perfil, **p.datos_reales} for p in personas[:25]]),
                use_container_width=True,
                hide_index=True,
            )
    else:
        _render_generated_examples(personas)
    if universo.evidence_source_ids:
        st.caption("Panel sintético sustentado en menciones de soporte. La composición describe esta selección; no estima la proporción de toda la clientela.")

    c1, c2 = st.columns(2)
    with c1:
        back_label = "← Cambiar archivo o columnas" if universo.origen == "datos_reales" else "← Cambiar la descripción"
        if st.button(back_label, key="aud_step2_back", use_container_width=True):
            set("wiz_audience_step", 1)
            st.rerun()
    with c2:
        if st.button("Guardar audiencia", key="aud_save", use_container_width=True, type="primary"):
            try:
                store = session_store()
                if universo.evidence_source_ids and store is None:
                    raise ValueError("Abrí la app local para guardar esta audiencia con evidencia privada.")
                if store:
                    for persona in personas:
                        store.register_agent(universo.id, persona.to_dict())
                save_universe(universo)
                save_expansion(universo.id, snapshot)
            except Exception as exc:
                st.error(f"Error al guardar: {exc}")
                return
            for key in ["aud_temp_universo", "aud_temp_personas", "aud_temp_snapshot",
                        "aud_form", "aud_upload", "aud_modo", "aud_source", "aud_public_sources", "aud_nombre", "aud_descripcion", "aud_cantidad"]:
                st.session_state.pop(key, None)
            st.session_state["aud_just_saved"] = {"id": universo.id, "nombre": universo.nombre}
            set("wiz_audience_step", 1)
            st.rerun()


def _render_editable_shares(universo, personas):
    """Tabla de grupos con el % editable; al aplicar se vuelven a repartir las personas (sin IA)."""
    counts = {perfil.nombre: len([p for p in personas if p.perfil == perfil.nombre]) for perfil in universo.perfiles}
    editor_df = pd.DataFrame([
        {
            "Grupo": perfil.nombre,
            "%": float(perfil.porcentaje),
            "Personas": counts.get(perfil.nombre, 0),
            "Quiénes son": perfil.descripcion,
        }
        for perfil in universo.perfiles
    ])
    version = st.session_state.get("aud_shares_version", 0)
    edited = st.data_editor(
        editor_df,
        key=f"aud_shares_{universo.id}_{version}",
        hide_index=True,
        use_container_width=True,
        disabled=["Grupo", "Personas", "Quiénes son"],
        column_config={
            "%": st.column_config.NumberColumn("%", min_value=0.0, max_value=100.0, step=0.1, format="%.1f"),
        },
    )
    st.caption("Los porcentajes los propuso la IA. Si conocés las proporciones reales, corregilos y aplicá.")

    nuevos = [float(v or 0) for v in edited["%"].tolist()]
    if nuevos == [float(p.porcentaje) for p in universo.perfiles]:
        return
    total = sum(nuevos)
    if total <= 0:
        st.error("Al menos un grupo tiene que tener un porcentaje mayor a 0.")
        return
    if st.button("Aplicar porcentajes", key="aud_apply_shares", use_container_width=True):
        perfiles = [
            replace(perfil, porcentaje=round(valor * 100 / total, 1))
            for perfil, valor in zip(universo.perfiles, nuevos)
        ]
        universo = replace(universo, perfiles=perfiles)
        personas = expand_universe(universo)
        st.session_state["aud_temp_universo"] = universo
        st.session_state["aud_temp_personas"] = personas
        st.session_state["aud_temp_snapshot"] = build_expansion_snapshot(universo, personas)
        st.session_state["aud_shares_version"] = version + 1
        st.rerun()


def _render_generated_examples(personas):
    with st.expander("Ver algunas personas de ejemplo"):
        df_personas = pd.DataFrame([
            {
                "Grupo": p.perfil,
                "Arquetipo": p.arquetipo,
                "Edad": p.edad_rango,
                "Rol": p.rol,
                "Rubro": p.industria,
                "Le preocupa": p.principal_pain,
                "Lo mueve": p.motivador,
                "Objeción": p.objecion_base,
                "Sensibilidad al precio": p.sensibilidad_precio,
                "Canal": p.canal_preferido,
                "Antecedentes": len(p.evidence_refs),
            }
            for p in personas[:25]
        ])
        st.dataframe(df_personas, use_container_width=True, hide_index=True)


def render_audiencias_page():
    """Renderiza la página completa de audiencias con wizard de 2 pasos."""
    render_page_intro(
        "Audiencias",
        "¿A quién querés preguntarle?",
        "Describí a tu público con tus palabras o subí datos reales (encuesta, clientes). Esas personas van a responder tus preguntas.",
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
                "Origen": u.fuente if u.origen == "datos_reales" else "Descripción",
                "Creado": u.created_at,
            }
            for u in universos
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)
