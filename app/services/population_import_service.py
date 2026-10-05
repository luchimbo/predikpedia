"""
app/services/population_import_service.py — Audiencias a partir de datos reales.

Cada persona sintética es una fila real (encuesta, base de clientes, padrón):
las proporciones y las combinaciones de atributos salen de los datos, no del
LLM. El modelo solo "actúa" a esa persona cuando responde un estudio.
"""

import io
import random
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

import pandas as pd

from app.domain.models import PerfilCliente, PersonaSintetica, Universo

ROLE_ATTRIBUTE = "atributo"
ROLE_GROUP = "grupo"
ROLE_WEIGHT = "peso"
ROLE_ANSWER = "respuesta real"
ROLE_IGNORE = "ignorar"
ROLES = [ROLE_ATTRIBUTE, ROLE_GROUP, ROLE_WEIGHT, ROLE_ANSWER, ROLE_IGNORE]

DEFAULT_GROUP = "Población real"

# Columnas con datos personales: nunca se mandan al modelo por defecto.
PERSONAL_TOKENS = {
    "nombre", "apellido", "name", "email", "mail", "correo", "dni", "cuit", "cuil",
    "documento", "telefono", "tel", "celular", "phone", "whatsapp", "direccion",
    "domicilio", "address",
}
ID_TOKENS = {"id", "uuid", "codigo", "legajo"}
WEIGHT_TOKENS = {"peso", "ponderador", "ponderacion", "weight", "factor"}
GROUP_TOKENS = {"segmento", "grupo", "perfil", "cluster", "segment", "nse"}


class PopulationImportError(Exception):
    """El archivo o el mapeo no permiten armar una población."""


def _tokens(column: str) -> List[str]:
    text = unicodedata.normalize("NFKD", str(column)).encode("ascii", "ignore").decode().lower()
    return [t for t in re.split(r"[^a-z0-9]+", text) if t]


def read_table(data: bytes, filename: str) -> pd.DataFrame:
    """Lee un CSV (separador y codificación autodetectados) o un Excel."""
    name = filename.lower()
    try:
        if name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(data), dtype=str)
        else:
            df = None
            for encoding in ("utf-8-sig", "latin-1"):
                try:
                    df = pd.read_csv(io.BytesIO(data), sep=None, engine="python", dtype=str, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            if df is None:
                raise PopulationImportError("No se pudo leer la codificación del archivo.")
    except PopulationImportError:
        raise
    except Exception as exc:
        raise PopulationImportError(f"No se pudo leer el archivo: {exc}") from exc

    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all")
    if df.empty or len(df.columns) == 0:
        raise PopulationImportError("El archivo no tiene filas con datos.")
    return df


def is_personal_column(column: str) -> bool:
    return any(t in PERSONAL_TOKENS for t in _tokens(column))


def suggest_mapping(df: pd.DataFrame) -> Dict[str, str]:
    """Propone el rol de cada columna. El usuario puede cambiarlo antes de generar."""
    mapping: Dict[str, str] = {}
    group_taken = False
    for column in df.columns:
        tokens = set(_tokens(column))
        if tokens & PERSONAL_TOKENS or tokens & ID_TOKENS:
            mapping[column] = ROLE_IGNORE
        elif tokens & WEIGHT_TOKENS and _is_numeric(df[column]):
            mapping[column] = ROLE_WEIGHT
        elif tokens & GROUP_TOKENS and not group_taken:
            mapping[column] = ROLE_GROUP
            group_taken = True
        else:
            mapping[column] = ROLE_ATTRIBUTE
    return mapping


def _is_numeric(series: pd.Series) -> bool:
    values = series.dropna().astype(str).str.replace(",", ".", regex=False)
    return not values.empty and pd.to_numeric(values, errors="coerce").notna().all()


def _weights(df: pd.DataFrame, column: str) -> List[float]:
    values = pd.to_numeric(df[column].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    values = values.fillna(0).clip(lower=0)
    if values.sum() <= 0:
        raise PopulationImportError(f"La columna de peso '{column}' no tiene valores positivos.")
    return values.tolist()


def _clean(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none"} else text


def _sample_rows(n_rows: int, cantidad: int, weights: Optional[List[float]], rng: random.Random) -> List[int]:
    """Índices de filas a usar.

    Con pesos se sortea con reposición según el peso. Sin pesos se usan filas
    distintas mientras alcancen y, si se piden más personas que filas, se
    repiten filas al azar después de usar todas una vez.
    """
    indices = list(range(n_rows))
    if weights is not None:
        return rng.choices(indices, weights=weights, k=cantidad)
    if cantidad <= n_rows:
        return rng.sample(indices, cantidad)
    extra = rng.choices(indices, k=cantidad - n_rows)
    todas = indices + extra
    rng.shuffle(todas)
    return todas


def build_population(
    df: pd.DataFrame,
    mapping: Dict[str, str],
    cantidad: int,
    *,
    universe_id: str,
    nombre: str,
    descripcion: str = "",
    fuente: str = "",
) -> Tuple[Universo, List[PersonaSintetica]]:
    """Arma la audiencia: un grupo por valor de la columna `grupo` y una persona por fila sorteada."""
    if cantidad <= 0:
        raise PopulationImportError("La cantidad de personas debe ser mayor a 0.")
    if df.empty:
        raise PopulationImportError("El archivo no tiene filas.")

    attributes = [c for c in df.columns if mapping.get(c) == ROLE_ATTRIBUTE]
    groups = [c for c in df.columns if mapping.get(c) == ROLE_GROUP]
    weight_cols = [c for c in df.columns if mapping.get(c) == ROLE_WEIGHT]
    if len(groups) > 1:
        raise PopulationImportError("Elegí una sola columna como grupo.")
    if len(weight_cols) > 1:
        raise PopulationImportError("Elegí una sola columna como peso.")
    if not attributes and not groups:
        raise PopulationImportError("Marcá al menos una columna como atributo o grupo.")

    df = df.reset_index(drop=True)
    group_col = groups[0] if groups else None
    weights = _weights(df, weight_cols[0]) if weight_cols else None
    row_weights = weights or [1.0] * len(df)

    group_of = [(_clean(df.at[i, group_col]) or "Sin dato") if group_col else DEFAULT_GROUP for i in range(len(df))]
    total_weight = sum(row_weights)
    shares: Dict[str, float] = {}
    for grupo, w in zip(group_of, row_weights):
        shares[grupo] = shares.get(grupo, 0.0) + w

    descripcion_grupo = (
        (lambda g: f"Personas reales con {group_col} = {g}") if group_col
        else (lambda g: "Personas reales del archivo cargado")
    )
    perfiles = [
        PerfilCliente(nombre=g, descripcion=descripcion_grupo(g), porcentaje=round(w * 100 / total_weight, 1))
        for g, w in sorted(shares.items(), key=lambda item: -item[1])
    ]

    universo = Universo(
        id=universe_id,
        nombre=nombre.strip() or "Audiencia desde datos reales",
        descripcion=descripcion.strip(),
        cantidad_personas=cantidad,
        prompt_perfil=descripcion.strip(),
        perfiles=perfiles,
        origen="datos_reales",
        fuente=fuente,
    )

    porcentaje_de = {p.nombre: p.porcentaje for p in perfiles}
    rng = random.Random(universe_id)
    personas: List[PersonaSintetica] = []
    for numero, row in enumerate(_sample_rows(len(df), cantidad, weights, rng), start=1):
        grupo = group_of[row]
        datos = {col: _clean(df.at[row, col]) for col in attributes}
        if group_col:
            datos = {group_col: grupo, **datos}
        personas.append(PersonaSintetica(
            persona_id=f"P_{numero:06d}",
            persona_numero=numero,
            universo_id=universo.id,
            universo_nombre=universo.nombre,
            perfil=grupo,
            perfil_descripcion=descripcion_grupo(grupo),
            perfil_porcentaje_objetivo=porcentaje_de[grupo],
            contexto_operativo=universo.descripcion,
            notas=f"Fila {row + 1} de {fuente or 'los datos reales'}",
            datos_reales={k: v for k, v in datos.items() if v},
        ))
    return universo, personas
