"""Corre un estudio cerrado contra un benchmark guardado y reporta el error.

Sirve para comparar variantes (contexto, modelo, prompt) con las mismas personas:
la audiencia y su expansión se reutilizan, así que la única diferencia entre
corridas es lo que cambia en los argumentos o en el código del prompt.

Uso (desde la raíz del repo):
    .venv\\Scripts\\python.exe -X utf8 tools\\run_benchmark_experiment.py ^
        --universe-id universe_icg_... --benchmark-id bench_icg_... ^
        --label "B1 prompt" [--model google/gemini-3.5-flash] [--contexto-file ctx.txt] [--n 200]

Guarda el estudio en data/<usuario>/ (se ve en Resultados → Validación) y agrega
una línea a tools/experiments_log.jsonl.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

import pandas as pd  # noqa: E402

from app.config import config  # noqa: E402
from app.storage import repository as repo  # noqa: E402

LOG = ROOT / "tools" / "experiments_log.jsonl"
MANIFESTS = ROOT / ".private" / "experiment_manifests"


def experiment_manifest(personas, benchmark, contexto, prompt_hash, hidden, provider, model):
    def digest(value):
        return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return {"personas_sha256": digest(personas), "benchmark_sha256": digest(benchmark.to_dict()),
            "contexto_sha256": hashlib.sha256(contexto.encode("utf-8")).hexdigest(),
            "prompt_sha256": prompt_hash, "ocultar": sorted(hidden), "provider_mode": provider, "model": model}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--universe-id", required=True)
    parser.add_argument("--benchmark-id", required=True)
    parser.add_argument("--label", required=True, help="Nombre corto de la variante")
    parser.add_argument("--pregunta", default="")
    parser.add_argument("--contexto", default="")
    parser.add_argument("--contexto-file", default="")
    parser.add_argument("--model", default="", help="Modelo de OpenRouter; vacío = el configurado")
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--ocultar", default="", help="Columnas de datos reales a sacar del perfil, separadas por coma")
    parser.add_argument("--modo-cerrada", default="eleccion", choices=["eleccion", "probabilidades"])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--provider", choices=["local", "openrouter"], help="Fuerza proveedor; local nunca usa fallback pago")
    parser.add_argument("--local-base-url", default="", help="Endpoint compatible OpenAI, terminado en /v1")
    parser.add_argument("--local-model", default="")
    parser.add_argument("--resume-study", default="", help="Retoma este estudio; requiere manifest y configuración idéntica")
    parser.add_argument("--retry-errors", action="store_true", help="Al reanudar, vuelve a consultar solo las filas con error")
    parser.add_argument("--user", default=os.getenv("PREDIKPEDIA_DEFAULT_USER", "demo_user"))
    args = parser.parse_args()
    if args.n < 1 or args.workers < 1:
        parser.error("--n y --workers deben ser positivos")
    if args.provider == "local" and args.model:
        parser.error("Para local usá --local-model, no --model de OpenRouter")
    if (args.local_base_url or args.local_model) and args.provider != "local":
        parser.error("Los overrides locales requieren --provider local")
    if args.resume_study and not args.provider:
        parser.error("Reanudar requiere --provider explícito para impedir cambios de proveedor")
    if args.retry_errors and not args.resume_study:
        parser.error("--retry-errors requiere --resume-study")
    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider
    if args.provider == "local":
        os.environ.setdefault("LLM_LOCAL_API_KEY", "ollama")
        if args.local_base_url:
            os.environ["LLM_LOCAL_BASE_URL"] = args.local_base_url
        if args.local_model:
            os.environ["LLM_LOCAL_MODEL"] = args.local_model

    config.set_user(args.user)
    repo.use_local_storage()
    repo.set_active_user(args.user)

    from app.domain.models import Estudio
    from app.services.calibration_service import compare_with_benchmark
    from app.services.llm_service import LLMService
    from app.services.simulation_service import run_simulation
    from app.services.llm_routing import load_llm_settings
    from tools.benchmark_checkpoint import prepare_resume

    benchmark = next((b for b in repo.list_benchmarks() if b.id == args.benchmark_id), None)
    universo = repo.find_universe(args.universe_id)
    expansion = repo.find_latest_expansion(args.universe_id)
    if benchmark is None or universo is None or expansion is None:
        sys.exit("No se encontró el benchmark, la audiencia o sus personas.")
    personas = list(expansion["payload"].personas)[: args.n]
    # Mismas personas, menos información: sirve para medir cuánto aporta cada columna del perfil.
    hidden = {c.strip() for c in args.ocultar.split(",") if c.strip()}
    if hidden:
        personas = [{**p, "datos_reales": {k: v for k, v in p.get("datos_reales", {}).items() if k not in hidden}}
                    for p in personas]
    contexto = Path(args.contexto_file).read_text(encoding="utf-8").strip() if args.contexto_file else args.contexto
    prompt_hash = hashlib.sha256((ROOT / "app" / "services" / "study_response_service.py").read_bytes()).hexdigest()

    stamp = time.strftime("%Y%m%d_%H%M%S")
    estudio = Estudio(
        id=args.resume_study or f"study_exp_{stamp}_{uuid4().hex[:6]}", universo_id=universo.id, universo_nombre=universo.nombre,
        titulo=f"Experimento · {args.label}", pregunta=args.pregunta or benchmark.pregunta, contexto=contexto,
        template="experiment", mode="survey", respuestas_planeadas=len(personas), simulation_version="realism_v2",
        opciones=list(benchmark.opciones), temperature=args.temperature, modo_cerrada=args.modo_cerrada,
    )
    settings = load_llm_settings()
    model = settings.local_model if settings.provider_mode == "local" else (args.model or settings.openrouter_model)
    manifest = experiment_manifest(personas, benchmark, contexto, prompt_hash, hidden, settings.provider_mode, model)
    manifest_path = MANIFESTS / f"{estudio.id}.json"
    saved, pending = [], personas
    if args.resume_study:
        original = repo.find_study(args.resume_study)
        if original is None or not manifest_path.exists():
            parser.error("Falta el estudio o su manifest de reanudación")
        try:
            saved, pending = prepare_resume(original, estudio, repo.load_study_results(estudio.id), personas,
                                            json.loads(manifest_path.read_text(encoding="utf-8")), manifest, args.retry_errors)
        except ValueError as exc:
            parser.error(str(exc))
        estudio = original
    else:
        repo.save_study(estudio)
        MANIFESTS.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def engine() -> LLMService:
        if args.model:
            return LLMService(api_key=os.getenv("OPENROUTER_API_KEY"), model_name=args.model)
        # local_only: si Ollama falla la fila queda con error, nunca pasa a OpenRouter.
        return LLMService(local_only=args.provider == "local")

    # Cada hilo corre su tramo de personas con su propio cliente (la metadata es por instancia).
    chunks = [pending[i::args.workers] for i in range(args.workers) if pending[i::args.workers]]
    t0 = time.time()
    n_preserved, lock = len(saved), Lock()

    def checkpoint(answer, _done, _total):
        with lock:
            saved.append(answer)
            # No perder probabilidades individuales si se interrumpe una tanda larga.
            repo.save_study_results(estudio.id, saved)
            if len(saved) == 1 or len(saved) % 10 == 0 or len(saved) == len(personas):
                print(f"{estudio.id}: {len(saved)}/{len(personas)}; errores={sum(bool(a.error) for a in saved)}", flush=True)

    print(f"Inicio {estudio.id}; personas={len(personas)}; pendientes={len(pending)}; proveedor={os.getenv('LLM_PROVIDER', 'local')}", flush=True)
    if chunks:
        with ThreadPoolExecutor(len(chunks)) as pool:
            list(pool.map(lambda chunk: run_simulation(estudio, chunk, engine(), on_response=checkpoint), chunks))
    answers = saved
    repo.save_study_results(estudio.id, answers)

    result = compare_with_benchmark(pd.DataFrame([a.to_dict() for a in answers]), benchmark)
    total = result["total"] or {}
    models = sorted({a.llm_metadata.get("model", "") for a in answers} - {""})
    valid_probabilities = [a for a in answers if a.probabilidades and not a.error]
    summary = {
        "label": args.label, "study_id": estudio.id, "benchmark_id": benchmark.id, "models": models,
        "user": args.user, "universe_id": universo.id,
        "results_path": str(config.results_dir / f"{estudio.id}.json"),
        "providers": sorted({a.llm_metadata.get("provider", "") for a in answers} - {""}),
        "temperature": args.temperature,
        "prompt_sha256": prompt_hash,
        "contexto_sha256": hashlib.sha256(contexto.encode("utf-8")).hexdigest(),
        "costo_usd": 0 if args.provider == "local" else None,
        "status": "complete", "resumed": bool(args.resume_study), "preservadas": n_preserved,
        "n": len(answers), "errores": sum(1 for a in answers if a.error), "segundos": round(time.time() - t0),
        "mae": round(total.get("mae", float("nan")), 2), "tvd": round(total.get("tvd", float("nan")), 2),
        "ganadora_ok": total.get("misma_opcion_ganadora"),
        "simulado": {r["opcion"]: round(r["simulado"], 1) for r in total.get("filas", [])},
        "real": {r["opcion"]: round(r["real"], 1) for r in total.get("filas", [])},
        "mae_por_segmento": {s["segmento"]: round(s["mae"], 2) for s in result["segmentos"]},
        "contexto_chars": len(contexto),
        "modo_cerrada": args.modo_cerrada,
        "ocultar": sorted(hidden),
        # Promedio de las probabilidades declaradas: la misma distribución sin el ruido del sorteo.
        "esperado": ({o: round(sum(a.probabilidades.get(o, 0) for a in valid_probabilities)
                               / len(valid_probabilities), 1) for o in benchmark.opciones}
                     if valid_probabilities else None),
    }
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary, ensure_ascii=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
