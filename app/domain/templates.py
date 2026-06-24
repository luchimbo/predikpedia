"""
app/domain/templates.py — Templates de estudio research.

Cada template define:
  - Inputs esperados
  - Prompt base
  - Estructura de salida
  - Métricas sugeridas
  - Vista de resultados sugerida
"""

from typing import Dict, List


STUDY_TEMPLATES: Dict[str, Dict] = {
    "exploratory": {
        "id": "exploratory",
        "title": "Exploratorio",
        "description": "Entrevista abierta para descubrir necesidades, dolores y comportamientos.",
        "icon": "🔍",
        "inputs": ["pregunta_principal", "contexto"],
        "prompt_base": (
            "Actuá como la persona descrita en tu perfil. Respondé la siguiente pregunta "
            "de forma abierta y honesta, en primera persona. Sé específico sobre tu contexto, "
            "necesidades y limitaciones. No uses lenguaje corporativo genérico."
        ),
        "output_structure": {
            "response_text": "Respuesta completa en primera persona",
            "sentiment": "positive | negative | neutral | mixed",
            "intent": "explorar | comprar | rechazar | comparar",
            "main_objection": "Principal objeción o fricción",
            "main_driver": "Principal motivador o driver",
            "confidence": "high | medium | low",
            "quote": "Cita destacada de la respuesta",
        },
        "metrics": ["sentiment_distribution", "intent_breakdown", "top_objections", "top_drivers"],
        "result_view": "executive_summary_first",
    },
    "concept_test": {
        "id": "concept_test",
        "title": "Concept Test",
        "description": "Validá una idea o concepto de producto con reacciones sintéticas.",
        "icon": "💡",
        "inputs": ["pregunta_principal", "contexto", "concepto"],
        "prompt_base": (
            "Te presentan el siguiente concepto de producto/servicio. Desde tu perfil y contexto, "
            "respondé: ¿te interesaría? ¿Por qué sí o por qué no? Sé específico sobre qué parte "
            "del concepto resuena con vos y qué parte genera dudas."
        ),
        "output_structure": {
            "response_text": "Respuesta completa",
            "sentiment": "positive | negative | neutral | mixed",
            "intent": "comprar | rechazar | explorar | comparar",
            "main_objection": "Principal objeción al concepto",
            "main_driver": "Principal motivador para aceptar",
            "confidence": "high | medium | low",
            "price_sensitivity": "high | medium | low | none",
            "quote": "Cita destacada",
        },
        "metrics": ["acceptance_rate", "top_objections", "price_sensitivity", "concept_clarity"],
        "result_view": "concept_scorecard",
    },
    "messaging_test": {
        "id": "messaging_test",
        "title": "Messaging Test",
        "description": "Compará mensajes, subject lines o copy para ver cuál resuena más.",
        "icon": "💬",
        "inputs": ["pregunta_principal", "contexto", "mensaje_a", "mensaje_b"],
        "prompt_base": (
            "Te presentan dos mensajes. Desde tu perfil, indicá cuál te resulta más convincente "
            "y por qué. Sé específico sobre qué palabras o frases generan confianza o desconfianza."
        ),
        "output_structure": {
            "response_text": "Respuesta completa",
            "sentiment": "positive | negative | neutral | mixed",
            "intent": "comprar | rechazar | explorar | comparar",
            "main_objection": "Principal objeción",
            "main_driver": "Principal motivador",
            "confidence": "high | medium | low",
            "preferred_variant": "A | B | indiferente",
            "quote": "Cita destacada",
        },
        "metrics": ["variant_preference", "message_clarity", "trust_score", "top_objections"],
        "result_view": "comparison",
    },
    "pricing_test": {
        "id": "pricing_test",
        "title": "Pricing Test",
        "description": "Descubrí disposición a pagar y sensibilidad al precio.",
        "icon": "💰",
        "inputs": ["pregunta_principal", "contexto", "precio_propuesto"],
        "prompt_base": (
            "Te ofrecen un producto/servicio a un precio determinado. Desde tu perfil económico "
            "y contexto, respondé: ¿estarías dispuesto a pagar eso? ¿Por qué sí o por qué no? "
            "Sé crudo y realista sobre tu presupuesto."
        ),
        "output_structure": {
            "response_text": "Respuesta completa",
            "sentiment": "positive | negative | neutral | mixed",
            "intent": "comprar | rechazar | explorar | comparar",
            "main_objection": "Principal objeción de precio",
            "main_driver": "Principal motivador",
            "confidence": "high | medium | low",
            "price_sensitivity": "high | medium | low | none",
            "quote": "Cita destacada",
        },
        "metrics": ["price_acceptance", "sensitivity_distribution", "willingness_to_pay", "top_objections"],
        "result_view": "pricing_scorecard",
    },
    "feature_feedback": {
        "id": "feature_feedback",
        "title": "Feature Feedback",
        "description": "Obtené feedback sobre funcionalidades específicas.",
        "icon": "⚙️",
        "inputs": ["pregunta_principal", "contexto", "feature_descripcion"],
        "prompt_base": (
            "Te presentan una funcionalidad específica. Desde tu perfil y necesidades, respondé: "
            "¿te sería útil? ¿La usarías? ¿Qué le cambiarías? Sé específico y honesto."
        ),
        "output_structure": {
            "response_text": "Respuesta completa",
            "sentiment": "positive | negative | neutral | mixed",
            "intent": "comprar | rechazar | explorar | comparar",
            "main_objection": "Principal objeción",
            "main_driver": "Principal motivador",
            "confidence": "high | medium | low",
            "quote": "Cita destacada",
        },
        "metrics": ["usefulness_score", "adoption_likelihood", "improvement_suggestions", "top_objections"],
        "result_view": "feature_scorecard",
    },
}


def get_template(template_id: str) -> Dict | None:
    """Obtiene un template por ID."""
    return STUDY_TEMPLATES.get(template_id)


def list_templates() -> List[Dict]:
    """Lista todos los templates disponibles."""
    return list(STUDY_TEMPLATES.values())


def build_system_prompt(template_id: str, persona_profile: str, context: str = "") -> str:
    """Construye el system prompt para un template y persona."""
    template = get_template(template_id)
    if not template:
        return persona_profile

    base = template["prompt_base"]
    ctx = f"\n\nContexto: {context}" if context else ""
    return (
        f"{persona_profile}\n\n"
        f"INSTRUCCIONES DEL ESTUDIO:\n"
        f"{base}{ctx}\n\n"
        f"Respondé en primera persona, con realismo y consistencia con tu perfil. "
        f"Sé concreto y accionable en máximo 150 palabras."
    )


def build_json_prompt(template_id: str, user_question: str) -> str:
    """Construye el user prompt pidiendo salida JSON estructurada."""
    template = get_template(template_id)
    if not template:
        return user_question

    structure = template["output_structure"]
    fields = "\n".join([f'  "{k}": "..."' for k in structure.keys()])

    return (
        f"{user_question}\n\n"
        f"Respondé en formato JSON con exactamente estos campos:\n"
        f"{{{fields}\n}}"
    )
