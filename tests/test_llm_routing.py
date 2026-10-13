import asyncio
from datetime import datetime
import time
from types import SimpleNamespace
from unittest import TestCase, mock

from app.services.llm_routing import LLMConfigurationError, load_llm_settings, resolve_provider
from app.services.llm_service import LLMError, LLMService


def fake_clients(create):
    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **request: create(kwargs, request)))

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    class FakeAsyncClient(FakeClient):
        def __init__(self, **kwargs):
            async def async_create(**request):
                result = create(kwargs, request)
                return await result if asyncio.iscoroutine(result) else result
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=async_create))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

    return FakeClient, FakeAsyncClient


def response(content="ok"):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


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

    def test_default_is_local_at_all_hours(self):
        values = env()
        del values["LLM_PROVIDER"]
        settings = load_llm_settings(values)
        for hour in (0, 9, 12, 18, 23):
            with self.subTest(hour=hour):
                self.assertEqual("local", resolve_provider(settings, datetime(2026, 1, 2, hour)).provider)

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

        def create(kwargs, _):
            created.append(kwargs)
            return response()
        FakeClient, FakeAsyncClient = fake_clients(create)

        with mock.patch.dict("os.environ", settings_env, clear=False), \
             mock.patch("app.services.llm_service.OpenAI", FakeClient), \
             mock.patch("app.services.llm_service.AsyncOpenAI", FakeAsyncClient), \
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
        def create(kwargs, _):
            if kwargs["base_url"] == "http://localhost:11434/v1":
                raise RuntimeError("relay unavailable")
            return response("fallback ok")
        FakeClient, FakeAsyncClient = fake_clients(create)

        resolution = SimpleNamespace(provider="local", mode="schedule", scheduled_provider="local")
        with mock.patch.dict("os.environ", env(), clear=False), \
             mock.patch("app.services.llm_service.OpenAI", FakeClient), \
             mock.patch("app.services.llm_service.AsyncOpenAI", FakeAsyncClient), \
             mock.patch("app.services.llm_service.resolve_provider", return_value=resolution):
            service = LLMService()
            self.assertEqual("fallback ok", service.generate("system", "prompt", max_retries=1))
        self.assertEqual("openrouter", service.get_request_metadata()["provider"])
        self.assertTrue(service.get_request_metadata()["fallback_used"])

    def test_slow_local_is_cancelled_then_falls_back_with_same_inputs(self):
        calls = []
        cancelled = []

        async def slow_response():
            try:
                await asyncio.sleep(10)
                return response("late local answer")
            finally:
                cancelled.append(True)

        def create(kwargs, request):
            calls.append((kwargs, request))
            return slow_response() if kwargs["base_url"] == "http://localhost:11434/v1" else response('{"answer":"fallback"}')
        FakeClient, FakeAsyncClient = fake_clients(create)

        with mock.patch.dict("os.environ", env(LLM_PROVIDER="local"), clear=True), \
             mock.patch("app.services.llm_service.OpenAI", FakeClient), \
             mock.patch("app.services.llm_service.AsyncOpenAI", FakeAsyncClient), \
             mock.patch("app.services.llm_service.LOCAL_RESPONSE_TIMEOUT_SECONDS", 0.03):
            service = LLMService()
            start = time.monotonic()
            result = service.generate("system", "prompt", timeout=120, expect_json=True, temperature=0.2)
            elapsed = time.monotonic() - start
        self.assertEqual({"answer": "fallback"}, result)
        self.assertLess(elapsed, 1)
        self.assertEqual([True], cancelled)
        self.assertEqual(2, len(calls))  # Only one local attempt, even with default max_retries=3.
        self.assertEqual(0, calls[0][0]["max_retries"])
        self.assertEqual(0.03, calls[0][1]["timeout"])
        self.assertEqual(120, calls[1][1]["timeout"])
        self.assertEqual(calls[0][1]["messages"], calls[1][1]["messages"])
        self.assertEqual(0.2, calls[1][1]["temperature"])
        self.assertEqual("local_timeout", service.get_request_metadata()["fallback_reason"])

    def test_local_success_uses_capped_deadline_and_never_calls_openrouter(self):
        calls = []
        def create(kwargs, request):
            calls.append((kwargs, request))
            return response("local ok")
        _, FakeAsyncClient = fake_clients(create)
        with mock.patch.dict("os.environ", env(LLM_PROVIDER="local"), clear=True), \
             mock.patch("app.services.llm_service.AsyncOpenAI", FakeAsyncClient), \
             mock.patch("app.services.llm_service.OpenAI") as remote:
            service = LLMService()
            self.assertEqual("local ok", service.generate("system", "prompt", timeout=120))
        remote.assert_not_called()
        self.assertEqual(60, calls[0][1]["timeout"])
        self.assertEqual("local", service.get_request_metadata()["provider"])
        self.assertFalse(service.get_request_metadata()["fallback_used"])

    def test_local_error_falls_back_once_and_next_request_tries_local_again(self):
        calls = []
        local_calls = 0
        def create(kwargs, _):
            nonlocal local_calls
            calls.append(kwargs["base_url"])
            if kwargs["base_url"] == "http://localhost:11434/v1":
                local_calls += 1
                if local_calls == 1:
                    raise RuntimeError("relay unavailable")
            return response()
        FakeClient, FakeAsyncClient = fake_clients(create)
        with mock.patch.dict("os.environ", env(LLM_PROVIDER="local"), clear=True), \
             mock.patch("app.services.llm_service.OpenAI", FakeClient), \
             mock.patch("app.services.llm_service.AsyncOpenAI", FakeAsyncClient):
            service = LLMService(api_key="session-key", model_name="session-model")
            self.assertEqual("ok", service.generate("system", "first"))
            self.assertEqual("local_error", service.get_request_metadata()["fallback_reason"])
            self.assertEqual("session-model", service.get_request_metadata()["model"])
            self.assertEqual("ok", service.generate("system", "second"))
        self.assertEqual(["http://localhost:11434/v1", "https://openrouter.ai/api/v1", "http://localhost:11434/v1"], calls)
        self.assertFalse(service.get_request_metadata()["fallback_used"])

    def test_both_providers_fail_raises_error_without_stale_metadata(self):
        def create(*_):
            raise RuntimeError("unavailable")
        FakeClient, FakeAsyncClient = fake_clients(create)
        with mock.patch.dict("os.environ", env(LLM_PROVIDER="local"), clear=True), \
             mock.patch("app.services.llm_service.OpenAI", FakeClient), \
             mock.patch("app.services.llm_service.AsyncOpenAI", FakeAsyncClient):
            service = LLMService()
            service.last_request_metadata = {"provider": "local"}
            with self.assertRaisesRegex(LLMError, "Fallaron proveedor local y fallback OpenRouter"):
                service.generate("system", "prompt", max_retries=1)
        self.assertEqual({}, service.get_request_metadata())

    def test_openrouter_override_does_not_try_local(self):
        FakeClient, _ = fake_clients(lambda *_: response())
        with mock.patch.dict("os.environ", env(LLM_PROVIDER="openrouter"), clear=True), \
             mock.patch("app.services.llm_service.OpenAI", FakeClient), \
             mock.patch("app.services.llm_service.AsyncOpenAI") as local:
            self.assertEqual("ok", LLMService().generate("system", "prompt"))
        local.assert_not_called()
