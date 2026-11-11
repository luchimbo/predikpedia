from contextvars import copy_context
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

from app.config import config
from app.domain.models import Estudio, RespuestaEstudio
from app.services.model_usage import model_usage, usage_rows
from app.services.study_queue import WORKER_LOCK, enqueue, process_next, recover_interrupted, study_jobs, worker_online
from app.services.study_recovery import prepare_survey, study_lock
from app.services.variant_comparison import compare_variants
from app.storage.repository import load_study_results, save_study_results, use_local_storage
from test_study_realism import response
from tools.control_suite import baseline_for, read_verified, sha


class ModelUsageTests(TestCase):
    def test_legacy_and_fallback(self):
        counts, fallback = model_usage([{}, {"provider": "local", "model": "qwen"},
                                        {"provider": "openrouter", "model": "g", "fallback_used": True}])
        self.assertEqual(fallback, 1)
        self.assertEqual(counts["Sin registro", "Sin registro"], 1)
        self.assertTrue(all(row["%"] == 33.3 for row in usage_rows(counts)))

    def test_ab_usage_ignores_unpaired_answers(self):
        a = Estudio("a", "u", "U", "A", "Q", "", opciones=["Sí", "No"], variant="A", paired_study_id="b")
        b = replace(a, id="b", variant="B", paired_study_id="a")
        paired = RespuestaEstudio("a", "one", "G", 1, "Q", "", "Texto", opcion_elegida="Sí",
                                   llm_metadata={"provider": "local", "model": "qwen"})
        unpaired = replace(paired, persona_id="two", llm_metadata={"provider": "openrouter", "model": "g"})
        result = compare_variants(a, b, [paired, unpaired], [replace(paired, estudio_id="b")])
        self.assertEqual(result["model_usage_a"], result["model_usage_b"])
        self.assertEqual(sum(result["model_usage_a"][0].values()), 1)


class WorkerTests(TestCase):
    def test_worker_recovers_checkpoint_and_coalesces_submissions(self):
        with TemporaryDirectory() as directory:
            copy_context().run(self._exercise, directory)

    def _exercise(self, directory):
        use_local_storage()
        config.set_session_dir(directory)
        study = Estudio("s", "u", "U", "Título", "Q", "", resumable=True, respuestas_planeadas=2)
        other = replace(study, id="second")
        people = [{"persona_id": "one"}, {"persona_id": "two"}]
        prepare_survey(study, people)
        prepare_survey(other, people)
        enqueue([study.id, other.id])
        enqueue([study.id])
        self.assertEqual(list(study_jobs()), [study.id, other.id])
        first = RespuestaEstudio(study.id, "one", "General", 1, "Q", "", "Ya guardada")
        save_study_results(study.id, [first])
        engine = mock.Mock()
        engine.generate.return_value = response()
        self.assertFalse(worker_online())
        with study_lock(WORKER_LOCK):
            self.assertTrue(worker_online())
            with mock.patch("app.services.study_queue.continue_survey", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    process_next(lambda _: engine, lambda _: None)
        self.assertEqual(study_jobs()[study.id].status, "running")
        with study_lock(WORKER_LOCK):
            recover_interrupted()
            self.assertTrue(process_next(lambda _: engine, lambda _: None))
        self.assertEqual(engine.generate.call_count, 1)
        self.assertEqual(engine.generate.call_args.kwargs["agent_id"], "two")
        self.assertEqual(study_jobs()[study.id].status, "done")
        self.assertEqual(study_jobs()[other.id].status, "queued")
        self.assertEqual(load_study_results(study.id)[0], first)


class ControlSuiteTests(TestCase):
    def test_changed_frozen_file_is_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("sample.json", "benchmark.json"):
                entry = {"path": name, "sha256": sha(b"{}")}
                path = root / name
                path.write_bytes(b"{}")
                self.assertEqual(read_verified(root, entry), "{}")
                path.write_bytes(b"[]")
                with self.assertRaisesRegex(ValueError, "Cambió"):
                    read_verified(root, entry)

    def test_only_same_manifest_complete_run_can_be_baseline(self):
        runs = [{"started_at": date, "manifest_sha256": manifest, "status": status}
                for date, manifest, status in [("1", "same", "partial"), ("2", "other", "complete"),
                                               ("3", "same", "complete"), ("4", "same", "complete")]]
        self.assertEqual(baseline_for(runs, "same"), runs[2])
        self.assertIsNone(baseline_for(runs[:2], "same"))
