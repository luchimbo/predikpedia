"""Prepara controles políticos privados sin inferencias ni ajustes del prompt.

Fuentes verificadas: Latinobarómetro 2023 (Argentina, aprobación binaria) y
LAPOP 2026 (Argentina, evaluación ordinal; NO se recodifica como aprobación).
Los originales, CSV, benchmark y audiencia permanecen privados. El manifiesto
documenta calidad y linaje, sin exponer respuestas individuales por consola.
"""

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import config
from app.services.calibration_service import benchmark_from_rows
from app.services.population_import_service import build_population
from app.services.universe_service import build_expansion_snapshot
from app.storage import repository as repo

NS = "No sabe / no contesta"
SPECS = {
    "lb2023": {
        "country": "idenpa", "country_code": 32, "id": "numentre", "weight": "wt",
        "target": "P15STGBS", "party": "P43STGBS_A", "ideology": "P16ST",
        "options": ["Aprueba", "No aprueba", NS],
        "question": "¿Usted aprueba o no aprueba la gestión del gobierno que encabeza el presidente Alberto Fernández?",
        "name": "Latinobarómetro 2023 · Argentina · control independiente",
        "date": "2023-02/04", "url": "https://www.latinobarometro.org/latinobarometro-2023",
        "description": "Adultos de Argentina entrevistados por Latinobarómetro entre febrero y abril de 2023. El gobierno evaluado es el de Alberto Fernández.",
        "license": "Investigación no comercial; prohibida la redistribución. Latinobarómetro Study 2023, Corporación Latinobarómetro, Madrid: JD Systems Institute.",
    },
    "lapop2026": {
        "country": "pais", "country_code": 17, "id": "idnum", "weight": "wt",
        "target": "m1", "party": "vb11", "ideology": "l1n",
        "options": ["Muy bueno", "Bueno", "Ni bueno, ni malo (regular)", "Malo", "Muy malo (pésimo)", NS],
        "question": "Hablando en general acerca del gobierno actual, ¿diría usted que el trabajo que está realizando el presidente Javier Milei es muy bueno, bueno, ni bueno ni malo (regular), malo o muy malo (pésimo)?",
        "name": "LAPOP 2026 · Argentina · evaluación ordinal",
        "date": "2026-03-20/2026-05-20",
        "url": "https://www.vanderbilt.edu/center-for-global-democracy/data/directory/",
        "description": "Personas de edad de votar de Argentina entrevistadas por LAPOP del 20 de marzo al 20 de mayo de 2026. El gobierno evaluado es el de Javier Milei.",
        "license": "Investigación no comercial; prohibida la redistribución. These data were supplied by LAPOP Lab at Vanderbilt University, which takes no responsibility for any interpretation of the data.",
    },
}


def missing_code(value):
    if isinstance(value, pd.io.stata.StataMissingValue):
        return str(value)
    return "." if pd.isna(value) else ""


def fix_text(value):
    text = str(value).strip()
    if "Ã" in text or "Â" in text:
        try:
            return text.encode("latin1").decode("utf8")
        except (UnicodeError, ValueError):
            pass
    return text


def party_group(value, source):
    missing = missing_code(value)
    if missing in (".a", ".b", ".e", ".") or (not missing and value in (-1, -2, -5)):
        return NS
    mappings = {
        "lb2023": {
            32001: "Peronismo (PJ / Unión por la Patria)", 32002: "Peronismo (PJ / Unión por la Patria)",
            32042: "Peronismo (PJ / Unión por la Patria)", 32045: "Peronismo (PJ / Unión por la Patria)",
            32005: "Juntos por el Cambio (PRO / UCR)", 32006: "Juntos por el Cambio (PRO / UCR)",
            32044: "Juntos por el Cambio (PRO / UCR)", 32041: "Izquierda (FIT)",
            # No se inventa equivalencia de Avanza Libertad con La Libertad Avanza.
            32048: "Avanza Libertad (categoría LB2023)",
            94: "Otro partido", 95: "Voto en blanco o nulo", 96: "Ninguno / no votaría",
            97: "No inscrito / no tenía edad",
        },
        "lapop2026": {
            172501: "La Libertad Avanza", 172502: "Peronismo (PJ / Unión por la Patria)",
            172503: "Peronismo (PJ / Unión por la Patria)",
            172504: "Juntos por el Cambio (PRO / UCR)", 172506: "Juntos por el Cambio (PRO / UCR)",
            172505: "Izquierda (FIT)", 172577: "Otro partido",
        },
    }
    if missing or value not in mappings[source]:
        raise ValueError(f"Partido no mapeado en {source}: {value}")
    return mappings[source][value]


def response_option(value, source):
    missing = missing_code(value)
    # Inaplicable/no preguntado nunca se convierte en una opinión NS/NC.
    allowed = (".a", ".b") if source == "lapop2026" else (".a", ".b", ".e")
    if missing in allowed or (source == "lb2023" and not missing and value in (-1, -2, -5)):
        return NS
    size = 5 if source == "lapop2026" else 2
    if missing or value not in range(1, size + 1):
        raise ValueError(f"Respuesta real no aplicable/desconocida: {value}")
    return SPECS[source]["options"][int(value) - 1]


def read_source(path, source):
    spec = SPECS[source]
    with pd.io.stata.StataReader(path) as reader:
        data = reader.read(convert_categoricals=False, convert_missing=True)
        labels = reader.value_labels()
        label_names = dict(zip(data.columns, reader._lbllist))
    needed = [spec[k] for k in ("country", "id", "weight", "target", "party", "ideology")]
    if source == "lapop2026":
        needed += ["vb10", "q1tc", "q2", "edre", "region", "upm", "strata", "fecha"]
    else:
        needed += ["reg", "sexo", "reedad", "REEEDUC_1", "S2", "P6STGBS", "diareal", "mesreal"]
    absent = set(needed) - set(data.columns)
    if absent:
        raise ValueError(f"Faltan columnas de la versión documentada: {sorted(absent)}")
    ar = data[data[spec["country"]] == spec["country_code"]].copy()
    if ar.empty or ar[spec["id"]].map(str).duplicated().any() or ar[spec["id"]].map(missing_code).any():
        raise ValueError("La base argentina está vacía o tiene IDs vacíos/duplicados.")
    weights = pd.to_numeric(ar[spec["weight"]], errors="coerce")
    if any(not math.isfinite(w) or w <= 0 for w in weights):
        raise ValueError("Los ponderadores deben ser positivos y finitos.")

    def label(column, value):
        missing = missing_code(value)
        if missing in (".a", ".b", ".e", ".") or (not missing and value in (-1, -2, -5)):
            return NS
        if missing:
            return "No aplicable" if missing == ".c" else "No preguntado"
        return fix_text(labels.get(label_names[column], {}).get(value, value))

    def labeled(column):
        return ar[column].map(lambda v: label(column, v))

    def ideology(value):
        missing = missing_code(value)
        if missing or value in (-1, -2, -5):
            if missing not in ("", ".", ".a", ".b", ".e"):
                raise ValueError("Ideología no preguntada/no aplicable.")
            return NS
        if source == "lb2023" and value == 97:
            return "No se ubica"
        minimum = 0 if source == "lb2023" else 1
        if value not in range(minimum, 11):
            raise ValueError(f"Ideología fuera de escala: {value}")
        return f"{int(value)} ({minimum} = izquierda, 10 = derecha)"

    if source == "lb2023":
        table = pd.DataFrame({
            "region": labeled("reg").str.removeprefix("AR: "), "sexo": labeled("sexo"),
            "edad": labeled("reedad"), "nivel_educativo": labeled("REEEDUC_1"),
            "clase_social_subjetiva": labeled("S2"),
            "situacion_economica_pais_vs_hace_un_anio": labeled("P6STGBS"),
            "ideologia": ar[spec["ideology"]].map(ideology),
            "partido_que_votaria": ar[spec["party"]].map(lambda v: party_group(v, source)),
        })
        if not ar.mesreal.isin([2, 3, 4]).all():
            raise ValueError("Fechas fuera de la ventana LB2023 documentada.")
        dates = pd.to_datetime({"year": [2023] * len(ar), "month": ar.mesreal.tolist(), "day": ar.diareal.tolist()})
    else:
        parties = []
        for sympathy, party in zip(ar.vb10, ar.vb11):
            if sympathy == 2:
                if missing_code(party) != ".c":
                    raise ValueError("VB11 no respeta el filtro de VB10=2.")
                parties.append("No simpatiza con ningún partido")
            elif sympathy == 1:
                parties.append(party_group(party, source))
            elif missing_code(sympathy) in (".a", ".b"):
                if missing_code(party) != ".c":
                    raise ValueError("VB11 no respeta el filtro de VB10 ausente.")
                parties.append(NS)
            else:
                raise ValueError("VB10 desconocido/no preguntado.")
        table = pd.DataFrame({
            "region": labeled("region"), "sexo": labeled("q1tc"),
            "edad": ar.q2.map(lambda v: f"{int(v)} años"), "nivel_educativo": labeled("edre"),
            "ideologia": ar.l1n.map(ideology), "partido_con_el_que_simpatiza": parties,
        })
        dates = pd.to_datetime(pd.to_numeric(ar.fecha), unit="D", origin="1960-01-01")
        if not dates.between("2026-03-20", "2026-05-20").all():
            raise ValueError("Fechas fuera de la ventana LAPOP documentada.")
    table["respuesta_real"] = ar[spec["target"]].map(lambda v: response_option(v, source))
    table["peso"] = weights
    table = table.reset_index(drop=True)
    group = "partido_que_votaria" if source == "lb2023" else "partido_con_el_que_simpatiza"
    qa = {
        "n_real": len(table), "ids_unicos": ar[spec["id"]].map(str).nunique(),
        "fechas_observadas": [str(dates.min().date()), str(dates.max().date())],
        "peso_min": float(weights.min()), "peso_max": float(weights.max()),
        "peso_suma": float(weights.sum()), "n_por_grupo": dict(Counter(table[group])),
        "ns_ideologia": int((table.ideologia == NS).sum()),
        "columnas_perfil": [c for c in table if c not in ("respuesta_real", "peso")],
        "columnas_originales": {k: spec[k] for k in ("id", "target", "party", "ideology", "weight")},
        "diseno": {"upm": "upm", "estrato": "strata"} if source == "lapop2026" else {},
    }
    return table, group, qa


def prepare(path, source, out_dir, n, tag):
    if n <= 0 or not tag or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for c in tag):
        raise ValueError("n debe ser positivo y tag solo admite minúsculas, números, guion y guion bajo.")
    target = Path(out_dir).resolve()
    if not target.is_relative_to((ROOT / ".private").resolve()):
        raise ValueError("Los derivados deben permanecer en .private/.")
    spec = SPECS[source]
    universe_id, benchmark_id = f"universe_{source}_ar_{tag}", f"bench_{source}_ar_{tag}"
    csv_path, manifest_path = target / f"{source}_argentina.csv", target / f"{source}_manifest.json"
    config.set_user("privado")
    repo.use_local_storage()
    repo.set_active_user("privado")
    if csv_path.exists() or manifest_path.exists() or repo.find_universe(universe_id) or any(b.id == benchmark_id for b in repo.list_benchmarks()):
        raise ValueError("Ya existe esta preparación; usá otro tag y directorio para no sobrescribirla.")
    table, group, qa = read_source(path, source)
    mapping = {c: "atributo" for c in table}
    mapping.update({group: "grupo", "respuesta_real": "respuesta real", "peso": "peso"})
    universe, people = build_population(table, mapping, n, universe_id=universe_id, nombre=spec["name"],
                                        descripcion=spec["description"], fuente=csv_path.name)
    forbidden = {"respuesta_real", "peso", spec["target"], spec["id"], "upm", "strata", "fecha"}
    if any(forbidden & set(p.datos_reales) for p in people):
        raise ValueError("Fuga de respuesta/identificadores/diseño hacia el perfil.")
    benchmark, _ = benchmark_from_rows(table, "respuesta_real", spec["options"], segment_column=group,
                                       weight_column="peso", id=benchmark_id, nombre=spec["name"],
                                       pregunta=spec["question"], fuente=f"{source} Argentina (ponderado)", fecha=spec["date"])
    qa["n_sim_por_grupo"] = dict(Counter(p.perfil for p in people))
    qa["grupos_sin_muestra"] = sorted(set(qa["n_por_grupo"]) - set(qa["n_sim_por_grupo"]))
    qa["n_muestra"] = n
    target.mkdir(parents=True, exist_ok=True)
    table.to_csv(csv_path, index=False, encoding="utf8")
    repo.save_universe(universe)
    repo.save_expansion(universe.id, build_expansion_snapshot(universe, people))
    repo.save_benchmark(benchmark)
    manifest = {"schema_version": 1, "source": source, "url": spec["url"], "license": spec["license"],
                "original_path": str(Path(path).resolve()), "original_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                "csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
                "universe_id": universe_id, "benchmark_id": benchmark_id,
                "evaluacion_llm": "pendiente; no se consultó un modelo", "qa": qa}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf8")
    print(json.dumps({"universe_id": universe_id, "benchmark_id": benchmark_id, "manifest": str(manifest_path),
                      "n_real": len(table), "n_muestra": n, "grupos_sin_muestra": qa["grupos_sin_muestra"]}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=SPECS)
    parser.add_argument("dta")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--n", type=int, default=200)
    args = parser.parse_args()
    prepare(args.dta, args.source, args.out_dir, args.n, args.tag)


if __name__ == "__main__":
    main()
