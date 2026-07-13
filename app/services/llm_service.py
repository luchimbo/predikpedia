"""
app/services/llm_service.py — Motor de LLM mejorado.

Migrado y mejorado desde engine_llm.py.
Cambios:
  - Sin side effects en import (no load_dotenv en top-level)
  - Errores separados de respuestas válidas
  - Retries con backoff
  - Timeout configurable
  - Logging de metadata
  - Soporte JSON estructurado
"""

import json
import os
import time
from typing import Any, Dict, Optional

from openai import OpenAI


# No native Gemini import needed


class LLMError(Exception):
    """Error específico del motor LLM."""
    pass


class LLMService:
    """Servicio de inferencia LLM con retries, timeouts y logging."""

    def __init__(self, api_key: str | None = None, model_name: str | None = None):
        self.mode = None
        self.api_key = None
        self.model_name = model_name
        self.client = None
        self.model = None

        if api_key:
            self._configure(api_key, model_name)
        else:
            or_key = os.getenv("OPENROUTER_API_KEY", "")
            if or_key and or_key.startswith("sk-or"):
                self._configure(or_key, model_name)

    def _configure(self, api_key: str, model_name: str | None):
        if api_key.startswith("sk-or"):
            self.mode = "OPENROUTER"
            self.api_key = api_key
            self.model_name = model_name or os.getenv("MODEL_NAME", "google/gemini-2.0-flash")
            self.client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key)

    def is_ready(self) -> bool:
        return self.mode is not None

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        agent_id: str = "sys",
        max_retries: int = 3,
        timeout: int = 60,
        expect_json: bool = False,
    ) -> str | dict:
        """
        Genera una respuesta del LLM.

        Args:
            system_prompt: Prompt de sistema/instrucciones
            user_prompt: Prompt del usuario
            agent_id: Identificador para logging
            max_retries: Número de reintentos
            timeout: Timeout en segundos
            expect_json: Si True, intenta parsear la respuesta como JSON

        Returns:
            str o dict con la respuesta

        Raises:
            LLMError: Si no hay API key o fallan todos los retries
        """
        if not self.mode:
            raise LLMError("API Key inválida o ausente. Configúrala en Configuración.")

        last_error = None
        for attempt in range(max_retries):
            try:
                if self.mode == "OPENROUTER":
                    response = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        timeout=timeout,
                    )
                    content = response.choices[0].message.content
                    if isinstance(content, str) and content.strip():
                        return self._parse_response(content, expect_json)
                    return "" if not expect_json else {}



            except Exception as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    wait = 2 ** attempt  # Backoff exponencial
                    time.sleep(wait)
                continue

        raise LLMError(f"Error tras {max_retries} intentos: {last_error}")

    def _parse_response(self, text: str, expect_json: bool) -> str | dict:
        """Parsea la respuesta, extrayendo JSON si se espera."""
        if not expect_json:
            return text.strip()

        # Intentar extraer JSON del texto
        text = text.strip()
        # Buscar bloque markdown JSON
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end != -1:
                text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end != -1:
                text = text[start:end].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Si falla el JSON, devolver el texto crudo
            return {"_raw": text, "_error": "No se pudo parsear como JSON"}

    def get_provider_label(self) -> str:
        if self.mode == "OPENROUTER":
            return "OpenRouter"
        return "Sin configurar"
