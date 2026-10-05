from unittest import TestCase

from app.domain.models import PerfilCliente, Universo
from app.services.audience_design_service import AudienceDesignError, design_segments, parse_segments
from app.services.llm_service import LLMError
from app.services.universe_service import GENERIC_ATTRIBUTES, SAMPLED_FIELDS, expand_universe


def segment(nombre, porcentaje, **atributos):
    return {"nombre": nombre, "descripcion": f"Desc {nombre}", "porcentaje": porcentaje, "atributos": atributos}


class FakeLLM:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls = result, error, []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.result


class ParseSegmentsTests(TestCase):
    def test_normalizes_percentages_and_cleans_values(self):
        perfiles = parse_segments({"segmentos": [
            segment("Dueños", "60%", rol=["Dueño", " ", "Dueño"], edad_rango="45-60"),
            segment("Revendedores", 20, rol=["Revendedor"], campo_inventado=["x"]),
        ]})
        self.assertEqual([75.0, 25.0], [p.porcentaje for p in perfiles])
        self.assertEqual(["Dueño", "Dueño"], perfiles[0].atributos["rol"])
        self.assertEqual(["45-60"], perfiles[0].atributos["edad_rango"])
        self.assertNotIn("campo_inventado", perfiles[1].atributos)

    def test_zero_percentages_split_evenly_and_duplicate_names_are_renamed(self):
        perfiles = parse_segments([segment("A", 0, rol=["x"]), segment("a", 0, rol=["y"])])
        self.assertEqual([50.0, 50.0], [p.porcentaje for p in perfiles])
        self.assertEqual(["A", "a 2"], [p.nombre for p in perfiles])

    def test_rejects_unusable_payloads(self):
        for payload in ({"_raw": "texto", "_error": "x"}, {"segmentos": []}, {"segmentos": [segment("A", 100)]}, "texto"):
            with self.assertRaises(AudienceDesignError):
                parse_segments(payload)


class DesignSegmentsTests(TestCase):
    def test_single_llm_call_with_brief(self):
        llm = FakeLLM({"segmentos": [segment("A", 100, rol=["Panadero"])]})
        perfiles = design_segments("Panaderos de González Catán", llm=llm)
        self.assertEqual(1, len(llm.calls))
        self.assertIn("González Catán", llm.calls[0]["user_prompt"])
        self.assertTrue(llm.calls[0]["expect_json"])
        self.assertEqual(["Panadero"], perfiles[0].atributos["rol"])

    def test_llm_error_becomes_design_error(self):
        with self.assertRaises(AudienceDesignError):
            design_segments("brief", llm=FakeLLM(error=LLMError("caído")))


class ExpansionTests(TestCase):
    def universo(self, perfiles, cantidad=200):
        return Universo(id="u_test", nombre="Test", descripcion="brief", cantidad_personas=cantidad, perfiles=perfiles)

    def test_personas_use_segment_attributes(self):
        perfiles = [
            PerfilCliente("Dueños", "d", 70, {"rol": ["Dueño"], "industria": ["Panadería"], "objetivo": ["Bajar costos"]}),
            PerfilCliente("Revendedores", "r", 30, {"rol": ["Revendedor"]}),
        ]
        personas = expand_universe(self.universo(perfiles))
        duenos = [p for p in personas if p.perfil == "Dueños"]
        revendedores = [p for p in personas if p.perfil == "Revendedores"]
        self.assertEqual((140, 60), (len(duenos), len(revendedores)))
        self.assertTrue(all(p.rol == "Dueño" and p.industria == "Panadería" and p.objetivo == "Bajar costos" for p in duenos))
        self.assertTrue(all(p.rol == "Revendedor" and p.objetivo == "" for p in revendedores))
        # Campos sin valores propios caen en los genéricos.
        self.assertTrue(all(p.industria in GENERIC_ATTRIBUTES["industria"] for p in revendedores))

    def test_expansion_is_deterministic(self):
        perfiles = [PerfilCliente("A", "a", 100, {"rol": ["x", "y", "z"]})]
        first = [p.to_dict() for p in expand_universe(self.universo(perfiles, 50))]
        second = [p.to_dict() for p in expand_universe(self.universo(perfiles, 50))]
        for row in first + second:
            row.pop("created_at")
        self.assertEqual(first, second)

    def test_generic_expansion_matches_previous_algorithm(self):
        # Reproduce el sorteo del código anterior a los atributos por segmento.
        import random

        personas = expand_universe(self.universo([], 30))
        rng = random.Random("u_test")
        esperado = [{campo: rng.choice(GENERIC_ATTRIBUTES[campo]) for campo in SAMPLED_FIELDS} for _ in range(30)]
        rng.shuffle(esperado)
        obtenido = [{campo: getattr(p, campo) for campo in SAMPLED_FIELDS} for p in personas]
        self.assertEqual(esperado, obtenido)


class PerfilSerializationTests(TestCase):
    def test_old_profiles_without_attributes_still_load(self):
        perfil = PerfilCliente.from_dict({"nombre": "General", "descripcion": "x", "porcentaje": 100})
        self.assertEqual({}, perfil.atributos)

    def test_attributes_round_trip(self):
        perfil = PerfilCliente("A", "a", 100, {"rol": ["x"]})
        self.assertEqual(perfil, PerfilCliente.from_dict(perfil.to_dict()))


def arquetipo(edad, rol, precio, **extra):
    return {"edad_rango": edad, "rol": rol, "sensibilidad_precio": precio, **extra}


class ArchetypeTests(TestCase):
    def payload(self):
        return {"segmentos": [
            {"nombre": "Tradicionales", "descripcion": "d", "porcentaje": 60, "arquetipos": [
                arquetipo("50-60", "Dueño con oficio", "Alta"),
                arquetipo("40-50", "Dueño heredero", "Media", campo_inventado="x", objetivo=" "),
                "no es un dict",
                {},
            ] + [arquetipo(f"{20 + i}-{30 + i}", f"Rol {i}", "Baja") for i in range(12)]},
            {"nombre": "Modernos", "descripcion": "m", "porcentaje": 40, "arquetipos": [
                arquetipo("25-35", "Emprendedor", "Media"),
                arquetipo("30-40", "Socio joven", "Baja"),
            ]},
        ]}

    def test_parse_cleans_limits_and_derives_attributes(self):
        tradicionales, modernos = parse_segments(self.payload())
        self.assertEqual(10, len(tradicionales.arquetipos))
        self.assertEqual(arquetipo("40-50", "Dueño heredero", "Media"), tradicionales.arquetipos[1])
        self.assertEqual(["Media", "Baja"], modernos.atributos["sensibilidad_precio"])
        self.assertEqual(["Emprendedor", "Socio joven"], modernos.atributos["rol"])

    def test_expansion_copies_whole_archetypes_and_uses_all_before_repeating(self):
        perfiles = parse_segments(self.payload())
        universo = Universo(id="u_arq", nombre="T", descripcion="b", cantidad_personas=40, perfiles=perfiles)
        personas = expand_universe(universo)
        by_profile = {p.nombre: p.arquetipos for p in perfiles}
        for persona in personas:
            combo = {"edad_rango": persona.edad_rango, "rol": persona.rol, "sensibilidad_precio": persona.sensibilidad_precio}
            self.assertIn(combo, by_profile[persona.perfil])
        tradicionales = [p.rol for p in personas if p.perfil == "Tradicionales"]
        self.assertEqual(24, len(tradicionales))
        # 24 personas con 10 arquetipos: todos aparecen al menos 2 veces y ninguno más de 3.
        counts = [tradicionales.count(a["rol"]) for a in by_profile["Tradicionales"]]
        self.assertTrue(all(2 <= c <= 3 for c in counts), counts)

    def test_archetype_expansion_is_deterministic(self):
        perfiles = parse_segments(self.payload())
        universo = Universo(id="u_arq", nombre="T", descripcion="b", cantidad_personas=30, perfiles=perfiles)
        first = [(p.perfil, p.rol) for p in expand_universe(universo)]
        self.assertEqual(first, [(p.perfil, p.rol) for p in expand_universe(universo)])

    def test_archetypes_round_trip(self):
        perfil = parse_segments(self.payload())[1]
        self.assertEqual(perfil, PerfilCliente.from_dict(perfil.to_dict()))
