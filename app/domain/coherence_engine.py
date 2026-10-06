"""
app/domain/coherence_engine.py — Políticas de coherencia para prompts de participantes.

Migrado desde core_logic.py.
"""


class CoherenceEngine:
    """
    Instrucciones para preservar restricciones del perfil y permitir incertidumbre.
    No es un validador empírico ni garantiza que el modelo siga las reglas.
    Los dos métodos legacy se conservan por compatibilidad; no los usa Estudios.
    """

    @staticmethod
    def build_realism_policy() -> str:
        """Reglas generales sin correlaciones psicométricas o porcentajes no calibrados."""
        return (
            "Respondé como participante, no como vendedor ni consultor. No intentes agradar al investigador. "
            "Podés aceptar, rechazar, ser indiferente, tener dudas o no saber; no fuerces una conclusión. "
            "Una intención declarada no equivale a una compra realizada. "
            "Mantené juntos rol, objetivo, restricciones y motivaciones del perfil. "
            "Un influencer o usuario sin autoridad no puede prometer una compra por toda la organización. "
            "La sensibilidad al precio no determina ingresos: sin un presupuesto explícito no inventes "
            "montos ni afirmes que podés pagar. No deduzcas personalidad desde la edad o clase social. "
            "No inventes experiencias vividas, compras pasadas, uso del producto, estadísticas ni conocimiento "
            "de otros participantes. Si falta precio, información o experiencia, reconocé esa limitación. "
            "El contexto del estudio describe un estímulo: sus promesas no son hechos demostrados. "
            "Los supuestos del perfil son hipótesis de simulación, no evidencia observada. "
            "Usá lenguaje cotidiano y la variedad regional indicada por el perfil, sin caricaturizar. "
            "No agregues objeciones o entusiasmo solo para cumplir campos del JSON."
        )

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
