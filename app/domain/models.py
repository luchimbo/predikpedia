"""
app/domain/models.py — Entidades del dominio Predikpedia.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class PerfilCliente:
    nombre: str
    descripcion: str
    porcentaje: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PerfilCliente":
        return cls(
            nombre=str(data.get("nombre", "")).strip(),
            descripcion=str(data.get("descripcion", "")).strip(),
            porcentaje=float(data.get("porcentaje", 0)),
        )


@dataclass
class PersonaSintetica:
    """Persona sintética individual enriquecida para research profundo."""

    persona_id: str
    persona_numero: int
    universo_id: str
    universo_nombre: str
    perfil: str
    perfil_descripcion: str
    perfil_porcentaje_objetivo: float

    # Campos enriquecidos (plan maestro)
    edad_rango: str = ""
    rol: str = ""
    industria: str = ""
    objetivo: str = ""
    principal_pain: str = ""
    motivador: str = ""
    objecion_base: str = ""
    sensibilidad_precio: str = ""
    comportamiento: str = ""
    canal_preferido: str = ""
    contexto_operativo: str = ""
    notas: str = ""

    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PersonaSintetica":
        return cls(
            persona_id=str(data.get("persona_id", "")).strip(),
            persona_numero=int(data.get("persona_numero", 0)),
            universo_id=str(data.get("universo_id", "")).strip(),
            universo_nombre=str(data.get("universo_nombre", "")).strip(),
            perfil=str(data.get("perfil", "")).strip(),
            perfil_descripcion=str(data.get("perfil_descripcion", "")).strip(),
            perfil_porcentaje_objetivo=float(data.get("perfil_porcentaje_objetivo", 0)),
            edad_rango=str(data.get("edad_rango", "")).strip(),
            rol=str(data.get("rol", "")).strip(),
            industria=str(data.get("industria", "")).strip(),
            objetivo=str(data.get("objetivo", "")).strip(),
            principal_pain=str(data.get("principal_pain", "")).strip(),
            motivador=str(data.get("motivador", "")).strip(),
            objecion_base=str(data.get("objecion_base", "")).strip(),
            sensibilidad_precio=str(data.get("sensibilidad_precio", "")).strip(),
            comportamiento=str(data.get("comportamiento", "")).strip(),
            canal_preferido=str(data.get("canal_preferido", "")).strip(),
            contexto_operativo=str(data.get("contexto_operativo", "")).strip(),
            notas=str(data.get("notas", "")).strip(),
            created_at=str(data.get("created_at", _now_iso())),
        )


@dataclass
class Universo:
    id: str
    nombre: str
    descripcion: str
    cantidad_personas: int
    prompt_perfil: str = ""
    perfiles: List[PerfilCliente] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "nombre": self.nombre,
            "descripcion": self.descripcion,
            "cantidad_personas": self.cantidad_personas,
            "prompt_perfil": self.prompt_perfil,
            "perfiles": [p.to_dict() for p in self.perfiles],
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Universo":
        perfiles = [PerfilCliente.from_dict(item) for item in data.get("perfiles", [])]
        return cls(
            id=str(data.get("id", "")).strip(),
            nombre=str(data.get("nombre", "")).strip(),
            descripcion=str(data.get("descripcion", "")).strip(),
            cantidad_personas=int(data.get("cantidad_personas", 0)),
            prompt_perfil=str(data.get("prompt_perfil", "")).strip(),
            perfiles=perfiles,
            created_at=str(data.get("created_at", _now_iso())),
        )


@dataclass
class Estudio:
    id: str
    universo_id: str
    universo_nombre: str
    titulo: str
    pregunta: str
    contexto: str
    template: str = "exploratory"  # Tipo de estudio
    respuestas_por_persona: int = 1
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Estudio":
        return cls(
            id=str(data.get("id", "")).strip(),
            universo_id=str(data.get("universo_id", "")).strip(),
            universo_nombre=str(data.get("universo_nombre", "")).strip(),
            titulo=str(data.get("titulo", "")).strip(),
            pregunta=str(data.get("pregunta", "")).strip(),
            contexto=str(data.get("contexto", "")).strip(),
            template=str(data.get("template", "exploratory")).strip(),
            respuestas_por_persona=int(data.get("respuestas_por_persona", 1)),
            created_at=str(data.get("created_at", _now_iso())),
        )


@dataclass
class RespuestaEstudio:
    estudio_id: str
    persona_id: str
    perfil: str
    repeticion: int
    pregunta: str
    contexto: str
    respuesta: str
    sintesis: str = ""

    # Campos enriquecidos para análisis
    sentiment: str = ""  # positive, negative, neutral, mixed
    intent: str = ""  # comprar, rechazar, explorar, etc.
    main_objection: str = ""
    main_driver: str = ""
    confidence: str = ""  # high, medium, low
    price_sensitivity: str = ""  # high, medium, low, none
    quote: str = ""  # Cita destacada de la respuesta

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RespuestaEstudio":
        return cls(
            estudio_id=str(data.get("estudio_id", "")).strip(),
            persona_id=str(data.get("persona_id", "")).strip(),
            perfil=str(data.get("perfil", "")).strip(),
            repeticion=int(data.get("repeticion", 1)),
            pregunta=str(data.get("pregunta", "")).strip(),
            contexto=str(data.get("contexto", "")).strip(),
            respuesta=str(data.get("respuesta", "")).strip(),
            sintesis=str(data.get("sintesis", "")).strip(),
            sentiment=str(data.get("sentiment", "")).strip(),
            intent=str(data.get("intent", "")).strip(),
            main_objection=str(data.get("main_objection", "")).strip(),
            main_driver=str(data.get("main_driver", "")).strip(),
            confidence=str(data.get("confidence", "")).strip(),
            price_sensitivity=str(data.get("price_sensitivity", "")).strip(),
            quote=str(data.get("quote", "")).strip(),
        )


@dataclass
class ExpansionSnapshot:
    """Snapshot de una expansión de universo."""

    universo_id: str
    universo_nombre: str
    total_personas: int
    personas: List[Dict[str, Any]]
    resumen_perfiles: List[Dict[str, Any]]
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "universo_id": self.universo_id,
            "universo_nombre": self.universo_nombre,
            "total_personas": self.total_personas,
            "personas": self.personas,
            "resumen_perfiles": self.resumen_perfiles,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExpansionSnapshot":
        return cls(
            universo_id=str(data.get("universo_id", "")).strip(),
            universo_nombre=str(data.get("universo_nombre", "")).strip(),
            total_personas=int(data.get("total_personas", 0)),
            personas=data.get("personas", []),
            resumen_perfiles=data.get("resumen_perfiles", []),
            created_at=str(data.get("created_at", _now_iso())),
        )
