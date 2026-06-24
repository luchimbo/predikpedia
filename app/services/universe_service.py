"""
app/services/universe_service.py — Expansión de universos en personas sintéticas.

Migrado y mejorado desde services_universo_expansion.py y engine_universos.py.
Cambios clave:
  - Respeta los perfiles del universo (antes asignaba "General" a todos)
  - Genera personas enriquecidas con campos del plan maestro
  - Sin dependencias legacy
"""

import random
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.domain.models import ExpansionSnapshot, PerfilCliente, PersonaSintetica, Universo


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

    # Distribuir personas por perfil
    for perfil in perfiles:
        count = max(1, round(universo.cantidad_personas * (perfil.porcentaje / total_pct)))
        for _ in range(count):
            persona = _build_persona(universo, perfil, rng)
            personas.append(persona)

    # Ajustar al total exacto (puede haber diferencia por redondeo)
    while len(personas) > universo.cantidad_personas:
        personas.pop()
    while len(personas) < universo.cantidad_personas:
        # Agregar al perfil mayoritario
        main_perfil = max(perfiles, key=lambda p: p.porcentaje)
        personas.append(_build_persona(universo, main_perfil, rng))

    # Shuffle y asignar IDs secuenciales
    rng.shuffle(personas)
    for i, persona in enumerate(personas, start=1):
        persona.persona_numero = i
        persona.persona_id = f"P_{i:06d}"

    return personas


def _build_persona(universo: Universo, perfil: PerfilCliente, rng: random.Random) -> PersonaSintetica:
    """Construye una persona sintética individual enriquecida."""
    edades = ["18-25", "26-35", "36-45", "46-55", "56-65", "65+"]
    roles = ["Usuario final", "Decisor", "Influencer", "Gatekeeper", "Comprador"]
    industrias = ["Tecnología", "Retail", "Salud", "Educación", "Finanzas", "Manufactura", "Servicios"]
    pains = [
        "Falta de tiempo",
        "Precio elevado",
        "Complejidad de uso",
        "Falta de confianza",
        "Mala experiencia previa",
        "Falta de información",
    ]
    motivadores = [
        "Ahorrar tiempo",
        "Reducir costos",
        "Mejorar calidad",
        "Innovación",
        "Recomendación de pares",
        "Tendencia de mercado",
    ]
    objeciones = [
        "Es muy caro",
        "No veo el valor",
        "Es complicado",
        "No confío en la marca",
        "Ya tengo una solución",
        "No es prioritario",
    ]
    comportamientos = ["Analítico", "Impulsivo", "Social", "Conservador", "Innovador"]
    canales = ["WhatsApp", "Email", "Redes sociales", "Sitio web", "Referido", "Tienda física"]

    return PersonaSintetica(
        persona_id="",  # Se asigna después del shuffle
        persona_numero=0,
        universo_id=universo.id,
        universo_nombre=universo.nombre,
        perfil=perfil.nombre,
        perfil_descripcion=perfil.descripcion,
        perfil_porcentaje_objetivo=perfil.porcentaje,
        edad_rango=rng.choice(edades),
        rol=rng.choice(roles),
        industria=rng.choice(industrias),
        objetivo="",
        principal_pain=rng.choice(pains),
        motivador=rng.choice(motivadores),
        objecion_base=rng.choice(objeciones),
        sensibilidad_precio=rng.choice(["Alta", "Media", "Baja"]),
        comportamiento=rng.choice(comportamientos),
        canal_preferido=rng.choice(canales),
        contexto_operativo=universo.descripcion or "",
        notas="",
    )


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
