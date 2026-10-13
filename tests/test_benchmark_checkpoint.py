import unittest

from app.domain.models import Estudio, RespuestaEstudio
from tools.benchmark_checkpoint import prepare_resume


class BenchmarkCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.study = Estudio(id="s", universo_id="u", universo_nombre="U", titulo="T", pregunta="Q", contexto="C",
                             respuestas_planeadas=2, opciones=["Sí", "No"], temperature=1, modo_cerrada="probabilidades")
        self.people = [{"persona_id": "a"}, {"persona_id": "b"}]
        self.manifest = {"model": "qwen", "provider_mode": "local", "personas_sha256": "people", "prompt_sha256": "prompt"}
        self.good = RespuestaEstudio(estudio_id="s", persona_id="a", perfil="P", repeticion=1,
                                    pregunta="Q", contexto="C", respuesta="R", probabilidades={"Sí": 60, "No": 40})
        self.failed = RespuestaEstudio(estudio_id="s", persona_id="b", perfil="P", repeticion=1,
                                      pregunta="Q", contexto="C", respuesta="[ERROR]", error="offline")

    def resume(self, answers, **kwargs):
        return prepare_resume(self.study, self.study, answers, self.people, self.manifest, self.manifest, **kwargs)

    def test_completed_people_are_never_called_again(self):
        saved, pending = self.resume([self.good])
        self.assertEqual(saved, [self.good])
        self.assertEqual(pending, [{"persona_id": "b"}])

    def test_retry_only_errors_is_explicit_and_preserves_valid_distribution(self):
        saved, pending = self.resume([self.good, self.failed])
        self.assertEqual(len(saved), 2)
        self.assertEqual(pending, [])
        saved, pending = self.resume([self.good, self.failed], retry_errors=True)
        self.assertEqual(saved, [self.good])
        self.assertEqual(pending, [{"persona_id": "b"}])
        self.assertEqual(self.good.probabilidades, {"Sí": 60, "No": 40})

    def test_model_population_prompt_or_provider_change_aborts(self):
        for key in self.manifest:
            with self.subTest(key=key), self.assertRaises(ValueError):
                prepare_resume(self.study, self.study, [self.good], self.people, self.manifest,
                               {**self.manifest, key: "changed"})

    def test_question_or_temperature_change_aborts(self):
        for key, value in [("pregunta", "New question"), ("temperature", 0), ("respuestas_planeadas", 3)]:
            requested = Estudio.from_dict({**self.study.to_dict(), key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                prepare_resume(self.study, requested, [self.good], self.people, self.manifest, self.manifest)

    def test_duplicate_and_other_study_rows_abort(self):
        with self.assertRaises(ValueError):
            self.resume([self.good, self.good])
        unrelated = RespuestaEstudio.from_dict({**self.good.to_dict(), "estudio_id": "other"})
        with self.assertRaises(ValueError):
            self.resume([unrelated])


if __name__ == "__main__":
    unittest.main()
