"""
Reintentos ligeros ante fallos transitorios de red o servidor.
"""

from __future__ import annotations

import imaplib
import smtplib
import socket
import ssl
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

_RETRYABLE_TYPES = (
    socket.timeout,
    TimeoutError,
    ConnectionResetError,
    ConnectionAbortedError,
    BrokenPipeError,
    imaplib.IMAP4.abort,
)


def is_retryable_error(exc: BaseException) -> bool:
    """Indica si conviene reintentar la operación una vez más."""
    if isinstance(exc, _RETRYABLE_TYPES):
        return True
    if isinstance(exc, OSError) and "timed out" in str(exc).lower():
        return True
    if isinstance(exc, ssl.SSLError):
        return True
    if isinstance(exc, (imaplib.IMAP4.error, smtplib.SMTPException)):
        lowered = str(exc).lower()
        if "temporary" in lowered or "try again" in lowered or "4.7" in lowered:
            return True
    return False


def call_with_retry(
    operation: Callable[[], T],
    *,
    max_attempts: int = 2,
    delay_sec: float = 1.5,
) -> T:
    """Ejecuta operation; reintenta una vez si el error parece transitorio."""
    last: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return operation()
        except BaseException as exc:
            last = exc
            if attempt + 1 >= max_attempts or not is_retryable_error(exc):
                raise
            time.sleep(delay_sec)
    assert last is not None
    raise last
