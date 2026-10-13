"""Compara B2, p^k, corrección por grupo y baseline con parámetros congelados.

Solo evaluación offline. Cada opción/grupo y los casos sin entrenamiento quedan
en el artefacto privado. No usa los resultados de prueba para elegir un método.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.probability_calibration_service import evaluate, require_external
from tools.calibrate_probabilities import fingerprint, load_dataset, read_json, save_private
from tools.fit_group_probability_correction import apply_correction, baseline_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--power-calibration", required=True)
    parser.add_argument("--group-calibration", required=True)
    parser.add_argument("--planned-n", type=int, default=0, help="Tamaño planeado para identificar checkpoints parciales")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    rows, benchmark, source = load_dataset(args.results, args.benchmark)
    attempted = source["cobertura"]["n_intentadas"]
    planned = args.planned_n or attempted
    if planned < attempted or args.planned_n < 0:
        raise ValueError("El tamaño planeado no puede ser menor que los casos intentados.")
    status = "partial" if attempted < planned else "complete"
    group_artifact, power_artifact = read_json(args.group_calibration), read_json(args.power_calibration)
    require_external(power_artifact, benchmark, source["modelos"])
    if group_artifact["entrenamiento"] != power_artifact["entrenamiento"]:
        raise ValueError("Los dos ajustes deben provenir de exactamente el mismo entrenamiento.")
    corrected = apply_correction(rows, group_artifact, benchmark, source["modelos"])
    scores = {
        "b2_bruto": evaluate(rows, benchmark),
        "p_potencia": evaluate(rows, benchmark, power_artifact["exponente"]),
        "correccion_log_grupos": evaluate(corrected, benchmark),
        "baseline_encuesta_entrenamiento": evaluate(baseline_rows(rows, group_artifact), benchmark),
    }
    payload = {
        "schema_version": 1, "tipo": "evaluacion_politica_externa", "created_at": datetime.now(timezone.utc).isoformat(),
        "fuente": source, "calibraciones": {"potencia": fingerprint(args.power_calibration), "grupos": fingerprint(args.group_calibration)},
        "parametros_ajustados_en_prueba": False, "costo_usd": 0, "resultados": scores,
        "status": status, "n_planeadas": planned, "n_guardadas": attempted,
        "grupos_sin_ajuste_especifico": sorted({r["grupo"] for r in rows if not group_artifact["grupos"].get(r["grupo"], {}).get("ajuste_especifico")}),
        "grupos_con_baseline_global": sorted({r["grupo"] for r in rows if r["grupo"] not in group_artifact["baseline"]["por_grupo"]}),
        "advertencia": "Otra ola histórica; la aprobación puede cambiar al cambiar el gobierno. No es un control prospectivo ni mide error individual.",
    }
    save_private(args.out, payload)
    summary = {"experiment_type": "political_holdout", "stage": "evaluate", "benchmark_id": benchmark.id,
               "label": "Prueba política externa · cuatro métodos congelados", "models": source["modelos"],
               "n": len(rows), "validacion_externa": True, "costo_usd": 0,
               "status": status, "n_planeadas": planned, "n_guardadas": attempted,
               "metricas": {name: {"mae_macro_pp": s["mae_grupos_macro_pp"], "mae_total_pp": s["total"]["mae_pp"]}
                            for name, s in scores.items()}, "artifact": fingerprint(args.out)}
    with (ROOT / "tools/experiments_log.jsonl").open("a", encoding="utf8") as fh:
        fh.write(json.dumps(summary, ensure_ascii=False, allow_nan=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
