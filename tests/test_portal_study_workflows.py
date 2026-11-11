import base64
import hashlib
import hmac
import json
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import replace
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
from uuid import uuid4

from app.config import config
from app.domain.models import Benchmark, Estudio, RespuestaEstudio, Universo
from app.pages import validacion
from app.services.portal_auth import verify_handoff
from app.services.study_recovery import continue_survey, prepare_survey, study_lock
from app.services.variant_comparison import compare_variants
from app.storage import repository
from test_study_realism import response


SECRET = "test-key-" * 4


def token_for(owner, **claims):
    payload = {"sub": owner, "aud": "predikpedia-streamlit", "iat": 100, "exp": 160, **claims}
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
    signature = hmac.new(SECRET.encode(), encoded, hashlib.sha256).digest()
    return encoded.decode() + "." + base64.urlsafe_b64encode(signature).decode().rstrip("=")


class PortalTests(TestCase):
    def test_claims_and_expiration(self):
        owner = str(uuid4())
        token = token_for(owner)
        self.assertEqual(verify_handoff(token, SECRET, 101), owner)
        self.assertIsNone(verify_handoff(token, SECRET, 160))
        self.assertIsNone(verify_handoff(token, "different-key-" * 4, 101))
        self.assertIsNone(verify_handoff(token_for(owner, aud="other"), SECRET, 101))
        self.assertIsNone(verify_handoff(token_for(owner, exp=200), SECRET, 101))

    def test_two_sessions_keep_owner_paths_and_storage_separate(self):
        a, b = str(uuid4()), str(uuid4())

        def bind(owner, other, local):
            verified = verify_handoff(token_for(owner), SECRET, 101)
            repository.set_active_user(verified)
            config.set_user(verified, create=False)
            if local:
                repository.use_local_storage()
            with self.assertRaises(ValueError):
                repository._owned_remote_path(f"supabase://{other}/estudios/s.json")

        def identity():
            return repository._uid(), config.data_dir.name, repository.uses_supabase()

        sessions = [copy_context(), copy_context()]
        with mock.patch.object(repository, "_SUPABASE_CONFIGURED", True):
            sessions[0].run(bind, a, b, True)
            sessions[1].run(bind, b, a, False)
            self.assertEqual(sessions[0].run(identity), (a, a, False))
            self.assertEqual(sessions[1].run(identity), (b, b, True))


    def test_streamlit_uses_verified_identity_even_with_different_uid(self):
        from streamlit.testing.v1 import AppTest

        a, b = str(uuid4()), str(uuid4())
        with mock.patch.dict("os.environ", {"PREDIKPEDIA_REQUIRE_PORTAL_AUTH": "1",
                                            "PREDIKPEDIA_HANDOFF_SECRET": SECRET}), \
             mock.patch("app.services.portal_auth.time.time", return_value=101), \
             mock.patch.object(repository, "_SUPABASE_CONFIGURED", True), \
             mock.patch.object(config, "ensure_directories"), \
             mock.patch("app.services.credits_service.CreditsService._ensure_ledger"), \
             mock.patch.object(repository, "_sb", mock.Mock(list_files=mock.Mock(return_value=[])), create=True):
            first = AppTest.from_file("predikpedia.py")
            first.query_params.update(session=token_for(a), uid=b)
            first.run()
            self.assertFalse(first.exception)
            self.assertEqual(first.session_state["data_owner_id"], a)
            self.assertNotIn("session", first.query_params)

            second = AppTest.from_file("predikpedia.py")
            second.query_params.update(session=token_for(b), uid=a)
            second.run()
            self.assertFalse(second.exception)
            self.assertEqual(second.session_state["data_owner_id"], b)

            invalid = AppTest.from_file("predikpedia.py")
            invalid.query_params.update(session="invalid", uid=b)
            invalid.run()
            self.assertFalse(invalid.exception)
            self.assertTrue(invalid.info)
            self.assertNotIn("data_owner_id", invalid.session_state)


class SurveyTests(TestCase):
    def test_interrupt_then_resume_and_retry_without_duplicates(self):
        with TemporaryDirectory() as directory:
            copy_context().run(self._exercise_recovery, directory)

    def _exercise_recovery(self, directory):
        repository.use_local_storage()
        config.set_session_dir(directory)
        study = Estudio("survey", "u", "Audience", "Title", "Question?", "",
                       respuestas_planeadas=3, resumable=True)
        sample = [{"persona_id": str(i), "notas": "Original"} for i in range(3)]
        prepare_survey(study, sample)
        sample[2]["notas"] = "Changed"
        engine = mock.Mock()
        engine.generate.side_effect = [response(), {}, RuntimeError("interrupted")]
        with self.assertRaisesRegex(RuntimeError, "interrupted"):
            continue_survey(study, engine)
        saved = repository.load_study_results(study.id)
        self.assertEqual([a.persona_id for a in saved], ["0", "1"])
        self.assertTrue(saved[1].error)

        engine.generate.reset_mock(side_effect=True)
        engine.generate.return_value = response()
        answers = continue_survey(study, engine)
        self.assertEqual(engine.generate.call_count, 1)
        self.assertEqual(engine.generate.call_args.kwargs["agent_id"], "2")
        self.assertIn("Original", engine.generate.call_args.kwargs["system_prompt"])
        self.assertEqual(answers[0], saved[0])

        engine.generate.reset_mock()
        answers = continue_survey(study, engine, retry_errors=True)
        self.assertEqual(engine.generate.call_args.kwargs["agent_id"], "1")
        self.assertEqual([a.persona_id for a in answers], ["0", "1", "2"])
        self.assertTrue(all(not a.error for a in answers))

        with study_lock(study.id), ThreadPoolExecutor(max_workers=1) as pool:
            other = copy_context()
            concurrent = pool.submit(other.run, continue_survey, study, engine)
            with self.assertRaisesRegex(ValueError, "otra sesión"):
                concurrent.result(timeout=2)

    def test_paired_results_exclude_missing_and_show_empty_segments(self):
        a = Estudio("a", "u", "Audience", "A", "Pregunta", "Estímulo A",
                    opciones=["Sí", "No"], variant="A", paired_study_id="b")
        b = replace(a, id="b", variant="B", paired_study_id="a")
        first = RespuestaEstudio("a", "p1", "G1", 1, a.pregunta, "", "Texto", opcion_elegida="Sí")
        second = replace(first, estudio_id="b", opcion_elegida="No")
        unpaired = replace(first, persona_id="p2", perfil="G2")
        comparison = compare_variants(a, b, [first, unpaired], [second])
        self.assertEqual(comparison["pairs"], 1)
        self.assertEqual(comparison["valid_a"], 2)
        self.assertEqual(comparison["rows"][0]["B − A (pp)"], -100)
        group_two = next(row for row in comparison["rows"] if row["Segmento"] == "G2")
        self.assertEqual(group_two["Pares"], 0)
        self.assertIsNone(group_two["B − A (pp)"])

    def test_benchmark_compatibility_and_independence(self):
        study = Estudio("s", "u", "Audience", "Title", "Pregunta", "",
                        opciones=["Sí", "No"], research_snapshot_id="r")
        benchmark = Benchmark("b", "Survey", "Pregunta", ["Sí", "No"], {"Sí": 70, "No": 30}, 100,
                              fuente="https://source.test/survey")
        self.assertTrue(validacion._compatible(benchmark, study))
        self.assertFalse(validacion._compatible(replace(benchmark, pregunta="Otra pregunta"), study))
        snapshot = {"documents": [{"id": "d", "url": benchmark.fuente, "title": "Fuente"}],
                    "project": {"excluded_ids": []}}
        with mock.patch("app.components.evidence.session_store", return_value=object()), \
             mock.patch("app.storage.research_repository.ResearchRepository") as repo:
            repo.return_value.get_snapshot.return_value = snapshot
            self.assertIn("se usó para construir", validacion.benchmark_independence_issue(study, benchmark))
            independent = replace(benchmark, fuente="https://other.test/survey")
            self.assertEqual(validacion.benchmark_independence_issue(study, independent), "")

        audience = Universo("u", "Audience", "", 10, origen="datos_reales", fuente="input.csv (10 filas)", source_digest="hash")
        with mock.patch.object(validacion, "find_universe", return_value=audience):
            renamed = replace(benchmark, fuente="renamed.csv", source_digest="hash")
            self.assertIn("se usó para construir",
                          validacion.benchmark_independence_issue(replace(study, research_snapshot_id=""), renamed))


    def test_ab_flow_creates_linked_surveys_and_renders_coverage(self):
        from streamlit.testing.v1 import AppTest

        with TemporaryDirectory() as directory:
            script = f"""from app.config import config
from app.storage.repository import use_local_storage
from app.pages.estudios import render_estudios_page
from app.pages.resultados import render_resultados_page
import streamlit as st
config.set_session_dir({directory!r})
use_local_storage()
if st.session_state.get("current_page") == "Resultados":
    render_resultados_page()
else:
    render_estudios_page()
"""
            audience = Universo("u", "Audience", "Brief", 2)
            personas = [{"persona_id": str(i), "perfil": "G1"} for i in range(2)]
            engine = mock.Mock()
            engine.generate.side_effect = [response(opcion_elegida=o) for o in ["Sí", "Sí", "Sí", "No"]]
            with mock.patch("app.pages.estudios.list_universes", return_value=[audience]), \
                 mock.patch("app.pages.estudios._personas_for", return_value=personas), \
                 mock.patch("app.pages.estudios.LLMService", return_value=engine):
                app = AppTest.from_string(script).run()
                app.toggle(key="est_ab").set_value(True).run()
                app.text_area(key="est_variant_a").set_value("Estímulo uno")
                app.text_area(key="est_variant_b").set_value("Estímulo dos")
                app.text_area(key="est_pregunta").set_value("¿Te interesa?")
                app.text_area(key="est_opciones").set_value("Sí\nNo")
                app.button(key="est_run").click().run()
                self.assertFalse(app.exception)
                self.assertEqual(app.session_state["current_page"], "Resultados")
                result_page = AppTest.from_string(script)
                result_page.session_state["current_page"] = "Resultados"
                result_page.run()
                self.assertFalse(result_page.exception)
                self.assertTrue(any("2 de 2 respuestas válidas" in el.value for el in result_page.caption))
                self.assertTrue(any("2 personas con respuesta válida en ambas variantes" in el.value for el in result_page.caption))
                self.assertIn("Estímulo uno", engine.generate.call_args_list[0].kwargs["system_prompt"])
                self.assertIn("Estímulo dos", engine.generate.call_args_list[2].kwargs["system_prompt"])
