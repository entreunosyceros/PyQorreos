"""La traducción no debe disparar el límite de peticiones de Google."""

import pyqorreos.core.translate as translate


class TooManyRequests(Exception):
    pass


class _FakeTranslator:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[str] = []

    def translate(self, text: str) -> str:
        self.calls.append(text)
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _install(monkeypatch, responses):
    fake = _FakeTranslator(responses)
    monkeypatch.setattr(translate, "_last_request_at", 0.0)
    monkeypatch.setattr(translate, "_get_translator", lambda _lang: fake)
    monkeypatch.setattr(translate.time, "sleep", lambda _seconds: None)
    return fake


def test_subject_and_body_share_one_request(monkeypatch) -> None:
    fake = _install(monkeypatch, ["Hola <<<PYQ>>> cuerpo traducido"])

    body, subject = translate.translate_message("body text", "Hello", "es")

    assert len(fake.calls) == 1
    assert "<<<PYQ>>>" in fake.calls[0]
    assert subject == "Hola"
    assert body == "cuerpo traducido"


def test_retries_when_google_rate_limits(monkeypatch) -> None:
    sleeps: list[float] = []
    fake = _install(monkeypatch, [TooManyRequests("429"), "hola"])
    monkeypatch.setattr(translate.time, "sleep", sleeps.append)

    assert translate.translate_text("hello", "es") == "hola"
    assert len(fake.calls) == 2
    assert 1.0 in sleeps


def test_long_message_waits_between_chunks(monkeypatch) -> None:
    sleeps: list[float] = []
    fake = _install(monkeypatch, ["A", "B", "C"])
    monkeypatch.setattr(translate.time, "sleep", sleeps.append)

    body, subject = translate.translate_message("x" * 4501, "Asunto", "es")

    assert body
    assert subject == "C"
    assert len(fake.calls) == 3
    assert sleeps
    assert all(wait >= translate._MIN_INTERVAL_SEC - 0.01 for wait in sleeps)


def test_gives_up_with_a_short_message(monkeypatch) -> None:
    fake = _install(
        monkeypatch,
        [TooManyRequests("too many requests")] * 5,
    )

    try:
        translate.translate_text("hello", "es")
    except RuntimeError as exc:
        assert "limitado las peticiones" in str(exc)
    else:
        raise AssertionError("debía fallar tras agotar los reintentos")
    assert len(fake.calls) == 5
