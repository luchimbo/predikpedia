"""
app/services/analysis_service.py — Análisis de resultados de estudios.

Migrado y mejorado desde ui_universos.py.
"""

import re
from collections import Counter
from typing import Any, Dict, List

import pandas as pd

from app.domain.models import Estudio, RespuestaEstudio


STOPWORDS_ES = {
    "de", "la", "el", "en", "y", "a", "que", "los", "las", "un", "una", "para", "con", "por",
    "del", "al", "se", "su", "sus", "como", "más", "mas", "es", "son", "lo", "le", "les", "mi",
    "tu", "ya", "si", "sí", "o", "u", "me", "te", "nos", "vos", "yo", "desde", "esta", "este",
    "estos", "estas", "hay", "muy", "porque", "también", "tambien", "sobre", "entre", "sin", "cada",
}


def _tokenize(text: str) -> List[str]:
    """Tokeniza un texto en palabras clave."""
    tokens = re.findall(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ]{3,}", str(text).lower())
    return [t for t in tokens if t not in STOPWORDS_ES]


def top_keywords(texts: List[str], top_n: int = 6) -> List[str]:
    """Extrae las palabras clave más frecuentes de una lista de textos."""
    counter = Counter()
    for text in texts:
        counter.update(_tokenize(text))
    return [word for word, _ in counter.most_common(top_n)]


def insights_by_profile(resultados_df: pd.DataFrame) -> pd.DataFrame:
    """Genera un DataFrame con insights agregados por perfil."""
    if resultados_df.empty:
        return pd.DataFrame(columns=["Perfil", "Personas", "Respuestas", "Largo promedio", "Temas clave"])

    rows: List[Dict[str, Any]] = []
    for perfil, grupo in resultados_df.groupby("perfil"):
        respuestas = grupo["respuesta"].fillna("").astype(str).tolist()
        personas = len(set(grupo["persona_id"].astype(str).tolist()))
        largo_promedio = int(round(sum(len(r) for r in respuestas) / max(len(respuestas), 1)))
        temas = ", ".join(top_keywords(respuestas, top_n=6))
        rows.append({
            "Perfil": perfil,
            "Personas": personas,
            "Respuestas": len(respuestas),
            "Largo promedio": largo_promedio,
            "Temas clave": temas or "-",
        })

    return pd.DataFrame(rows).sort_values(["Respuestas", "Personas"], ascending=False)


def profile_summary(resultados_df: pd.DataFrame) -> Dict[str, str]:
    """Genera un resumen textual por perfil."""
    sintesis: Dict[str, str] = {}
    if resultados_df.empty:
        return sintesis

    for perfil, grupo in resultados_df.groupby("perfil"):
        respuestas = grupo["respuesta"].fillna("").astype(str).tolist()
        top_3 = top_keywords(respuestas, top_n=3)
        primer_fragmento = ""
        if respuestas:
            primer_fragmento = respuestas[0].replace("\n", " ").strip()[:180]
        temas = ", ".join(top_3) if top_3 else "sin temas dominantes"
        if primer_fragmento:
            sintesis[perfil] = f"Temas dominantes: {temas}. Señal textual: {primer_fragmento}"
        else:
            sintesis[perfil] = f"Temas dominantes: {temas}."

    return sintesis


def representative_responses(resultados_df: pd.DataFrame, limit_per_profile: int = 2) -> pd.DataFrame:
    """Extrae respuestas representativas (más largas) por perfil."""
    if resultados_df.empty:
        return pd.DataFrame(columns=["Perfil", "Persona", "Respuesta"])

    rows: List[Dict[str, str]] = []
    for perfil, grupo in resultados_df.groupby("perfil"):
        muestra = grupo.copy()
        muestra["_largo"] = muestra["respuesta"].fillna("").astype(str).str.len()
        muestra = muestra.sort_values("_largo", ascending=False).head(limit_per_profile)
        for _, row in muestra.iterrows():
            rows.append({
                "Perfil": str(perfil),
                "Persona": str(row.get("persona_id", "")),
                "Respuesta": str(row.get("respuesta", "")).replace("\n", " ").strip(),
            })

    return pd.DataFrame(rows)


def filter_by_patterns(resultados_df: pd.DataFrame, patterns: List[str], limit: int = 6) -> List[Dict[str, str]]:
    """Filtra respuestas que coinciden con patrones regex."""
    if resultados_df.empty:
        return []

    pattern = re.compile("|".join(patterns), re.IGNORECASE)
    rows: List[Dict[str, str]] = []
    for _, row in resultados_df.iterrows():
        respuesta = str(row.get("respuesta", "")).replace("\n", " ").strip()
        if respuesta and pattern.search(respuesta):
            rows.append({
                "perfil": str(row.get("perfil", "Perfil sin nombre")),
                "persona_id": str(row.get("persona_id", "")),
                "evidencia": respuesta[:280],
            })
        if len(rows) >= limit:
            break
    return rows


def build_executive_report(estudio: Estudio, resultados_df: pd.DataFrame) -> Dict[str, Any]:
    """Construye un informe ejecutivo completo de un estudio."""
    if resultados_df.empty:
        return {
            "conclusion": "No hay respuestas suficientes para construir un informe ejecutivo.",
            "insights": [],
            "objeciones": [],
            "oportunidades": [],
            "respuestas_destacadas": [],
            "proximas_preguntas": [],
            "markdown": "# Informe ejecutivo\n\nNo hay respuestas suficientes.",
        }

    respuestas = resultados_df["respuesta"].fillna("").astype(str).tolist()
    temas_generales = top_keywords(respuestas, top_n=8)
    insights_df = insights_by_profile(resultados_df)
    representativas_df = representative_responses(resultados_df, limit_per_profile=1)
    perfil_principal = ""
    if not insights_df.empty:
        perfil_principal = str(insights_df.iloc[0].get("Perfil", ""))
    tema_txt = ", ".join(temas_generales[:5]) if temas_generales else "sin temas dominantes claros"

    personas = len(set(resultados_df["persona_id"]))
    conclusion = (
        f"La pregunta concentra {len(resultados_df)} respuesta(s) de "
        f"{personas} persona(s). Los temas más visibles son {tema_txt}."
    )
    if perfil_principal:
        conclusion += f" El perfil con mayor volumen de evidencia es {perfil_principal}."

    # Insights
    insights: List[Dict[str, str]] = []
    for _, row in insights_df.head(5).iterrows():
        perfil = str(row.get("Perfil", "Perfil sin nombre"))
        temas = str(row.get("Temas clave", "-")).strip() or "-"
        respuestas_count = str(row.get("Respuestas", "0"))
        evidencia = ""
        muestra = resultados_df[resultados_df["perfil"].astype(str) == perfil]
        if not muestra.empty:
            evidencia = str(muestra.iloc[0].get("respuesta", "")).replace("\n", " ").strip()[:220]
        insights.append({
            "hallazgo": f"En {perfil}, los temas dominantes son {temas}.",
            "perfil": perfil,
            "evidencia": evidencia,
            "implicancia": f"Este segmento aporta {respuestas_count} respuesta(s); conviene leerlo como señal prioritaria.",
        })

    # Objeciones y oportunidades
    objeciones = filter_by_patterns(
        resultados_df,
        [r"\bno\b", r"duda", r"problema", r"riesgo", r"caro", r"dif[ií]cil", r"falta", r"preocupa", r"desconf", r"pero"],
    )
    oportunidades = filter_by_patterns(
        resultados_df,
        [r"interesa", r"valor", r"ayuda", r"mejor", r"claro", r"facil", r"f[aá]cil", r"necesito", r"conviene", r"usaria", r"usar[ií]a"],
    )
    respuestas_destacadas = representativas_df.to_dict(orient="records") if not representativas_df.empty else []

    proximas_preguntas = [
        f"¿Qué haría que {perfil_principal or 'este perfil'} cambie su respuesta frente a esta pregunta?",
        f"¿Cuáles de estos temas pesan más en la decisión: {tema_txt}?",
        "¿Qué objeción concreta debería resolverse primero para aumentar aceptación?",
        "¿Qué mensaje alternativo sería más creíble para cada perfil?",
    ]

    # Markdown
    md_lines = [
        "# Informe ejecutivo",
        "",
        "## Conclusión principal",
        conclusion,
        "",
        "## Insights clave",
    ]
    if insights:
        for item in insights:
            md_lines.extend([
                f"- {item['hallazgo']}",
                f"  Evidencia: {item['evidencia'] or 'Sin evidencia textual destacada.'}",
                f"  Implicancia: {item['implicancia']}",
            ])
    else:
        md_lines.append("- Sin insights suficientes por perfil.")

    md_lines.extend(["", "## Objeciones y fricciones"])
    if objeciones:
        for item in objeciones:
            md_lines.append(f"- {item['perfil']}: {item['evidencia']}")
    else:
        md_lines.append("- No se detectaron objeciones explícitas.")

    md_lines.extend(["", "## Oportunidades"])
    if oportunidades:
        for item in oportunidades:
            md_lines.append(f"- {item['perfil']}: {item['evidencia']}")
    else:
        md_lines.append("- No se detectaron oportunidades explícitas.")

    md_lines.extend(["", "## Próximas preguntas sugeridas"])
    for pregunta in proximas_preguntas:
        md_lines.append(f"- {pregunta}")

    return {
        "conclusion": conclusion,
        "insights": insights,
        "objeciones": objeciones,
        "oportunidades": oportunidades,
        "respuestas_destacadas": respuestas_destacadas,
        "proximas_preguntas": proximas_preguntas,
        "markdown": "\n".join(md_lines),
    }
