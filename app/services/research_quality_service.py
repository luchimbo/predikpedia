"""Inspectable evidence gate. The LLM proposes findings; these rules decide readiness."""

from datetime import date
import re
import unicodedata
from urllib.parse import urlsplit
from math import ceil


def normalized(text):
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    return " ".join(text.split())


def contains_quote(text, quote):
    return len(str(quote).strip()) >= 20 and normalized(quote) in normalized(text)


def scope_matches(text, target, *, region=False):
    stop = {"personas", "publico", "gente", "sobre", "entre", "desde", "quienes", "tienen", "region"}
    terms = [t for t in re.findall(r"[a-z]+", normalized(target)) if len(t) >= 4 and t not in stop]
    words = re.findall(r"[a-z]+", normalized(text))
    matched = sum(any(w.startswith(t[:max(4, len(t) - 2)]) for w in words) for t in terms)
    return bool(terms) and matched >= (len(terms) if region else ceil(len(terms) / 2))


# Palabras que describen a toda la población, sin recortar un subgrupo.
GENERAL_TERMS = {"poblacion", "general", "adulta", "adultas", "adulto", "adultos", "persona", "personas", "gente",
                 "habitante", "habitantes", "ciudadano", "ciudadanos", "ciudadania", "residente", "residentes",
                 "mayor", "mayores", "edad", "ano", "anos", "mas", "votante", "votantes", "elector", "electores",
                 "hogar", "hogares", "total", "publico", "toda", "todo", "todas", "todos", "sociedad"}
FILLER = {"de", "del", "la", "las", "los", "el", "en", "con", "y", "o", "que", "a"}


def general_population(brief):
    """True when the audience is everyone in the region, e.g. "población adulta de Argentina"."""
    region = [t for t in re.findall(r"[a-z]+", normalized(brief.region)) if len(t) >= 4]
    rest = [t for t in re.findall(r"[a-z]+", normalized(brief.audience))
            if t not in FILLER and t not in GENERAL_TERMS
            and not any(t.startswith(r[:max(4, len(r) - 2)]) for r in region)]
    return not rest


def document_about_region(document, region):
    """The source names the region (title or text). Weaker than a quote: the model must also mark it direct."""
    terms = [t for t in re.findall(r"[a-z]+", normalized(region)) if len(t) >= 4]
    if not terms:
        return False
    if scope_matches(document.title, region, region=True):
        return True
    words = re.findall(r"[a-z]+", normalized(document.text))
    return all(any(w.startswith(t[:max(4, len(t) - 2)]) for w in words) for t in terms)


def validate_finding(finding, document, brief, dimension):
    issues = []
    if not document or document.status != "read":
        return ["La fuente no fue leída."]
    if not contains_quote(document.text, finding.get("quote", "")):
        issues.append("El fragmento de respaldo no existe en el documento.")
    if finding.get("classification") not in {"documented", "individual_report", "approximation", "assumption"}:
        issues.append("Falta clasificar el hallazgo.")
    scope_ok = {}
    for field, target in (("population_quote", brief.audience), ("region_quote", brief.region)):
        quote = finding.get(field, "")
        scope_ok[field] = contains_quote(document.text, quote) and scope_matches(quote, target, region=field == "region_quote")
    # The backing sentence itself may name the region ("la desocupación en Argentina..."), or the whole
    # source is about it: national news rarely repeats the country in every sentence, and the model often
    # copies only the bare place name as region_quote, which is too short to verify.
    region_quote = str(finding.get("region_quote") or "")
    # A region quote that is not in the source is a fabricated scope and is never overridden.
    if not scope_ok["region_quote"] and normalized(region_quote) in normalized(document.text):
        scope_ok["region_quote"] = any(contains_quote(document.text, finding.get(field, "")) and
                                       scope_matches(finding.get(field, ""), brief.region, region=True)
                                       for field in ("quote", "population_quote")) or document_about_region(document, brief.region)
    # For the whole population of a region, a sourced statistic about that region is already about the
    # audience; national news rarely restates "adult population". Subgroups still need their own quote.
    if general_population(brief) and scope_ok["region_quote"]:
        scope_ok["population_quote"] = True
    if not all(scope_ok.values()):
        issues.append("No se acredita correspondencia con el público y la región.")
    if finding.get("scope") != "direct" or finding.get("classification") in {"approximation", "assumption"}:
        issues.append("La evidencia es aproximada.")
    if finding.get("contradiction"):
        issues.append("Hay una contradicción pendiente.")
    try:
        observed = finding.get("observed_on") or document.published_at
        if document.published_at and date.fromisoformat(document.published_at[:10]) > date.fromisoformat(brief.as_of):
            issues.append("La publicación es posterior al escenario.")
        if finding.get("observed_on") and not contains_quote(document.text, finding.get("date_quote", "")):
            issues.append("La fecha declarada no tiene respaldo textual.")
        if finding.get("observed_on"):
            from dateparser.search import search_dates
            dates = search_dates(finding.get("date_quote", ""), languages=["es", "en"],
                                settings={"STRICT_PARSING": True, "DATE_ORDER": "DMY"}) or []
            if not any(parsed.date().isoformat() == finding["observed_on"] for _, parsed in dates):
                issues.append("La fecha de observación no coincide con el fragmento.")
        if observed and date.fromisoformat(observed[:10]) > date.fromisoformat(brief.as_of):
            issues.append("La evidencia proviene de una fecha posterior al escenario.")
        if dimension.get("max_age_days") is not None:
            age = (date.fromisoformat(brief.as_of) - date.fromisoformat(observed[:10])).days
            if age < 0 or age > int(dimension["max_age_days"]):
                issues.append("La evidencia no corresponde al período del estudio.")
    except (ValueError, TypeError):
        issues.append("Falta una fecha válida para este aspecto.")
    for field in ("origin_quote", "method_quote", "weight_quote"):
        if finding.get(field) and not contains_quote(document.text, finding[field]):
            issues.append("El origen o método declarado no aparece en la fuente.")
    if dimension["id"] == "proportions":
        if finding.get("kind") not in {"survey", "statistics"} or finding.get("classification") != "documented":
            issues.append("Una reseña o comentario no respalda proporciones poblacionales.")
        if not contains_quote(document.text, finding.get("method_quote", "")) or not contains_quote(document.text, finding.get("weight_quote", "")):
            issues.append("Falta el método y la ponderación de la población.")
    return list(dict.fromkeys(issues))


def diagnose(project, documents):
    from app.services.public_search_service import normalize_url
    reserved = {normalize_url(u) for u in project.brief.holdout_urls}
    documents = {d.id: d for d in documents if d.id not in project.excluded_ids and normalize_url(d.url) not in reserved}
    rows, valid_findings, reasons = [], [], []
    if not project.dimensions:
        reasons.append("Todavía no se definieron los aspectos necesarios.")
    for name in project.required_inputs:
        if name == "price" and not project.brief.price.strip():
            reasons.append("Indicá el precio y la moneda de la propuesta propia.")
        elif name == "stimulus" and not project.brief.stimulus.strip():
            reasons.append("Agregá el material exacto que van a evaluar.")
    for dimension in project.dimensions:
        candidates = [f for f in project.findings if f.get("dimension_id") == dimension["id"]
                      and f.get("document_id") in documents]
        good, problems = [], []
        for finding in candidates:
            issues = validate_finding(finding, documents.get(finding.get("document_id")), project.brief, dimension)
            if issues:
                problems.extend(issues)
            else:
                good.append(finding)
        # A data source with method, or corroboration from independent origins, supports a
        # general dimension. A single personal anecdote can only support a personal report.
        origins = {normalized(f.get("origin_quote")) or urlsplit(documents[f["document_id"]].url).hostname for f in good}
        # Identical documents on different hosts still constitute a single observation.
        hashes = {documents[f["document_id"]].content_hash for f in good}
        primary = any(f.get("kind") in {"survey", "statistics", "interview", "technical"}
                      and contains_quote(documents[f["document_id"]].text, f.get("method_quote", "")) for f in good)
        corroborated = primary or (len(origins) >= 2 and len(hashes) >= 2)
        backed = bool(good) and corroborated
        state = "backed" if backed else "approximate" if candidates else "unknown"
        if good and not corroborated:
            problems.append("Falta un origen con método documentado o corroboración independiente.")
        if any(f.get("contradiction") for f in candidates):
            state = "approximate"
            problems.append("Hay una contradicción pendiente.")
        if state == "backed":
            valid_findings.extend(good)
        row = {"id": dimension["id"], "label": dimension["label"], "critical": dimension["critical"],
               "status": state, "reason": dimension["reason"], "issues": list(dict.fromkeys(problems)),
               "finding_ids": [f["id"] for f in good] if state == "backed" else []}
        rows.append(row)
        if row["critical"] and state != "backed":
            reasons.append(f"Falta respaldo suficiente para: {row['label']}.")
    audit = project.audit
    if audit.get("complete") is not True:
        reasons.append("Falta completar la revisión de cobertura, diversidad y contradicciones.")
    for item in audit.get("gaps", []) + audit.get("contradictions", []):
        if item.get("critical", True):
            reasons.append(str(item.get("reason") or "Hay un vacío central sin resolver."))
    eligible = not reasons
    status = "sufficient" if eligible else "limited" if audit.get("suggested_scope") and valid_findings else "insufficient"
    return {"status": status, "can_build": eligible, "brief_signature": project.brief.signature,
            "rows": rows, "reasons": list(dict.fromkeys(reasons)),
            "valid_finding_ids": list(dict.fromkeys(f["id"] for f in valid_findings)),
            "limitations": audit.get("limitations", []), "gaps": audit.get("gaps", []),
            "contradictions": audit.get("contradictions", []), "suggested_scope": audit.get("suggested_scope", ""),
            "precision": "No validada contra respuestas reales",
            "composition": "documented" if project.brief.goal == "proportions" else "balanced_simulation"}
