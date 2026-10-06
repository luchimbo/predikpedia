"""
app/domain/models.py — Entidades del dominio Predikpedia.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class ArquetipoPersona:
    """Combinación conjunta de atributos; peso relativo dentro del segmento."""

    nombre: str
    peso: float
    atributos: Dict[str, str]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArquetipoPersona":
        return cls(
            nombre=str(data.get("nombre", "")).strip(),
            peso=float(data.get("peso", 1)),
            atributos={str(k): v.strip() for k, v in (data.get("atributos") or {}).items()
                       if isinstance(v, str) and v.strip()},
        )


@dataclass
class PerfilCliente:
    nombre: str
    descripcion: str
    porcentaje: float
    # Valores posibles por campo de PersonaSintetica (edad_rango, rol, ...).
    # Vacío = la expansión usa los valores genéricos.
    atributos: Dict[str, List[str]] = field(default_factory=dict)
    arquetipos: List[ArquetipoPersona] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PerfilCliente":
        raw_atributos = data.get("atributos") or {}
        atributos = {
            str(key): [str(v).strip() for v in values if str(v).strip()]
            for key, values in raw_atributos.items()
            if isinstance(values, list)
        } if isinstance(raw_atributos, dict) else {}
        return cls(
            nombre=str(data.get("nombre", "")).strip(),
            descripcion=str(data.get("descripcion", "")).strip(),
            porcentaje=float(data.get("porcentaje", 0)),
            atributos={k: v for k, v in atributos.items() if v},
            arquetipos=[ArquetipoPersona.from_dict(item) for item in data.get("arquetipos", [])],
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

    # Identifica la combinación conjunta usada, sin alterar los campos anteriores.
    arquetipo: str = ""
    identity_id: str = ""
    evidence_refs: List[str] = field(default_factory=list)
    evidence_source_ids: List[str] = field(default_factory=list)

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
            arquetipo=str(data.get("arquetipo", "")).strip(),
            identity_id=str(data.get("identity_id", "")),
            evidence_refs=list(data.get("evidence_refs") or []),
            evidence_source_ids=list(data.get("evidence_source_ids") or []),
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
    evidence_source_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "nombre": self.nombre,
            "descripcion": self.descripcion,
            "cantidad_personas": self.cantidad_personas,
            "prompt_perfil": self.prompt_perfil,
            "perfiles": [p.to_dict() for p in self.perfiles],
            "created_at": self.created_at,
            "evidence_source_ids": self.evidence_source_ids,
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
            evidence_source_ids=list(data.get("evidence_source_ids") or []),
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
    simulation_version: str = "legacy"
    mode: str = "survey"
    memory_enabled: bool = False
    follow_up_questions: List[str] = field(default_factory=list)
    social_seed: int = 42
    interaction_graph: Dict[str, List[str]] = field(default_factory=dict)

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
            simulation_version=str(data.get("simulation_version", "legacy")),
            mode=str(data.get("mode", "survey")),
            memory_enabled=data.get("memory_enabled") is True,
            follow_up_questions=list(data.get("follow_up_questions") or []),
            social_seed=int(data.get("social_seed", 42)),
            interaction_graph=dict(data.get("interaction_graph") or {}),
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
    response_id: str = ""
    identity_id: str = ""
    phase: str = "individual"
    round_number: int = 1
    question_index: int = 1
    evidence_refs: List[str] = field(default_factory=list)
    memory_refs: List[str] = field(default_factory=list)
    exposure_ids: List[str] = field(default_factory=list)
    llm_metadata: Dict[str, Any] = field(default_factory=dict)

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
            response_id=str(data.get("response_id", "")),
            identity_id=str(data.get("identity_id", "")),
            phase=str(data.get("phase", "individual")),
            round_number=int(data.get("round_number", 1)),
            question_index=int(data.get("question_index", 1)),
            evidence_refs=list(data.get("evidence_refs") or []),
            memory_refs=list(data.get("memory_refs") or []),
            exposure_ids=list(data.get("exposure_ids") or []),
            llm_metadata=dict(data.get("llm_metadata") or {}),
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
