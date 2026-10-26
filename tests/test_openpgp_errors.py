"""Errores y resiliencia OpenPGP (sin bloquear la aplicación)."""

from __future__ import annotations

from email import policy
from email.message import EmailMessage

import pytest

from pyqorreos.core.openpgp import (
    OpenPgpSettings,
    classify_mime_message,
    decrypt_message,
    encrypt_outgoing_message,
    get_gpg,
    import_key_file,
    process_incoming_message,
    verify_signed_message,
)
from tests.conftest import MockGpg, make_multipart_encrypted, make_multipart_signed


def test_get_gpg_file_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    from pyqorreos.core import openpgp as mod

    class BrokenGpg:
        def __init__(self, *args, **kwargs):
            raise FileNotFoundError("gpg")

    monkeypatch.setattr(mod, "openpgp_available", lambda: True)
    monkeypatch.setattr(mod, "gnupg", type("gnupg", (), {"GPG": BrokenGpg}))
    assert get_gpg() is None


def test_decrypt_file_not_found_via_gpg(mock_gpg: MockGpg) -> None:
    mock_gpg.decrypt_side_effect = FileNotFoundError("gpg missing")
    inner, status = decrypt_message(make_multipart_encrypted())
    assert inner is None
    assert status.error


def test_verify_file_not_found_via_gpg(mock_gpg: MockGpg) -> None:
    mock_gpg.verify_side_effect = FileNotFoundError("gpg missing")
    status = verify_signed_message(make_multipart_signed())
    assert status.signature_valid is False
    assert status.error


def test_encrypt_outgoing_no_gpg_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    from pyqorreos.core import openpgp as mod

    monkeypatch.setattr(mod, "get_gpg", lambda *_a, **_k: None)
    msg = EmailMessage(policy=policy.default)
    msg.set_content("hola")
    with pytest.raises(RuntimeError, match="gpg|OpenPGP|python-gnupg"):
        encrypt_outgoing_message(
            msg,
            recipients=["a@b.com"],
            sign=False,
            encrypt=True,
            signing_key_id="",
        )


def test_process_incoming_never_raises_on_corrupt_inline() -> None:
    from tests.conftest import make_inline_encrypted

    raw = make_inline_encrypted(complete=False).as_bytes()
    msg, status = process_incoming_message(
        raw,
        settings=OpenPgpSettings(enabled=True),
    )
    assert msg is not None
    assert status.error


def test_process_incoming_never_raises_on_empty_raw() -> None:
    msg, status = process_incoming_message(
        b"",
        settings=OpenPgpSettings(enabled=True),
    )
    assert msg is not None
    assert classify_mime_message(msg) == "none"


def test_process_incoming_decrypt_exception_survives(mock_gpg: MockGpg) -> None:
    mock_gpg.decrypt_side_effect = OSError("pinentry closed")
    msg, status = process_incoming_message(
        make_multipart_encrypted().as_bytes(),
        settings=OpenPgpSettings(enabled=True),
    )
    assert msg is not None
    assert status.encrypted is True
    assert status.error


def test_import_key_no_gpg(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from pyqorreos.core import openpgp as mod

    monkeypatch.setattr(mod, "get_gpg", lambda *_a, **_k: None)
    key_file = tmp_path / "pub.asc"
    key_file.write_text("fake key", encoding="utf-8")
    count, err = import_key_file(str(key_file))
    assert count == 0
    assert err


def test_classify_many_edge_messages_without_exception() -> None:
    cases = [
        EmailMessage(policy=policy.default),
        EmailMessage(policy=policy.default),
        EmailMessage(policy=policy.default),
    ]
    cases[1].set_content("-----BEGIN PGP MESSAGE-----\n")
    cases[2].set_type("multipart/signed")
    cases[2].set_param("protocol", "text/plain")
    for msg in cases:
        kind = classify_mime_message(msg)
        assert kind in ("none", "corrupt", "signed", "encrypted", "inline")
