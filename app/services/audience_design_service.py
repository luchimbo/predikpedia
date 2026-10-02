"""
app/services/audience_design_service.py — Diseño de segmentos a partir del brief.

Una sola llamada al LLM convierte la descripción libre de la audiencia en
segmentos (PerfilCliente) con porcentajes y valores plausibles por atributo.
La expansión después sortea personas dentro de esos valores, así que el costo
no depende de la cantidad de personas.
"""

from typing import Any, Dict, List, Optional

from app.domain.models import PerfilCliente
from app.services.llm_service import LLMError, LLMService
from app.services.universe_service import OPTIONAL_FIELDS, SAMPLED_FIELDS

MAX_SEGMENTS = 6
MAX_VALUES_PER_FIELD = 8

FIELD_GUIDE = {
    "edad_rango": "rangos de edad, ej. \"30-40\"",
    "rol": "rol o situación de la persona frente a la decisión",
    "industria": "rubro, ocupación o tipo de negocio",
    "objetivo": "qué busca lograr",
    "principal_pain": "principal dolor o problema",
    "motivador": "qué lo mueve a actuar o comprar",
    "objecion_base": "objeción típica antes de comprar o adoptar",
    "sensibilidad_precio": "solo \"Alta\", \"Media\" o \"Baja\" (repetí valores para ponderar)",
    "comportamiento": "estilo de decisión, ej. \"Conservador\", \"Analítico\"",
    "canal_preferido": "canales por los que se informa o compra",
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
    todos = SAMPLED_FIELDS + OPTIONAL_FIELDS
    guia = "\n".join(f"- {campo}: {FIELD_GUIDE[campo]}" for campo in todos)
    campos = ",\n".join(f'        "{campo}": ["...", "...", "..."]' for campo in todos)
    return (
        f"Brief de la audiencia:\n\"\"\"\n{descripcion.strip()}\n\"\"\"\n\n"
        f"Definí entre 2 y {MAX_SEGMENTS - 2} segmentos (o 1 si el brief es claramente homogéneo). "
        "Si el brief menciona segmentos o proporciones, respetalos. Los porcentajes deben sumar 100.\n"
        f"Para cada atributo dá entre 3 y {MAX_VALUES_PER_FIELD} valores posibles, coherentes con ese segmento. "
        "Podés repetir un valor para que salga más seguido.\n\n"
        f"Atributos:\n{guia}\n\n"
        "Respondé solo JSON válido (sin comentarios ni texto extra) con esta forma:\n"
        "{\n"
        '  "segmentos": [\n'
        "    {\n"
        '      "nombre": "Nombre corto del segmento",\n'
        '      "descripcion": "1-2 oraciones sobre quiénes son y su contexto",\n'
        '      "porcentaje": 50,\n'
        '      "atributos": {\n'
        f"{campos}\n"
        "      }\n"
        "    }\n"
        "  ]\n"
        "}"
    )


def _clean_values(values: Any) -> List[str]:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return []
    cleaned = [str(v).strip() for v in values if str(v).strip()]
    return cleaned[:MAX_VALUES_PER_FIELD]


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

        raw_atributos = raw.get("atributos") if isinstance(raw.get("atributos"), dict) else {}
        atributos: Dict[str, List[str]] = {}
        for campo in SAMPLED_FIELDS + OPTIONAL_FIELDS:
            valores = _clean_values(raw_atributos.get(campo))
            if valores:
                atributos[campo] = valores

        perfiles.append(PerfilCliente(
            nombre=nombre,
            descripcion=str(raw.get("descripcion", "")).strip(),
            porcentaje=max(porcentaje, 0.0),
            atributos=atributos,
        ))

    if not perfiles:
        raise AudienceDesignError("El modelo no devolvió segmentos válidos.")
    if not any(p.atributos for p in perfiles):
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
