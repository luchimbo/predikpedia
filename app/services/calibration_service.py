"""Comparación entre la distribución simulada y un resultado real (benchmark), sin UI.

Métricas, siempre en puntos porcentuales (pp):
- MAE: error absoluto medio por opción. "En promedio, cada opción se equivoca X pp".
- TVD (distancia de variación total): la mitad de la suma de errores absolutos. Es el
  % de respuestas que habría que mover de opción para que la simulación coincida con la real.
- Margen por azar: cuánto puede diferir una opción solo por el tamaño de las dos muestras
  (95%, aproximación normal). Una diferencia menor que el margen no se puede distinguir del ruido.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

import pandas as pd

from app.domain.models import Benchmark
from app.services.analysis_service import valid_responses
from app.services.study_response_service import match_option, normalize_option

Z_95 = 1.96


def distribution(values: Iterable[str], options: Sequence[str]) -> Dict[str, float]:
    """Porcentaje por opción (todas las opciones aparecen, aunque sea con 0)."""
    counts = Counter(v for v in values if v in options)
    total = sum(counts.values())
    if not total:
        return {}
    return {o: counts.get(o, 0) * 100 / total for o in options}


def simulated_distributions(resultados_df: pd.DataFrame, options: Sequence[str],
                            phase: Optional[str] = None) -> Dict[str, Any]:
    """Distribución simulada total y por grupo, a partir de las respuestas guardadas.

    Solo cuentan las respuestas válidas con una opción elegida. phase filtra la
    ronda en estudios de interacción ("individual" o "after_interaction").
    """
    df = valid_responses(resultados_df)
    if not df.empty and phase and "phase" in df:
        df = df.loc[df["phase"] == phase]
    if df.empty or "opcion_elegida" not in df:
        return {"total": {}, "n": 0, "por_segmento": {}, "n_por_segmento": {}}
    df = df.loc[df["opcion_elegida"].isin(options)]
    por_segmento, n_por_segmento = {}, {}
    if "perfil" in df:
        for perfil, group in df.groupby("perfil"):
            por_segmento[str(perfil)] = distribution(group["opcion_elegida"], options)
            n_por_segmento[str(perfil)] = len(group)
    return {"total": distribution(df["opcion_elegida"], options), "n": len(df),
            "por_segmento": por_segmento, "n_por_segmento": n_por_segmento}


def max_margin_of_error(n: int) -> float:
    """Margen al 95% (en pp) de una muestra de n, en el peor caso (p = 50%)."""
    return Z_95 * math.sqrt(0.25 / n) * 100 if n > 0 else math.inf


def compare(simulated: Mapping[str, float], real: Mapping[str, float], options: Sequence[str],
            n_sim: int, n_real: int) -> Dict[str, Any]:
    """Compara dos distribuciones sobre las mismas opciones."""
    rows: List[Dict[str, Any]] = []
    for option in options:
        sim, act = float(simulated.get(option, 0.0)), float(real.get(option, 0.0))
        # Margen de la diferencia entre dos proporciones independientes.
        if n_sim > 0 and n_real > 0:
            # Con 0% o 100% la fórmula da margen 0; se usa 50% para no declarar certeza falsa.
            p_eff = act / 100 if 0 < act < 100 else 0.5
            noise = Z_95 * math.sqrt(p_eff * (1 - p_eff) * (1 / n_sim + 1 / n_real)) * 100
        else:
            noise = math.inf
        diff = sim - act
        rows.append({"opcion": option, "simulado": sim, "real": act, "diferencia": diff,
                     "margen_azar": noise, "fuera_de_margen": abs(diff) > noise})
    abs_errors = [abs(r["diferencia"]) for r in rows]
    mae = sum(abs_errors) / len(abs_errors) if abs_errors else 0.0
    tvd = sum(abs_errors) / 2
    sim_top, real_top = _leader(simulated, options), _leader(real, options)
    return {
        "filas": rows,
        "mae": mae,
        "tvd": tvd,
        "n_sim": n_sim,
        "n_real": n_real,
        "misma_opcion_ganadora": bool(sim_top) and sim_top == real_top,
        "ganadora_simulada": sim_top,
        "ganadora_real": real_top,
        "opciones_fuera_de_margen": sum(1 for r in rows if r["fuera_de_margen"]),
    }


def _leader(dist: Mapping[str, float], options: Sequence[str]) -> str:
    """Opción más elegida; un empate se informa como tal en vez de elegir una al azar."""
    if not dist:
        return ""
    top = max(dist.get(o, 0.0) for o in options)
    leaders = [o for o in options if abs(dist.get(o, 0.0) - top) < 0.05]
    return leaders[0] if len(leaders) == 1 else "empate entre " + " y ".join(leaders)


def compare_with_benchmark(resultados_df: pd.DataFrame, benchmark: Benchmark,
                           phase: Optional[str] = None) -> Dict[str, Any]:
    """Comparación total y por segmento entre un estudio cerrado y su benchmark.

    Los segmentos se emparejan por nombre (sin tildes ni mayúsculas). Los que no
    tienen par se informan aparte en vez de compararse con otra cosa.
    """
    options = list(benchmark.opciones)
    sim = simulated_distributions(resultados_df, options, phase)
    total = compare(sim["total"], benchmark.distribucion, options, sim["n"], benchmark.n) if sim["n"] else None

    real_by_key = {normalize_option(name): name for name in benchmark.por_segmento}
    segmentos, sin_par_sim = [], []
    for perfil, dist in sim["por_segmento"].items():
        real_name = real_by_key.pop(normalize_option(perfil), None)
        if real_name is None:
            sin_par_sim.append(perfil)
            continue
        cmp = compare(dist, benchmark.por_segmento[real_name], options,
                      sim["n_por_segmento"][perfil], benchmark.n_por_segmento.get(real_name, 0))
        segmentos.append({"segmento": perfil, **cmp})
    return {
        "total": total,
        "segmentos": sorted(segmentos, key=lambda s: -s["n_sim"]),
        "segmentos_sin_par_simulados": sorted(sin_par_sim),
        "segmentos_sin_par_reales": sorted(real_by_key.values()),
        "sim": sim,
    }


# ── Construir benchmarks ─────────────────────────────────────────────────────


def map_values(values: Iterable[Any], options: Sequence[str],
               manual: Optional[Mapping[str, str]] = None) -> Dict[str, Optional[str]]:
    """Valor real distinto -> opción del estudio (None = se descarta).

    manual tiene prioridad (valor -> opción, o "" para descartar); el resto se
    empareja por texto con match_option. Los números no se toman como índice:
    en una encuesta real "1" suele ser un código, no la primera opción.
    """
    manual = manual or {}
    mapping: Dict[str, Optional[str]] = {}
    for raw in values:
        key = "" if raw is None or (isinstance(raw, float) and math.isnan(raw)) else str(raw).strip()
        if key in mapping:
            continue
        if key in manual:
            mapping[key] = manual[key] or None
        elif key.isdigit():
            mapping[key] = None
        else:
            mapping[key] = match_option(key, options)
    return mapping


def benchmark_from_rows(df: pd.DataFrame, option_column: str, options: Sequence[str], *,
                        segment_column: str = "", manual_mapping: Optional[Mapping[str, str]] = None,
                        weight_column: str = "", **meta: Any) -> tuple[Benchmark, Dict[str, int]]:
    """Arma un Benchmark desde microdatos (una fila por respondente).

    Devuelve el benchmark y los valores descartados con su cantidad de filas, para
    mostrarlos: un valor sin mapear no debe desaparecer en silencio.
    """
    if option_column not in df:
        raise ValueError(f"No existe la columna {option_column}.")
    if segment_column and segment_column not in df:
        raise ValueError(f"No existe la columna {segment_column}.")
    keys = df[option_column].map(lambda v: "" if pd.isna(v) else str(v).strip())
    mapping = map_values(keys.unique(), options, manual_mapping)
    mapped = keys.map(mapping)
    descartados = {k: int(c) for k, c in keys[mapped.isna()].value_counts().items()}
    if weight_column:
        if weight_column not in df:
            raise ValueError(f"No existe la columna {weight_column}.")
        raw_weights = df[weight_column].astype(str).str.replace(",", ".", regex=False)
        weights = pd.to_numeric(raw_weights, errors="coerce").fillna(0).clip(lower=0)
    else:
        weights = pd.Series(1.0, index=df.index)
    keep = mapped.notna() & (weights > 0)
    if not keep.any():
        raise ValueError("Ninguna fila corresponde a las opciones del estudio. Revisá la correspondencia de valores.")

    def weighted(mask: pd.Series) -> Dict[str, float]:
        totals = weights[mask].groupby(mapped[mask]).sum()
        total = float(totals.sum())
        return {o: float(totals.get(o, 0.0)) * 100 / total for o in options}

    por_segmento, n_por_segmento = {}, {}
    if segment_column:
        segs = df[segment_column].map(lambda v: "Sin dato" if pd.isna(v) or not str(v).strip() else str(v).strip())
        for seg in segs[keep].unique():
            mask = keep & (segs == seg)
            por_segmento[seg] = weighted(mask)
            n_por_segmento[seg] = int(mask.sum())
    benchmark = Benchmark(
        id=meta.pop("id", ""), nombre=meta.pop("nombre", ""), pregunta=meta.pop("pregunta", ""),
        opciones=list(options), distribucion=weighted(keep),
        # n son filas (respondentes), no la suma de pesos: es lo que define el margen de error.
        n=int(keep.sum()), por_segmento=por_segmento, n_por_segmento=n_por_segmento,
        segmento_columna=segment_column, **meta,
    )
    return benchmark, descartados


def benchmark_from_counts(counts: Mapping[str, float], options: Sequence[str], n: int = 0, **meta: Any) -> Benchmark:
    """Benchmark desde totales publicados (porcentajes o cantidades por opción).

    Si no se informa n y los valores son cantidades enteras, n es su suma.
    """
    values = {o: max(float(counts.get(o, 0) or 0), 0.0) for o in options}
    total = sum(values.values())
    if total <= 0:
        raise ValueError("Cargá al menos un valor mayor que cero.")
    if n <= 0:
        if all(v.is_integer() for v in values.values()) and abs(total - 100) > 0.5:
            n = int(total)
        else:
            raise ValueError("Indicá cuántas personas respondieron la encuesta real (n).")
    return Benchmark(
        id=meta.pop("id", ""), nombre=meta.pop("nombre", ""), pregunta=meta.pop("pregunta", ""),
        opciones=list(options), distribucion={o: v * 100 / total for o, v in values.items()}, n=int(n), **meta,
    )


def verdict(result: Mapping[str, Any]) -> str:
    """Una línea en lenguaje llano sobre una comparación total."""
    mae, n_sim, n_real = result["mae"], result["n_sim"], result["n_real"]
    partes = [f"En promedio, cada opción se desvía {mae:.1f} pp del resultado real."]
    partes.append("La opción más elegida coincide." if result["misma_opcion_ganadora"]
                  else f"Más elegida en la simulación: {result['ganadora_simulada']}; en la real: {result['ganadora_real']}.")
    fuera = result["opciones_fuera_de_margen"]
    if fuera:
        partes.append(f"{fuera} opción(es) se desvían más de lo que explica el tamaño de las muestras.")
    else:
        partes.append("Ninguna desviación supera lo que se espera por azar con estas muestras.")
    if min(n_sim, n_real) < 100:
        partes.append(f"Ojo: con {min(n_sim, n_real)} respuestas el margen por azar es grande; la comparación es orientativa.")
    return " ".join(partes)
