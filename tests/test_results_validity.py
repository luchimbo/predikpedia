from unittest import TestCase

import pandas as pd

from app.domain.models import Estudio, RespuestaEstudio
from app.services.analysis_service import error_mask, valid_responses


def respuesta(persona_id, texto, error=""):
    return RespuestaEstudio(
        estudio_id="s1", persona_id=persona_id, perfil="Dueños", repeticion=1,
        pregunta="¿?", contexto="", respuesta=texto, error=error,
    ).to_dict()


class ValidResponsesTests(TestCase):
    def test_excludes_new_and_legacy_errors(self):
        df = pd.DataFrame([
            respuesta("P1", "Me interesa si baja el precio"),
            respuesta("P2", "", error="openrouter no respondió"),
            respuesta("P3", "[ERROR: timeout]"),
        ])
        self.assertEqual([False, True, True], error_mask(df).tolist())
        self.assertEqual(["P1"], valid_responses(df)["persona_id"].tolist())

    def test_legacy_rows_without_error_column(self):
        df = pd.DataFrame([{"persona_id": "P1", "respuesta": "ok"}, {"persona_id": "P2", "respuesta": "[ERROR: x]"}])
        self.assertEqual(["P1"], valid_responses(df)["persona_id"].tolist())

    def test_empty_dataframe(self):
        self.assertTrue(valid_responses(pd.DataFrame()).empty)


class BackwardCompatibilityTests(TestCase):
    def test_old_json_loads_with_defaults(self):
        estudio = Estudio.from_dict({"id": "s1", "universo_id": "u", "universo_nombre": "U",
                                     "titulo": "t", "pregunta": "p", "contexto": ""})
        self.assertEqual(0, estudio.respuestas_planeadas)
        r = RespuestaEstudio.from_dict({"estudio_id": "s1", "persona_id": "P1", "perfil": "x",
                                        "pregunta": "p", "contexto": "", "respuesta": "hola"})
        self.assertEqual("", r.error)
