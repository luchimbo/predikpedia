"""Prepara Latinobarómetro (Argentina) para validar: CSV, audiencia y benchmark.

Pregunta: aprobación de la gestión del gobierno (P15STGBS). Las personas llevan
demografía y, como identidad política, la autoubicación ideológica (P16ST) y el
partido que votaría (P39STGBS.A); con --ocultar en run_benchmark_experiment.py se
puede correr la misma muestra sin esas columnas.

Licencia: Latinobarómetro prohíbe redistribuir sus datos. El CSV va a la carpeta que
indiques (fuera del repo) y la audiencia se guarda en data/privado/ (ignorado por git).

Uso:
    .venv\\Scripts\\python.exe -X utf8 tools\\prepare_latinobarometro.py ruta\\Latinobarometro_2024_Stata_esp.dta ^
        --out-dir C:\\temp [--n 200]
"""

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from app.config import config  # noqa: E402
from app.storage import repository as repo  # noqa: E402

ARGENTINA = 32
OPTIONS = ["Aprueba", "No aprueba", "No sabe / no contesta"]
PREGUNTA = "¿Usted aprueba o no aprueba la gestión del gobierno que encabeza el presidente Javier Milei?"
PARTIDOS = {
    "La Libertad Avanza": "La Libertad Avanza",
    "Partido Justicialista": "Peronismo (PJ / Unión por la Patria)",
    "Union por la Patria": "Peronismo (PJ / Unión por la Patria)",
    "Frente para la Victoria": "Peronismo (PJ / Unión por la Patria)",
    "Frente de Izquierda": "Izquierda (FIT)",
    "Partido Obrero": "Izquierda (FIT)",
    "Union Civica Radical": "Juntos por el Cambio (PRO / UCR)",
    "Propuesta Republicana": "Juntos por el Cambio (PRO / UCR)",
    "Juntos por el Cambio": "Juntos por el Cambio (PRO / UCR)",
    "No vota": "Ninguno / no votaría",
    "nulo": "Voto en blanco o nulo",
}


def _labels(reader: pd.io.stata.StataReader, df: pd.DataFrame):
    value_labels = reader.value_labels()
    label_of = dict(zip(df.columns, reader._lbllist))
    return lambda col, value: value_labels.get(label_of.get(col, ""), {}).get(value, value)


def _partido(text) -> str:
    if pd.isna(text):
        return "No sabe / no contesta"
    for key, value in PARTIDOS.items():
        if key.lower() in str(text).lower():
            return value
    return "Otro partido"


def argentina_table(dta: str) -> pd.DataFrame:
    reader = pd.io.stata.StataReader(dta)
    df = reader.read(convert_categoricals=False)
    label = _labels(reader, df)
    ar = df[df["IDENPA"] == ARGENTINA]

    def col(name):
        return ar[name].map(lambda v: label(name, v) if pd.notna(v) else pd.NA)

    region = col("REG").map(lambda v: "Buenos Aires - interior" if v == -32635 else str(v).replace("AR: ", "").replace("/", " - "))
    ideologia = col("P16ST").map(lambda v: "No contesta" if pd.isna(v) else ("No se ubica" if v == "Ninguno" else f"{v} (0 = izquierda, 10 = derecha)"))
    aprobacion = ar["P15STGBS"].map({1: "Aprueba", 2: "No aprueba"}).fillna("No sabe / no contesta")
    return pd.DataFrame({
        "region": region,
        "sexo": col("SEXO").astype(str),
        "edad": col("REEDAD").astype(str),
        "nivel_educativo": col("REEDUC.1").astype(str),
        "clase_social_subjetiva": col("S2").map(lambda v: "No contesta" if pd.isna(v) else str(v)),
        "situacion_economica_pais_vs_hace_un_anio": col("P7STGBS").map(lambda v: "No contesta" if pd.isna(v) else str(v)),
        "ideologia": ideologia,
        "partido_que_votaria": col("P39STGBS.A").map(_partido),
        "aprobacion_gobierno": aprobacion,
        "peso": ar["WT"].round(6),
    })


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dta")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--user", default="privado")
    args = parser.parse_args()

    config.set_user(args.user)
    repo.use_local_storage()
    repo.set_active_user(args.user)
    from app.services.calibration_service import benchmark_from_rows
    from app.services.population_import_service import build_population
    from app.services.universe_service import build_expansion_snapshot

    table = argentina_table(args.dta)
    csv_path = Path(args.out_dir) / "latinobarometro_2024_argentina_aprobacion.csv"
    table.to_csv(csv_path, index=False, encoding="utf-8")

    stamp = time.strftime("%Y%m%d_%H%M%S")
    mapping = {c: "atributo" for c in table.columns}
    mapping.update({"region": "grupo", "aprobacion_gobierno": "respuesta real", "peso": "peso"})
    universo, personas = build_population(
        table, mapping, args.n, universe_id=f"universe_lb2024_ar_{stamp}",
        nombre="Latinobarómetro 2024 · Argentina",
        descripcion="Adultos de Argentina entrevistados cara a cara por Latinobarómetro, agosto y septiembre de 2024.",
        fuente=csv_path.name,
    )
    repo.save_universe(universo)
    repo.save_expansion(universo.id, build_expansion_snapshot(universo, personas))
    bench, _ = benchmark_from_rows(
        table, "aprobacion_gobierno", OPTIONS, segment_column="partido_que_votaria", weight_column="peso",
        id=f"bench_lb2024_ar_{stamp}", nombre="Latinobarómetro 2024 · Argentina", pregunta=PREGUNTA,
        fuente="Latinobarómetro 2024 (ponderado)", fecha="2024-08/09",
    )
    repo.save_benchmark(bench)
    print(f"csv={csv_path}\nuniverse={universo.id}\nbenchmark={bench.id}\nn_real={bench.n}")
    print({k: round(v, 1) for k, v in bench.distribucion.items()})
    for seg, dist in bench.por_segmento.items():
        print(f"  {seg} (n={bench.n_por_segmento[seg]}):", {k: round(v, 1) for k, v in dist.items()})


if __name__ == "__main__":
    main()
