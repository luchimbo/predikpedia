"""Deterministic LLM provider selection, evaluated for every request."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, time
from typing import Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class LLMConfigurationError(ValueError):
    """Raised when the LLM environment configuration is invalid."""


@dataclass(frozen=True)
class LLMSettings:
    provider_mode: str
    timezone: ZoneInfo
    local_start: time
    local_end: time
    local_base_url: str
    local_model: str
    local_api_key: str
    openrouter_api_key: str
    openrouter_model: str


@dataclass(frozen=True)
class ProviderResolution:
    provider: str  # "local" or "openrouter"
    mode: str
    scheduled_provider: str | None


def _required(env: Mapping[str, str], key: str, default: str = "") -> str:
    return env.get(key, default).strip()


def _parse_time(value: str, key: str) -> time:
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise LLMConfigurationError(f"{key} debe usar formato HH:MM (recibido: {value!r}).") from exc


def load_llm_settings(env: Mapping[str, str] | None = None) -> LLMSettings:
    """Read and validate routing configuration without checking provider secrets."""
    source = os.environ if env is None else env
    mode = _required(source, "LLM_PROVIDER", "schedule").lower()
    if mode not in {"schedule", "local", "openrouter"}:
        raise LLMConfigurationError("LLM_PROVIDER debe ser schedule, local u openrouter.")

    timezone_name = _required(source, "LLM_SCHEDULE_TIMEZONE", "America/Argentina/Buenos_Aires")
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise LLMConfigurationError(f"LLM_SCHEDULE_TIMEZONE no es válida: {timezone_name!r}.") from exc

    start = _parse_time(_required(source, "LLM_LOCAL_START", "09:30"), "LLM_LOCAL_START")
    end = _parse_time(_required(source, "LLM_LOCAL_END", "17:30"), "LLM_LOCAL_END")
    if start >= end:
        raise LLMConfigurationError("LLM_LOCAL_START debe ser anterior a LLM_LOCAL_END; no se admiten franjas nocturnas.")

    return LLMSettings(
        provider_mode=mode,
        timezone=timezone,
        local_start=start,
        local_end=end,
        local_base_url=_required(source, "LLM_LOCAL_BASE_URL").rstrip("/"),
        local_model=_required(source, "LLM_LOCAL_MODEL", "qwen2.5:32b"),
        local_api_key=_required(source, "LLM_LOCAL_API_KEY"),
        openrouter_api_key=_required(source, "OPENROUTER_API_KEY"),
        openrouter_model=_required(source, "OPENROUTER_MODEL", "google/gemini-2.5-flash-lite"),
    )


def resolve_provider(settings: LLMSettings, now: datetime | None = None) -> ProviderResolution:
    """Select provider. Schedule is start-inclusive and end-exclusive."""
    if settings.provider_mode in {"local", "openrouter"}:
        return ProviderResolution(settings.provider_mode, settings.provider_mode, None)

    current = now or datetime.now(settings.timezone)
    if current.tzinfo is None:
        current = current.replace(tzinfo=settings.timezone)
    local_now = current.astimezone(settings.timezone).time().replace(tzinfo=None)
    scheduled = "local" if settings.local_start <= local_now < settings.local_end else "openrouter"
    return ProviderResolution(scheduled, "schedule", scheduled)


def validate_provider_settings(settings: LLMSettings, provider: str) -> None:
    if provider == "local":
        if not settings.local_base_url:
            raise LLMConfigurationError("Falta LLM_LOCAL_BASE_URL para el proveedor local.")
        if not settings.local_api_key:
            raise LLMConfigurationError("Falta LLM_LOCAL_API_KEY para el proveedor local.")
    elif provider == "openrouter" and not settings.openrouter_api_key:
        raise LLMConfigurationError("Falta OPENROUTER_API_KEY para OpenRouter.")
