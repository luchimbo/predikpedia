"""Estima y prueba p^k offline, sin llamadas LLM ni cambios en los datos originales.

fit: solo lee entrenamiento y congela k. evaluate: exige otra encuesta/ola y el
mismo modelo. Los artefactos derivados se guardan en .private/ (ignorado).
Para comparar dos olas, --second-results y --second-benchmark calculan cambio
de saldo bruto y corregido, junto al real. No se ajusta nada en evaluate.
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.domain.models import Benchmark
from app.services.probability_calibration_service import (
    benchmark_signature, evaluate, fit, prepare_rows, require_external, wave_change,
)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fingerprint(path):
    return {"path": str(Path(path).resolve()), "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}


def load_dataset(results, benchmark_path, population="", group_column=""):
    benchmark = Benchmark.from_dict(read_json(benchmark_path))
    if not benchmark.fuente or not benchmark.fecha or not benchmark.pregunta or not benchmark.id:
        raise ValueError("El benchmark necesita id, fuente, fecha y pregunta para identificar la encuesta/ola.")
    people = read_json(population).get("personas", []) if population else []
    rows, coverage = prepare_rows(read_json(results), benchmark.opciones, population=people, group_column=group_column)
    models = sorted({r["modelo"] for r in rows})
    if len(models) != 1 or not models[0]:
        raise ValueError("Se necesita una corrida con un solo modelo identificado.")
    source = {"benchmark_id": benchmark.id, "benchmark_firma": list(benchmark_signature(benchmark)),
              "modelos": models, "grupo_columna": group_column or "perfil", "cobertura": coverage,
              "resultados": fingerprint(results), "benchmark": fingerprint(benchmark_path)}
    if population:
        source["poblacion"] = fingerprint(population)
    return rows, benchmark, source


def save_private(path, payload):
    target = Path(path).resolve()
    private = (ROOT / ".private").resolve()
    if not target.is_relative_to(private):
        raise ValueError("Guardá los derivados en .private/ para proteger los datos con licencia.")
    if target.exists():
        raise ValueError("El artefacto ya existe: usá otro nombre para preservar el parámetro congelado.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Artefacto: {target}")


def record_summary(payload, path):
    """Solo agregados al log compartido; filas y derivados quedan privados."""
    training = payload["tipo"] == "calibracion_entrenamiento"
    if training:
        source, raw, corrected = payload["entrenamiento"], payload["bruto"], payload["ajustado"]
    else:
        source = payload["primera"]["fuente"]
        raw, corrected = payload["primera"]["bruto"], payload["primera"]["corregido"]
    entry = {"label": f"p^k {'entrenamiento' if training else 'prueba externa'} · {source['benchmark_id']}",
             "experiment_type": "probability_calibration", "stage": "fit" if training else "evaluate",
             "benchmark_id": source["benchmark_id"], "models": source["modelos"], "n": raw["n"],
             "exponente": payload.get("exponente", payload.get("exponente_congelado")),
             "mae_macro_bruto_pp": raw["mae_grupos_macro_pp"],
             "mae_macro_corregido_pp": corrected["mae_grupos_macro_pp"],
             "mae_ponderado_bruto_pp": raw["mae_grupos_ponderado_pp"],
             "mae_ponderado_corregido_pp": corrected["mae_grupos_ponderado_pp"],
             "validacion_externa": not training, "costo_usd": 0, "artifact": fingerprint(path)}
    if "cambio_saldo" in payload:
        entry["cambio_saldo"] = payload["cambio_saldo"]
        entry["segunda_ola_benchmark_id"] = payload["segunda"]["fuente"]["benchmark_id"]
    with (ROOT / "tools" / "experiments_log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("fit", "evaluate"):
        p = sub.add_parser(name)
        p.add_argument("--results", required=True)
        p.add_argument("--benchmark", required=True)
        p.add_argument("--population", default="")
        p.add_argument("--group-column", default="")
        p.add_argument("--out", required=True)
        if name == "evaluate":
            p.add_argument("--calibration", required=True)
            p.add_argument("--second-results", default="")
            p.add_argument("--second-benchmark", default="")
            p.add_argument("--positive", nargs="+", default=[])
            p.add_argument("--negative", nargs="+", default=[])
    args = parser.parse_args()
    try:
        rows, benchmark, source = load_dataset(args.results, args.benchmark, args.population, args.group_column)
        payload = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                   "metodo": "p^k por persona, renormalizado; promedio esperado sin sorteo", "costo_usd": 0}
        if args.command == "fit":
            fitted = fit(rows, benchmark)
            payload.update({"tipo": "calibracion_entrenamiento", "estado": "pendiente_validacion_externa",
                            "entrenamiento": source, **fitted})
            print(f"Entrenamiento: k={fitted['exponente']:g}; MAE macro de grupos "
                  f"{fitted['bruto']['mae_grupos_macro_pp']:.2f} -> {fitted['ajustado']['mae_grupos_macro_pp']:.2f} pp")
        else:
            calibration = read_json(args.calibration)
            require_external(calibration, benchmark, source["modelos"])
            k = calibration["exponente"]
            first = {"fuente": source, "bruto": evaluate(rows, benchmark), "corregido": evaluate(rows, benchmark, k)}
            payload.update({"tipo": "evaluacion_externa", "calibracion": fingerprint(args.calibration),
                            "exponente_congelado": k, "primera": first,
                            "transferencia_entre_preguntas": benchmark_signature(benchmark)[2] != calibration["entrenamiento"]["benchmark_firma"][2]})
            if bool(args.second_results) != bool(args.second_benchmark):
                raise ValueError("La segunda ola requiere resultados y benchmark.")
            if args.second_results:
                if args.population or args.group_column:
                    raise ValueError("Dos olas usan el perfil guardado; prepará grupos comparables antes de evaluar.")
                other_rows, other_benchmark, other_source = load_dataset(args.second_results, args.second_benchmark)
                require_external(calibration, other_benchmark, other_source["modelos"])
                if (benchmark_signature(benchmark) == benchmark_signature(other_benchmark)
                        or benchmark.id == other_benchmark.id):
                    raise ValueError("El cambio requiere dos olas diferentes.")
                if benchmark.opciones != other_benchmark.opciones or benchmark_signature(benchmark)[2] != benchmark_signature(other_benchmark)[2]:
                    raise ValueError("Las dos olas deben tener la misma pregunta y opciones.")
                second = {"fuente": other_source, "bruto": evaluate(other_rows, other_benchmark),
                          "corregido": evaluate(other_rows, other_benchmark, k)}
                payload["segunda"] = second
                real_change = wave_change(benchmark.distribucion, other_benchmark.distribucion,
                                         positive=args.positive, negative=args.negative)
                change = {"real_pp": real_change, "orden": "segunda menos primera", "positivas": args.positive, "negativas": args.negative}
                for mode in ("bruto", "corregido"):
                    value = wave_change(first[mode]["total"]["simulado"], second[mode]["total"]["simulado"],
                                        positive=args.positive, negative=args.negative)
                    change[f"{mode}_pp"] = value
                    change[f"error_{mode}_pp"] = abs(value - real_change)
                payload["cambio_saldo"] = change
                print(json.dumps(change, ensure_ascii=False))
            print(f"Prueba externa: MAE macro de grupos {first['bruto']['mae_grupos_macro_pp']:.2f} -> "
                  f"{first['corregido']['mae_grupos_macro_pp']:.2f} pp; k congelado={k:g}")
        save_private(args.out, payload)
        record_summary(payload, args.out)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f"No se pudo calibrar/evaluar: {exc}\n")


if __name__ == "__main__":
    main()
