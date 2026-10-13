"""Versioned public-evidence dossiers. No synthetic output is source evidence."""

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
import hashlib
import json
import re
from uuid import uuid4
from zoneinfo import ZoneInfo

SCHEMA = "predikpedia.public_evidence/v1"


def stamp():
    return datetime.now(timezone.utc).isoformat()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


@dataclass
class ResearchBrief:
    question: str
    audience: str
    region: str
    stimulus: str = ""
    goal: str = "explore"
    price: str = ""
    situation: str = ""
    as_of: str = ""
    options: list = field(default_factory=list)
    holdout_urls: list = field(default_factory=list)

    def __post_init__(self):
        if not self.as_of:
            self.as_of = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date().isoformat()
        if self.goal not in {"explore", "proportions"}:
            raise ValueError("El objetivo debe ser explorar o estimar proporciones.")
        if any(not value.strip() for value in (self.question, self.audience, self.region)):
            raise ValueError("Completá pregunta, público y región.")
        try:
            date.fromisoformat(self.as_of)
        except ValueError:
            raise ValueError("Indicá la fecha del escenario con formato AAAA-MM-DD.") from None
        if self.price and not re.search(r"gratis|sin costo|gratuit", self.price, re.I):
            if not re.search(r"\d", self.price) or not re.search(r"[$€£]|\b(?:ARS|USD|EUR|BRL|MXN|CLP|COP|PEN|UYU|pesos|d[oó]lares|euros|reales|soles)\b", self.price, re.I):
                raise ValueError("Indicá un monto y su moneda, o aclará si es gratis.")
        if self.options and (not 2 <= len(self.options) <= 12 or any(not isinstance(o, str) or not o.strip() for o in self.options)
                             or len({o.strip().casefold() for o in self.options}) != len(self.options)):
            raise ValueError("Una pregunta cerrada necesita entre 2 y 12 opciones distintas.")
        from app.services.public_search_service import normalize_url
        self.holdout_urls = list(dict.fromkeys(normalize_url(u) for u in self.holdout_urls))

    def to_dict(self):
        return asdict(self)

    @property
    def signature(self):
        return fingerprint(self.to_dict())

    @property
    def participant_stimulus(self):
        return "\n".join(filter(None, (self.stimulus, f"Precio: {self.price}" if self.price else "", self.situation)))


@dataclass
class ResearchDocument:
    id: str
    url: str
    title: str = ""
    text: str = ""
    status: str = "unusable"
    fetched_at: str = field(default_factory=stamp)
    published_at: str = ""
    content_hash: str = ""
    error: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class ResearchProject:
    brief: ResearchBrief
    id: str = field(default_factory=lambda: uuid4().hex)
    schema_version: str = SCHEMA
    created_at: str = field(default_factory=stamp)
    parent_id: str = ""
    dimensions: list = field(default_factory=list)
    required_inputs: list = field(default_factory=list)
    document_ids: list = field(default_factory=list)
    excluded_ids: list = field(default_factory=list)
    queries: list = field(default_factory=list)
    rounds: int = 0
    findings: list = field(default_factory=list)
    audit: dict = field(default_factory=dict)
    diagnosis: dict = field(default_factory=dict)
    events: list = field(default_factory=list)
    stage: str = "brief"
    universe_id: str = ""
    snapshot_id: str = ""

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        if value.get("schema_version") != SCHEMA:
            raise ValueError("El expediente usa una versión no compatible.")
        return cls(**{**value, "brief": ResearchBrief(**value["brief"])})
