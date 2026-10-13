"""Congela una corrección por grupo SOLO en entrenamiento, sin llamadas LLM.

Desplazamiento logarítmico por opción, acotado a log(3) y reducido por
n_sim/(n_sim+30). Grupos con menos de 20 respuestas usan el ajuste global.
Estos límites son fijos: no se eligen contra el control. El baseline usa las
frecuencias reales de entrenamiento por grupo (n_real>=50), o el total.
"""

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.probability_calibration_service import evaluate, require_external, sharpen
from tools.calibrate_probabilities import fingerprint, load_dataset, save_private


def offsets(real, expected, n):
    if n < 1:
        raise ValueError("La corrección requiere observaciones de entrenamiento.")
    limit = math.log(3)
    return {o: max(-limit, min(limit, math.log((real[o] + .5) / (expected[o] + .5)))) * n / (n + 30)
            for o in real}


def fit_correction(rows, benchmark, source):
    raw = evaluate(rows, benchmark)
    global_offset = offsets(raw["total"]["real"], raw["total"]["simulado"], raw["n"])
    groups = {}
    for group in raw["grupos"]:
        usable = group["n_sim"] >= 20
        groups[group["grupo"]] = {
            "n_sim": group["n_sim"], "n_real": group["n_real"],
            "ajuste_especifico": usable,
            "offsets": offsets(group["real"], group["simulado"], group["n_sim"]) if usable else global_offset,
        }
    return {
        "schema_version": 1, "tipo": "correccion_log_por_grupo", "estado": "pendiente_validacion_externa",
        "created_at": datetime.now(timezone.utc).isoformat(), "entrenamiento": source,
        "opciones": benchmark.opciones, "smoothing_pp": .5, "max_ratio": 3,
        "prior_n": 30, "min_n_sim": 20, "offsets_globales": global_offset, "grupos": groups,
        "baseline": {"tipo": "frecuencias_entrenamiento_por_grupo", "min_n_real": 50,
                     "global": benchmark.distribucion,
                     "por_grupo": {g: d for g, d in benchmark.por_segmento.items()
                                   if benchmark.n_por_segmento.get(g, 0) >= 50}},
        "costo_usd": 0,
    }


def apply_correction(rows, artifact, benchmark, models):
    require_external(artifact, benchmark, models)
    if list(benchmark.opciones) != artifact["opciones"]:
        raise ValueError("Otra escala necesita otra corrección; no se colapsan opciones.")
    return transform_rows(rows, artifact)


def transform_rows(rows, artifact):
    """Aplica offsets congelados por persona; grupo nuevo usa el global."""
    options = artifact["opciones"]
    output = []
    for row in rows:
        probabilities = sharpen(row["probabilidades"], options, 1)
        delta = artifact["grupos"].get(row["grupo"], {}).get("offsets", artifact["offsets_globales"])
        adjusted = sharpen({o: probabilities[o] * math.exp(delta[o]) for o in options}, options, 1)
        output.append({**row, "probabilidades": adjusted})
    return output


def baseline_rows(rows, artifact):
    baseline = artifact["baseline"]
    return [{**r, "probabilidades": dict(baseline["por_grupo"].get(r["grupo"], baseline["global"]))}
            for r in rows]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--population", required=True)
    parser.add_argument("--group-column", default="partido_que_votaria")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    rows, benchmark, source = load_dataset(args.results, args.benchmark, args.population, args.group_column)
    artifact = fit_correction(rows, benchmark, source)
    artifact["diagnostico_entrenamiento"] = {
        "bruto": evaluate(rows, benchmark),
        "corregido": evaluate(transform_rows(rows, artifact), benchmark),
        "baseline": evaluate(baseline_rows(rows, artifact), benchmark),
    }
    save_private(args.out, artifact)
    diag = artifact["diagnostico_entrenamiento"]
    summary = {"experiment_type": "group_probability_calibration", "stage": "fit",
               "benchmark_id": benchmark.id, "models": source["modelos"], "n": len(rows),
               "label": "Corrección log por grupo acotada · solo entrenamiento",
               "validacion_externa": False, "costo_usd": 0,
               "mae_macro_bruto_pp": diag["bruto"]["mae_grupos_macro_pp"],
               "mae_macro_corregido_pp": diag["corregido"]["mae_grupos_macro_pp"],
               "artifact": fingerprint(args.out)}
    with (ROOT / "tools/experiments_log.jsonl").open("a", encoding="utf8") as fh:
        fh.write(json.dumps(summary, ensure_ascii=False, allow_nan=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
