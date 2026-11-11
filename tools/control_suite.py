"""Run or replay the frozen private controls and keep aggregate history locally."""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd

from app.domain.models import Benchmark, Estudio, RespuestaEstudio
from app.services.calibration_service import compare_with_benchmark
from app.services.llm_service import LLMService
from app.services.simulation_service import run_simulation

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tools/control_suite_v1.json"
PROMPT = ROOT / "app/services/study_response_service.py"
ENGINE = ROOT / "app/services/simulation_service.py"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical_sha(value):
    return sha(json.dumps(value, ensure_ascii=False, sort_keys=True).encode())


def read_verified(root, entry, *, text=False):
    path = root / entry["path"]
    content = path.read_text(encoding="utf8").encode() if text else path.read_bytes()
    if sha(content) != entry["sha256"]:
        raise ValueError(f"Cambió el insumo congelado {entry['path']}.")
    return content.decode("utf8")


def load_case(case, inputs):
    expansion = json.loads(read_verified(inputs, case["expansion"]))
    raw_benchmark = json.loads(read_verified(inputs, case["benchmark"]))
    context = read_verified(ROOT, case["context"], text=True).strip()
    people = expansion["personas"]
    allowed = set(case["allowed_profile_columns"])
    if (len(people) != case["n"] or len({p["persona_id"] for p in people}) != case["n"]
            or expansion["universo_id"] != case["universe_id"]
            or any(set(p.get("datos_reales", {})) - allowed for p in people)):
        raise ValueError(f"La muestra congelada de {case['id']} no coincide con el protocolo.")
    return people, raw_benchmark, context


def summarize(study, benchmark, people, answers, provider, model):
    expected = {p["persona_id"] for p in people}
    seen = {answer.persona_id for answer in answers}
    if len(seen) != len(answers) or not seen.issubset(expected) or any(
        a.estudio_id != study.id or a.pregunta != study.pregunta or a.contexto != study.contexto for a in answers
    ):
        raise ValueError("Las respuestas no corresponden al estudio congelado.")
    frame = pd.DataFrame([a.to_dict() for a in answers])
    result = compare_with_benchmark(frame, benchmark)
    total = result["total"]
    valid = total["n_sim"] if total else 0
    matching_model = all(
        a.llm_metadata.get("provider") == provider and a.llm_metadata.get("model") == model
        and a.llm_metadata.get("fallback_used") is not True
        for a in answers if not a.error and a.opcion_elegida in benchmark.opciones
    )
    def metrics(row):
        return {key: row[key] for key in ("n_sim", "n_real", "mae", "tvd")}

    return {"planned": len(people), "processed": len(answers), "valid": valid,
            "complete": valid == len(people) and matching_model,
            "total": metrics(total) if total else None,
            "segments": {row["segmento"]: metrics(row) for row in result["segmentos"]},
            "unmatched_real": result["segmentos_sin_par_reales"],
            "unmatched_simulated": result["segmentos_sin_par_simulados"]}


def historical(inputs, case, study, people, raw_benchmark, context, provider, model):
    sid = study.id
    previous = Estudio.from_dict(json.loads((inputs / f"data/privado/estudios/{sid}.json").read_text(encoding="utf8")))
    manifest = json.loads((inputs / f".private/experiment_manifests/{sid}.json").read_text(encoding="utf8"))
    expected = {"personas_sha256": canonical_sha(people), "benchmark_sha256": canonical_sha(raw_benchmark),
                "contexto_sha256": sha(context.encode()), "ocultar": [],
                "provider_mode": provider, "model": model}
    if any(manifest.get(key) != value for key, value in expected.items()) or any(
        getattr(previous, key) != getattr(study, key)
        for key in ("universo_id", "pregunta", "opciones", "contexto", "mode", "modo_cerrada",
                    "temperature", "respuestas_planeadas", "respuestas_por_persona")
    ) or not manifest.get("prompt_sha256"):
        raise ValueError(f"La corrida histórica {case['id']} no coincide con los insumos congelados.")
    rows = json.loads((inputs / f"data/privado/resultados/{sid}.json").read_text(encoding="utf8"))
    return [RespuestaEstudio.from_dict(row) for row in rows], manifest["prompt_sha256"], previous.simulation_version


def baseline_for(history, manifest_sha):
    return next((run for run in sorted(history, key=lambda item: item["started_at"])
                 if run["manifest_sha256"] == manifest_sha and run["status"] == "complete"), None)


def write_atomic(path, content):
    temp = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    try:
        temp.write_text(content, encoding="utf8")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def render_report(run, baseline):
    lines = ["# Controles de precisión", "",
             f"{run['label']} · {run['provider']} / {run['model']} · {run['origin']} · {run['status']}", "",
             f"Referencia: {baseline['label']}" if baseline else "Referencia pendiente de una ejecución completa.", "",
             "| Caso | Segmento | Válidas | MAE (pp) | TVD (pp) | Δ MAE (pp) | Δ TVD (pp) |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for key, case in run["cases"].items():
        base = baseline["cases"].get(key, {}) if baseline else {}
        for segment, metrics in [("Total", case["total"]), *case["segments"].items()]:
            previous = base.get("total") if segment == "Total" else base.get("segments", {}).get(segment)
            delta = [f"{metrics[k] - previous[k]:+.2f}" if metrics and previous else "—" for k in ("mae", "tvd")]
            scores = [f"{metrics[k]:.2f}" if metrics else "—" for k in ("mae", "tvd")]
            count = f"{case['valid']}/{case['planned']}" if segment == "Total" else str(metrics["n_sim"])
            label = segment.replace("|", "&#124;")
            lines.append(f"| {case['label']} | {label} | {count} | {' | '.join(scores + delta)} |")
        missing = case["unmatched_real"]
        if missing:
            lines.append(f"| {case['label']} | Segmentos reales sin par: {', '.join(missing).replace('|', '&#124;')} | — | — | — | — | — |")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs-root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".private/control_suite")
    parser.add_argument("--provider", required=True, choices=["local", "openrouter"])
    parser.add_argument("--model", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--local-base-url")
    parser.add_argument("--replay-historical", action="store_true")
    args = parser.parse_args(argv)
    manifest_data = MANIFEST.read_bytes()
    suite = json.loads(manifest_data)
    try:
        inputs = [(case, *load_case(case, args.inputs_root)) for case in suite["cases"]]
    except (ValueError, OSError) as exc:
        parser.error(str(exc))

    os.environ["LLM_PROVIDER"] = args.provider
    if args.provider == "local":
        os.environ["LLM_LOCAL_MODEL"] = args.model
        if args.local_base_url:
            os.environ["LLM_LOCAL_BASE_URL"] = args.local_base_url
    else:
        os.environ["OPENROUTER_MODEL"] = args.model
    engine = LLMService(local_only=args.provider == "local")
    if not args.replay_historical and not engine.is_ready():
        parser.error("Configurá las credenciales y la URL del proveedor elegido.")

    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    run_id = f"{now:%Y%m%dT%H%M%S}_{uuid4().hex[:8]}"
    run = {"started_at": now.isoformat(), "label": args.label, "manifest_sha256": sha(manifest_data),
           "provider": args.provider, "model": args.model, "status": "partial",
           "origin": "histórica" if args.replay_historical else "nueva", "cases": {}}
    history = [json.loads(path.read_text(encoding="utf8")) for path in output.glob("run_*.json")]

    def persist():
        write_atomic(output / f"run_{run_id}.json", json.dumps(run, ensure_ascii=False, indent=2, allow_nan=False))
        baseline = baseline_for([*history, run], run["manifest_sha256"])
        write_atomic(output / f"run_{run_id}.md", render_report(run, baseline))

    persist()
    for case, people, raw_benchmark, context in inputs:
        benchmark = Benchmark.from_dict(raw_benchmark)
        study = Estudio(case["historical_study_id"], case["universe_id"], case["label"], args.label,
                       benchmark.pregunta, context, respuestas_planeadas=len(people),
                       simulation_version="realism_v2", opciones=benchmark.opciones,
                       temperature=suite["temperature"], modo_cerrada=suite["mode"])
        answers = []
        prompt_sha = sha(PROMPT.read_text(encoding="utf8").encode())
        engine_version = study.simulation_version
        engine_sha = None if args.replay_historical else sha(ENGINE.read_text(encoding="utf8").encode())

        def save_case():
            stats = summarize(study, benchmark, people, answers, args.provider, args.model)
            run["cases"][case["id"]] = {"label": case["label"], "prompt_sha256": prompt_sha,
                                       "engine_version": engine_version, "engine_sha256": engine_sha, **stats}
            persist()

        def checkpoint(answer, done, total):
            answers.append(answer)
            if done == 1 or done % 10 == 0 or done == total:
                save_case()
                print(f"{case['id']} · {done}/{total}", flush=True)

        if args.replay_historical:
            answers, prompt_sha, engine_version = historical(
                args.inputs_root, case, study, people, raw_benchmark, context, args.provider, args.model)
            save_case()
        else:
            try:
                run_simulation(study, people, engine, on_response=checkpoint)
            finally:
                save_case()
    if all(case["complete"] for case in run["cases"].values()) and len(run["cases"]) == len(inputs):
        run["status"] = "complete"
    persist()
    print(output / f"run_{run_id}.md")
    return 0 if run["status"] == "complete" else 1
