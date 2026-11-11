"""Summarize provenance for the exact answers included in a result."""
from collections import Counter


def model_usage(metadata):
    counts = Counter()
    fallback = 0
    for item in metadata:
        item = item if isinstance(item, dict) else {}
        counts[str(item.get("provider") or "Sin registro"), str(item.get("model") or "Sin registro")] += 1
        fallback += item.get("fallback_used") is True
    return counts, fallback


def usage_rows(counts):
    total = sum(counts.values())
    return [{"Proveedor": provider, "Modelo": model, "Respuestas": count,
             "%": round(count * 100 / total, 1)}
            for (provider, model), count in sorted(counts.items())]
