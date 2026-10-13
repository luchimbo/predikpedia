import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import pandas as pd

from app.config import config
from app.domain.models import Benchmark, Estudio, RespuestaEstudio
from app.services.calibration_service import (
    benchmark_from_counts,
    benchmark_from_rows,
    compare,
    compare_with_benchmark,
    max_margin_of_error,
    simulated_distributions,
)
from app.services.llm_service import LLMError
from app.services.simulation_service import run_simulation
from app.services.study_response_service import build_user_prompt, match_option, parse_study_response
from app.storage import repository

OPTIONS = ["Milei", "Kicillof", "No sabe"]


def payload(option="Milei", **extra):
    return {"response_text": "Lo voto porque sí.", "sentiment": "neutral", "intent": "no_aplica",
            "main_objection": "", "main_driver": "", "confidence": "low", "quote": "Lo voto",
            "opcion_elegida": option, **extra}


def respuesta(perfil, opcion, error=""):
    return RespuestaEstudio(estudio_id="s1", persona_id=f"P{id(object())}", perfil=perfil, repeticion=1,
                            pregunta="¿A quién votarías?", contexto="", respuesta="texto" if not error else "",
                            error=error, opcion_elegida=opcion).to_dict()


class ClosedQuestionContractTests(TestCase):
    def test_prompt_lists_options_only_when_closed(self):
        self.assertIn('"Kicillof"', build_user_prompt("¿A quién votarías?", OPTIONS))
        self.assertIn("opcion_elegida", build_user_prompt("¿A quién votarías?", OPTIONS))
        self.assertNotIn("opcion_elegida", build_user_prompt("¿Qué opinás?"))

    def test_match_option_tolerates_accents_case_and_index(self):
        self.assertEqual("No sabe", match_option("no sabé.", OPTIONS))
        self.assertEqual("Kicillof", match_option("2", OPTIONS))
        self.assertIsNone(match_option("Bullrich", OPTIONS))
        self.assertIsNone(match_option("7", OPTIONS))

    def test_parse_returns_canonical_option(self):
        self.assertEqual("Milei", parse_study_response(payload("MILEI"), OPTIONS)["opcion_elegida"])

    def test_option_outside_list_is_an_error_not_a_vote(self):
        with self.assertRaises(LLMError):
            parse_study_response(payload("Bullrich"), OPTIONS)
        with self.assertRaises(LLMError):
            parse_study_response({k: v for k, v in payload().items() if k != "opcion_elegida"}, OPTIONS)

    def test_open_question_ignores_option_field(self):
        self.assertNotIn("opcion_elegida", parse_study_response(payload("cualquiera")))


class ProbabilityModeTests(TestCase):
    def test_prompt_asks_for_probabilities(self):
        prompt = build_user_prompt("¿A quién votarías?", OPTIONS, "probabilidades")
        self.assertIn('"probabilidades"', prompt)
        self.assertNotIn('"opcion_elegida"', prompt)

    def test_normalizes_and_samples_reproducibly(self):
        raw = payload(probabilidades={"milei": 30, "Kicillof": 10, "No sabé": 0})
        first = parse_study_response(raw, OPTIONS, "probabilidades", seed="r1")
        self.assertAlmostEqual(75.0, first["probabilidades"]["Milei"])
        self.assertEqual(first["opcion_elegida"], parse_study_response(raw, OPTIONS, "probabilidades", seed="r1")["opcion_elegida"])
        self.assertIn(first["opcion_elegida"], ["Milei", "Kicillof"])  # una opción con 0 nunca sale

    def test_sampling_follows_the_distribution(self):
        raw = payload(probabilidades={"Milei": 80, "Kicillof": 20, "No sabe": 0})
        picks = [parse_study_response(raw, OPTIONS, "probabilidades", seed=f"r{i}")["opcion_elegida"] for i in range(500)]
        self.assertAlmostEqual(0.8, picks.count("Milei") / 500, delta=0.06)

    def test_invalid_probabilities_are_errors(self):
        for bad in [None, {"Bullrich": 100}, {"Milei": -5, "Kicillof": 10}, {"Milei": 0}, {"Milei": "mucho"}]:
            with self.assertRaises(LLMError):
                parse_study_response(payload(probabilidades=bad), OPTIONS, "probabilidades", seed="x")

    def test_old_studies_default_to_single_choice(self):
        self.assertEqual("eleccion", Estudio.from_dict({"id": "s"}).modo_cerrada)


class Model:
    def __init__(self, options_by_call):
        self.options = list(options_by_call)
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return payload(self.options[len(self.calls) - 1])


def study(**overrides):
    base = dict(id="s1", universo_id="u1", universo_nombre="U", titulo="t", pregunta="¿A quién votarías?",
                contexto="", opciones=list(OPTIONS), temperature=1.0)
    return Estudio(**{**base, **overrides})


PERSONAS = [{"persona_id": f"P{i}", "perfil": "C3"} for i in range(3)]


class ClosedStudySimulationTests(TestCase):
    def test_saves_chosen_option_and_sends_temperature(self):
        model = Model(["Milei", "kicillof", "Bullrich"])
        answers = run_simulation(study(), PERSONAS, model)
        self.assertEqual(["Milei", "Kicillof", ""], [a.opcion_elegida for a in answers])
        self.assertTrue(answers[2].error)  # opción inventada: queda como error, no cuenta
        self.assertTrue(all(call["temperature"] == 1.0 for call in model.calls))

    def test_interview_rejects_closed_questions(self):
        with self.assertRaises(ValueError):
            run_simulation(study(mode="interview"), PERSONAS, Model(["Milei"] * 3))

    def test_rejects_duplicate_options(self):
        with self.assertRaises(ValueError):
            run_simulation(study(opciones=["Milei", "milei"]), PERSONAS, Model(["Milei"] * 3))


class MetricsTests(TestCase):
    def test_known_distributions(self):
        result = compare({"A": 60, "B": 40}, {"A": 55, "B": 45}, ["A", "B"], n_sim=100, n_real=1000)
        self.assertAlmostEqual(5.0, result["mae"])
        self.assertAlmostEqual(5.0, result["tvd"])
        self.assertTrue(result["misma_opcion_ganadora"])
        # Margen: 1.96 * sqrt(.55 * .45 * (1/100 + 1/1000)) ≈ 10.2 pp; 5 pp todavía puede ser azar.
        self.assertFalse(result["filas"][0]["fuera_de_margen"])

    def test_three_options_tvd_is_half_the_abs_sum(self):
        result = compare({"A": 50, "B": 30, "C": 20}, {"A": 30, "B": 30, "C": 40}, ["A", "B", "C"], 500, 500)
        self.assertAlmostEqual(40 / 3, result["mae"])
        self.assertAlmostEqual(20.0, result["tvd"])
        self.assertFalse(result["misma_opcion_ganadora"])
        self.assertEqual(2, result["opciones_fuera_de_margen"])

    def test_tie_in_real_result_is_not_a_match(self):
        result = compare({"A": 60, "B": 40}, {"A": 50, "B": 50}, ["A", "B"], 100, 100)
        self.assertFalse(result["misma_opcion_ganadora"])
        self.assertEqual("empate entre A y B", result["ganadora_real"])

    def test_margin_of_error(self):
        self.assertAlmostEqual(2.53, max_margin_of_error(1500), places=2)
        self.assertEqual(float("inf"), max_margin_of_error(0))

    def test_simulated_distribution_skips_errors_and_groups(self):
        df = pd.DataFrame([respuesta("C3", "Milei"), respuesta("C3", "Kicillof"), respuesta("D/E", "Milei"),
                           respuesta("D/E", "", error="falló")])
        dist = simulated_distributions(df, OPTIONS)
        self.assertEqual(3, dist["n"])
        self.assertAlmostEqual(200 / 3, dist["total"]["Milei"])
        self.assertEqual(0, dist["total"]["No sabe"])
        self.assertEqual({"C3": 2, "D/E": 1}, dist["n_por_segmento"])


class BenchmarkBuildTests(TestCase):
    def test_from_rows_maps_weights_segments_and_reports_discarded(self):
        df = pd.DataFrame({
            "NSE": ["C3", "C3", "D/E", "D/E", "D/E"],
            "Voto": ["Milei", "kicillof", "Milei", "Ns/Nc", "Otro"],
            "Peso": ["1", "3", "1,5", "1", "1"],
        })
        bench, discarded = benchmark_from_rows(df, "Voto", OPTIONS, segment_column="NSE", weight_column="Peso",
                                               manual_mapping={"Ns/Nc": "No sabe"}, id="b1", nombre="Real")
        self.assertEqual({"Otro": 1}, discarded)
        self.assertEqual(4, bench.n)
        self.assertAlmostEqual(2.5 * 100 / 6.5, bench.distribucion["Milei"])
        self.assertAlmostEqual(75.0, bench.por_segmento["C3"]["Kicillof"])
        self.assertEqual({"C3": 2, "D/E": 2}, bench.n_por_segmento)

    def test_numeric_codes_are_not_taken_as_option_index(self):
        df = pd.DataFrame({"Voto": ["1", "Milei"]})
        _, discarded = benchmark_from_rows(df, "Voto", OPTIONS)
        self.assertEqual({"1": 1}, discarded)

    def test_from_counts_infers_n_from_integer_counts(self):
        bench = benchmark_from_counts({"Milei": 600, "Kicillof": 300, "No sabe": 100}, OPTIONS)
        self.assertEqual(1000, bench.n)
        self.assertAlmostEqual(60.0, bench.distribucion["Milei"])
        with self.assertRaises(ValueError):
            benchmark_from_counts({"Milei": 60, "Kicillof": 40}, OPTIONS)  # porcentajes sin n

    def test_compare_with_benchmark_pairs_segments_by_name(self):
        bench = Benchmark(id="b", nombre="r", pregunta="p", opciones=OPTIONS,
                          distribucion={"Milei": 50, "Kicillof": 50, "No sabe": 0}, n=100,
                          por_segmento={"c3": {"Milei": 50, "Kicillof": 50, "No sabe": 0},
                                        "ABC1": {"Milei": 80, "Kicillof": 20, "No sabe": 0}},
                          n_por_segmento={"c3": 50, "ABC1": 50})
        df = pd.DataFrame([respuesta("C3", "Milei"), respuesta("C3", "Kicillof"), respuesta("D/E", "Milei")])
        result = compare_with_benchmark(df, bench)
        self.assertEqual(["C3"], [s["segmento"] for s in result["segmentos"]])
        self.assertAlmostEqual(0.0, result["segmentos"][0]["mae"])
        self.assertEqual(["D/E"], result["segmentos_sin_par_simulados"])
        self.assertEqual(["ABC1"], result["segmentos_sin_par_reales"])


class CompatibilityAndStorageTests(TestCase):
    def test_old_json_loads_without_new_fields(self):
        estudio = Estudio.from_dict({"id": "s", "universo_id": "u", "universo_nombre": "U",
                                     "titulo": "t", "pregunta": "p", "contexto": ""})
        self.assertEqual([], estudio.opciones)
        self.assertIsNone(estudio.temperature)
        r = RespuestaEstudio.from_dict({"estudio_id": "s", "persona_id": "P", "perfil": "x",
                                        "pregunta": "p", "contexto": "", "respuesta": "hola"})
        self.assertEqual("", r.opcion_elegida)

    def test_benchmark_roundtrip_in_local_storage(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(config, "benchmarks_dir", Path(tmp)), \
                patch.object(repository, "_USE_SUPABASE", False):
            bench = benchmark_from_counts({"Milei": 6, "Kicillof": 4}, ["Milei", "Kicillof"], id="b1", nombre="R")
            repository.save_benchmark(bench)
            loaded = repository.list_benchmarks()
            self.assertEqual([bench.to_dict()], [b.to_dict() for b in loaded])
            repository.delete_benchmark("b1")
            self.assertEqual([], repository.list_benchmarks())
