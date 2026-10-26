"""Verificación de firmas OpenPGP."""

from __future__ import annotations

import pytest

from pyqorreos.core.openpgp import (
    OpenPgpSettings,
    process_incoming_message,
    verify_signature,
    verify_signed_message,
)
from tests.conftest import (
    MockGpg,
    MockVerifyResult,
    make_inline_signed,
    make_multipart_signed,
)


def test_verify_alias_points_to_same_function() -> None:
    assert verify_signature is verify_signed_message


def test_verify_gpg_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    from pyqorreos.core import openpgp as mod

    monkeypatch.setattr(mod, "get_gpg", lambda *_a, **_k: None)
    status = verify_signed_message(make_multipart_signed())
    assert status.signed is True
    assert status.signature_valid is False
    assert status.error


def test_verify_multipart_signed_missing_signature_part(mock_gpg: MockGpg) -> None:
    from email import policy
    from email.message import EmailMessage

    msg = EmailMessage(policy=policy.default)
    msg.set_type("multipart/signed")
    msg.set_param("protocol", "application/pgp-signature")
    msg.set_boundary("only-one")
    body = EmailMessage(policy=policy.default)
    body.set_content("solo cuerpo")
    msg.attach(body)
    status = verify_signed_message(msg)
    assert status.signature_valid is False
    assert "incompleta" in status.error.lower() or "parte firmada" in status.error.lower()


def test_verify_unknown_public_key(mock_gpg: MockGpg) -> None:
    mock_gpg.verify_result = MockVerifyResult(
        valid=False,
        status="No public key for verification",
    )
    status = verify_signed_message(make_multipart_signed())
    assert status.signed is True
    assert status.signature_valid is False
    assert "clave pública" in status.error.lower()


def test_verify_valid_signature(mock_gpg: MockGpg) -> None:
    mock_gpg.verify_result = MockVerifyResult(
        valid=True,
        username="bob@example.com",
    )
    status = verify_signed_message(make_multipart_signed())
    assert status.signature_valid is True
    assert status.signer == "bob@example.com"
    assert status.error == ""


def test_verify_inline_signed_message(mock_gpg: MockGpg) -> None:
    mock_gpg.verify_result = MockVerifyResult(valid=True, username="clearsign@example.com")
    status = verify_signed_message(make_inline_signed())
    assert status.signature_valid is True
    assert status.signer == "clearsign@example.com"


def test_verify_timeout(mock_gpg: MockGpg) -> None:
    mock_gpg.verify_side_effect = TimeoutError()
    status = verify_signed_message(make_multipart_signed())
    assert status.signature_valid is False
    assert "Tiempo de espera" in status.error


def test_process_signed_only_message(mock_gpg: MockGpg) -> None:
    mock_gpg.verify_result = MockVerifyResult(valid=True, username="signer@test.com")
    msg, status = process_incoming_message(
        make_multipart_signed().as_bytes(),
        settings=OpenPgpSettings(enabled=True),
    )
    assert msg.get_content_type() == "multipart/signed"
    assert status.signed is True
    assert status.signature_valid is True
    assert status.encrypted is False


def test_process_signed_wrong_protocol_not_verified(monkeypatch: pytest.MonkeyPatch) -> None:
    from pyqorreos.core import openpgp as mod

    called = False

    def fake_verify(*_a, **_k):
        nonlocal called
        called = True
        return mod.PgpStatus()

    monkeypatch.setattr(mod, "verify_signed_message", fake_verify)
    msg, status = process_incoming_message(
        make_multipart_signed(protocol="text/plain").as_bytes(),
        settings=OpenPgpSettings(enabled=True),
    )
    assert not called
    assert status.signed is False
