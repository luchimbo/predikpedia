"""LLM service with request-time provider routing and safe operational metadata."""

from __future__ import annotations

import json
import os
import time
from typing import Any

from openai import OpenAI

from app.services.llm_routing import (
    LLMConfigurationError,
    ProviderResolution,
    load_llm_settings,
    resolve_provider,
    validate_provider_settings,
)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class LLMError(Exception):
    """Failure returned by the inference layer, never a valid LLM response."""


class LLMService:
    """OpenAI-compatible inference service.

    Provider selection deliberately happens in :meth:`generate`, not in the
    constructor, so long-running studies respect the schedule on each request.
    """

    def __init__(self, api_key: str | None = None, model_name: str | None = None):
        self._session_openrouter_key = api_key
        self._session_openrouter_model = model_name
        self.last_request_metadata: dict[str, Any] = {}

    def _settings(self):
        try:
            settings = load_llm_settings()
        except LLMConfigurationError as exc:
            raise LLMError(str(exc)) from exc
        if self._session_openrouter_key:
            # A key entered in Streamlit is an OpenRouter session override only.
            settings = settings.__class__(
                **{**settings.__dict__, "openrouter_api_key": self._session_openrouter_key,
                   "openrouter_model": self._session_openrouter_model or settings.openrouter_model}
            )
        return settings

    def _client_for(self, provider: str, settings):
        try:
            validate_provider_settings(settings, provider)
        except LLMConfigurationError as exc:
            raise LLMError(str(exc)) from exc
        if provider == "local":
            return OpenAI(base_url=settings.local_base_url, api_key=settings.local_api_key), settings.local_model
        return OpenAI(base_url=OPENROUTER_BASE_URL, api_key=settings.openrouter_api_key), settings.openrouter_model

    def is_ready(self) -> bool:
        try:
            settings = self._settings()
            resolution = resolve_provider(settings)
            validate_provider_settings(settings, resolution.provider)
            return True
        except (LLMError, LLMConfigurationError):
            return False

    def get_request_metadata(self) -> dict[str, Any]:
        """Return non-secret metadata for the most recent request."""
        return dict(self.last_request_metadata)

    def _generate_with_provider(
        self, provider: str, settings, system_prompt: str, user_prompt: str,
        max_retries: int, timeout: int, expect_json: bool,
    ) -> str | dict:
        client, model = self._client_for(provider, settings)
        last_error: Exception | None = None
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    timeout=timeout,
                )
                content = response.choices[0].message.content
                return self._parse_response(content or "", expect_json)
            except Exception as exc:  # provider errors are normalized below
                last_error = exc
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        raise LLMError(f"{provider} no respondió tras {max_retries} intentos: {last_error}")

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        agent_id: str = "sys",
        max_retries: int = 3,
        timeout: int = 60,
        expect_json: bool = False,
    ) -> str | dict:
        del agent_id  # reserved for caller logging; never sent to the provider
        settings = self._settings()
        resolution: ProviderResolution = resolve_provider(settings)
        fallback_used = False
        selected_provider = resolution.provider
        try:
            result = self._generate_with_provider(
                selected_provider, settings, system_prompt, user_prompt, max_retries, timeout, expect_json
            )
        except LLMError as local_error:
            if resolution.mode == "schedule" and selected_provider == "local":
                fallback_used = True
                selected_provider = "openrouter"
                try:
                    result = self._generate_with_provider(
                        selected_provider, settings, system_prompt, user_prompt, max_retries, timeout, expect_json
                    )
                except LLMError as fallback_error:
                    raise LLMError(f"Fallaron proveedor local y fallback OpenRouter: {fallback_error}") from fallback_error
            else:
                raise local_error

        model = settings.local_model if selected_provider == "local" else settings.openrouter_model
        self.last_request_metadata = {
            "provider": selected_provider,
            "model": model,
            "mode": resolution.mode,
            "scheduled_provider": resolution.scheduled_provider,
            "fallback_used": fallback_used,
        }
        return result

    @staticmethod
    def _parse_response(text: str, expect_json: bool) -> str | dict:
        text = text.strip()
        if not expect_json:
            return text
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            text = text[start:end].strip() if end != -1 else text[start:].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            text = text[start:end].strip() if end != -1 else text[start:].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"_raw": text, "_error": "No se pudo parsear como JSON"}

    def get_provider_label(self) -> str:
        try:
            resolution = resolve_provider(self._settings())
            return "Ollama local" if resolution.provider == "local" else "OpenRouter"
        except LLMError:
            return "Sin configurar"
