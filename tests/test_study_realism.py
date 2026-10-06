from unittest import TestCase, mock

import pandas as pd

from app.domain.models import Estudio, Universo
from app.services.analysis_service import build_executive_report, insights_by_profile, representative_responses, valid_responses
from app.services.llm_service import LLMError
from app.services.study_response_service import build_system_prompt, parse_study_response


def response(**overrides):
    return {
        "response_text": "No sé si lo compraría: falta conocer el precio.",
        "sentiment": "neutral", "intent": "no_se", "main_objection": "Falta el precio",
        "main_driver": "", "confidence": "low", "quote": "falta conocer el precio.",
        **overrides,
    }


class StudyResponseTests(TestCase):
    def test_uncertainty_and_noncommercial_questions_are_preserved(self):
        for intent in ("no_se", "no_aplica", "indiferente", "comprar", "rechazar"):
            result = parse_study_response(response(intent=intent))
            self.assertEqual(intent, result["intent"])
            self.assertEqual("", result["main_driver"])
            self.assertEqual("none", result["price_sensitivity"])

    def test_invalid_output_never_becomes_an_opinion(self):
        missing = response()
        missing.pop("confidence")
        for item in ("texto", [], {"_raw": "promesa", "_error": "bad json"}, missing,
                     response(response_text=""), response(intent="comprar | rechazar"),
                     response(sentiment="fantástico"), response(confidence=None),
                     response(price_sensitivity=5)):
            with self.subTest(payload=item), self.assertRaises(LLMError):
                parse_study_response(item)

    def test_fabricated_quote_is_replaced_with_response_excerpt(self):
        result = parse_study_response(response(quote="Lo compro sin pensarlo"))
        self.assertEqual(result["response_text"], result["quote"])

    def test_profile_notes_and_operational_context_reach_prompt(self):
        prompt = build_system_prompt({"rol": "Usuario final", "notas": "No decide compras",
                                      "contexto_operativo": "Panadería en Rosario", "arquetipo": "Empleado"}, "Nuevo software")
        for value in ("Usuario final", "No decide compras", "Panadería en Rosario", "Empleado", "Nuevo software"):
            self.assertIn(value, prompt)

    def test_execution_uses_policy_and_saves_structured_uncertainty(self):
        from app.pages import estudios
        ui = mock.MagicMock()
        ui.session_state = {"est_stop_flag": False}
        ui.empty.return_value.button.return_value = False
        ui.button.return_value = False
        engine = mock.MagicMock()
        engine.is_ready.return_value = True
        engine.generate.return_value = response()
        with mock.patch.object(estudios, "st", ui), mock.patch.object(estudios, "LLMService", return_value=engine), \
             mock.patch.object(estudios, "save_study"), mock.patch.object(estudios, "save_study_results") as save, \
             mock.patch.object(estudios, "set"):
            estudios._execute_study(Universo("u", "U", "brief", 1),
                                     [{"persona_id": "P_1", "perfil": "A", "notas": "Sin presupuesto"}],
                                     "T", "¿Comprarías?", "Oferta", 1, None)
        ui.error.assert_not_called()
        saved = save.call_args.args[1][0]
        self.assertEqual("no_se", saved.intent)
        self.assertIn("Sin presupuesto", engine.generate.call_args.kwargs["system_prompt"])

    def test_execution_records_malformed_json_as_error(self):
        from app.pages import estudios
        ui = mock.MagicMock()
        ui.session_state = {"est_stop_flag": False}
        ui.empty.return_value.button.return_value = False
        ui.button.return_value = False
        engine = mock.MagicMock()
        engine.generate.return_value = {"_raw": "No es JSON", "_error": "bad json"}
        with mock.patch.object(estudios, "st", ui), mock.patch.object(estudios, "LLMService", return_value=engine), \
             mock.patch.object(estudios, "save_study"), mock.patch.object(estudios, "save_study_results") as save, \
             mock.patch.object(estudios, "set"):
            estudios._execute_study(Universo("u", "U", "brief", 1), [{"persona_id": "P_1"}], "T", "Q", "", 1, None)
        ui.error.assert_not_called()
        saved = save.call_args.args[1][0]
        self.assertTrue(saved.respuesta.startswith("[ERROR:"))
        self.assertEqual("", saved.intent)


class AnalysisValidityTests(TestCase):
    def setUp(self):
        self.df = pd.DataFrame([
            {"persona_id": "1", "perfil": "A", "respuesta": "No sé si compraría", "intent": "no_se"},
            {"persona_id": "2", "perfil": "B", "respuesta": "[ERROR: proveedor caído]", "intent": ""},
            {"persona_id": "3", "perfil": "B", "respuesta": None, "intent": ""},
        ])

    def test_analysis_excludes_errors_without_removing_uncertainty(self):
        self.assertEqual(["no_se"], valid_responses(self.df)["intent"].tolist())
        self.assertEqual(1, insights_by_profile(self.df).iloc[0]["Respuestas"])
        self.assertEqual(["A"], representative_responses(self.df)["Perfil"].tolist())
        report = build_executive_report(Estudio("e", "u", "U", "T", "Q", ""), self.df)
        self.assertIn("1 respuesta(s)", report["conclusion"])
        self.assertNotIn("proveedor", report["markdown"])
        self.assertEqual(3, len(self.df))  # Mantiene los datos originales para exportar.

    def test_all_errors_return_empty_report(self):
        report = build_executive_report(Estudio("e", "u", "U", "T", "Q", ""), self.df.iloc[1:])
        self.assertEqual([], report["insights"])
