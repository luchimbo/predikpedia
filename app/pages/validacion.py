"""
app/pages/validacion.py — Pestaña "Validación" de Resultados.

Compara la distribución de un estudio con pregunta cerrada contra un resultado
real (benchmark) y muestra el error en puntos porcentuales, total y por grupo.
Es la medición que dice si un cambio en la simulación la acerca o la aleja de la realidad.
"""

from datetime import datetime
from typing import Dict, Optional
from uuid import uuid4

import pandas as pd
import streamlit as st

from app.components.shell import render_section_title, render_soft_panel, render_stat_card
from app.domain.models import Benchmark, Estudio
from app.services.calibration_service import (
    benchmark_from_counts,
    benchmark_from_rows,
    compare_with_benchmark,
    map_values,
    max_margin_of_error,
    verdict,
)
from app.services.population_import_service import PopulationImportError, read_table
from app.services.study_response_service import normalize_option
from app.storage.repository import delete_benchmark, list_benchmarks, load_study_results, save_benchmark

NEW = "__nuevo__"
DISCARD = "(descartar)"
MAX_VALUES_TO_MAP = 40


def _compatible(benchmark: Benchmark, estudio: Estudio) -> bool:
    """Mismo estudio, o las mismas opciones (sin importar tildes ni orden)."""
    if benchmark.estudio_id == estudio.id:
        return True
    return sorted(map(normalize_option, benchmark.opciones)) == sorted(map(normalize_option, estudio.opciones))


def _new_benchmark_id() -> str:
    return f"bench_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"


def _meta_inputs(estudio: Estudio, prefix: str) -> Dict[str, str]:
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        nombre = st.text_input("Nombre", key=f"{prefix}_nombre", placeholder="Ej: Encuesta Opinaia, octubre")
    with c2:
        fuente = st.text_input("Fuente", key=f"{prefix}_fuente", placeholder="Quién la hizo y cómo")
    with c3:
        fecha = st.text_input("Fecha de campo", key=f"{prefix}_fecha", placeholder="2026-09")
    return {"id": _new_benchmark_id(), "nombre": nombre.strip() or "Resultado real", "pregunta": estudio.pregunta,
            "fuente": fuente.strip(), "fecha": fecha.strip(), "estudio_id": estudio.id}


def _render_from_file(estudio: Estudio) -> Optional[Benchmark]:
    st.caption("Subí los microdatos: una fila por persona encuestada, con la opción que eligió. "
               "Si además tiene la columna de grupo de la audiencia, se compara grupo por grupo.")
    uploaded = st.file_uploader("Archivo de la encuesta real", type=["csv", "xlsx", "xls"], key=f"val_file_{estudio.id}")
    if uploaded is None:
        return None
    try:
        df = read_table(uploaded.getvalue(), uploaded.name)
    except PopulationImportError as exc:
        st.error(str(exc))
        return None

    columns = list(df.columns)
    c1, c2, c3 = st.columns(3)
    with c1:
        option_col = st.selectbox("Columna con la respuesta", columns, key=f"val_optcol_{estudio.id}",
                                  index=len(columns) - 1)
    with c2:
        segment_col = st.selectbox("Columna de grupo (opcional)", ["", *columns], key=f"val_segcol_{estudio.id}",
                                   format_func=lambda c: c or "Sin grupos",
                                   help="La misma que usaste como grupo en la audiencia, para comparar grupo por grupo.")
    with c3:
        weight_col = st.selectbox("Columna de peso (opcional)", ["", *columns], key=f"val_wcol_{estudio.id}",
                                  format_func=lambda c: c or "Sin ponderar")

    values = df[option_col].fillna("").astype(str).str.strip()
    counts = values.value_counts()
    auto = map_values(counts.index, estudio.opciones)
    manual: Dict[str, str] = {}
    if len(counts) > MAX_VALUES_TO_MAP:
        st.warning(f"La columna tiene {len(counts)} valores distintos; parece texto libre o un código. "
                   "Elegí la columna con la opción respondida.")
        return None
    with st.expander("¿A qué opción corresponde cada respuesta?", expanded=any(v is None for v in auto.values())):
        st.caption("Lo que coincide por texto ya está asignado. Lo que quede en «descartar» no cuenta.")
        choices = [DISCARD, *estudio.opciones]
        for value, count in counts.items():
            current = auto.get(value)
            picked = st.selectbox(f"«{value or '(vacío)'}» · {count} filas", choices,
                                  index=choices.index(current) if current else 0,
                                  key=f"val_map_{estudio.id}_{option_col}_{value}")
            manual[value] = "" if picked == DISCARD else picked

    meta = _meta_inputs(estudio, f"val_file_meta_{estudio.id}")
    try:
        benchmark, descartados = benchmark_from_rows(
            df, option_col, estudio.opciones, segment_column=segment_col,
            manual_mapping=manual, weight_column=weight_col, **meta,
        )
    except ValueError as exc:
        st.error(str(exc))
        return None
    if descartados:
        st.caption("Descartadas: " + ", ".join(f"«{k or '(vacío)'}» ({v})" for k, v in descartados.items()))
    st.caption(f"{benchmark.n} respuestas válidas · margen de la encuesta real ±{max_margin_of_error(benchmark.n):.1f} pp")
    return benchmark


def _render_from_totals(estudio: Estudio) -> Optional[Benchmark]:
    st.caption("Cargá los porcentajes publicados (o las cantidades) de cada opción.")
    counts = {}
    cols = st.columns(min(4, len(estudio.opciones)))
    for i, option in enumerate(estudio.opciones):
        with cols[i % len(cols)]:
            counts[option] = st.number_input(option, min_value=0.0, value=0.0, step=1.0,
                                             key=f"val_manual_{estudio.id}_{i}")
    n = int(st.number_input("Personas encuestadas (n)", min_value=0, value=0, step=1, key=f"val_manual_n_{estudio.id}",
                            help="Define el margen de error. Si cargás cantidades, se calcula solo."))
    meta = _meta_inputs(estudio, f"val_manual_meta_{estudio.id}")
    if not any(counts.values()):
        return None
    try:
        return benchmark_from_counts(counts, estudio.opciones, n, **meta)
    except ValueError as exc:
        st.error(str(exc))
        return None


def _render_new_benchmark(estudio: Estudio) -> None:
    source = st.radio("¿Cómo lo cargás?", ["archivo", "totales"], horizontal=True, key=f"val_source_{estudio.id}",
                      format_func={"archivo": "Archivo con una fila por persona", "totales": "Escribir los porcentajes"}.get)
    benchmark = _render_from_file(estudio) if source == "archivo" else _render_from_totals(estudio)
    if benchmark is None:
        return
    if st.button("Guardar resultado real", key=f"val_save_{estudio.id}", type="primary", use_container_width=True):
        save_benchmark(benchmark)
        # La key del selector ya se instanció en este run: se aplica en el próximo.
        st.session_state[f"val_bench_next_{estudio.id}"] = benchmark.id
        st.rerun()


def _fmt_pp(value: float) -> str:
    return "—" if value == float("inf") else f"±{value:.1f}"


def _render_comparison(estudio: Estudio, all_df: pd.DataFrame, benchmark: Benchmark) -> None:
    if estudio.research_snapshot_id:
        from app.components.evidence import session_store
        from app.storage.research_repository import ResearchRepository
        from app.services.public_research_service import benchmark_overlaps_research
        store = session_store()
        snapshot = ResearchRepository(store).get_snapshot(estudio.research_snapshot_id) if store else None
        if not snapshot:
            st.warning("Abrí el expediente local para verificar la independencia de la referencia real.")
            return
        if benchmark_overlaps_research(snapshot, benchmark):
            st.error("Esta referencia se usó para construir la audiencia. Elegí otra fuente independiente para validar.")
            return
        st.caption("La independencia requiere otra encuesta o fuente: repetir una corrida no crea una referencia nueva.")
    phase = None
    if estudio.mode == "social":
        labels = {"individual": "Respuesta individual inicial", "after_interaction": "Respuesta tras interacción"}
        phase = st.selectbox("Ronda a comparar", list(labels), format_func=labels.get, key=f"val_phase_{estudio.id}")
    result = compare_with_benchmark(all_df, benchmark, phase)
    total = result["total"]
    if total is None:
        st.info("Todavía no hay respuestas válidas con una opción elegida para comparar.")
        return

    cols = st.columns(3)
    with cols[0]:
        render_stat_card("Error medio por opción", f"{total['mae']:.1f} pp", "Cuanto más bajo, mejor")
    with cols[1]:
        render_stat_card("Respuestas a mover", f"{total['tvd']:.1f}%", "Para igualar la distribución real")
    with cols[2]:
        render_stat_card("Opción ganadora", "Coincide" if total["misma_opcion_ganadora"] else "No coincide")
    render_soft_panel("Lectura", verdict(total))

    table = pd.DataFrame(total["filas"])
    chart = table.set_index("opcion")[["simulado", "real"]].rename(columns={"simulado": "Simulado", "real": "Real"})
    st.bar_chart(chart, horizontal=True, stack=False, x_label="% de respuestas", y_label="")
    st.dataframe(pd.DataFrame({
        "Opción": table["opcion"],
        "Simulado %": table["simulado"].round(1),
        "Real %": table["real"].round(1),
        "Diferencia (pp)": table["diferencia"].round(1),
        "Margen por azar (pp)": table["margen_azar"].map(_fmt_pp),
        "¿Más que el azar?": table["fuera_de_margen"].map({True: "Sí", False: "No"}),
    }), use_container_width=True, hide_index=True)
    st.caption(f"Simulación: {total['n_sim']} respuestas · Real: {total['n_real']} respuestas · "
               f"{benchmark.fuente or 'sin fuente'} {benchmark.fecha}".strip())

    render_section_title("Por grupo")
    if not benchmark.por_segmento:
        st.caption("Este resultado real no tiene grupos. Subí los microdatos con la columna de grupo para ver dónde se equivoca la simulación.")
    elif not result["segmentos"]:
        st.caption("Ningún grupo de la audiencia tiene el mismo nombre que los grupos del resultado real.")
    else:
        st.dataframe(pd.DataFrame([{
            "Grupo": s["segmento"],
            "Respuestas simuladas": s["n_sim"],
            "Respuestas reales": s["n_real"],
            "Error medio (pp)": round(s["mae"], 1),
            "Ganadora real": s["ganadora_real"],
            "Ganadora simulada": s["ganadora_simulada"],
        } for s in result["segmentos"]]), use_container_width=True, hide_index=True)
    unmatched = result["segmentos_sin_par_simulados"] + result["segmentos_sin_par_reales"]
    if benchmark.por_segmento and unmatched:
        st.caption("Sin par para comparar: " + ", ".join(unmatched))


def render_validacion_tab(estudio: Estudio) -> None:
    """Compara el estudio con un resultado real cargado por el usuario."""
    st.caption("Medí qué tan cerca queda la simulación de una encuesta real con la misma pregunta y las mismas opciones.")
    if not estudio.opciones:
        st.info("La validación necesita una pregunta cerrada. En Estudios elegí «Cerrada (eligen una opción)» "
                "y usá las mismas opciones que la encuesta real.")
        return
    all_df = pd.DataFrame([r.to_dict() for r in load_study_results(estudio.id)])
    if all_df.empty:
        st.info("Este estudio todavía no tiene respuestas.")
        return

    benchmarks = [b for b in list_benchmarks() if _compatible(b, estudio)]
    by_id = {b.id: b for b in benchmarks}
    key = f"val_bench_{estudio.id}"
    if f"val_bench_next_{estudio.id}" in st.session_state:
        st.session_state[key] = st.session_state.pop(f"val_bench_next_{estudio.id}")
    if st.session_state.get(key) not in [*by_id, NEW]:
        st.session_state[key] = benchmarks[0].id if benchmarks else NEW
    selected = st.selectbox(
        "Resultado real",
        [*by_id, NEW],
        key=key,
        format_func=lambda bid: "+ Cargar un resultado real" if bid == NEW
        else f"{by_id[bid].nombre} · n={by_id[bid].n}" + (f" · {by_id[bid].fecha}" if by_id[bid].fecha else ""),
    )
    if selected == NEW:
        _render_new_benchmark(estudio)
        return
    _render_comparison(estudio, all_df, by_id[selected])
    if st.button("Borrar este resultado real", key=f"val_delete_{selected}"):
        delete_benchmark(selected)
        st.session_state[f"val_bench_next_{estudio.id}"] = NEW
        st.rerun()
