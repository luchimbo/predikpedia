"""Exportador determinista MiroFish para el sandbox de TooMatch.

No modifica universos existentes: genera un contrato portable de población v1.
"""
from __future__ import annotations
import argparse, hashlib, json, random
from pathlib import Path

SCHEMA = "toomatch.population/v1"
NAMES = {
    "Mujer": ["Agustina", "Belén", "Camila", "Delfina", "Emilia", "Fiorella", "Guadalupe", "Helena", "Ivana", "Josefina", "Kiara", "Lucía", "Malena", "Natalia", "Olivia", "Paula", "Rocío", "Sofía", "Tamara", "Valentina"],
    "Hombre": ["Agustín", "Benjamín", "Bruno", "Damián", "Esteban", "Federico", "Gonzalo", "Hernán", "Ignacio", "Julián", "Kevin", "Leonardo", "Martín", "Nicolás", "Octavio", "Pablo", "Ramiro", "Santiago", "Tomás", "Valentín"],
}
STYLES = ["directa", "reflexiva", "sarcástica", "introvertida", "social", "calma"]
INTERESTS = ["cine independiente y caminatas", "cocina y música en vivo", "libros y cafés", "trekking y fotografía", "teatro y diseño", "ciclismo y podcasts"]
BIOGRAPHIES = ["Vive en una ciudad argentina y sostiene una rutina laboral estable.", "Valora los vínculos intencionales y reserva tiempo para sus amistades.", "Equilibra proyectos personales con una vida social moderada."]

def load_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schemaVersion") != SCHEMA or config.get("size") != 40:
        raise ValueError("Configuración TooMatch inválida.")
    return config

def profiles(config: dict) -> list[dict]:
    rng = random.Random(config["seed"])
    quotas = [("Mujer", "hetero", 17), ("Mujer", "bi", 2), ("Mujer", "lesbiana", 1), ("Hombre", "hetero", 17), ("Hombre", "bi", 1), ("Hombre", "gay", 2)]
    result, counters = [], {"Mujer": 0, "Hombre": 0}
    for gender, orientation, count in quotas:
        for _ in range(count):
            counters[gender] += 1
            age = rng.randint(25, 45)
            goal = rng.choices(["casual", "seria", "matrimonio"], weights=[18, 57, 25])[0]
            wants_kids = rng.choices(["si", "no", "abierta"], weights=[35, 35, 30])[0]
            relationship = rng.choices(["monogamia", "abierta"], weights=[88, 12])[0]
            style = rng.choice(STYLES)
            name = NAMES[gender][counters[gender] - 1]
            identifier = f"tm-ar-{gender[0].lower()}{counters[gender]:02d}"
            dealbreakers = ["sin tabaco", relationship]
            dealbreakers.append("quiere hijos" if wants_kids == "si" else "no quiere hijos" if wants_kids == "no" else "hablar de hijos sin presión")
            result.append({
                "id": identifier, "name": name, "gender": gender, "orientation": orientation, "age": age,
                "minAge": max(25, age - rng.randint(3, 8)), "maxAge": min(45, age + rng.randint(3, 8)),
                "goal": goal, "kids": wants_kids, "relationshipModel": relationship, "style": style,
                "availability": rng.choice(["dos noches por semana", "fines de semana", "noches de semana y domingo"]),
                "interests": rng.choice(INTERESTS), "dealbreakers": dealbreakers,
                "bigFive": {trait: round(rng.uniform(.18, .88), 2) for trait in "OCEAN"},
                "biography": rng.choice(BIOGRAPHIES),
                "backstory": f"{name} tiene un estilo {style}; prioriza {goal} y su principal límite es {dealbreakers[-1]}.",
                "communicationBias": "tiende a preguntar antes de concluir" if style in ("reflexiva", "calma") else "prefiere definir pronto lo importante",
                "frustrationTolerance": rng.choice(["baja", "media", "alta"]), "memory": [],
                "seed": rng.randrange(1, 2**31),
            })
    rng.shuffle(result)
    return result

def build(config: dict) -> dict:
    people = profiles(config)
    counts = {key: sum(1 for person in people if person["orientation"] == key) for key in ("hetero", "bi", "gay", "lesbiana")}
    return {"schemaVersion": SCHEMA, "population": {"id": config["populationId"], "version": config["version"], "country": "Argentina", "ageRange": "25-45", "size": 40, "orientationTarget": config["orientationDistribution"], "orientationActual": counts}, "seed": config["seed"], "source": config["source"], "profiles": people}

def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--config", type=Path, required=True); parser.add_argument("--out", type=Path, required=True); args = parser.parse_args()
    document = build(load_config(args.config)); args.out.parent.mkdir(parents=True, exist_ok=True); args.out.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.out), "profiles": len(document["profiles"]), "sha256": hashlib.sha256(args.out.read_bytes()).hexdigest()}, ensure_ascii=False))

if __name__ == "__main__": main()
