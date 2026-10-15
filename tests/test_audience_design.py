from unittest import TestCase

from app.domain.models import PerfilCliente, PersonaSintetica, Universo
from app.services.audience_design_service import AudienceDesignError, design_audience, design_segments, parse_segments
from app.services.llm_service import LLMError
from app.services.universe_service import GENERIC_ATTRIBUTES, SAMPLED_FIELDS, distribution_summary, expand_universe


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


def archetype(nombre, peso=1, **overrides):
    atributos = {campo: "No especificado" for campo in SAMPLED_FIELDS}
    atributos.update(objetivo="Evaluar una solución", notas="Hipótesis del brief", **overrides)
    return {"nombre": nombre, "peso": peso, "atributos": atributos}


class CoherentAudienceTests(TestCase):
    def profiles(self):
        return parse_segments({"segmentos": [{
            "nombre": "Panadería", "porcentaje": 100, "descripcion": "Negocio local",
            "arquetipos": [
                archetype("Dueño", 3, rol="Decisor", motivador="Reducir costos", sensibilidad_precio="Alta"),
                archetype("Empleado", 1, rol="Usuario final", motivador="Ahorrar tiempo", sensibilidad_precio="No especificado"),
            ],
        }]})

    def test_joint_attributes_are_never_crossed_and_weights_are_respected(self):
        universo = Universo("coherente", "Test", "brief", 500, perfiles=self.profiles())
        people = expand_universe(universo)
        for person in people:
            if person.arquetipo == "Dueño":
                self.assertEqual(("Decisor", "Reducir costos", "Alta"), (person.rol, person.motivador, person.sensibilidad_precio))
            else:
                self.assertEqual(("Usuario final", "Ahorrar tiempo", "No especificado"), (person.rol, person.motivador, person.sensibilidad_precio))
            self.assertEqual("Hipótesis del brief", person.notas)
        # Margen amplio para muestreo determinista 3:1; detecta ignorar los pesos.
        owners = sum(p.arquetipo == "Dueño" for p in people)
        self.assertTrue(330 < owners < 420)
        repeated = expand_universe(universo)
        self.assertEqual([(p.arquetipo, p.rol) for p in people], [(p.arquetipo, p.rol) for p in repeated])

    def test_archetypes_and_personas_survive_json_round_trip(self):
        import json
        universo = Universo("u", "Test", "brief", 3, perfiles=self.profiles())
        restored = Universo.from_dict(json.loads(json.dumps(universo.to_dict())))
        self.assertEqual(universo, restored)
        for person in expand_universe(restored):
            self.assertEqual(person, PersonaSintetica.from_dict(json.loads(json.dumps(person.to_dict()))))

    def test_incomplete_archetype_does_not_silently_get_generic_attributes(self):
        item = archetype("A")
        del item["atributos"]["rol"]
        with self.assertRaises(AudienceDesignError):
            parse_segments([{"nombre": "A", "porcentaje": 100, "arquetipos": [item]}])

    def test_invalid_archetypes_are_rejected(self):
        for items in ([], [archetype("A", 0)], [archetype("A", float("nan"))],
                      [archetype("A", float("inf"))], [archetype("A", "x")],
                      [archetype("A"), archetype("a")],
                      [archetype("A", sensibilidad_precio="Siempre compra")]):
            with self.subTest(items=items), self.assertRaises(AudienceDesignError):
                parse_segments([{"nombre": "A", "porcentaje": 100, "arquetipos": items}])

    def test_small_samples_do_not_assign_zero_weight_segments_or_trim_last_segment(self):
        profiles = parse_segments([
            {"nombre": name, "porcentaje": pct, "arquetipos": [archetype(name)]}
            for name, pct in [("Cero", 0), ("Menor", 10), ("Mayor", 90)]
        ])
        people = expand_universe(Universo("small", "Test", "brief", 2, perfiles=profiles))
        self.assertEqual(["Mayor", "Mayor"], [p.perfil for p in people])

    def test_legacy_persona_without_archetype_still_loads(self):
        payload = expand_universe(Universo("old", "Test", "brief", 1))[0].to_dict()
        payload.pop("arquetipo")
        self.assertEqual("", PersonaSintetica.from_dict(payload).arquetipo)

    def test_equal_weights_spread_every_archetype_evenly(self):
        # Pesos iguales: con 24 personas y 10 arquetipos todos aparecen 2 o 3 veces.
        profiles = parse_segments([{"nombre": "A", "porcentaje": 100, "arquetipos": [
            archetype(f"Arquetipo {i}", rol=f"Rol {i}") for i in range(10)]}])
        people = expand_universe(Universo("parejo", "Test", "brief", 24, perfiles=profiles))
        counts = [sum(p.rol == f"Rol {i}" for p in people) for i in range(10)]
        self.assertTrue(all(2 <= c <= 3 for c in counts), counts)

    def test_archetypes_fill_attributes_for_views(self):
        perfil = self.profiles()[0]
        self.assertEqual(["Decisor", "Usuario final"], perfil.atributos["rol"])
        self.assertNotIn("notas", perfil.atributos)

    def test_flat_archetypes_saved_by_previous_version_still_load(self):
        # Formato plano {campo: valor} que guardaba la versión anterior.
        perfil = PerfilCliente.from_dict({"nombre": "A", "descripcion": "", "porcentaje": 100,
                                          "arquetipos": [{"edad_rango": "25-35", "rol": "Emprendedor"}, {}]})
        self.assertEqual(1, len(perfil.arquetipos))
        self.assertEqual({"edad_rango": "25-35", "rol": "Emprendedor"}, perfil.arquetipos[0].atributos)
        person = expand_universe(Universo("plano", "Test", "brief", 1, perfiles=[perfil]))[0]
        self.assertEqual(("25-35", "Emprendedor"), (person.edad_rango, person.rol))


class GeneralDistributionTests(TestCase):
    BRIEF = ("De CABA son un 20%\nDel interior son un 80%\n"
             "el 50% tiene entre 18 y 29 años\nel 50% tiene más de 30 años\n"
             "60% estudiantes (15 a 20 años)\n40% productores (30 a 50 años)")

    def design(self, segmentos, distribuciones=None):
        return {"segmentos": segmentos, "distribuciones": distribuciones or []}

    def segments(self, *pairs):
        return [{"nombre": n, "porcentaje": pct, "arquetipos": [archetype(n, edad_rango=edad)]} for n, pct, edad in pairs]

    def good_design(self):
        return self.design(
            self.segments(("Estudiantes", 40, "15-20"), ("Productores", 60, "25-50")),
            [{"nombre": "Región", "valores": {"CABA": 20, "Interior": 80}},
             {"nombre": "Edad", "valores": {"18-29": 50, "30+": 50}}],
        )

    def test_keeps_distributions_with_a_single_call_when_every_percentage_is_used(self):
        llm = FakeLLM(self.good_design())
        diseno = design_audience(self.BRIEF, llm=llm)
        self.assertEqual(1, len(llm.calls))
        self.assertEqual(["Región", "Edad"], [d.nombre for d in diseno.distribuciones])
        self.assertEqual([], diseno.avisos)

    def test_merged_segments_trigger_one_correction(self):
        merged = self.design(self.segments(("Todos", 100, "15-50")))

        class Sequence(FakeLLM):
            def generate(inner, **kwargs):
                inner.calls.append(kwargs)
                return merged if len(inner.calls) == 1 else self.good_design()

        llm = Sequence()
        diseno = design_audience(self.BRIEF, llm=llm)
        self.assertEqual(2, len(llm.calls))
        self.assertIn("Quedaron sin usar", llm.calls[1]["user_prompt"])
        self.assertEqual([40.0, 60.0], [p.porcentaje for p in diseno.perfiles])
        self.assertEqual([], diseno.avisos)

    def test_warns_when_the_correction_still_misses_percentages(self):
        llm = FakeLLM(self.design(self.segments(("Todos", 100, "15-50"))))
        diseno = design_audience(self.BRIEF, llm=llm)
        self.assertEqual(2, len(llm.calls))
        self.assertEqual(1, len(diseno.avisos))

    def universe(self):
        diseno = design_audience(self.BRIEF, llm=FakeLLM(self.good_design()))
        return Universo("dist", "Test", self.BRIEF, 200, perfiles=diseno.perfiles, distribuciones=diseno.distribuciones)

    def test_expansion_hits_every_target_and_respects_archetype_ages(self):
        universo = self.universe()
        people = expand_universe(universo)
        summary = {(r["Característica"], r["Valor"]): r["Logrado %"] for r in distribution_summary(universo, people)}
        self.assertEqual({("Región", "CABA"): 20.0, ("Región", "Interior"): 80.0,
                          ("Edad", "18-29"): 50.0, ("Edad", "30+"): 50.0}, summary)
        for person in people:
            self.assertIn(person.rasgos["Región"], ("CABA", "Interior"))
            # Los estudiantes solo entran en 18-29; los productores completan ese 50%.
            expected = ("18-20",) if person.perfil == "Estudiantes" else ("25-29", "30-50")
            self.assertIn(person.edad_rango, expected)
        self.assertEqual([p.to_dict() for p in people], [p.to_dict() for p in expand_universe(universo)])

    def test_distributions_and_traits_survive_json_round_trip(self):
        import json
        universo = self.universe()
        loaded = Universo.from_dict(json.loads(json.dumps(universo.to_dict())))
        self.assertEqual(universo.distribuciones, loaded.distribuciones)
        person = expand_universe(universo)[0]
        self.assertEqual(person.rasgos, PersonaSintetica.from_dict(json.loads(json.dumps(person.to_dict()))).rasgos)

    def test_traits_reach_the_participant_prompt(self):
        from app.services.study_response_service import build_system_prompt
        person = expand_universe(self.universe())[0]
        self.assertIn(person.rasgos["Región"], build_system_prompt(person.to_dict()))

    def test_identity_of_personas_without_traits_is_unchanged(self):
        from app.storage.evidence_repository import identity_for
        persona = {"persona_id": "P_000001", "perfil": "A", "rol": "x"}
        self.assertEqual(identity_for("u", persona), identity_for("u", {**persona, "rasgos": {}}))
        self.assertNotEqual(identity_for("u", persona), identity_for("u", {**persona, "rasgos": {"Región": "CABA"}}))
