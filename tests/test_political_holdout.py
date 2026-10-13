"""Protege faltantes estructurales, identidad política y aislamiento del control."""

import unittest

import pandas as pd

from app.domain.models import Benchmark
from app.services.probability_calibration_service import benchmark_signature
from tools.fit_group_probability_correction import apply_correction, baseline_rows, fit_correction, transform_rows
from tools.prepare_political_holdout import NS, party_group, response_option


class PoliticalHoldoutTests(unittest.TestCase):
    def test_missing_not_asked_is_not_an_opinion(self):
        self.assertEqual(response_option(-5, "lb2023"), NS)
        self.assertEqual(response_option(pd.io.stata.StataMissingValue(102), "lapop2026"), NS)
        for value in [-3, -4, 0, 88]:
            with self.assertRaises(ValueError):
                response_option(value, "lb2023")
        for value in [pd.io.stata.StataMissingValue(104), pd.io.stata.StataMissingValue(127)]:
            with self.assertRaises(ValueError):
                response_option(value, "lapop2026")

    def test_party_mapping_does_not_invent_libertarian_equivalence(self):
        self.assertEqual(party_group(32048, "lb2023"), "Avanza Libertad (categoría LB2023)")
        self.assertEqual(party_group(172501, "lapop2026"), "La Libertad Avanza")
        self.assertEqual(party_group(32045, "lb2023"), party_group(172503, "lapop2026"))
        with self.assertRaises(ValueError):
            party_group(99999, "lb2023")

    def fixture(self):
        benchmark = Benchmark(id="train", nombre="train", pregunta="Aprueba?", opciones=["Sí", "No"],
                              distribucion={"Sí": 60, "No": 40}, n=100,
                              por_segmento={"A": {"Sí": 90, "No": 10}, "B": {"Sí": 10, "No": 90}},
                              n_por_segmento={"A": 80, "B": 20}, fuente="X", fecha="2024")
        rows = [{"persona_id": str(i), "grupo": "A" if i < 25 else "B",
                 "probabilidades": {"Sí": 50, "No": 50}, "modelo": "modelo"} for i in range(30)]
        source = {"benchmark_id": benchmark.id, "benchmark_firma": list(benchmark_signature(benchmark)), "modelos": ["modelo"]}
        return benchmark, rows, fit_correction(rows, benchmark, source)

    def test_small_and_new_groups_use_frozen_global_offset(self):
        benchmark, rows, artifact = self.fixture()
        self.assertTrue(artifact["grupos"]["A"]["ajuste_especifico"])
        self.assertFalse(artifact["grupos"]["B"]["ajuste_especifico"])
        self.assertEqual(artifact["grupos"]["B"]["offsets"], artifact["offsets_globales"])
        known = transform_rows([rows[-1]], artifact)[0]["probabilidades"]
        new = transform_rows([{**rows[-1], "grupo": "Nuevo"}], artifact)[0]["probabilidades"]
        self.assertEqual(known, new)
        self.assertAlmostEqual(sum(known.values()), 100)
        self.assertEqual(rows[-1]["probabilidades"], {"Sí": 50, "No": 50})
        self.assertEqual(baseline_rows([rows[-1]], artifact)[0]["probabilidades"], artifact["baseline"]["global"])

    def test_external_application_rejects_training_model_and_scale(self):
        benchmark, rows, artifact = self.fixture()
        with self.assertRaises(ValueError):
            apply_correction(rows, artifact, benchmark, ["modelo"])
        external = Benchmark.from_dict({**benchmark.to_dict(), "id": "test", "fecha": "2023"})
        with self.assertRaises(ValueError):
            apply_correction(rows, artifact, external, ["otro"])
        external.opciones = ["Bueno", "Regular", "Malo"]
        with self.assertRaises(ValueError):
            apply_correction(rows, artifact, external, ["modelo"])


if __name__ == "__main__":
    unittest.main()
