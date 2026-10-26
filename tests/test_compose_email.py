"""Tests para utilidades de composición de correo."""

from __future__ import annotations

from email.message import EmailMessage

from pyqorreos.core.compose_email import apply_read_receipt_headers, parse_read_receipt_request


def test_apply_read_receipt_headers() -> None:
    msg = EmailMessage()
    apply_read_receipt_headers(msg, "sender@example.com")
    assert msg["Disposition-Notification-To"] == "sender@example.com"


def test_parse_read_receipt_request() -> None:
    msg = EmailMessage()
    msg["Disposition-Notification-To"] = "reader@example.com"
    assert parse_read_receipt_request(msg) == "reader@example.com"
