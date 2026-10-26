"""Descifrado y procesamiento entrante OpenPGP."""

from __future__ import annotations

from email import policy
from email.message import EmailMessage

import pytest

from pyqorreos.core.openpgp import (
    OpenPgpSettings,
    decrypt_message,
    process_incoming_message,
)
from tests.conftest import (
    MockDecryptResult,
    MockGpg,
    MockVerifyResult,
    make_inline_encrypted,
    make_multipart_encrypted,
)


def test_decrypt_gpg_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    from pyqorreos.core import openpgp as mod

    monkeypatch.setattr(mod, "get_gpg", lambda *_a, **_k: None)
    inner, status = decrypt_message(make_multipart_encrypted())
    assert inner is None
    assert status.encrypted is True
    assert status.error


def test_decrypt_no_ciphertext(mock_gpg: MockGpg) -> None:
    msg = EmailMessage(policy=policy.default)
    msg.set_content("sin cifrado")
    inner, status = decrypt_message(msg)
    assert inner is None
    assert "No se encontró contenido cifrado" in status.error
    assert mock_gpg.decrypt_calls == []


def test_decrypt_success_plain_inner(mock_gpg: MockGpg) -> None:
    inner_bytes = (
        b"From: a@b.com\r\n"
        b"To: c@d.com\r\n"
        b"Subject: secreto\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"\r\n"
        b"Hola descifrado"
    )
    mock_gpg.decrypt_result = MockDecryptResult(ok=True, data=inner_bytes)
    inner, status = decrypt_message(make_multipart_encrypted())
    assert inner is not None
    assert inner.get("Subject") == "secreto"
    assert status.encrypted is True
    assert status.signed is False


def test_decrypt_success_signed_inner_sig_info(mock_gpg: MockGpg) -> None:
    inner_bytes = (
        b"From: a@b.com\r\n"
        b"Subject: firmado\r\n"
        b"Content-Type: text/plain\r\n"
        b"\r\n"
        b"texto"
    )
    mock_gpg.decrypt_result = MockDecryptResult(
        ok=True,
        data=inner_bytes,
        sig_info=True,
        username="signer@example.com",
    )
    inner, status = decrypt_message(make_multipart_encrypted())
    assert inner is not None
    assert status.encrypted is True
    assert status.signed is True
    assert status.signature_valid is True
    assert status.signer == "signer@example.com"


def test_decrypt_failure_returns_none(mock_gpg: MockGpg) -> None:
    mock_gpg.decrypt_result = MockDecryptResult(ok=False, status="bad passphrase")
    inner, status = decrypt_message(make_multipart_encrypted())
    assert inner is None
    assert status.error


def test_decrypt_cancelled_passphrase(mock_gpg: MockGpg) -> None:
    mock_gpg.decrypt_result = MockDecryptResult(
        ok=False, status="Operation cancelled by user"
    )
    inner, status = decrypt_message(make_multipart_encrypted())
    assert inner is None
    assert status.error == "Descifrado cancelado"


def test_decrypt_timeout(mock_gpg: MockGpg) -> None:
    mock_gpg.decrypt_side_effect = TimeoutError()
    inner, status = decrypt_message(make_multipart_encrypted())
    assert inner is None
    assert "Tiempo de espera" in status.error


def test_process_auto_decrypt_disabled() -> None:
    raw = make_multipart_encrypted().as_bytes()
    msg, status = process_incoming_message(
        raw,
        settings=OpenPgpSettings(enabled=True, auto_decrypt=False),
    )
    assert status.encrypted is True
    assert "desactivado" in status.error.lower()
    assert msg.get_content_type() == "multipart/encrypted"


def test_process_incoming_disabled_skips_decrypt(monkeypatch: pytest.MonkeyPatch) -> None:
    from pyqorreos.core import openpgp as mod

    called = False

    def fake_decrypt(*_a, **_k):
        nonlocal called
        called = True
        return None, mod.PgpStatus()

    monkeypatch.setattr(mod, "decrypt_message", fake_decrypt)
    msg, status = process_incoming_message(
        make_multipart_encrypted().as_bytes(),
        settings=OpenPgpSettings(enabled=False),
    )
    assert not called
    assert status.encrypted is False


def test_process_corrupt_inline(mock_gpg: MockGpg) -> None:
    raw = make_inline_encrypted(complete=False).as_bytes()
    msg, status = process_incoming_message(
        raw,
        settings=OpenPgpSettings(enabled=True),
    )
    assert msg is not None
    assert status.encrypted is True
    assert "dañado" in status.error.lower()
    assert mock_gpg.decrypt_calls == []


def test_process_encrypted_and_signed_combined(mock_gpg: MockGpg) -> None:
    signed_inner = (
        b"Content-Type: multipart/signed; protocol=application/pgp-signature; "
        b'boundary="sig"\r\n'
        b"\r\n"
        b"--sig\r\n"
        b"Content-Type: text/plain\r\n"
        b"\r\n"
        b"Hola\r\n"
        b"--sig\r\n"
        b"Content-Type: application/pgp-signature\r\n"
        b"\r\n"
        b"signature\r\n"
        b"--sig--\r\n"
    )
    mock_gpg.decrypt_result = MockDecryptResult(
        ok=True,
        data=signed_inner,
        sig_info=True,
        username="alice@example.com",
    )
    mock_gpg.verify_result = MockVerifyResult(
        valid=True, username="alice@example.com"
    )

    msg, status = process_incoming_message(
        make_multipart_encrypted().as_bytes(),
        settings=OpenPgpSettings(enabled=True),
    )
    assert msg is not None
    assert status.encrypted is True
    assert status.signed is True
    assert status.signature_valid is True
    assert status.signer == "alice@example.com"
