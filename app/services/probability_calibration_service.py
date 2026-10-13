"""Calibración experimental offline de B2; no cambia respuestas ni prompts.

El exponente se estima contra grupos de UNA encuesta. La evaluación externa usa
ese parámetro congelado. Se promedian probabilidades individuales, nunca se
eleva a una potencia la distribución agregada ni se optimiza un sorteo.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any, Mapping, Sequence

from app.domain.models import Benchmark
from app.services.study_response_service import normalize_option

DEFAULT_EXPONENTS = (1.0, 1.25, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0)


def sharpen(probabilities: Mapping[str, float], options: Sequence[str], exponent: float) -> dict[str, float]:
    """p^k renormalizado a %, estable incluso con exponentes grandes y ceros."""
    if not math.isfinite(exponent) or exponent <= 0:
        raise ValueError("El exponente debe ser finito y positivo.")
    if not options or len(set(options)) != len(options) or set(probabilities) != set(options):
        raise ValueError("Las probabilidades deben cubrir exactamente las opciones, sin duplicados.")
    values = {o: float(probabilities[o]) for o in options}
    if any(not math.isfinite(v) or v < 0 for v in values.values()) or not any(values.values()):
        raise ValueError("Las probabilidades deben ser finitas, no negativas y sumar más de cero.")
    maximum = max(values.values())
    # Dividir por el máximo antes de potenciar preserva el resultado y evita overflow.
    powered = {o: (v / maximum) ** exponent for o, v in values.items()}
    total = sum(powered.values())
    return {o: v * 100 / total for o, v in powered.items()}


def prepare_rows(answers: Sequence[Mapping[str, Any]], options: Sequence[str], *,
                 population: Sequence[Mapping[str, Any]] = (), group_column: str = "") -> tuple[list[dict], dict]:
    """Una respuesta válida por persona; grupos reales por join estricto de ID.

    Los errores operativos se contabilizan aparte. Una probabilidad mal formada,
    un join incompleto o rondas/repeticiones mezcladas abortan, sin ocultar filas.
    """
    by_id = {}
    if group_column:
        for p in population:
            key = str(p.get("persona_id", ""))
            if not key or key in by_id:
                raise ValueError("La población tiene IDs vacíos o duplicados.")
            by_id[key] = p
        if not by_id:
            raise ValueError("La columna de grupo requiere una población original.")
    rows, seen, excluded = [], set(), Counter()
    for answer in answers:
        key = str(answer.get("persona_id", ""))
        if not key or key in seen:
            raise ValueError("Se requiere una sola respuesta por persona, con ID no vacío.")
        seen.add(key)
        if answer.get("phase", "individual") != "individual" or answer.get("question_index", 1) != 1:
            raise ValueError("Separá preguntas y rondas antes de calibrar.")
        group = str(answer.get("perfil", "")).strip()
        if group_column:
            if key not in by_id:
                raise ValueError(f"Falta persona {key} en la población original.")
            group = str((by_id[key].get("datos_reales") or {}).get(group_column, "")).strip()
        if not group:
            raise ValueError("Hay personas sin grupo de comparación.")
        text = str(answer.get("respuesta", "")).strip()
        if str(answer.get("error") or "").strip() or not text or text.startswith("[ERROR"):
            excluded[group] += 1
            continue
        probabilities = answer.get("probabilidades")
        if not isinstance(probabilities, dict) or not probabilities:
            raise ValueError("Faltan probabilidades individuales B2; el resumen del log no las reemplaza.")
        rows.append({"persona_id": key, "grupo": group, "probabilidades": sharpen(probabilities, options, 1),
                     "modelo": str((answer.get("llm_metadata") or {}).get("model", ""))})
    if not rows:
        raise ValueError("No hay respuestas B2 válidas.")
    return rows, {"n_intentadas": len(answers), "n_validas": len(rows),
                  "errores_por_grupo": dict(excluded)}


def _errors(simulated: Mapping[str, float], real: Mapping[str, float], options: Sequence[str]) -> dict:
    if set(real) != set(options) or any(not math.isfinite(float(v)) or float(v) < 0 for v in real.values()):
        raise ValueError("El benchmark tiene opciones o porcentajes inválidos.")
    if not math.isclose(sum(real.values()), 100, abs_tol=0.1):
        raise ValueError("La distribución real debe sumar 100%.")
    errors = [abs(simulated[o] - real[o]) for o in options]
    return {"mae_pp": sum(errors) / len(options), "tvd_pp": sum(errors) / 2,
            "simulado": dict(simulated), "real": dict(real)}


def evaluate(rows: Sequence[Mapping[str, Any]], benchmark: Benchmark, exponent: float = 1) -> dict:
    """Error total y dentro de cada grupo, sin ruido de sorteo ni margen ficticio.

    El promedio ponderado usa n de personas simuladas por grupo; no es error de
    predicción individual ni ponderación de encuesta. También se informa macro.
    """
    if not rows:
        raise ValueError("No hay probabilidades para evaluar.")
    options = benchmark.opciones
    totals = {o: 0.0 for o in options}
    groups, counts = {}, Counter()
    real_names = {normalize_option(g): g for g in benchmark.por_segmento}
    if len(real_names) != len(benchmark.por_segmento):
        raise ValueError("Los nombres de grupo del benchmark son ambiguos.")
    for row in rows:
        group = str(row["grupo"])
        if normalize_option(group) not in real_names:
            raise ValueError(f"El grupo {group} no tiene benchmark real.")
        probabilities = sharpen(row["probabilidades"], options, exponent)
        groups.setdefault(group, {o: 0.0 for o in options})
        counts[group] += 1
        for option, value in probabilities.items():
            totals[option] += value
            groups[group][option] += value
    segments = []
    for group in sorted(groups):
        real_name = real_names[normalize_option(group)]
        segments.append({"grupo": group, "n_sim": counts[group],
                         "n_real": benchmark.n_por_segmento.get(real_name, 0),
                         **_errors({o: v / counts[group] for o, v in groups[group].items()},
                                   benchmark.por_segmento[real_name], options)})
    total = _errors({o: v / len(rows) for o, v in totals.items()}, benchmark.distribucion, options)
    covered = {normalize_option(g) for g in groups}
    return {"exponente": exponent, "n": len(rows), "total": total, "grupos": segments,
            "mae_grupos_macro_pp": sum(s["mae_pp"] for s in segments) / len(segments),
            "mae_grupos_ponderado_pp": sum(s["mae_pp"] * s["n_sim"] for s in segments) / len(rows),
            "grupos_reales_sin_muestra": sorted(g for g in benchmark.por_segmento if normalize_option(g) not in covered)}


def fit(rows: Sequence[Mapping[str, Any]], benchmark: Benchmark,
        exponents: Sequence[float] = DEFAULT_EXPONENTS) -> dict:
    """Elige k por MAE macro de grupos solo en entrenamiento; empate -> menor k."""
    candidates = sorted(set(exponents) | {1.0})
    scores = [evaluate(rows, benchmark, k) for k in candidates]
    best = min(scores, key=lambda s: (s["mae_grupos_macro_pp"], s["exponente"]))
    return {"exponente": best["exponente"], "objetivo": "mae_grupos_macro_pp",
            "grilla": candidates, "en_limite_superior": best["exponente"] == candidates[-1],
            "bruto": next(s for s in scores if s["exponente"] == 1), "ajustado": best,
            "candidatos": [{"exponente": s["exponente"], "total_mae_pp": s["total"]["mae_pp"],
                            "mae_grupos_macro_pp": s["mae_grupos_macro_pp"],
                            "mae_grupos_ponderado_pp": s["mae_grupos_ponderado_pp"]} for s in scores]}


def benchmark_signature(benchmark: Benchmark) -> tuple[str, str, str]:
    """La misma fuente/ola/pregunta no se vuelve externa cambiando su ID."""
    return (benchmark.fuente.strip().casefold(), benchmark.fecha.strip().casefold(),
            normalize_option(benchmark.pregunta))


def require_external(calibration: Mapping[str, Any], benchmark: Benchmark, models: Sequence[str]) -> None:
    training = calibration["entrenamiento"]
    if benchmark.id == training["benchmark_id"] or list(benchmark_signature(benchmark)) == training["benchmark_firma"]:
        raise ValueError("El benchmark de prueba es el de entrenamiento; otra corrida no es otra encuesta.")
    if sorted(models) != sorted(training["modelos"]):
        raise ValueError("La corrección es por modelo; se necesita entrenamiento B2 del mismo modelo.")


def wave_change(first: Mapping[str, float], second: Mapping[str, float], *,
                positive: Sequence[str], negative: Sequence[str]) -> float:
    """Cambio de saldo (segunda ola menos primera), en pp."""
    if not positive or not negative or set(positive) & set(negative):
        raise ValueError("Definí opciones positivas y negativas no vacías y disjuntas.")
    if len(set(positive)) != len(positive) or len(set(negative)) != len(negative):
        raise ValueError("No repitas opciones en el saldo.")
    if any(o not in first or o not in second for o in [*positive, *negative]):
        raise ValueError("Las opciones del saldo deben existir en ambas olas.")
    def balance(dist):
        return sum(dist[o] for o in positive) - sum(dist[o] for o in negative)
    return balance(second) - balance(first)
