"""Tests para reintentos ante fallos transitorios."""

from __future__ import annotations

import imaplib
import socket

import pytest

from pyqorreos.core.retry import call_with_retry, is_retryable_error


def test_is_retryable_socket_timeout() -> None:
    assert is_retryable_error(socket.timeout())


def test_is_retryable_imap_abort() -> None:
    assert is_retryable_error(imaplib.IMAP4.abort())


def test_is_not_retryable_value_error() -> None:
    assert not is_retryable_error(ValueError("bad input"))


def test_call_with_retry_succeeds_first_try() -> None:
    calls = {"n": 0}

    def op() -> str:
        calls["n"] += 1
        return "ok"

    assert call_with_retry(op) == "ok"
    assert calls["n"] == 1


def test_call_with_retry_retries_transient_error(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def op() -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise socket.timeout()
        return "ok"

    monkeypatch.setattr("pyqorreos.core.retry.time.sleep", lambda _s: None)
    assert call_with_retry(op) == "ok"
    assert calls["n"] == 2


def test_call_with_retry_does_not_retry_permanent_error() -> None:
    calls = {"n": 0}

    def op() -> str:
        calls["n"] += 1
        raise ValueError("permanent")

    with pytest.raises(ValueError, match="permanent"):
        call_with_retry(op)
    assert calls["n"] == 1
