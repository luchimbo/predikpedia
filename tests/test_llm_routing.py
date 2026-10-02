from datetime import datetime
from types import SimpleNamespace
from unittest import TestCase, mock

from app.services.llm_routing import LLMConfigurationError, load_llm_settings, resolve_provider
from app.services.llm_service import LLMService


def env(**overrides):
    values = {
        "LLM_PROVIDER": "schedule",
        "LLM_SCHEDULE_TIMEZONE": "America/Argentina/Buenos_Aires",
        "LLM_LOCAL_START": "09:30",
        "LLM_LOCAL_END": "17:30",
        "LLM_LOCAL_BASE_URL": "http://localhost:11434/v1",
        "LLM_LOCAL_API_KEY": "x",
        "OPENROUTER_API_KEY": "sk-or-test",
        "OPENROUTER_MODEL": "test-model",
    }
    values.update(overrides)
    return values


class RoutingTests(TestCase):
    def resolve_at(self, when):
        settings = load_llm_settings(env())
        return resolve_provider(settings, when).provider

    def test_before_window_uses_openrouter(self):
        self.assertEqual("openrouter", self.resolve_at(datetime(2026, 1, 2, 9, 29, 59)))

    def test_start_is_local(self):
        self.assertEqual("local", self.resolve_at(datetime(2026, 1, 2, 9, 30, 0)))

    def test_end_minus_one_second_is_local(self):
        self.assertEqual("local", self.resolve_at(datetime(2026, 1, 2, 17, 29, 59)))

    def test_end_is_openrouter(self):
        self.assertEqual("openrouter", self.resolve_at(datetime(2026, 1, 2, 17, 30, 0)))

    def test_manual_overrides_ignore_time(self):
        self.assertEqual("local", resolve_provider(load_llm_settings(env(LLM_PROVIDER="local")), datetime(2026, 1, 2, 23)).provider)
        self.assertEqual("openrouter", resolve_provider(load_llm_settings(env(LLM_PROVIDER="openrouter")), datetime(2026, 1, 2, 10)).provider)

    def test_invalid_values_fail_fast(self):
        with self.assertRaises(LLMConfigurationError):
            load_llm_settings(env(LLM_PROVIDER="other"))
        with self.assertRaises(LLMConfigurationError):
            load_llm_settings(env(LLM_LOCAL_START="17:30", LLM_LOCAL_END="09:30"))
        with self.assertRaises(LLMConfigurationError):
            load_llm_settings(env(LLM_SCHEDULE_TIMEZONE="Mars/Olympus"))

    def test_service_resolves_provider_for_each_generate(self):
        settings_env = env()
        created = []

        class FakeClient:
            def __init__(self, **kwargs):
                created.append(kwargs)
                self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **_: SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]
                )))

        with mock.patch.dict("os.environ", settings_env, clear=False), \
             mock.patch("app.services.llm_service.OpenAI", FakeClient), \
             mock.patch("app.services.llm_service.resolve_provider", side_effect=[
                 SimpleNamespace(provider="local", mode="schedule", scheduled_provider="local"),
                 SimpleNamespace(provider="openrouter", mode="schedule", scheduled_provider="openrouter"),
             ]) as resolver:
            service = LLMService()
            self.assertEqual("ok", service.generate("system", "first", max_retries=1))
            self.assertEqual("ok", service.generate("system", "second", max_retries=1))
        self.assertEqual(2, resolver.call_count)
        self.assertEqual("http://localhost:11434/v1", created[0]["base_url"])
        self.assertEqual("https://openrouter.ai/api/v1", created[1]["base_url"])

    def test_schedule_local_failure_falls_back_to_openrouter(self):
        class FakeClient:
            def __init__(self, **kwargs):
                def create(**_):
                    if kwargs["base_url"] == "http://localhost:11434/v1":
                        raise RuntimeError("relay unavailable")
                    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="fallback ok"))])
                self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))

        resolution = SimpleNamespace(provider="local", mode="schedule", scheduled_provider="local")
        with mock.patch.dict("os.environ", env(), clear=False), \
             mock.patch("app.services.llm_service.OpenAI", FakeClient), \
             mock.patch("app.services.llm_service.resolve_provider", return_value=resolution):
            service = LLMService()
            self.assertEqual("fallback ok", service.generate("system", "prompt", max_retries=1))
        self.assertEqual("openrouter", service.get_request_metadata()["provider"])
        self.assertTrue(service.get_request_metadata()["fallback_used"])
