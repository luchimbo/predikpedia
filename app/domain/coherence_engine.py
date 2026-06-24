"""
app/domain/coherence_engine.py — Middleware de validación de fidelidad humana.

Migrado desde core_logic.py.
"""


class CoherenceEngine:
    """
    Middleware de Cifrado Lógico para Validación de Fidelidad Humana.
    Verifica que las respuestas del LLM no rompan las reglas de oro de la psicometría.
    """

    @staticmethod
    def get_skepticism_threshold(conscientiousness_score: float) -> str:
        """
        Filtro de Resistencia: Un perfil altamente responsable/ordenado (C > 0.7)
        será inherentemente escéptico ante soluciones mágicas o atajos de IA.
        """
        if conscientiousness_score > 0.75:
            return (
                "Tu nivel de Responsabilidad (C) es altísimo. Exiges métricas empíricas "
                "y rechazas de plano cualquier promesa 'mágica' o infundada. Eres "
                "extremadamente resistente a cambiar de proveedor sin pruebas."
            )
        elif conscientiousness_score < 0.3:
            return (
                "Tu nivel de Responsabilidad (C) es bajo. Eres impulsivo, te dejas llevar "
                "por promesas disruptivas y no te importan tanto los riesgos estructurales."
            )
        return (
            "Mides racionalmente las promesas tecnológicas. Pides pruebas pero estás "
            "abierto si soluciona el problema de urgencia."
        )

    @staticmethod
    def build_sincerity_filter_prompt(socioeconomic_level: str) -> str:
        """
        Filtro de Sinceridad: Previene el sesgo alineado (Sycophancy) del LLM
        donde un perfil pobre mágicamente 'acepta gastos' por ser políticamente correcto.
        """
        if socioeconomic_level == "Bajo":
            return (
                "FILTRO DE SINCERIDAD (CRÍTICO): Eres de Nivel Socioeconómico Bajo. "
                "Si en tu respuesta omites el dolor del precio o dices frases como "
                "'el precio no me importa' o 'gastaría sin problemas', DEBES justificar "
                "matemáticamente cómo vas a pagar eso (ej: endeudándote, quitando otro "
                "gasto base) o de lo contrario generarás una contradicción existencial. "
                "Sé crudo y real."
            )
        return ""
