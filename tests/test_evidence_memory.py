import csv
import json
import tempfile
from pathlib import Path
from unittest import TestCase

import pandas as pd

from app.domain.models import Estudio, PersonaSintetica, Universo
from app.services.analysis_service import build_executive_report, primary_responses, social_comparison
from app.services.evidence_service import build_source_population, evidence_for_persona, import_reviews_seed, import_support_csv
from app.services.llm_service import LLMError
from app.services.simulation_service import run_simulation, social_graph
from app.storage.evidence_repository import EvidenceRepository, identity_for


STAMP = 1700000000000


def write_csv(path, rows):
    fields = ["_id", "chat_row_id", "from_me", "key_id", "sender_jid_row_id", "timestamp", "message_type", "text_data"]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for index, row in enumerate(rows, 1):
            writer.writerow({"_id": str(index), "chat_row_id": "10", "from_me": "0", "key_id": f"key-{index}",
                             "sender_jid_row_id": "45", "timestamp": str(STAMP + index * 1000), "message_type": "0", **row})


class Model:
    def __init__(self, fail_first=False):
        self.calls = []
        self.fail_first = fail_first

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail_first and len(self.calls) == 1:
            raise LLMError("secret-request-body")
        text = f"Opinión simulada de {kwargs['agent_id']}, respuesta {len(self.calls)}."
        return {"response_text": text, "sentiment": "neutral", "intent": "no_aplica", "main_driver": "",
                "main_objection": "", "confidence": "low", "price_sensitivity": "none", "quote": text}

    def get_request_metadata(self):
        return {"provider": "fake", "model": "test"}


class EvidenceTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = EvidenceRepository("owner", self.root / "private")
        self.path = self.root / "support.csv"
        write_csv(self.path, [
            {"chat_row_id": "-1", "text_data": "", "timestamp": "null"},
            {"text_data": "Soy Mario Particular. MIDI falla. Email mario@example.com, teléfono +54 11 5555 6666"},
            {"from_me": "1", "text_data": "Instalá drivers de Ableton"},
            {"text_data": "No se solucionó todavía"},
            {"timestamp": str(STAMP + 20 * 86400000), "text_data": "Ahora funciona"},
            {"chat_row_id": "20", "text_data": "Tengo ruido de audio y una fuente"},
            {"chat_row_id": "20", "timestamp": "null", "text_data": "Consulta de cable sin fecha"},
            {"chat_row_id": "30", "text_data": "null", "message_type": "3"},
        ])
        self.imported = import_support_csv(self.store, self.path, "support-db")

    def test_import_is_idempotent_and_messages_are_not_clients(self):
        self.assertEqual((8, 1, 7, 3, 5), tuple(self.imported[k] for k in ("records", "system_records", "new_messages", "chats", "cases")))
        repeated = import_support_csv(self.store, self.path, "support-db")
        self.assertTrue(repeated["already_imported"])
        self.assertEqual(1, len(self.store.list_sources()))
        with self.store.connect() as db:
            self.assertEqual(7, db.execute("SELECT count(*) FROM messages").fetchone()[0])
        self.assertEqual(2, len(self.store.eligible_chats(self.imported["source_id"])))

    def test_directions_resolution_and_unknown_dates_are_preserved(self):
        cases = self.store.list_cases(self.imported["source_id"])
        dated = [c for c in cases if c["observation"]["support_themes"]]
        self.assertEqual(1, len(dated))
        self.assertIn("Software, instalación y drivers", dated[0]["observation"]["support_themes"])
        self.assertNotIn("Software, instalación y drivers", dated[0]["observation"]["incoming_themes"])
        self.assertTrue(any(c["started_ms"] is None for c in cases))
        self.assertTrue(any(c["observation"]["possible_resolution_message_refs"] for c in cases))
        self.assertTrue(all(c["observation"]["resolution"] == "unknown" for c in cases))

    def test_automatic_provider_context_contains_no_original_body(self):
        universe = Universo("u", "Support", "Scenario", 2, evidence_source_ids=[self.imported["source_id"]])
        personas = build_source_population(self.store, universe, self.imported["source_id"])
        evidence = [evidence_for_persona(self.store, p.to_dict()) for p in personas]
        text = json.dumps(evidence)
        for private in ("Mario", "mario@example.com", "5555", "Instalá", "No se solucionó"):
            self.assertNotIn(private, text)
        self.assertTrue(all(p.edad_rango == "No especificado" and p.sensibilidad_precio == "No especificado" for p in personas))
        self.assertEqual(2, len({p.persona_id for p in personas}))
        again = build_source_population(self.store, universe, self.imported["source_id"])
        self.assertEqual([p.identity_id for p in personas], [p.identity_id for p in again])
        with self.assertRaises(ValueError):
            build_source_population(self.store, Universo("too-big", "T", "C", 3), self.imported["source_id"])

    def test_review_is_explicit_and_raw_text_never_becomes_context(self):
        case = next(c for c in self.store.list_cases(self.imported["source_id"]) if c["observation"]["support_themes"])
        for summary, checked in (("Resumen", False), ("Email mario@example.com", True)):
            with self.assertRaises(ValueError):
                self.store.review_case(case["id"], summary, "unknown", reviewed_privacy=checked)
        self.store.review_case(case["id"], "Cliente consulta MIDI; soporte propone drivers. No hay confirmación de solución.", "unknown", reviewed_privacy=True)
        context = evidence_for_persona(self.store, {"evidence_refs": [case["id"]]})
        self.assertIn("reviewed_summary", context[0])
        self.assertEqual("unknown", context[0]["resolution"])
        self.assertNotIn("Mario", json.dumps(context))

    def test_incremental_import_preserves_old_episode_bindings(self):
        old_cases = self.store.list_cases(self.imported["source_id"])
        with self.path.open(encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))
        rows.append({"_id": "new", "chat_row_id": "10", "key_id": "new-key", "from_me": "0", "text_data": "Cable MIDI", "timestamp": str(STAMP + 21 * 86400000)})
        updated = self.root / "updated.csv"
        write_csv(updated, rows)
        result = import_support_csv(self.store, updated, "support-db")
        self.assertEqual((1, 7), (result["new_messages"], result["duplicate_messages"]))
        for case in old_cases:
            self.assertEqual(case["observation"], self.store.case(case["id"])["observation"])

    def test_bad_file_rolls_back_and_other_owner_and_account_are_isolated(self):
        bad = self.root / "bad.csv"
        write_csv(bad, [{"text_data": "USB"}, {"chat_row_id": "not-an-id", "text_data": "MIDI"}])
        with self.assertRaises(ValueError):
            import_support_csv(self.store, bad, "support-db")
        self.assertEqual(1, len(self.store.list_sources()))
        second = import_support_csv(self.store, self.path, "other-db")
        self.assertEqual(7, second["new_messages"])
        other = EvidenceRepository("../owner-other", self.root / "private")
        self.assertEqual([], other.list_sources())
        self.assertNotEqual(self.store.path, other.path)

    def test_reviews_are_general_context_with_separate_business_report(self):
        path = self.root / "reviews.json"
        path.write_text(json.dumps({"schema_version": "predikpedia.evidence_seed/v1", "source_type": "google_business_reviews",
                                   "business": "PC MIDI", "reviews": [{"id": "r1", "customer_report_summary": "Cuestiona los repuestos",
                                   "business_response_summary": "El negocio dice esperar respuesta", "themes": ["repuestos"]}]}), encoding="utf-8")
        source = import_reviews_seed(self.store, path, privacy_reviewed=True)
        evidence = evidence_for_persona(self.store, {"evidence_source_ids": [source["source_id"]]})
        self.assertEqual("general_context_not_personal_history", evidence[0]["scope"])
        self.assertNotEqual(evidence[0]["public_customer_report"], evidence[0]["business_response"])


class MemoryAndInteractionTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = EvidenceRepository("a", self.temp.name)
        self.personas = [{"persona_id": f"P_{i}", "perfil": "A", "notas": "Sin presupuesto declarado"} for i in range(3)]

    def study(self, identity, mode="survey", **kwargs):
        return Estudio(identity, "u", "U", "T", "¿Qué información necesitás?", "C", mode=mode, **kwargs)

    def test_independent_repetitions_do_not_read_or_write_interview_memory(self):
        model = Model()
        study = self.study("independent", respuestas_por_persona=2)
        rows = run_simulation(study, self.personas[:1], model, store=self.store)
        self.assertNotIn(rows[0].respuesta, model.calls[1]["system_prompt"])
        self.assertEqual([], rows[1].memory_refs)
        self.assertEqual([], self.store.history(rows[0].identity_id))
        self.assertEqual(2, len(self.store.run_responses(study.id)))

    def test_followups_remember_and_history_survives_reopening_without_cross_panel_leak(self):
        model = Model()
        study = self.study("interview-1", "interview", memory_enabled=True, follow_up_questions=["¿Por qué?"])
        rows = run_simulation(study, self.personas[:1], model, store=self.store)
        self.assertIn(rows[0].respuesta, model.calls[1]["system_prompt"])
        self.assertEqual([rows[0].response_id], rows[1].memory_refs)
        reopened = EvidenceRepository("a", self.temp.name)
        next_model = Model()
        next_rows = run_simulation(self.study("interview-2", "interview", memory_enabled=True), self.personas[:1], next_model, store=reopened)
        self.assertIn(rows[1].respuesta, next_model.calls[0]["system_prompt"])
        self.assertTrue(next_rows[0].memory_refs)
        self.assertEqual("synthetic_output_not_source_fact", reopened.history(rows[0].identity_id)[0]["origin"])
        other = EvidenceRepository("b", self.temp.name)
        self.assertEqual([], other.history(rows[0].identity_id))
        self.assertNotEqual(rows[0].identity_id, identity_for("another-panel", self.personas[0]))
        self.assertNotEqual(rows[0].identity_id, identity_for("u", {**self.personas[0], "notas": "Perfil nuevo"}))

    def test_social_rounds_only_expose_initial_peers_and_keep_baseline(self):
        model = Model()
        study = self.study("social", "social", memory_enabled=True)
        rows = run_simulation(study, self.personas, model, store=self.store)
        self.assertEqual(["individual"] * 3 + ["after_interaction"] * 3, [r.phase for r in rows])
        self.assertEqual(study.interaction_graph, social_graph(list(reversed([p["persona_id"] for p in self.personas]))))
        first_ids = {r.response_id for r in rows[:3]}
        for row in rows[3:]:
            self.assertTrue(set(row.exposure_ids).issubset(first_ids))
            self.assertNotIn(next(r.response_id for r in rows[:3] if r.persona_id == row.persona_id), row.exposure_ids)
        self.assertEqual(3, len(social_comparison(pd.DataFrame([r.to_dict() for r in rows]))))

    def test_error_never_becomes_peer_opinion_or_memory(self):
        model = Model(fail_first=True)
        study = self.study("social-errors", "social", memory_enabled=True)
        rows = run_simulation(study, self.personas, model, store=self.store)
        self.assertTrue(rows[0].respuesta.startswith("[ERROR:"))
        self.assertTrue(rows[3].respuesta.startswith("[ERROR:"))
        self.assertEqual([], self.store.history(rows[0].identity_id))
        self.assertNotIn("secret-request-body", json.dumps([r.to_dict() for r in rows]))
        self.assertTrue(all(rows[0].response_id not in r.exposure_ids for r in rows[3:]))

    def test_stop_and_caller_failure_preserve_checkpoint(self):
        checks = iter([False, True])
        rows = run_simulation(self.study("stopped", "interview", memory_enabled=True, follow_up_questions=["Más"]),
                              self.personas[:1], Model(), store=self.store, should_stop=lambda: next(checks))
        self.assertEqual(1, len(rows))
        self.assertEqual(1, len(self.store.run_responses("stopped")))
        def failing_callback(*args):
            raise RuntimeError("UI disconnected")
        with self.assertRaises(RuntimeError):
            run_simulation(self.study("ui-disconnected"), self.personas[:1], Model(), store=self.store, on_response=failing_callback)
        self.assertEqual(1, len(self.store.run_responses("ui-disconnected")))

    def test_missing_sources_fail_before_calling_provider(self):
        model = Model()
        with self.assertRaises(ValueError):
            run_simulation(self.study("missing"), [{**self.personas[0], "evidence_refs": ["missing-ref"]}], model, store=self.store)
        self.assertEqual([], model.calls)

    def test_report_grain_does_not_combine_rounds_or_questions(self):
        model = Model()
        study = self.study("grains", "social")
        rows = run_simulation(study, self.personas, model)
        df = pd.DataFrame([r.to_dict() for r in rows])
        self.assertEqual(3, len(primary_responses(study, df)))
        report = build_executive_report(study, df)
        self.assertIn("3 respuesta(s)", report["conclusion"])
        after = build_executive_report(study, df.loc[df.phase == "after_interaction"], selection_explicit=True)
        self.assertIn("tras interacción", after["conclusion"])
        interview = self.study("q", "interview")
        only_follow_up = df.copy()
        only_follow_up["question_index"] = 2
        self.assertTrue(primary_responses(interview, only_follow_up).empty)

    def test_old_json_defaults_and_new_fields_roundtrip(self):
        study = Estudio.from_dict({"id": "legacy", "universo_id": "u"})
        self.assertEqual(("survey", False, []), (study.mode, study.memory_enabled, study.follow_up_questions))
        new = self.study("new", "social", social_seed=5, memory_enabled=True)
        self.assertEqual(new.to_dict(), Estudio.from_dict(new.to_dict()).to_dict())
