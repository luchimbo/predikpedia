import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "generate_toomatch_population.py"
CONFIG = ROOT / "config" / "toomatch_ar_25_45_v1.json"

def run(output):
    subprocess.run([sys.executable, str(GENERATOR), "--config", str(CONFIG), "--out", str(output)], check=True)
    return json.loads(output.read_text(encoding="utf-8"))

def test_population_is_deterministic_and_calibrated(tmp_path):
    first, second = run(tmp_path / "one.json"), run(tmp_path / "two.json")
    assert first == second
    assert len(first["profiles"]) == 40
    assert first["population"]["orientationActual"] == {"hetero": 34, "bi": 3, "gay": 2, "lesbiana": 1}
    assert all(25 <= p["age"] <= 45 and set(p["bigFive"]) == set("OCEAN") for p in first["profiles"])
