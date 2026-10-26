"""Tests OpenPGP (sin binario gpg real)."""

from __future__ import annotations

from email import policy
from email.message import EmailMessage

from pyqorreos.core.openpgp import (
    PgpStatus,
    OpenPgpSettings,
    classify_mime_message,
    pgp_status_summary,
    settings_from_user_prefs,
)
from pyqorreos.core.user_preferences import UserPreferences

# Tests para la clasificación de mensajes MIME
def test_classify_multipart_encrypted() -> None:
    msg = EmailMessage(policy=policy.default)
    msg.set_type("multipart/encrypted")
    msg.set_param("protocol", "application/pgp-encrypted")
    assert classify_mime_message(msg) == "encrypted"

# Tests para la clasificación de mensajes firmados
def test_classify_multipart_signed() -> None:
    msg = EmailMessage(policy=policy.default)
    msg.set_type("multipart/signed")
    msg.set_param("protocol", "application/pgp-signature")
    assert classify_mime_message(msg) == "signed"

# Tests para la clasificación de mensajes cifrados en línea
def test_classify_inline_encrypted() -> None:
    msg = EmailMessage(policy=policy.default)
    msg.set_content(
        "-----BEGIN PGP MESSAGE-----\n"
        "dGVzdA==\n"
        "-----END PGP MESSAGE-----"
    )
    assert classify_mime_message(msg) == "inline"

# Tests para la clasificación de mensajes de texto plano
def test_classify_plain_text() -> None:
    msg = EmailMessage(policy=policy.default)
    msg.set_content("Hola mundo")
    assert classify_mime_message(msg) == "none"

# Tests para la generación de un resumen del estado OpenPGP
def test_pgp_status_summary() -> None:
    status = PgpStatus(
        encrypted=True,
        signed=True,
        signature_valid=True,
        signer="alice@example.com",
    )
    text = pgp_status_summary(status)
    assert "Cifrado OpenPGP" in text
    assert "firma válida" in text
    assert "alice@example.com" in text

# Tests para la conversión de preferencias de usuario a configuraciones OpenPGP
def test_settings_from_user_prefs() -> None:
    prefs = UserPreferences(
        openpgp_enabled=True,
        openpgp_auto_decrypt=False,
        openpgp_sign_by_default=True,
        openpgp_encrypt_by_default=True,
        openpgp_use_system_gnupg_home=True,
        openpgp_signing_key_id="ABCD1234",
        openpgp_cache_decrypted_bodies=False,
    )
    settings = settings_from_user_prefs(prefs)
    assert settings == OpenPgpSettings(
        enabled=True,
        auto_decrypt=False,
        sign_by_default=True,
        encrypt_by_default=True,
        use_system_gnupg_home=True,
        signing_key_id="ABCD1234",
        cache_decrypted_bodies=False,
    )


# Tests para el procesamiento de mensajes entrantes cuando OpenPGP está deshabilitado
def test_process_incoming_disabled_skips_decrypt(monkeypatch) -> None:
    from pyqorreos.core import openpgp as mod

    called = False

    def fake_decrypt(*_a, **_k):
        nonlocal called
        called = True
        return None, PgpStatus()
    # Monkeypatch para que decrypt_message devuelva None y PgpStatus()
    monkeypatch.setattr(mod, "decrypt_message", fake_decrypt)
    # Mensaje de prueba para el procesamiento de mensajes entrantes
    raw = (
        b"From: a@b.com\r\n"
        b"To: c@d.com\r\n"
        b"Subject: test\r\n"
        b"Content-Type: multipart/encrypted; protocol=application/pgp-encrypted\r\n"
        b"\r\n"
        b"--boundary\r\n"
        b"Content-Type: application/pgp-encrypted\r\n"
        b"\r\n"
        b"Version: 1\r\n"
        b"--boundary\r\n"
        b"Content-Type: application/octet-stream\r\n"
        b"\r\n"
        b"fakecipher\r\n"
        b"--boundary--\r\n"
    )
    msg, status = mod.process_incoming_message(
        raw, settings=OpenPgpSettings(enabled=False)
    )
    assert not called
    assert status.encrypted is False
    assert msg.get("Subject") == "test"
