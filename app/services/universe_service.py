"""
app/services/universe_service.py — Expansión de universos en personas sintéticas.

Migrado y mejorado desde services_universo_expansion.py y engine_universos.py.
Cambios clave:
  - Respeta los perfiles del universo (antes asignaba "General" a todos)
  - Genera personas enriquecidas con campos del plan maestro
  - Sin dependencias legacy
"""

import random
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.domain.models import ArquetipoPersona, DistribucionGeneral, ExpansionSnapshot, PerfilCliente, PersonaSintetica, Universo
from app.storage.evidence_repository import identity_for


def expand_universe(universo: Universo) -> List[PersonaSintetica]:
    """
    Expande un universo en personas sintéticas individuales.
    Distribuye personas según los perfiles definidos en el universo.
    """
    if universo.cantidad_personas <= 0:
        raise ValueError("La cantidad de personas debe ser mayor a 0.")

    perfiles = universo.perfiles
    if not perfiles:
        # Si no hay perfiles definidos, crear uno genérico
        perfiles = [PerfilCliente(nombre="General", descripcion=universo.prompt_perfil or "Sin descripción", porcentaje=100.0)]

    # Validar que los porcentajes sumen ~100
    total_pct = sum(p.porcentaje for p in perfiles)
    if total_pct <= 0:
        raise ValueError("Los porcentajes de perfiles deben sumar > 0.")

    personas: List[PersonaSintetica] = []
    rng = random.Random(universo.id)  # Seed determinista

    # En los diseños con arquetipos, mayores restos conserva el total exacto sin
    # sobreasignar segmentos pequeños ni dar personas a segmentos con peso 0.
    counts = None
    if any(p.arquetipos for p in perfiles):
        counts = _largest_remainder(universo.cantidad_personas, [p.porcentaje for p in perfiles])

    # Distribuir personas por perfil (camino anterior sin cambios para legacy).
    for index, perfil in enumerate(perfiles):
        if perfil.porcentaje <= 0:
            continue  # Un grupo puesto en 0% a mano no aporta personas.
        count = counts[index] if counts is not None else max(1, round(universo.cantidad_personas * (perfil.porcentaje / total_pct)))
        for arquetipo in _archetype_sequence(perfil, count, rng):
            personas.append(_build_persona(universo, perfil, rng, arquetipo))

    # Ajustar al total exacto (puede haber diferencia por redondeo)
    while len(personas) > universo.cantidad_personas:
        personas.pop()
    while len(personas) < universo.cantidad_personas:
        # Agregar al perfil mayoritario
        main_perfil = max(perfiles, key=lambda p: p.porcentaje)
        personas.append(_build_persona(universo, main_perfil, rng))

    if universo.distribuciones:
        # Rng propio: no altera el sorteo de las audiencias sin distribuciones.
        rng_dist = random.Random(f"{universo.id}:distribuciones")
        for distribucion in universo.distribuciones:
            _apply_distribution(personas, distribucion, rng_dist)

    # Shuffle y asignar IDs secuenciales
    rng.shuffle(personas)
    for i, persona in enumerate(personas, start=1):
        persona.persona_numero = i
        persona.persona_id = f"P_{i:06d}"
        persona.identity_id = identity_for(universo.id, persona.to_dict())

    return personas


GENERIC_ATTRIBUTES: Dict[str, List[str]] = {
    "edad_rango": ["18-25", "26-35", "36-45", "46-55", "56-65", "65+"],
    "rol": ["Usuario final", "Decisor", "Influencer", "Gatekeeper", "Comprador"],
    "industria": ["Tecnología", "Retail", "Salud", "Educación", "Finanzas", "Manufactura", "Servicios"],
    "principal_pain": [
        "Falta de tiempo",
        "Precio elevado",
        "Complejidad de uso",
        "Falta de confianza",
        "Mala experiencia previa",
        "Falta de información",
    ],
    "motivador": [
        "Ahorrar tiempo",
        "Reducir costos",
        "Mejorar calidad",
        "Innovación",
        "Recomendación de pares",
        "Tendencia de mercado",
    ],
    "objecion_base": [
        "Es muy caro",
        "No veo el valor",
        "Es complicado",
        "No confío en la marca",
        "Ya tengo una solución",
        "No es prioritario",
    ],
    "sensibilidad_precio": ["Alta", "Media", "Baja"],
    "comportamiento": ["Analítico", "Impulsivo", "Social", "Conservador", "Innovador"],
    "canal_preferido": ["WhatsApp", "Email", "Redes sociales", "Sitio web", "Referido", "Tienda física"],
}

# El orden importa: define la secuencia del sorteo y, con ella, la
# reproducibilidad de las expansiones ya guardadas.
SAMPLED_FIELDS = list(GENERIC_ATTRIBUTES.keys())

# Campos que solo se completan si el perfil trae valores propios.
OPTIONAL_FIELDS = ["objetivo"]


def _largest_remainder(total: int, weights: List[float]) -> List[int]:
    """Reparte `total` según `weights` sumando exactamente `total`."""
    suma = sum(w for w in weights if w > 0)
    if suma <= 0:
        return [0] * len(weights)
    cuotas = [total * max(w, 0) / suma for w in weights]
    counts = [int(cuota) for cuota in cuotas]
    orden = sorted(range(len(weights)), key=lambda i: cuotas[i] - counts[i], reverse=True)
    for i in orden[:total - sum(counts)]:
        counts[i] += 1
    return counts


def _archetype_sequence(perfil: PerfilCliente, count: int, rng: random.Random) -> List[Optional[ArquetipoPersona]]:
    """Arquetipos para las `count` personas de un perfil.

    Cada arquetipo recibe personas en proporción a su peso (mayores restos),
    así ninguno con peso queda afuera por azar; el orden se mezcla. Sin
    arquetipos no usa el rng, para reproducir las audiencias legacy.
    """
    if not perfil.arquetipos:
        return [None] * count
    cantidades = _largest_remainder(count, [a.peso for a in perfil.arquetipos])
    secuencia = [a for a, n in zip(perfil.arquetipos, cantidades) for _ in range(n)]
    rng.shuffle(secuencia)
    return secuencia


def _build_persona(
    universo: Universo,
    perfil: PerfilCliente,
    rng: random.Random,
    arquetipo: Optional[ArquetipoPersona] = None,
) -> PersonaSintetica:
    """Construye una persona sintética.

    Con arquetipo, copia la combinación completa; los campos que el arquetipo
    no trae quedan vacíos en vez de sortearse, para no inventar datos. Sin
    arquetipo, sortea cada atributo del perfil (o los genéricos) por separado.
    """
    if arquetipo is not None:
        return PersonaSintetica(
            persona_id="", persona_numero=0,
            universo_id=universo.id, universo_nombre=universo.nombre,
            perfil=perfil.nombre, perfil_descripcion=perfil.descripcion,
            perfil_porcentaje_objetivo=perfil.porcentaje,
            contexto_operativo=universo.descripcion or "",
            arquetipo=arquetipo.nombre,
            **{campo: arquetipo.atributos.get(campo, "")
               for campo in SAMPLED_FIELDS + OPTIONAL_FIELDS + ["notas"]},
        )
    atributos = perfil.atributos or {}
    valores: Dict[str, str] = {}
    for campo in SAMPLED_FIELDS:
        valores[campo] = rng.choice(atributos.get(campo) or GENERIC_ATTRIBUTES[campo])
    for campo in OPTIONAL_FIELDS:
        opciones = atributos.get(campo)
        valores[campo] = rng.choice(opciones) if opciones else ""

    return PersonaSintetica(
        persona_id="",  # Se asigna después del shuffle
        persona_numero=0,
        universo_id=universo.id,
        universo_nombre=universo.nombre,
        perfil=perfil.nombre,
        perfil_descripcion=perfil.descripcion,
        perfil_porcentaje_objetivo=perfil.porcentaje,
        contexto_operativo=universo.descripcion or "",
        notas="",
        **valores,
    )


AGE_OPEN_END = 120
# Para ponderar rangos abiertos ("50+") como si terminaran acá.
AGE_SPAN_CAP = 80


def is_age_distribution(nombre: str) -> bool:
    return normalize_label(nombre).startswith("edad")


def normalize_label(text: str) -> str:
    plain = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", plain.casefold()).strip()


def parse_age_range(text: str) -> Optional[Tuple[int, int]]:
    """"18-29", "18 a 29", "50+", "más de 50", "menos de 18" → (desde, hasta). None si no se entiende."""
    t = normalize_label(text)
    nums = [int(n) for n in re.findall(r"\d+", t)]
    if not nums:
        return None
    if len(nums) >= 2 and nums[0] <= nums[1]:
        return nums[0], nums[1]
    n = nums[0]
    if "+" in t or "mas de" in t or "mayor" in t:
        return n, AGE_OPEN_END
    if "menos de" in t or "menor" in t:
        return 0, max(n - 1, 0)
    return n, n


def _format_age(desde: int, hasta: int) -> str:
    if hasta >= AGE_OPEN_END:
        return f"{desde}+"
    return str(desde) if desde == hasta else f"{desde}-{hasta}"


def _age_overlap(persona_age: str, categoria: str) -> Optional[Tuple[int, int]]:
    a, b = parse_age_range(persona_age), parse_age_range(categoria)
    if a is None or b is None:
        return None
    desde, hasta = max(a[0], b[0]), min(a[1], b[1])
    return (desde, hasta) if desde <= hasta else None


def _affinity(persona_age: str, categoria: str, es_edad: bool) -> float:
    """Peso inicial del cruce: la parte del rango de la persona que cae en la categoría.

    Así un rango 30-40 casi nunca termina en "40" por tocar apenas 40-49.
    0 = incompatible; 1 = sin información de edad para comparar.
    """
    if not es_edad or parse_age_range(persona_age) is None or parse_age_range(categoria) is None:
        return 1.0
    rango = _age_overlap(persona_age, categoria)
    if rango is None:
        return 0.0
    desde, hasta = parse_age_range(persona_age)
    largo = min(hasta, AGE_SPAN_CAP) - desde + 1
    return max(min(rango[1], AGE_SPAN_CAP) - rango[0] + 1, 1) / max(largo, 1)


def _apply_distribution(personas: List[PersonaSintetica], distribucion: DistribucionGeneral,
                        rng: random.Random) -> None:
    """Asigna un valor de la distribución a cada persona.

    El total respeta los porcentajes y cada valor es compatible con el grupo
    de la persona: con la edad, un arquetipo de 15-20 años solo cae en
    categorías que se superponen con ese rango. El reparto entre grupos sale
    de un ajuste proporcional iterativo (grupos × categorías, con ceros
    donde no hay compatibilidad).
    """
    categorias = list(distribucion.valores)
    if not categorias or not personas:
        return
    es_edad = is_age_distribution(distribucion.nombre)
    objetivos = _largest_remainder(len(personas), [distribucion.valores[c] for c in categorias])

    grupos: Dict[Tuple[str, str, str], List[PersonaSintetica]] = {}
    for persona in personas:
        grupos.setdefault((persona.perfil, persona.arquetipo, persona.edad_rango), []).append(persona)
    claves = list(grupos)
    afinidad = []
    for clave in claves:
        fila = [_affinity(clave[2], c, es_edad) for c in categorias]
        afinidad.append(fila if any(fila) else [1.0] * len(categorias))
    compat = [[v > 0 for v in fila] for fila in afinidad]

    # Ajuste proporcional iterativo: filas = tamaño de cada grupo, columnas = objetivo.
    matriz = [[len(grupos[k]) * v for v in fila] for k, fila in zip(claves, afinidad)]
    for _ in range(200):
        for j, objetivo in enumerate(objetivos):
            col = sum(fila[j] for fila in matriz)
            if col > 0:
                for fila in matriz:
                    fila[j] *= objetivo / col
        for i, clave in enumerate(claves):
            suma = sum(matriz[i])
            if suma > 0:
                matriz[i] = [v * len(grupos[clave]) / suma for v in matriz[i]]

    cuentas = [_largest_remainder(len(grupos[k]), fila) for k, fila in zip(claves, matriz)]
    _fix_column_totals(cuentas, compat, objetivos)

    for clave, fila in zip(claves, cuentas):
        miembros = list(grupos[clave])
        rng.shuffle(miembros)
        valores = [c for c, n in zip(categorias, fila) for _ in range(n)]
        for persona, valor in zip(miembros, valores):
            if es_edad:
                rango = _age_overlap(persona.edad_rango, valor)
                persona.edad_rango = _format_age(*rango) if rango else valor
            else:
                persona.rasgos[distribucion.nombre] = valor


def _fix_column_totals(cuentas: List[List[int]], compat: List[List[bool]], objetivos: List[int]) -> None:
    """Mueve personas sueltas entre categorías para que cada total quede igual al objetivo."""
    for _ in range(sum(objetivos)):
        totales = [sum(fila[j] for fila in cuentas) for j in range(len(objetivos))]
        sobra = [j for j in range(len(objetivos)) if totales[j] > objetivos[j]]
        falta = [j for j in range(len(objetivos)) if totales[j] < objetivos[j]]
        movido = False
        for j_mas in sobra:
            for j_menos in falta:
                for fila, ok in zip(cuentas, compat):
                    if fila[j_mas] > 0 and ok[j_menos]:
                        fila[j_mas] -= 1
                        fila[j_menos] += 1
                        movido = True
                        break
                if movido:
                    break
            if movido:
                break
        if not movido:
            return


def distribution_summary(universo: Universo, personas: List[PersonaSintetica]) -> List[Dict[str, Any]]:
    """Objetivo vs. logrado por cada valor de cada distribución general."""
    filas = []
    total = len(personas) or 1
    for distribucion in universo.distribuciones:
        es_edad = is_age_distribution(distribucion.nombre)
        suma = sum(distribucion.valores.values()) or 1
        for categoria, pct in distribucion.valores.items():
            if es_edad:
                # La persona cuenta si su rango entra completo en la categoría.
                cuenta = sum(1 for p in personas
                             if parse_age_range(p.edad_rango) is not None
                             and _age_overlap(p.edad_rango, categoria) == parse_age_range(p.edad_rango))
            else:
                cuenta = sum(1 for p in personas if p.rasgos.get(distribucion.nombre) == categoria)
            filas.append({"Característica": distribucion.nombre, "Valor": categoria,
                          "Objetivo %": round(pct * 100 / suma, 1), "Logrado %": round(cuenta * 100 / total, 1)})
    return filas


def build_expansion_snapshot(universo: Universo, personas: List[PersonaSintetica]) -> ExpansionSnapshot:
    """Construye un snapshot resumido de la expansión."""
    resumen: Dict[str, Dict[str, Any]] = {}
    for persona in personas:
        perfil = persona.perfil
        if perfil not in resumen:
            resumen[perfil] = {"perfil": perfil, "cantidad": 0}
        resumen[perfil]["cantidad"] += 1

    return ExpansionSnapshot(
        universo_id=universo.id,
        universo_nombre=universo.nombre,
        total_personas=len(personas),
        personas=[p.to_dict() for p in personas],
        resumen_perfiles=sorted(resumen.values(), key=lambda x: x["perfil"]),
    )
