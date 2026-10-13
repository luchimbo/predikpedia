"""Prepara una ola del ICG (UTDT) para validar: CSV, audiencia y benchmark.

La base histórica (.dta) se baja de
https://www.utdt.edu/ver_contenido.php?id_contenido=17876&id_item_menu=28756

Uso:
    .venv\\Scripts\\python.exe -X utf8 tools\\prepare_icg_wave.py ruta\\icg.dta 2025 1 [--n 200]

Escribe research_sources/icg_<año>_<mes>_evaluacion_gobierno.csv y guarda en
data/<usuario>/ una audiencia desde datos reales (grupo = zona, peso = ponderador
UTDT, la evaluación del gobierno como "respuesta real" para que el modelo no la vea)
y el benchmark ponderado de esa pregunta. Las otras preguntas del ICG sobre el
gobierno se excluyen: están tan correlacionadas que le darían la respuesta al modelo.
"""

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from app.config import config  # noqa: E402
from app.storage import repository as repo  # noqa: E402

OPTIONS = ["Muy bien", "Bien", "Regular", "Mal", "Muy mal", "No sabe / no contesta"]
EVAL = dict(zip(["MuyBien", "Bien", "Regular", "Mal", "MuyMal", "NSNC"], OPTIONS))
SIT = {"Mejor": "Mejor", "Igual": "Igual", "Peor": "Peor", "NSNC": "No sabe"}
EDU = {"Primario": "Primario", "Secundario": "Secundario", "TercOUniv": "Terciario o universitario"}
ZONA = {"CABA": "CABA", "BsAs": "Conurbano bonaerense", "Interior": "Interior"}
PREGUNTA = "En términos generales, ¿cómo evalúa la gestión del gobierno nacional?"


def wave_table(dta: str, year: int, month: int) -> pd.DataFrame:
    df = pd.read_stata(dta)
    year_col = df.columns[2]  # "año"; el nombre viene con la codificación de Stata
    w = df[(df[year_col] == year) & (df["mes"] == month)]
    if w.empty:
        sys.exit(f"No hay ola {year}-{month:02d} en la base.")
    edad = w["edad"].astype(str).map(lambda v: {"18a29": "18 a 29", "30a49": "30 a 49"}.get(v, "50 o más"))
    return pd.DataFrame({
        "zona": w["Zona"].astype(str).map(ZONA),
        "ciudad": w["Ciudad"].astype(str),
        "sexo": w["sexo"].astype(str),
        "edad": edad,
        "nivel_educativo": w["edu"].astype(str).map(EDU),
        "situacion_economica_vs_hace_un_anio": w["sitec"].astype(str).map(SIT),
        "evaluacion_gobierno": w["eval_gob"].astype(str).map(EVAL),
        "peso": w["ponderacion_UTDT"].round(6),
    })


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dta")
    parser.add_argument("year", type=int)
    parser.add_argument("month", type=int)
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--user", default=os.getenv("PREDIKPEDIA_DEFAULT_USER", "demo_user"))
    args = parser.parse_args()

    config.set_user(args.user)
    repo.use_local_storage()
    repo.set_active_user(args.user)
    from app.services.calibration_service import benchmark_from_rows
    from app.services.population_import_service import build_population
    from app.services.universe_service import build_expansion_snapshot

    tag = f"{args.year}_{args.month:02d}"
    table = wave_table(args.dta, args.year, args.month)
    csv_path = ROOT / "research_sources" / f"icg_{tag}_evaluacion_gobierno.csv"
    table.to_csv(csv_path, index=False, encoding="utf-8")

    stamp = time.strftime("%Y%m%d_%H%M%S")
    mapping = {c: "atributo" for c in table.columns}
    mapping.update({"zona": "grupo", "evaluacion_gobierno": "respuesta real", "peso": "peso"})
    universo, personas = build_population(
        table, mapping, args.n, universe_id=f"universe_icg_{tag}_{stamp}",
        nombre=f"ICG {args.year}-{args.month:02d} (UTDT) · adultos Argentina",
        descripcion=f"Adultos de Argentina encuestados por la UTDT (Índice de Confianza en el Gobierno), {args.month:02d}/{args.year}.",
        fuente=csv_path.name,
    )
    repo.save_universe(universo)
    repo.save_expansion(universo.id, build_expansion_snapshot(universo, personas))
    bench, _ = benchmark_from_rows(
        table, "evaluacion_gobierno", OPTIONS, segment_column="zona", weight_column="peso",
        id=f"bench_icg_{tag}_{stamp}", nombre=f"ICG UTDT · {args.year}-{args.month:02d}", pregunta=PREGUNTA,
        fuente="Índice de Confianza en el Gobierno, UTDT (ponderado)", fecha=f"{args.year}-{args.month:02d}",
    )
    repo.save_benchmark(bench)
    print(f"csv={csv_path}\nuniverse={universo.id}\nbenchmark={bench.id}\nn_real={bench.n}")
    print({k: round(v, 1) for k, v in bench.distribucion.items()})


if __name__ == "__main__":
    main()
