"""LLM service with request-time provider routing and safe operational metadata."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, InternalServerError, OpenAI

from app.services.llm_routing import (
    LLMConfigurationError,
    ProviderResolution,
    load_llm_settings,
    resolve_provider,
    validate_provider_settings,
)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LOCAL_RESPONSE_TIMEOUT_SECONDS = 60
# Ollama restarts its runner after a crash and reloads the model before answering again.
LOCAL_SERVER_RETRY_DELAY_SECONDS = 20


class LLMError(Exception):
    """Failure returned by the inference layer, never a valid LLM response."""


class LLMLocalTimeout(LLMError):
    """The complete local response exceeded its time budget."""


class LLMLocalServerError(LLMError):
    """Ollama failed or dropped the connection (e.g. its runner crashed)."""


class LLMService:
    """OpenAI-compatible inference service.

    Provider selection deliberately happens in :meth:`generate`, not in the
    constructor. Local inference has a total deadline and OpenRouter fallback.
    """

    def __init__(self, api_key: str | None = None, model_name: str | None = None, *, local_only: bool = False):
        self.local_only = local_only
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

    def _client_for(self, provider: str, settings, *, asynchronous: bool = False):
        try:
            validate_provider_settings(settings, provider)
        except LLMConfigurationError as exc:
            raise LLMError(str(exc)) from exc
        client_class = AsyncOpenAI if asynchronous else OpenAI
        # Retries are owned by this service, so SDK retries cannot extend the deadline.
        if provider == "local":
            return client_class(base_url=settings.local_base_url, api_key=settings.local_api_key, max_retries=0), settings.local_model
        return client_class(base_url=OPENROUTER_BASE_URL, api_key=settings.openrouter_api_key, max_retries=0), settings.openrouter_model

    def is_ready(self) -> bool:
        try:
            settings = self._settings()
            resolution = (ProviderResolution("local", "local_only", None) if self.local_only else resolve_provider(settings))
            validate_provider_settings(settings, resolution.provider)
            return True
        except (LLMError, LLMConfigurationError):
            return False

    def get_request_metadata(self) -> dict[str, Any]:
        """Return non-secret metadata for the most recent request."""
        return dict(self.last_request_metadata)

    def _generate_local_with_deadline(
        self, settings, system_prompt: str, user_prompt: str,
        timeout: int, expect_json: bool, temperature: float | None,
    ) -> str | dict:
        budget = min(timeout, LOCAL_RESPONSE_TIMEOUT_SECONDS)

        async def request():
            client, model = self._client_for("local", settings, asynchronous=True)
            async with client:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    timeout=budget,
                    **({"temperature": temperature} if temperature is not None else {}),
                )
                return self._parse_response(response.choices[0].message.content or "", expect_json)

        async def bounded_request():
            # Covers the whole response, including a body arriving in slow chunks.
            # Cancellation closes the HTTP client before starting the fallback.
            return await asyncio.wait_for(request(), timeout=budget)

        try:
            return asyncio.run(bounded_request())
        except (TimeoutError, APITimeoutError) as exc:
            raise LLMLocalTimeout(f"Ollama superó el límite de {budget} segundos.") from exc
        except LLMError:
            raise
        except (InternalServerError, APIConnectionError) as exc:
            raise LLMLocalServerError(f"local no respondió: {exc}") from exc
        except Exception as exc:
            raise LLMError(f"local no respondió: {exc}") from exc

    def _generate_with_provider(
        self, provider: str, settings, system_prompt: str, user_prompt: str,
        max_retries: int, timeout: int, expect_json: bool, temperature: float | None = None,
    ) -> str | dict:
        if provider == "local":
            return self._generate_local_with_deadline(
                settings, system_prompt, user_prompt, timeout, expect_json, temperature
            )
        client, model = self._client_for(provider, settings)
        # Sin temperature explícita cada proveedor usa la suya y los estudios no son comparables.
        extra = {"temperature": temperature} if temperature is not None else {}
        last_error: Exception | None = None
        with client:
            for attempt in range(max_retries):
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        timeout=timeout,
                        **extra,
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
        temperature: float | None = None,
    ) -> str | dict:
        del agent_id  # reserved for caller logging; never sent to the provider
        self.last_request_metadata = {}
        settings = self._settings()
        resolution: ProviderResolution = (ProviderResolution("local", "local_only", None)
                                          if self.local_only else resolve_provider(settings))
        fallback_used = False
        fallback_reason = None
        selected_provider = resolution.provider
        try:
            try:
                result = self._generate_with_provider(
                    selected_provider, settings, system_prompt, user_prompt, max_retries, timeout, expect_json, temperature
                )
            except LLMLocalServerError:
                if not self.local_only:
                    raise
                # Without a remote fallback, give a crashed Ollama runner one chance to come back.
                time.sleep(LOCAL_SERVER_RETRY_DELAY_SECONDS)
                result = self._generate_with_provider(
                    selected_provider, settings, system_prompt, user_prompt, max_retries, timeout, expect_json, temperature
                )
        except LLMError as local_error:
            if selected_provider == "local" and not self.local_only:
                fallback_used = True
                fallback_reason = "local_timeout" if isinstance(local_error, LLMLocalTimeout) else "local_error"
                selected_provider = "openrouter"
                try:
                    result = self._generate_with_provider(
                        selected_provider, settings, system_prompt, user_prompt, max_retries, timeout, expect_json, temperature
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
            "fallback_reason": fallback_reason,
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
