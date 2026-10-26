"""Tests para mensajes de error legibles."""

from __future__ import annotations

import smtplib
import socket

from pyqorreos.core.network_errors import friendly_mail_error


def test_microsoft_country_block_message() -> None:
    exc = smtplib.SMTPRecipientsRefused(
        {
            "user@msn.com": (
                550,
                b"5.7.1 country not allowed",
            )
        }
    )
    msg = friendly_mail_error(exc)
    assert "country not allowed" in msg.lower() or "país" in msg.lower()
    assert "VPN" in msg or "vpn" in msg.lower()


def test_localized_dns_error_is_friendly() -> None:
    exc = socket.gaierror(-2, "Nombre o servicio desconocido")

    assert friendly_mail_error(exc) == (
        "No se encontró el servidor. Revisa el nombre del host IMAP/SMTP."
    )


def test_english_dns_error_is_friendly() -> None:
    exc = socket.gaierror(-2, "Name or service not known")

    assert friendly_mail_error(exc) == (
        "No se encontró el servidor. Revisa el nombre del host IMAP/SMTP."
    )
