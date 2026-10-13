"""Corrección B2: distribución esperada, grupos reales y aislamiento de prueba."""

import math
import unittest

from app.domain.models import Benchmark
from app.services.probability_calibration_service import (
    benchmark_signature, evaluate, fit, prepare_rows, require_external, sharpen, wave_change,
)


class ProbabilityCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.options = ["Sí", "No"]
        self.benchmark = Benchmark(id="train", nombre="Encuesta", pregunta="¿Aprueba?", opciones=self.options,
                                   distribucion={"Sí": 50., "No": 50.}, n=100,
                                   por_segmento={"Partido A": {"Sí": 90., "No": 10.},
                                                 "Partido B": {"Sí": 10., "No": 90.}},
                                   n_por_segmento={"Partido A": 50, "Partido B": 50},
                                   fuente="Encuesta X", fecha="2024-09")
        self.rows = [{"persona_id": "a", "grupo": "Partido A", "probabilidades": {"Sí": 75., "No": 25.}},
                     {"persona_id": "b", "grupo": "Partido B", "probabilidades": {"Sí": 25., "No": 75.}}]

    def test_extremes_zeros_and_numerical_stability(self):
        self.assertEqual(sharpen({"Sí": 100, "No": 0}, self.options, 10000), {"Sí": 100., "No": 0.})
        self.assertEqual(sharpen({"Sí": 50, "No": 50}, self.options, 10000), {"Sí": 50., "No": 50.})
        self.assertAlmostEqual(sharpen({"Sí": 75, "No": 25}, self.options, 2)["Sí"], 90)

    def test_rejects_invalid_vectors(self):
        for probabilities in ({"Sí": 0, "No": 0}, {"Sí": -1, "No": 10}, {"Sí": math.nan, "No": 10},
                              {"Sí": math.inf, "No": 10}, {"Sí": 50}, {"Sí": 50, "No": 50, "Otro": 1}):
            with self.subTest(probabilities=probabilities), self.assertRaises(ValueError):
                sharpen(probabilities, self.options, 2)
        for k in (0, -1, math.nan, math.inf):
            with self.assertRaises(ValueError):
                sharpen({"Sí": 50, "No": 50}, self.options, k)

    def test_total_compensation_does_not_hide_group_error(self):
        score = evaluate(self.rows, self.benchmark)
        self.assertEqual(score["total"]["mae_pp"], 0)
        self.assertAlmostEqual(score["mae_grupos_macro_pp"], 15)
        fitted = fit(self.rows, self.benchmark, (1, 2, 4))
        self.assertEqual(fitted["exponente"], 2)
        self.assertAlmostEqual(fitted["ajustado"]["mae_grupos_macro_pp"], 0)
        self.assertEqual(self.rows[0]["probabilidades"]["Sí"], 75)

    def test_power_must_be_applied_before_aggregation(self):
        rows = [self.rows[0], {**self.rows[0], "persona_id": "c", "probabilidades": {"Sí": 50., "No": 50.}}]
        score = evaluate(rows, self.benchmark, 2)
        self.assertAlmostEqual(score["total"]["simulado"]["Sí"], 70)
        self.assertNotAlmostEqual(score["total"]["simulado"]["Sí"], sharpen({"Sí": 62.5, "No": 37.5}, self.options, 2)["Sí"])
        self.assertEqual(score["grupos_reales_sin_muestra"], ["Partido B"])

    def test_population_join_restores_party_and_tracks_failed_group(self):
        population = [{"persona_id": "a", "datos_reales": {"partido": "Partido A"}},
                      {"persona_id": "b", "datos_reales": {"partido": "Partido B"}}]
        answers = [{"persona_id": "a", "perfil": "Región", "respuesta": "texto", "probabilidades": {"Sí": 75, "No": 25}},
                   {"persona_id": "b", "perfil": "Región", "respuesta": "[ERROR: fallo]", "error": "fallo"}]
        rows, coverage = prepare_rows(answers, self.options, population=population, group_column="partido")
        self.assertEqual(rows[0]["grupo"], "Partido A")
        self.assertEqual(coverage["errores_por_grupo"], {"Partido B": 1})
        with self.assertRaises(ValueError):
            prepare_rows(answers, self.options, population=population[:1], group_column="partido")

    def test_missing_probabilities_and_repeated_people_abort(self):
        answer = {"persona_id": "a", "perfil": "Partido A", "respuesta": "texto", "probabilidades": {"Sí": 75, "No": 25}}
        with self.assertRaises(ValueError):
            prepare_rows([answer, answer], self.options)
        with self.assertRaises(ValueError):
            prepare_rows([{**answer, "probabilidades": {}}], self.options)

    def test_test_wave_and_model_are_independent(self):
        calibration = {"entrenamiento": {"benchmark_id": self.benchmark.id,
                                         "benchmark_firma": list(benchmark_signature(self.benchmark)), "modelos": ["qwen"]}}
        with self.assertRaises(ValueError):
            require_external(calibration, self.benchmark, ["qwen"])
        copied = Benchmark.from_dict({**self.benchmark.to_dict(), "id": "renamed"})
        with self.assertRaises(ValueError):
            require_external(calibration, copied, ["qwen"])
        other = Benchmark.from_dict({**self.benchmark.to_dict(), "id": "other", "fecha": "2025-01"})
        require_external(calibration, other, ["qwen"])
        with self.assertRaises(ValueError):
            require_external(calibration, other, ["gpt"])

    def test_wrong_signal_cannot_be_fixed_by_sharpening(self):
        # No preservar a la fuerza la hipótesis de que k>1 siempre mejora.
        reversed_rows = [{**r, "probabilidades": {"Sí": 100 - r["probabilidades"]["Sí"], "No": 100 - r["probabilidades"]["No"]}} for r in self.rows]
        self.assertEqual(fit(reversed_rows, self.benchmark)["exponente"], 1)

    def test_wave_change_uses_net_balance_in_pp(self):
        first = {"Sí": 30, "No": 50, "NSNC": 20}
        second = {"Sí": 60, "No": 30, "NSNC": 10}
        self.assertEqual(wave_change(first, second, positive=["Sí"], negative=["No"]), 50)
        with self.assertRaises(ValueError):
            wave_change(first, second, positive=["Sí"], negative=["Sí"])


if __name__ == "__main__":
    unittest.main()
