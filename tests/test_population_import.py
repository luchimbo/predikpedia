from collections import Counter
from unittest import TestCase

import pandas as pd

from app.domain.models import PersonaSintetica, Universo
from app.services.population_import_service import (
    ROLE_ATTRIBUTE,
    ROLE_GROUP,
    ROLE_IGNORE,
    ROLE_WEIGHT,
    PopulationImportError,
    build_population,
    read_table,
    suggest_mapping,
)


def sample_df():
    rows = []
    for i in range(30):
        nse = "D/E" if i < 20 else "ABC1"
        rows.append({
            "Nombre": f"Persona {i}",
            "Email": f"p{i}@x.com",
            "Edad": str(20 + i),
            "NSE": nse,
            "Zona": "GBA" if nse == "D/E" else "CABA",
            "Peso": "1" if nse == "D/E" else "4",
        })
    return pd.DataFrame(rows)


class ReadTableTests(TestCase):
    def test_reads_semicolon_latin1_csv(self):
        data = "Edad;Zona\n30;Morón\n45;Lanús\n".encode("latin-1")
        df = read_table(data, "encuesta.csv")
        self.assertEqual(["Edad", "Zona"], list(df.columns))
        self.assertEqual("Morón", df.iloc[0]["Zona"])

    def test_empty_file_fails(self):
        with self.assertRaises(PopulationImportError):
            read_table(b"Edad,Zona\n", "vacio.csv")


class SuggestMappingTests(TestCase):
    def test_ignores_personal_data_and_detects_weight(self):
        mapping = suggest_mapping(sample_df())
        self.assertEqual(ROLE_IGNORE, mapping["Nombre"])
        self.assertEqual(ROLE_IGNORE, mapping["Email"])
        self.assertEqual(ROLE_WEIGHT, mapping["Peso"])
        self.assertEqual(ROLE_ATTRIBUTE, mapping["Edad"])

    def test_ignores_id_columns(self):
        mapping = suggest_mapping(pd.DataFrame({"Agent_ID": ["a"], "Segmento": ["x"]}))
        self.assertEqual(ROLE_IGNORE, mapping["Agent_ID"])
        self.assertEqual(ROLE_GROUP, mapping["Segmento"])


class BuildPopulationTests(TestCase):
    def build(self, cantidad, mapping=None, df=None):
        df = sample_df() if df is None else df
        mapping = mapping or {**suggest_mapping(df), "NSE": ROLE_GROUP}
        return build_population(df, mapping, cantidad, universe_id="u1", nombre="Test", fuente="x.csv")

    def test_personas_are_real_rows_without_personal_data(self):
        df = sample_df()
        universo, personas = self.build(15, df=df)
        rows = {(r.Edad, r.NSE, r.Zona) for r in df.itertuples()}
        for p in personas:
            self.assertIn((p.datos_reales["Edad"], p.datos_reales["NSE"], p.datos_reales["Zona"]), rows)
            self.assertNotIn("Nombre", p.datos_reales)
            self.assertNotIn("Email", p.datos_reales)
            self.assertEqual(p.datos_reales["NSE"], p.perfil)
        self.assertEqual("datos_reales", universo.origen)

    def test_group_shares_use_weights(self):
        universo, _ = self.build(10)
        shares = {p.nombre: p.porcentaje for p in universo.perfiles}
        # 20 filas D/E con peso 1 y 10 filas ABC1 con peso 4 -> 20 vs 40
        self.assertAlmostEqual(33.3, shares["D/E"], places=1)
        self.assertAlmostEqual(66.7, shares["ABC1"], places=1)

    def test_weighted_sample_follows_weights(self):
        _, personas = self.build(3000)
        counts = Counter(p.perfil for p in personas)
        self.assertAlmostEqual(2 / 3, counts["ABC1"] / 3000, delta=0.04)

    def test_unweighted_uses_every_row_before_repeating(self):
        df = sample_df()
        mapping = {**suggest_mapping(df), "Peso": ROLE_IGNORE, "NSE": ROLE_ATTRIBUTE}
        _, personas = self.build(30, mapping=mapping, df=df)
        self.assertEqual(30, len({p.datos_reales["Edad"] for p in personas}))
        self.assertEqual({"Población real"}, {p.perfil for p in personas})

    def test_is_deterministic(self):
        _, a = self.build(12)
        _, b = self.build(12)
        self.assertEqual([p.datos_reales for p in a], [p.datos_reales for p in b])

    def test_rejects_mapping_without_attributes(self):
        df = sample_df()
        with self.assertRaises(PopulationImportError):
            build_population(df, {c: ROLE_IGNORE for c in df.columns}, 5, universe_id="u", nombre="x")


class SerializationTests(TestCase):
    def test_round_trip_and_old_json(self):
        _, personas = build_population(sample_df(), {**suggest_mapping(sample_df()), "NSE": ROLE_GROUP}, 2,
                                       universe_id="u", nombre="x")
        again = PersonaSintetica.from_dict(personas[0].to_dict())
        self.assertEqual(personas[0].datos_reales, again.datos_reales)
        old = Universo.from_dict({"id": "u", "nombre": "n", "descripcion": "", "cantidad_personas": 3})
        self.assertEqual("descripcion", old.origen)
        self.assertEqual({}, PersonaSintetica.from_dict({"persona_id": "P"}).datos_reales)
