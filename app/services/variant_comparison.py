"""Paired comparison of two closed-question surveys."""
from collections import Counter

from app.services.calibration_service import distribution
from app.services.model_usage import model_usage
from app.services.study_recovery import response_is_valid


def compare_variants(study_a, study_b, answers_a, answers_b):
    options = study_a.opciones
    if (study_a.variant != "A" or study_b.variant != "B"
            or study_a.paired_study_id != study_b.id or study_b.paired_study_id != study_a.id
            or study_a.universo_id != study_b.universo_id or study_a.pregunta != study_b.pregunta
            or not options or options != study_b.opciones):
        raise ValueError("Los estudios no forman un par A/B compatible.")

    def valid_by_person(answers):
        return {a.persona_id: a for a in answers if response_is_valid(a) and a.opcion_elegida in options}

    a = valid_by_person(answers_a)
    b = valid_by_person(answers_b)
    pairs = [(a[pid], b[pid]) for pid in sorted(a.keys() & b.keys()) if a[pid].perfil == b[pid].perfil]
    profiles = sorted({r.perfil for r in [*answers_a, *answers_b]})
    groups = [("Total", pairs)] + [(p, [(x, y) for x, y in pairs if x.perfil == p]) for p in profiles]
    rows = []
    for name, group in groups:
        rates_a = distribution((x.opcion_elegida for x, _ in group), options)
        rates_b = distribution((y.opcion_elegida for _, y in group), options)
        for option in options:
            rows.append({
                "Segmento": name, "Pares": len(group), "Opción": option,
                "A (%)": round(rates_a[option], 1) if group else None,
                "B (%)": round(rates_b[option], 1) if group else None,
                "B − A (pp)": round(rates_b[option] - rates_a[option], 1) if group else None,
            })

    def objections(responses):
        counts = Counter(r.main_objection.strip() for r in responses if r.main_objection.strip())
        return counts.most_common(3)

    return {
        "model_usage_a": model_usage(x.llm_metadata for x, _ in pairs),
        "model_usage_b": model_usage(y.llm_metadata for _, y in pairs),
        "rows": rows, "pairs": len(pairs), "valid_a": len(a), "valid_b": len(b),
        "objections_a": objections(x for x, _ in pairs),
        "objections_b": objections(y for _, y in pairs),
    }
