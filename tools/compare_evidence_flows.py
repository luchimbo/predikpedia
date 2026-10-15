"""Compara el flujo "describir con palabras" contra "evidencia pública" con un benchmark real.

Misma pregunta, opciones, contexto, n y modelo local; solo cambia cómo se arma la audiencia.
Protocolo en docs/COMPARACION_EVIDENCIA_PUBLICA.md. Todo corre con Ollama, sin respaldo remoto.

    prepare  busca y diagnostica evidencia pública (no crea audiencia)
    old      diseña una audiencia desde el brief y corre el estudio
    new      crea la audiencia fundamentada del expediente y corre el estudio
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
os.environ["LLM_PROVIDER"] = "local"

from app.config import config  # noqa: E402
from app.domain.models import Benchmark, Estudio, Universo  # noqa: E402
from app.domain.research_models import ResearchBrief  # noqa: E402
from app.services.audience_design_service import design_segments  # noqa: E402
from app.services.llm_service import LLMService  # noqa: E402
from app.services.public_research_service import PublicResearchService  # noqa: E402
from app.services.simulation_service import run_simulation  # noqa: E402
from app.services.universe_service import build_expansion_snapshot, expand_universe  # noqa: E402
from app.storage import repository as repo  # noqa: E402
from app.storage.evidence_repository import EvidenceRepository  # noqa: E402
from app.storage.research_repository import ResearchRepository  # noqa: E402

LOG = ROOT / "tools" / "experiments_log.jsonl"
USER = "privado"  # data/privado/ está ignorado por git; los documentos web quedan en la SQLite privada


def score(answers, benchmark, positive, negative):
    valid = [a for a in answers if a.probabilidades and not a.error]
    options = benchmark.opciones
    expected = {o: sum(a.probabilidades.get(o, 0) for a in valid) / len(valid) for o in options} if valid else {}
    real = benchmark.distribucion
    balance = lambda d: sum(d[o] for o in positive) - sum(d[o] for o in negative)  # noqa: E731
    return {
        "n": len(answers), "n_validas": len(valid),
        "modelos": sorted({a.llm_metadata.get("model", "") for a in answers} - {""}),
        "proveedores": sorted({a.llm_metadata.get("provider", "") for a in answers} - {""}),
        "esperado": {o: round(v, 2) for o, v in expected.items()},
        "mae_pp": round(sum(abs(expected[o] - real[o]) for o in options) / len(options), 2) if valid else None,
        "tvd_pp": round(sum(abs(expected[o] - real[o]) for o in options) / 2, 2) if valid else None,
        "saldo_pp": round(balance(expected), 2) if valid else None, "saldo_real_pp": round(balance(real), 2),
    }


def run_study(label, universe, personas, benchmark, context, args, *, store=None, snapshot_id="", study=None, saved=None):
    # Al retomar se conservan las respuestas válidas y se consulta solo a quienes faltan o fallaron.
    saved = [a for a in (saved or []) if not a.error]
    done = {a.persona_id for a in saved}
    pending = [p for p in personas if p["persona_id"] not in done]
    study = study or Estudio(
        id=f"study_cmp_{time.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}", universo_id=universe.id,
        universo_nombre=universe.nombre, titulo=f"Comparación · {label}", pregunta=benchmark.pregunta, contexto=context,
        template="experiment", mode="survey", respuestas_planeadas=len(personas), simulation_version="realism_v2",
        opciones=list(benchmark.opciones), temperature=1.0, modo_cerrada="probabilidades",
        research_snapshot_id=snapshot_id, local_only=bool(snapshot_id),
    )
    repo.save_study(study)

    def checkpoint(answer, _done, _total):
        saved.append(answer)
        repo.save_study_results(study.id, saved)
        if len(saved) % 20 == 0:
            print(f"{study.id}: {len(saved)}/{len(personas)}; errores={sum(bool(a.error) for a in saved)}", flush=True)

    started = time.time()
    if pending:
        run_simulation(study, pending, LLMService(local_only=True), store=store, on_response=checkpoint)
    repo.save_study_results(study.id, saved)
    summary = {"experiment_type": "evidence_flow_comparison", "label": label, "study_id": study.id,
               "universe_id": universe.id, "benchmark_id": benchmark.id, "user": USER,
               "grupos": {p.nombre: round(p.porcentaje, 1) for p in universe.perfiles},
               "arquetipos": sum(len(p.arquetipos) for p in universe.perfiles),
               "research_snapshot_id": snapshot_id, "segundos": round(time.time() - started), "costo_usd": 0,
               **score(saved, benchmark, args.positive, args.negative)}
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary, ensure_ascii=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["prepare", "old", "new"])
    parser.add_argument("--benchmark", required=True, help="JSON del benchmark real")
    parser.add_argument("--audience", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--contexto-file", required=True)
    parser.add_argument("--as-of", required=True, help="Fecha del escenario; la evidencia posterior se rechaza")
    parser.add_argument("--holdout-url", action="append", default=[])
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--project-id", default="", help="Expediente ya preparado (para new o para retomar prepare)")
    parser.add_argument("--label", default="")
    parser.add_argument("--resume-study", default="", help="Retoma una corrida del flujo anterior cortada a mitad")
    parser.add_argument("--positive", nargs="+", default=[])
    parser.add_argument("--negative", nargs="+", default=[])
    args = parser.parse_args()

    config.set_user(USER)
    repo.use_local_storage()
    repo.set_active_user(USER)
    benchmark = Benchmark.from_dict(json.loads(Path(args.benchmark).read_text(encoding="utf-8")))
    context = Path(args.contexto_file).read_text(encoding="utf-8").strip()
    description = args.audience + ". Región: " + args.region  # el mismo texto que usa el flujo nuevo

    if args.command == "old" and args.resume_study:
        study = repo.find_study(args.resume_study)
        if study is None or study.pregunta != benchmark.pregunta or study.contexto != context or study.research_snapshot_id:
            sys.exit("El estudio no existe o no corresponde a esta comparación del flujo anterior.")
        universe = repo.find_universe(study.universo_id)
        personas = repo.find_latest_expansion(study.universo_id)["payload"].personas
        run_study(args.label or study.titulo, universe, personas, benchmark, context, args,
                  study=study, saved=repo.load_study_results(study.id))
        return

    if args.command == "old":
        profiles = design_segments(description, LLMService(local_only=True))
        universe = Universo(id="universe_cmp_old_" + uuid4().hex[:8], nombre="Comparación · flujo anterior",
                            descripcion=description, cantidad_personas=args.n, prompt_perfil=description, perfiles=profiles)
        snapshot = build_expansion_snapshot(universe, expand_universe(universe))
        repo.save_universe(universe)
        repo.save_expansion(universe.id, snapshot)
        run_study(args.label or "flujo anterior", universe, snapshot.personas, benchmark, context, args)
        return

    store = EvidenceRepository(USER)
    research = ResearchRepository(store)
    service = PublicResearchService(research)
    if args.project_id:
        project = research.get(args.project_id)
        if project is None:
            sys.exit("No se encontró el expediente.")
    else:
        project = service.new_project(ResearchBrief(
            question=benchmark.pregunta, audience=args.audience, region=args.region, goal="explore",
            situation=context, as_of=args.as_of, options=list(benchmark.opciones), holdout_urls=args.holdout_url))
    print(f"Expediente {project.id}", flush=True)

    if args.command == "prepare":
        service.prepare(project)
        project = research.get(project.id)
        documents = research.documents(project.document_ids)
        diagnosis = project.diagnosis
        report = {"experiment_type": "evidence_flow_comparison", "stage": "prepare", "project_id": project.id,
                  "status": diagnosis.get("status"), "can_build": diagnosis.get("can_build"),
                  "aspectos": [{"id": r["id"], "central": r["critical"], "estado": r["status"]} for r in diagnosis.get("rows", [])],
                  "motivos": diagnosis.get("reasons", []), "busquedas": len(project.queries),
                  "documentos": len(documents), "leidos": sum(d.status == "read" for d in documents),
                  "hallazgos": len(project.findings), "hallazgos_validos": len(diagnosis.get("valid_finding_ids", [])),
                  "costo_usd": 0}
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(report, ensure_ascii=False) + "\n")
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return

    universe, personas, snapshot_id = service.build_audience(project, "Comparación · evidencia pública", args.n)
    snapshot = build_expansion_snapshot(universe, personas)
    repo.save_universe(universe)
    repo.save_expansion(universe.id, snapshot)
    project.universe_id, project.snapshot_id, project.stage = universe.id, snapshot_id, "audience"
    research.save(project)
    run_study(args.label or "evidencia pública", universe, snapshot.personas, benchmark, context, args,
              store=store, snapshot_id=snapshot_id)


if __name__ == "__main__":
    main()
