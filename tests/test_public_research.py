"""Evidence readiness, local-only inference, recovery and the Streamlit journey."""

from copy import deepcopy
from dataclasses import replace
from io import BytesIO
import json
from pathlib import Path
import tempfile
from unittest import TestCase, mock

from app.domain.models import Estudio, Universo, Benchmark
from app.domain.research_models import ResearchBrief, ResearchDocument, ResearchProject, fingerprint
from app.services.llm_service import LLMError, LLMService
from app.services.public_research_service import PublicResearchService, validate_research_run, benchmark_overlaps_research
from app.services.public_search_service import PublicSearch, normalize_url, validate_public_url
from app.services.research_quality_service import diagnose, general_population
from app.services.simulation_service import run_simulation
from app.storage.evidence_repository import EvidenceRepository
from app.storage.research_repository import ResearchRepository


POPULATION = "Músicos principiantes que graban en casa participaron del estudio."
REGION = "Esta investigación se realizó en Argentina durante septiembre de 2026."
METHOD = "Se entrevistó a una muestra de músicos mediante entrevistas semiestructuradas."
QUOTE = "Los músicos principiantes necesitan aprender a reducir ruido al grabar."
WEIGHTS = "Los datos se ponderaron por región y experiencia para representar a la población."
ORIGIN = "Los resultados pertenecen al Estudio público sobre grabación casera."
TEXT = "\n".join((POPULATION, REGION, METHOD, QUOTE, WEIGHTS, ORIGIN))


def brief(**kwargs):
    return ResearchBrief(question="¿Qué dificultades encontrás al grabar?", audience="Músicos principiantes",
                         region="Argentina", as_of="2026-10-09", **kwargs)


def document(**kwargs):
    return ResearchDocument(id="doc", url="https://example.org/research", title="Estudio de músicos principiantes",
                            text=TEXT, status="read", published_at="2026-09-01", content_hash=fingerprint(TEXT), **kwargs)


def finding(**kwargs):
    value = {"id": "f", "dimension_id": "needs", "document_id": "doc", "claim": QUOTE, "quote": QUOTE,
             "population_quote": POPULATION, "region_quote": REGION, "classification": "documented",
             "scope": "direct", "kind": "interview", "method_quote": METHOD, "weight_quote": "",
             "origin_quote": ORIGIN, "observed_on": "", "date_quote": "", "contradiction": False}
    value.update(kwargs)
    return value


def ready_project(**kwargs):
    project = ResearchProject(brief=brief(**kwargs), dimensions=[
        {"id": "needs", "label": "Necesidades", "reason": "Cambian la respuesta", "critical": True,
         "max_age_days": 365, "queries": ["músicos principiantes Argentina estudio necesidades"]},
        {"id": "knowledge", "label": "Conocimiento", "reason": "Limita lo que sabe", "critical": False,
         "max_age_days": None, "queries": ["músicos Argentina conocimientos"]}],
        document_ids=["doc"], findings=[finding()],
        audit={"complete": True, "gaps": [], "contradictions": [], "limitations": ["No prueba intención de compra."], "suggested_scope": ""})
    project.diagnosis = diagnose(project, [document()])
    return project


class ScriptedModel:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("Unexpected model request")
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return deepcopy(result)


def design():
    from app.services.universe_service import SAMPLED_FIELDS, OPTIONAL_FIELDS
    attrs = {k: "No especificado" for k in SAMPLED_FIELDS + OPTIONAL_FIELDS}
    attrs.update(objetivo="Aprender a reducir ruido", notas="No inventar biografía")
    return {"segmentos": [{"nombre": "Principiantes", "descripcion": "Descripción no verificada",
                           "porcentaje": 100, "arquetipos": [{"nombre": "Aprendiz", "peso": 7, "atributos": attrs}]}],
            "grounding": [{"segment": "Principiantes", "archetype": "Aprendiz", "attributes": {"objetivo": ["f"]}, "percentage_refs": []}]}


class QualityTests(TestCase):
    def test_user_price_requires_conditions_and_iso_date(self):
        for price in ("a definir", "100"):
            with self.assertRaisesRegex(ValueError, "moneda"):
                brief(price=price)
        self.assertEqual("USD 100", brief(price="USD 100").price)
        self.assertEqual("gratis", brief(price="gratis").price)
        with self.assertRaises(ValueError):
            ResearchBrief("Pregunta", "Público", "Argentina", as_of="2026-10-09T12:00:00")

    def test_later_publication_cannot_validate_a_historical_scenario(self):
        project = ready_project()
        doc = document()
        doc.published_at = "2026-10-10"
        quote = "El trabajo de campo se realizó el 1 de septiembre de 2026."
        doc.text += "\n" + quote
        project.findings[0].update(observed_on="2026-09-01", date_quote=quote)
        self.assertFalse(diagnose(project, [doc])["can_build"])

    def test_ready_means_exploratory_not_predictive_precision(self):
        diagnosis = ready_project().diagnosis
        self.assertTrue(diagnosis["can_build"])
        self.assertEqual("No validada contra respuestas reales", diagnosis["precision"])
        self.assertEqual("unknown", diagnosis["rows"][1]["status"])

    def test_critical_gaps_cannot_be_overridden_by_model_approval(self):
        project = ready_project()
        for changes in ({"quote": "Esta cita no existe dentro del documento original"},
                        {"population_quote": "Población inexistente en el documento original"},
                        {"region_quote": "Este estudio fue realizado en Chile durante octubre"},
                        {"scope": "approximate"}, {"contradiction": True}):
            with self.subTest(changes=changes):
                project.findings = [finding(**changes)]
                self.assertFalse(diagnose(project, [document()])["can_build"])

    def test_general_population_is_backed_by_a_regional_statistic(self):
        statistic = "La tasa de desocupación en Argentina llegó al 7,9% en el segundo trimestre."
        doc = replace(document(), text=TEXT + chr(10) + statistic)
        project = ready_project()
        project.brief = replace(project.brief, audience="Población adulta (18 años o más) de Argentina")
        project.findings = [finding(quote=statistic, population_quote="", region_quote=statistic)]
        self.assertTrue(diagnose(project, [doc])["can_build"])
        # A statistic that never names the region, in a source that is not about it, is not evidence about it.
        unnamed = "La tasa de desocupación llegó al 7,9% en el segundo trimestre del año."
        doc = replace(document(), text=TEXT.replace("Argentina", "la región") + chr(10) + unnamed)
        project.findings = [finding(quote=unnamed, population_quote="", region_quote="")]
        self.assertFalse(diagnose(project, [doc])["can_build"])
        # National sources rarely repeat the country in every sentence: a source about it is enough.
        doc = replace(doc, title="El desempleo en Argentina subió en el segundo trimestre")
        self.assertTrue(diagnose(project, [doc])["can_build"])

    def test_subgroup_audience_still_needs_its_own_population_quote(self):
        project = ready_project()
        project.findings = [finding(population_quote="")]
        self.assertFalse(diagnose(project, [document()])["can_build"])

    def test_general_population_detection(self):
        for audience, expected in (("Población adulta (18 años o más) de Argentina", True),
                                   ("Argentinos mayores de edad", True), ("Votantes de Argentina", True),
                                   ("Músicos principiantes", False),
                                   ("Adultos de Argentina que usan billeteras virtuales", False)):
            with self.subTest(audience=audience):
                self.assertEqual(expected, general_population(ResearchBrief("Pregunta", audience, "Argentina", as_of="2026-10-09")))

    def test_missing_and_unread_documents_do_not_count(self):
        for docs in ([], [replace(document(), status="unusable", text="snippet de buscador")]):
            self.assertFalse(diagnose(ready_project(), docs)["can_build"])

    def test_expired_unknown_or_future_date_blocks_time_sensitive_evidence(self):
        for published in ("", "2020-01-01", "2027-01-01"):
            self.assertFalse(diagnose(ready_project(), [replace(document(), published_at=published)])["can_build"])

    def test_fabricated_method_and_observation_date_are_rejected(self):
        project = ready_project()
        project.findings = [finding(method_quote="Una metodología que no está publicada en la fuente", kind="survey")]
        self.assertFalse(diagnose(project, [document()])["can_build"])
        project.findings = [finding(observed_on="2026-10-01", date_quote="Una fecha inexistente para el trabajo de campo")]
        self.assertFalse(diagnose(project, [document()])["can_build"])

    def test_population_proportions_need_population_method_and_weighting(self):
        project = ready_project(goal="proportions")
        project.dimensions[0]["id"] = "proportions"
        project.findings = [finding(dimension_id="proportions", kind="commentary", classification="individual_report")]
        self.assertFalse(diagnose(project, [document()])["can_build"])
        project.findings = [finding(dimension_id="proportions", kind="survey", weight_quote=WEIGHTS)]
        self.assertTrue(diagnose(project, [document()])["can_build"])

    def test_copies_or_one_publisher_do_not_count_as_independent_corroboration(self):
        project = ready_project()
        project.findings = [finding(kind="commentary", method_quote=""),
                            finding(id="f2", document_id="doc2", kind="commentary", method_quote="")]
        second = replace(document(), id="doc2", url="https://other.org/copy")
        self.assertFalse(diagnose(project, [document(), second])["can_build"])
        # Different text with the same original study still does not add independent evidence.
        second = replace(second, text=TEXT + " Otra publicación.", content_hash="different")
        self.assertFalse(diagnose(project, [document(), second])["can_build"])

    def test_qualitative_corroboration_needs_distinct_origins_and_content(self):
        project = ready_project()
        project.findings = [finding(kind="commentary", method_quote="", origin_quote=""),
                            finding(id="f2", document_id="doc2", kind="commentary", method_quote="", origin_quote="")]
        second = replace(document(), id="doc2", url="https://other.org/research", content_hash="different", text=TEXT + " Una observación distinta.")
        self.assertTrue(diagnose(project, [document(), second])["can_build"])

    def test_excluded_or_reserved_sources_cannot_back_the_audience(self):
        project = ready_project()
        project.excluded_ids = ["doc"]
        self.assertFalse(diagnose(project, [document()])["can_build"])
        project.excluded_ids = []
        project.brief.holdout_urls = [document().url]
        self.assertFalse(diagnose(project, [document()])["can_build"])

    def test_limited_scope_requires_another_diagnosis(self):
        project = ready_project()
        project.audit.update(gaps=[{"reason": "Faltan participantes de otra región", "critical": True}],
                             suggested_scope="Solo músicos principiantes")
        diagnosis = diagnose(project, [document()])
        self.assertEqual("limited", diagnosis["status"])
        self.assertFalse(diagnosis["can_build"])


class ResearchServiceTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = EvidenceRepository("owner", Path(self.temp.name))
        self.repo = ResearchRepository(self.store)
        self.repo.save_document(document())

    def test_snapshot_survives_restart_and_is_immutable(self):
        project = ready_project()
        self.repo.save(project)
        sid = self.repo.snapshot(project)
        project.brief.question = "Otra pregunta"
        self.repo.save(project)
        reopened = ResearchRepository(EvidenceRepository("owner", Path(self.temp.name)))
        self.assertNotEqual(reopened.get(project.id).brief.question, reopened.get_snapshot(sid)["project"]["brief"]["question"])
        other = ResearchRepository(EvidenceRepository("other", Path(self.temp.name)))
        self.assertIsNone(other.get(project.id))
        self.assertIsNone(other.get_snapshot(sid))

    def test_changed_brief_starts_new_project_and_keeps_old_diagnosis(self):
        project = ready_project()
        self.repo.save(project)
        service = PublicResearchService(self.repo, engine=ScriptedModel())
        new = service.new_project(replace(project.brief, question="Nueva pregunta"), project.id)
        self.assertFalse(new.diagnosis)
        self.assertTrue(self.repo.get(project.id).diagnosis["can_build"])
        self.assertEqual(project.id, new.parent_id)

    def test_read_and_search_failures_keep_progress_and_respect_limits(self):
        search = mock.Mock()
        search.search.side_effect = ValueError("blocked")
        service = PublicResearchService(self.repo, engine=ScriptedModel(), search=search, max_rounds=2, max_queries=2)
        project = ready_project()
        service.search_round(project)
        service.search_round(project)
        service.search_round(project)
        self.assertEqual(2, search.search.call_count)
        self.assertEqual(2, len(self.repo.get(project.id).queries))
        self.assertTrue(any(e["type"] == "limit" for e in project.events))

    def test_cached_documents_and_reruns_do_not_repeat_network(self):
        search = mock.Mock()
        service = PublicResearchService(self.repo, engine=ScriptedModel(), search=search)
        project = ready_project()
        service._read_url(project, document().url)
        search.read.assert_not_called()

    def test_reserved_benchmark_never_enters_search_documents(self):
        search = mock.Mock()
        project = ready_project(holdout_urls=["https://holdout.org/survey"])
        service = PublicResearchService(self.repo, engine=ScriptedModel(), search=search)
        service.add_urls(project, project.brief.holdout_urls)
        search.read.assert_not_called()

    def test_analysis_checkpoints_and_retry_does_not_repeat_completed_document(self):
        project = ready_project()
        project.findings = []
        project.audit = {}
        model = ScriptedModel({"findings": [finding()]}, LLMError("offline"),
                              {"gaps": [], "contradictions": [], "limitations": [], "suggested_scope": ""})
        service = PublicResearchService(self.repo, engine=model)
        with self.assertRaises(LLMError):
            service.analyze(project)
        self.assertEqual(1, len(self.repo.get(project.id).findings))
        service.analyze(project)
        self.assertEqual(3, len(model.calls))
        self.assertEqual(1, len(project.findings))
        service.analyze(project)
        self.assertEqual(3, len(model.calls))

    def test_document_analysis_does_not_see_the_participant_situation(self):
        project = ready_project(situation="Los salarios perdieron 40% de poder de compra.", stimulus="Guion del anuncio")
        project.findings, project.audit = [], {}
        self.repo.save_document(document())
        model = ScriptedModel({"findings": [finding()]}, {"gaps": [], "contradictions": [], "limitations": [], "suggested_scope": ""})
        PublicResearchService(self.repo, engine=model).analyze(project)
        sent = model.calls[0]["user_prompt"]
        self.assertNotIn("poder de compra", sent)
        self.assertNotIn("Guion del anuncio", sent)
        self.assertIn(project.brief.question, sent)

    def test_audit_is_global_and_consolidates_repeated_gaps_across_chunks(self):
        project = ready_project()
        project.findings = [finding(id=f"f{i}") for i in range(45)]
        project.events = [{"type": "analyzed", "document_id": "doc"}]
        project.audit = {}
        gap = {"reason": "Faltan mayores de 60", "critical": True}
        partial = {"gaps": [gap], "contradictions": [], "limitations": [], "suggested_scope": ""}
        model = ScriptedModel(partial, partial, {"gaps": [gap, dict(gap)], "contradictions": [],
                                                 "limitations": [], "suggested_scope": ""})
        PublicResearchService(self.repo, engine=model).analyze(project)
        self.assertEqual(3, len(model.calls))
        self.assertEqual([gap], project.audit["gaps"])

    def test_missing_product_price_stops_before_searching(self):
        project = ResearchProject(brief=replace(brief(), question="¿Comprarías este curso?"))
        dims = ready_project().dimensions
        model = ScriptedModel({"dimensions": dims, "required_inputs": []})
        search = mock.Mock()
        service = PublicResearchService(self.repo, engine=model, search=search)
        service.prepare(project)
        search.search.assert_not_called()
        self.assertIn("price", project.required_inputs)
        self.assertFalse(project.diagnosis["can_build"])

    def test_polls_of_the_question_itself_never_block_the_audience(self):
        project = ResearchProject(brief=brief())
        dims = ready_project().dimensions + [
            {"id": "opinion_publica", "label": "Opinión pública", "reason": "Cómo evalúan la gestión",
             "critical": True, "max_age_days": 30, "queries": ["Encuestas de opinión pública Argentina"]}]
        service = PublicResearchService(self.repo, engine=ScriptedModel({"dimensions": dims, "required_inputs": []}))
        service.plan(project)
        critical = {d["id"]: d["critical"] for d in project.dimensions}
        self.assertEqual({"needs": True, "knowledge": False, "opinion_publica": False}, critical)

    def test_missing_poll_of_the_question_is_not_a_central_gap(self):
        project = ready_project()
        project.audit = {}
        self.repo.save_document(document())
        audit = {"gaps": [{"reason": "Faltan encuestas de opinión pública sobre la gestión", "critical": True}],
                 "contradictions": [], "limitations": [], "suggested_scope": ""}
        project.events = [{"type": "analyzed", "document_id": "doc"}]
        PublicResearchService(self.repo, engine=ScriptedModel(audit)).analyze(project)
        self.assertFalse(project.audit["gaps"][0]["critical"])
        self.assertTrue(project.diagnosis["can_build"])

    def test_local_library_is_reevaluated_before_search_and_sufficient_cache_skips_it(self):
        project = ready_project()
        project.document_ids, project.findings, project.audit = [], [], {}
        model = ScriptedModel({"findings": [finding()]}, {"gaps": [], "contradictions": [],
                              "limitations": [], "suggested_scope": ""})
        search = mock.Mock()
        service = PublicResearchService(self.repo, engine=model, search=search)
        service.prepare(project)
        search.search.assert_not_called()
        search.read.assert_not_called()
        self.assertTrue(project.diagnosis["can_build"])
        self.assertEqual(2, len(model.calls))

    def test_build_is_gated_and_never_uses_generic_fallback(self):
        project = ready_project()
        project.findings = []
        model = ScriptedModel(design())
        service = PublicResearchService(self.repo, engine=model)
        with self.assertRaises(ValueError):
            service.build_audience(project, "Test", 50)
        self.assertEqual([], model.calls)
        project.findings = [finding()]
        model.responses = ["not json"]
        with self.assertRaises(LLMError):
            service.build_audience(project, "Test", 50)
        self.assertFalse(project.universe_id)

    def test_grounded_generation_scrubs_unsupported_attributes_and_preserves_sources(self):
        value = design()
        value["segmentos"][0]["arquetipos"][0]["atributos"]["rol"] = "Director con veinte años de experiencia"
        service = PublicResearchService(self.repo, engine=ScriptedModel(value))
        universe, personas, sid = service.build_audience(ready_project(), "Test", 50)
        self.assertEqual(50, len(personas))
        self.assertTrue(all(p.rol == "No especificado" for p in personas))
        self.assertEqual("balanced_simulation", self.repo.get_snapshot(sid)["composition"])
        self.assertEqual(sid, Universo.from_dict(universe.to_dict()).research_snapshot_id)

    def test_missing_grounding_is_requested_in_a_second_short_call(self):
        project = ready_project()
        self.repo.save_document(document())
        payload = design()
        links = {"grounding": payload.pop("grounding")}
        model = ScriptedModel(payload, links)
        universe, personas, _ = PublicResearchService(self.repo, engine=model).build_audience(project, "Grupo", 5)
        self.assertEqual(2, len(model.calls))
        self.assertEqual("Aprender a reducir ruido", universe.perfiles[0].arquetipos[0].atributos["objetivo"])

    def test_quoted_attributes_with_short_ids_are_grounded(self):
        project = ready_project()
        self.repo.save_document(document())
        payload = {"segmentos": [{"nombre": "Principiantes", "porcentaje": 100, "arquetipos": [{
            "nombre": "Aprendiz", "peso": 1, "atributos": {
                "objetivo": {"valor": "reducir ruido al grabar", "refs": ["h1"]},
                "sensibilidad_precio": {"valor": "precio bajo", "refs": []}}}]}]}
        model = ScriptedModel(payload)
        universe, _, snapshot_id = PublicResearchService(self.repo, engine=model).build_audience(project, "Grupo", 5)
        self.assertEqual(1, len(model.calls))
        self.assertIn('"id": "h1"', model.calls[0]["user_prompt"])
        attrs = universe.perfiles[0].arquetipos[0].atributos
        self.assertEqual("reducir ruido al grabar", attrs["objetivo"])
        self.assertEqual("No especificado", attrs["sensibilidad_precio"])
        self.assertEqual("No especificado", attrs["rol"])
        provenance = self.repo.get_snapshot(snapshot_id)["profile_provenance"]
        self.assertEqual(["f"], next(iter(provenance.values()))["finding_ids"])

    def test_frozen_question_and_stimulus_are_enforced_and_refs_are_recorded(self):
        project = ready_project()
        service = PublicResearchService(self.repo, engine=ScriptedModel(design()))
        universe, personas, sid = service.build_audience(project, "Test", 1)
        study = Estudio("s", universe.id, universe.nombre, "T", project.brief.question,
                        project.brief.participant_stimulus, local_only=True, research_snapshot_id=sid)
        answer = {"response_text": "Necesito reducir ruido.", "sentiment": "neutral", "intent": "explorar",
                  "main_driver": "", "main_objection": "", "confidence": "low", "price_sensitivity": "none", "quote": "Necesito reducir ruido."}
        model = ScriptedModel(answer)
        rows = run_simulation(study, [p.to_dict() for p in personas], model, store=self.store)
        self.assertEqual(["web:f"], rows[0].evidence_refs)
        self.assertIn("assigned_synthetic_scenario", model.calls[0]["system_prompt"])
        self.assertEqual([], self.store.history(rows[0].identity_id))
        altered = personas[0].to_dict()
        altered["rol"] = "Experiencia inventada"
        with self.assertRaisesRegex(ValueError, "persona cambió"):
            run_simulation(replace(study, id="altered"), [altered], ScriptedModel(), store=self.store)
        self.assertEqual([], self.store.run_responses("altered"))
        study.pregunta = "Cambio de pregunta"
        with self.assertRaises(ValueError):
            validate_research_run(study, self.store)
        study.pregunta = project.brief.question
        study.contexto = "Cambio de estímulo"
        with self.assertRaises(ValueError):
            validate_research_run(study, self.store)

    def test_reuse_preserves_identity_but_rejects_different_public_or_removed_evidence(self):
        project = ready_project()
        service = PublicResearchService(self.repo, engine=ScriptedModel(design()))
        universe, personas, sid = service.build_audience(project, "Test", 2)
        new_id = service.reuse_audience(project, universe)
        self.assertEqual(self.repo.get_snapshot(sid)["profile_provenance"], self.repo.get_snapshot(new_id)["profile_provenance"])
        project.brief.audience = "Productores profesionales"
        with self.assertRaises(ValueError):
            service.reuse_audience(project, universe)

    def test_reuse_rejects_edited_profiles_and_changed_composition(self):
        project = ready_project()
        service = PublicResearchService(self.repo, engine=ScriptedModel(design()))
        universe, _, _ = service.build_audience(project, "Test", 2)
        universe.perfiles[0].arquetipos[0].atributos["rol"] = "Director inventado"
        with self.assertRaisesRegex(ValueError, "perfiles cambiaron"):
            service.reuse_audience(project, universe)
        with mock.patch.object(service, "refresh_diagnosis", return_value={"can_build": True}):
            project.diagnosis["composition"] = "documented"
            with self.assertRaisesRegex(ValueError, "objetivo de composición"):
                service.reuse_audience(project, universe)

    def test_population_weights_are_grounded_and_frozen(self):
        project = ready_project(goal="proportions")
        quote = "Principiantes: 100% de la población de músicos evaluada en esta encuesta."
        doc = document()
        doc.text += "\n" + quote + "\n" + WEIGHTS
        doc.id, doc.content_hash = "population", fingerprint(doc.text)
        self.repo.save_document(doc)
        project.document_ids.append(doc.id)
        project.dimensions.append({"id": "proportions", "label": "Composición", "critical": True,
                                   "reason": "Pesos", "max_age_days": 365, "queries": []})
        project.findings.append(finding(id="weights", dimension_id="proportions", document_id=doc.id,
                                       claim=quote, quote=quote, kind="survey", weight_quote=WEIGHTS))
        value = design()
        value["grounding"][0]["percentage_refs"] = ["weights"]
        service = PublicResearchService(self.repo, engine=ScriptedModel(value))
        universe, _, sid = service.build_audience(project, "Test", 2)
        self.assertEqual(100, universe.perfiles[0].porcentaje)
        self.assertEqual(1, universe.perfiles[0].arquetipos[0].peso)
        self.assertEqual({"Principiantes": ["weights"]}, self.repo.get_snapshot(sid)["percentage_provenance"])
        value["segmentos"][0]["porcentaje"] = 80
        service.engine = ScriptedModel(value)
        with self.assertRaisesRegex(LLMError, "porcentajes"):
            service.build_audience(project, "Test", 2)

    def test_ai_report_uses_local_policy_for_evidence_study(self):
        import pandas as pd
        from app.pages.resultados import _run_ai_analysis
        study = Estudio("s", "u", "U", "Test", "Pregunta", "", research_snapshot_id="frozen", local_only=True)
        with mock.patch("app.pages.resultados.LLMService") as factory:
            factory.return_value.is_ready.return_value = False
            self.assertIn("Ollama", _run_ai_analysis(study, pd.DataFrame()))
            factory.assert_called_once_with(local_only=True)

    def test_benchmark_from_evidence_is_not_independent(self):
        project = ready_project()
        sid = self.repo.snapshot(project)
        benchmark = mock.Mock(fuente="Publicado en " + document().url)
        self.assertTrue(benchmark_overlaps_research(self.repo.get_snapshot(sid), benchmark))
        benchmark.fuente = "https://holdout.org/independent"
        self.assertFalse(benchmark_overlaps_research(self.repo.get_snapshot(sid), benchmark))

    def test_legacy_json_defaults(self):
        self.assertEqual("", Universo.from_dict({"id": "old"}).research_snapshot_id)
        study = Estudio.from_dict({"id": "old", "universo_id": "u"})
        self.assertFalse(study.local_only)
        self.assertEqual("", study.research_snapshot_id)


class SearchAndLocalTests(TestCase):
    def test_url_normalization_and_private_address_rejection(self):
        self.assertEqual("https://example.org/page?a=1", normalize_url("https://EXAMPLE.org/page?utm_source=x&a=1#part"))
        for url in ("file:///c:/secret", "https://user:password@example.org", "http://example.org:11434"):
            with self.assertRaises(ValueError):
                normalize_url(url)
        with mock.patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 0))]):
            with self.assertRaises(ValueError):
                validate_public_url("http://localhost/")

    def test_search_uses_bing_after_duckduckgo_failure(self):
        with mock.patch("ddgs.DDGS") as ddgs:
            ddgs.return_value.text.side_effect = [ValueError("blocked"), [{"href": "https://example.org"}]]
            self.assertEqual(1, len(PublicSearch().search("query")))
            self.assertEqual(["duckduckgo", "bing"], [c.kwargs["backend"] for c in ddgs.return_value.text.call_args_list])

    def test_html_reader_extracts_article_and_pdf_without_text_is_unusable(self):
        search = PublicSearch()
        html = ("<html><head><title>Estudio</title></head><body><article><h1>Estudio</h1><p>" + TEXT + "</p></article></body></html>").encode()
        with mock.patch.object(search, "_download", return_value=("https://example.org", "text/html", html)):
            result = search.read("https://example.org")
            self.assertEqual("read", result.status)
            self.assertIn(QUOTE, result.text)
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        pdf = BytesIO()
        writer.write(pdf)
        with mock.patch.object(search, "_download", return_value=("https://example.org", "application/pdf", pdf.getvalue())):
            self.assertEqual("unusable", search.read("https://example.org").status)

    def test_local_only_ignores_global_provider_and_never_falls_back(self):
        with mock.patch.dict("os.environ", {"LLM_PROVIDER": "openrouter", "LLM_LOCAL_BASE_URL": "http://localhost:11434/v1",
                                           "LLM_LOCAL_MODEL": "test", "LLM_LOCAL_API_KEY": "x"}), \
             mock.patch.object(LLMService, "_generate_with_provider", side_effect=LLMError("offline")) as generate:
            service = LLMService(local_only=True)
            with self.assertRaises(LLMError):
                service.generate("system", "user")
            self.assertEqual(1, generate.call_count)
            self.assertEqual("local", generate.call_args.args[0])

    def test_local_only_retries_once_after_ollama_server_error(self):
        from app.services.llm_service import LLMLocalServerError
        env = {"LLM_PROVIDER": "local", "LLM_LOCAL_BASE_URL": "http://localhost:11434/v1",
               "LLM_LOCAL_MODEL": "test", "LLM_LOCAL_API_KEY": "x"}
        with mock.patch.dict("os.environ", env), mock.patch("app.services.llm_service.time.sleep") as sleep, \
             mock.patch.object(LLMService, "_generate_with_provider",
                               side_effect=[LLMLocalServerError("500"), "ok"]) as generate:
            self.assertEqual("ok", LLMService(local_only=True).generate("system", "user"))
            self.assertEqual(["local", "local"], [c.args[0] for c in generate.call_args_list])
            sleep.assert_called_once()
        with mock.patch.dict("os.environ", env), mock.patch("app.services.llm_service.time.sleep"), \
             mock.patch.object(LLMService, "_generate_with_provider",
                               side_effect=[LLMLocalServerError("500"), LLMLocalServerError("500"), "x"]) as generate:
            with self.assertRaises(LLMError):
                LLMService(local_only=True).generate("system", "user")
            self.assertEqual(2, generate.call_count)


class StreamlitJourneyTests(TestCase):
    setUp = ResearchServiceTests.setUp
    # Only UI cases belong to this subclass; use the same isolated storage fixture.
    def test_question_first_form_rerun_invalidates_gate_and_reopens_draft(self):
        from streamlit.testing.v1 import AppTest
        project = ready_project()
        self.repo.save(project)
        service = PublicResearchService(self.repo, engine=ScriptedModel())
        code = '''import streamlit as st
from app.components.public_research import render_public_research
st.session_state.setdefault("private_storage_available", True)
render_public_research()
'''
        with mock.patch("app.components.public_research.session_store", return_value=self.store), \
             mock.patch("app.components.public_research.PublicResearchService", return_value=service), \
             mock.patch("app.components.public_research.list_universes", return_value=[]):
            app = AppTest.from_string(code, default_timeout=20).run()
            self.assertFalse(app.exception)
            app.selectbox(key="research_picker").select(project.id).run()
            self.assertFalse(app.exception)
            self.assertEqual(project.brief.question, app.text_area(key="research_question").value)
            self.assertTrue(any(b.label == "Crear audiencia y preparar estudio" for b in app.button))
            app.text_area(key="research_question").set_value("Pregunta modificada").run()
            self.assertFalse(app.exception)
            self.assertFalse(any(b.label == "Crear audiencia y preparar estudio" for b in app.button))
            app.selectbox(key="research_picker").select("").run()
            app.selectbox(key="research_picker").select(project.id).run()
            self.assertEqual(project.brief.question, app.text_area(key="research_question").value)

    def test_create_and_handoff_keeps_question_defaults_and_ollama_policy(self):
        from streamlit.testing.v1 import AppTest
        from app.services.universe_service import build_expansion_snapshot
        project = ready_project()
        self.repo.save(project)
        service = PublicResearchService(self.repo, engine=ScriptedModel(design()))
        code = '''import streamlit as st
from app.pages.estudios import render_estudios_page
from app.pages.resultados import render_resultados_page
st.session_state.setdefault("private_storage_available", True)
st.session_state.setdefault("public_research_mode", True)
if st.session_state.get("current_page") == "Resultados":
    render_resultados_page()
else:
    render_estudios_page()
'''
        saved = []
        studies, responses = [], []
        answer = {"response_text": "Necesito reducir ruido.", "sentiment": "neutral", "intent": "explorar",
                  "main_driver": "", "main_objection": "", "confidence": "low", "price_sensitivity": "none", "quote": "Necesito reducir ruido."}
        response_engine = ScriptedModel(answer, answer)
        response_engine.is_ready = lambda: True
        with mock.patch("app.components.public_research.session_store", return_value=self.store), \
             mock.patch("app.pages.estudios.session_store", return_value=self.store), \
             mock.patch("app.components.evidence.session_store", return_value=self.store), \
             mock.patch("app.components.public_research.PublicResearchService", return_value=service), \
             mock.patch("app.components.public_research.list_universes", side_effect=lambda: saved), \
             mock.patch("app.pages.estudios.list_universes", side_effect=lambda: saved), \
             mock.patch("app.components.public_research.save_universe", side_effect=saved.append), \
             mock.patch("app.components.public_research.save_expansion"), \
             mock.patch("app.pages.estudios.find_latest_expansion", return_value=None), \
             mock.patch("app.pages.estudios.save_expansion"), \
             mock.patch("app.pages.estudios.save_study", side_effect=studies.append), \
             mock.patch("app.pages.estudios.save_study_results", side_effect=lambda sid, rows: responses.__setitem__(slice(None), rows)), \
             mock.patch("app.pages.estudios.LLMService", return_value=response_engine) as engine_factory, \
             mock.patch("app.pages.resultados.list_studies", side_effect=lambda: studies), \
             mock.patch("app.pages.resultados.load_study_results", side_effect=lambda sid: responses), \
             mock.patch("app.pages.validacion.render_validacion_tab"), \
             mock.patch("app.pages.preguntas.render_preguntas_tab"), \
             mock.patch("app.pages.reportes.render_reportes_tab"), \
             mock.patch("app.pages.biblioteca.render_biblioteca_tab"):
            app = AppTest.from_string(code, default_timeout=20).run()
            app.selectbox(key="research_picker").select(project.id).run()
            next(b for b in app.button if b.label == "Crear audiencia y preparar estudio").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(1, len(saved))
            self.assertEqual(project.brief.question, app.text_area(key="est_pregunta").value)
            self.assertEqual("survey", app.selectbox(key="est_mode").value)
            self.assertEqual(1, app.number_input(key="est_rpp").value)
            self.assertEqual(50, app.number_input(key="est_limite_" + saved[0].id).value)
            app.number_input(key="est_limite_" + saved[0].id).set_value(2).run()
            app.button(key="est_run").click().run()
            self.assertFalse(app.exception)
            self.assertEqual("Resultados", app.session_state["current_page"])
            self.assertEqual(2, len(responses))
            self.assertTrue(studies[0].local_only)
            self.assertTrue(studies[0].research_snapshot_id)
            self.assertEqual(["web:f"], responses[0].evidence_refs)
            self.assertEqual(2, len(self.store.run_responses(studies[0].id)))
            engine_factory.assert_called_with(local_only=True)
            self.assertTrue(any(e.label == "Fundamento de la audiencia" for e in app.expander))
            self.assertTrue(any(e.value == "Suficiente para explorar" for e in app.subheader))

    def test_remote_session_does_not_open_private_store(self):
        from streamlit.testing.v1 import AppTest
        code = '''from app.components.public_research import render_public_research
render_public_research()
'''
        with mock.patch("app.components.public_research.session_store", return_value=None), \
             mock.patch("app.components.public_research.ResearchRepository") as repository:
            app = AppTest.from_string(code).run()
            self.assertFalse(app.exception)
            repository.assert_not_called()
            self.assertTrue(app.info)
