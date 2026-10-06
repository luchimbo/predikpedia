"""
app/services/audience_design_service.py — Diseño de segmentos a partir del brief.

Una sola llamada al LLM convierte la descripción libre de la audiencia en
segmentos (PerfilCliente) con porcentajes y valores plausibles por atributo.
La expansión elige combinaciones conjuntas de atributos (arquetipos) para
preservar su coherencia. El costo no depende de la cantidad de personas.
"""

import math
from typing import Any, Dict, List, Optional

from app.domain.models import ArquetipoPersona, PerfilCliente
from app.services.llm_service import LLMError, LLMService
from app.services.universe_service import OPTIONAL_FIELDS, SAMPLED_FIELDS

MAX_SEGMENTS = 6
MAX_VALUES_PER_FIELD = 8
MIN_ARCHETYPES = 4
MAX_ARCHETYPES = 10

FIELD_GUIDE = {
    "edad_rango": "rangos de edad, ej. \"30-40\"",
    "rol": "rol o situación de la persona frente a la decisión",
    "industria": "rubro, ocupación o tipo de negocio",
    "objetivo": "qué busca lograr",
    "principal_pain": "principal dolor o problema",
    "motivador": "qué lo mueve a actuar o comprar",
    "objecion_base": "objeción típica antes de comprar o adoptar",
    "sensibilidad_precio": "\"Alta\", \"Media\", \"Baja\" o \"No especificado\"; no inferir ingresos desde la edad o el rol",
    "comportamiento": "estilo de decisión, ej. \"Conservador\", \"Analítico\"",
    "canal_preferido": "canales por los que se informa o compra",
    "notas": "restricciones y supuestos del arquetipo; distinguir lo explícito del brief de lo hipotético",
}

SYSTEM_PROMPT = (
    "Sos un investigador de mercado senior. A partir de un brief de audiencia, "
    "diseñás segmentos realistas para simular personas sintéticas. Usás solo lo que "
    "el brief dice o implica de forma razonable; no inventás rubros, edades ni canales "
    "que lo contradigan. Escribís en español rioplatense, con valores cortos y concretos."
)


class AudienceDesignError(Exception):
    """El LLM no devolvió un diseño de segmentos utilizable."""


def _build_user_prompt(descripcion: str) -> str:
    todos = SAMPLED_FIELDS + OPTIONAL_FIELDS + ["notas"]
    guia = "\n".join(f"- {campo}: {FIELD_GUIDE[campo]}" for campo in todos)
    campos = ",\n".join(f'            "{campo}": "..."' for campo in todos)
    return (
        f"Brief de la audiencia:\n\"\"\"\n{descripcion.strip()}\n\"\"\"\n\n"
        f"Definí entre 2 y {MAX_SEGMENTS - 2} segmentos (o 1 si el brief es claramente homogéneo). "
        "Si el brief menciona segmentos o proporciones, respetalos. Los porcentajes deben sumar 100.\n"
        f"Dentro de cada segmento diseñá de {MIN_ARCHETYPES} a 8 arquetipos (menos si el brief no da base para más). "
        "Cada arquetipo contiene UNA combinación completa y coherente: rol, objetivo, dolor, "
        "motivador, objeción y comportamiento deben poder coexistir. La expansión mantiene esa "
        "combinación junta; no mezcla atributos entre arquetipos.\n"
        "Los arquetipos de un segmento deben ser distintos entre sí: variá edades, situaciones y "
        "posturas, e incluí escépticos y gente poco interesada si el brief lo permite. No fuerces "
        "todos los perfiles a comprar, ni todos a rechazar. No deduzcas personalidad desde edad o nivel económico. "
        "No inventes ingresos, presupuestos exactos, experiencias pasadas ni estadísticas. "
        "Para datos sin sustento usá 'No especificado'. El peso es relativo dentro del segmento "
        "y debe ser positivo: respetá proporciones explícitas o usá pesos iguales. "
        "Las proporciones no aportadas son hipótesis, no frecuencias de mercado medidas.\n\n"
        f"Atributos:\n{guia}\n\n"
        "Respondé solo JSON válido (sin comentarios ni texto extra) con esta forma:\n"
        "{\n"
        '  "segmentos": [\n'
        "    {\n"
        '      "nombre": "Nombre corto del segmento",\n'
        '      "descripcion": "1-2 oraciones sobre quiénes son y su contexto",\n'
        '      "porcentaje": 50,\n'
        '      "arquetipos": [{\n'
        '        "nombre": "Nombre corto de la combinación",\n'
        '        "peso": 1,\n'
        '        "atributos": {\n'
        f"{campos}\n"
        "        }\n"
        "      }]\n"
        "    }\n"
        "  ]\n"
        "}"
    )


def _clean_values(values: Any) -> List[str]:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return []
    cleaned = [v.strip() for v in values if isinstance(v, str) and v.strip()]
    return cleaned[:MAX_VALUES_PER_FIELD]


def _attributes_from_archetypes(arquetipos: List[ArquetipoPersona]) -> Dict[str, List[str]]:
    """Valores por campo (en orden de aparición) para vistas y código que usan `atributos`."""
    atributos: Dict[str, List[str]] = {}
    for arquetipo in arquetipos:
        for campo, valor in arquetipo.atributos.items():
            if campo == "notas":
                continue
            valores = atributos.setdefault(campo, [])
            if valor not in valores:
                valores.append(valor)
    return atributos


def _parse_archetypes(raw: Any) -> List[ArquetipoPersona]:
    """Rechaza diseños parciales para no completarlos con atributos genéricos ajenos."""
    if not isinstance(raw, list) or not raw or len(raw) > MAX_ARCHETYPES:
        raise AudienceDesignError("La lista de arquetipos está vacía o es inválida.")
    required = SAMPLED_FIELDS + OPTIONAL_FIELDS
    result = []
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("atributos"), dict):
            raise AudienceDesignError("El arquetipo no contiene atributos válidos.")
        attrs = {k: v.strip() for k, v in item["atributos"].items()
                 if k in required + ["notas"] and isinstance(v, str) and v.strip()}
        if any(field not in attrs for field in required):
            raise AudienceDesignError("El arquetipo está incompleto; faltan atributos vinculados.")
        if attrs["sensibilidad_precio"] not in ("Alta", "Media", "Baja", "No especificado"):
            raise AudienceDesignError("La sensibilidad al precio del arquetipo es inválida.")
        try:
            peso = float(item.get("peso", 1))
        except (TypeError, ValueError):
            raise AudienceDesignError("El peso del arquetipo es inválido.") from None
        nombre = item.get("nombre")
        if not isinstance(nombre, str) or not nombre.strip() or not math.isfinite(peso) or peso <= 0:
            raise AudienceDesignError("El arquetipo requiere nombre y peso positivo finito.")
        if any(a.nombre.casefold() == nombre.strip().casefold() for a in result):
            raise AudienceDesignError("Los nombres de arquetipos deben ser únicos por segmento.")
        result.append(ArquetipoPersona(nombre.strip(), peso, attrs))
    return result


def parse_segments(payload: Any) -> List[PerfilCliente]:
    """Valida y normaliza la respuesta del LLM. Lanza AudienceDesignError si no sirve."""
    if isinstance(payload, list):
        raw_segments = payload
    elif isinstance(payload, dict):
        raw_segments = payload.get("segmentos") or payload.get("segments") or []
    else:
        raw_segments = []
    if not isinstance(raw_segments, list):
        raw_segments = []

    perfiles: List[PerfilCliente] = []
    nombres_usados = set()
    for raw in raw_segments[:MAX_SEGMENTS]:
        if not isinstance(raw, dict):
            continue
        nombre = str(raw.get("nombre", "")).strip()
        if not nombre:
            continue
        base, n = nombre, 2
        while nombre.lower() in nombres_usados:
            nombre, n = f"{base} {n}", n + 1
        nombres_usados.add(nombre.lower())

        try:
            porcentaje = float(str(raw.get("porcentaje", 0)).replace("%", "").strip() or 0)
        except ValueError:
            porcentaje = 0.0
        if not math.isfinite(porcentaje):
            raise AudienceDesignError("El porcentaje del segmento debe ser finito.")

        raw_atributos = raw.get("atributos") if isinstance(raw.get("atributos"), dict) else {}
        atributos: Dict[str, List[str]] = {}
        for campo in SAMPLED_FIELDS + OPTIONAL_FIELDS:
            valores = _clean_values(raw_atributos.get(campo))
            if valores:
                atributos[campo] = valores

        arquetipos = _parse_archetypes(raw["arquetipos"]) if "arquetipos" in raw else []
        perfiles.append(PerfilCliente(
            nombre=nombre,
            descripcion=str(raw.get("descripcion", "")).strip(),
            porcentaje=max(porcentaje, 0.0),
            atributos=atributos or _attributes_from_archetypes(arquetipos),
            arquetipos=arquetipos,
        ))

    if not perfiles:
        raise AudienceDesignError("El modelo no devolvió segmentos válidos.")
    if not all(p.atributos or p.arquetipos for p in perfiles):
        raise AudienceDesignError("El modelo no devolvió atributos para los segmentos.")

    # Normalizar porcentajes a 100 (reparto parejo si vinieron todos en 0).
    total = sum(p.porcentaje for p in perfiles)
    for p in perfiles:
        p.porcentaje = round(p.porcentaje * 100 / total, 1) if total > 0 else round(100 / len(perfiles), 1)

    return perfiles


def design_segments(descripcion: str, llm: Optional[LLMService] = None) -> List[PerfilCliente]:
    """Diseña los segmentos de una audiencia a partir de su descripción."""
    if not descripcion.strip():
        raise AudienceDesignError("La descripción de la audiencia está vacía.")
    llm = llm or LLMService()
    try:
        result = llm.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=_build_user_prompt(descripcion),
            agent_id="audience_design",
            timeout=120,
            expect_json=True,
        )
    except LLMError as exc:
        raise AudienceDesignError(str(exc)) from exc
    return parse_segments(result)
