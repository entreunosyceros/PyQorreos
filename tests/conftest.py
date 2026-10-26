"""Fixtures compartidas para tests OpenPGP."""

from __future__ import annotations

from dataclasses import dataclass
from email import policy
from email.message import EmailMessage, Message

import pytest


@dataclass
class MockVerifyResult:
    valid: bool
    status: str = ""
    username: str = ""


@dataclass
class MockDecryptResult:
    ok: bool
    status: str = ""
    data: bytes | str = b""
    sig_info: object | None = None
    username: str = ""


class MockGpg:
    """Sustituto de gnupg.GPG para tests sin binario real."""

    def __init__(
        self,
        *,
        decrypt_result: MockDecryptResult | None = None,
        verify_result: MockVerifyResult | None = None,
        decrypt_side_effect: Exception | None = None,
        verify_side_effect: Exception | None = None,
    ) -> None:
        self.decrypt_result = decrypt_result or MockDecryptResult(ok=False, status="not configured")
        self.verify_result = verify_result or MockVerifyResult(valid=False, status="not configured")
        self.decrypt_side_effect = decrypt_side_effect
        self.verify_side_effect = verify_side_effect
        self.decrypt_calls: list[tuple[bytes, str | None]] = []
        self.verify_calls: list[tuple] = ()

    def decrypt(self, data: bytes, passphrase: str | None = None) -> MockDecryptResult:
        self.decrypt_calls.append((data, passphrase))
        if self.decrypt_side_effect:
            raise self.decrypt_side_effect
        return self.decrypt_result

    def verify(self, *args) -> MockVerifyResult:
        self.verify_calls = args
        if self.verify_side_effect:
            raise self.verify_side_effect
        return self.verify_result

    def list_keys(self, secret: bool = False) -> list[dict[str, str]]:
        if secret:
            return [{"fingerprint": "ABCD", "keyid": "1234", "uids": ["me@test.com"]}]
        return []

    def encrypt(self, *args, **kwargs) -> MockDecryptResult:
        return MockDecryptResult(ok=True, data=b"encrypted-mime")


def make_multipart_signed(*, protocol: str = "application/pgp-signature") -> EmailMessage:
    msg = EmailMessage(policy=policy.default)
    msg.set_type("multipart/signed")
    msg.set_param("protocol", protocol)
    msg.set_param("micalg", "pgp-sha256")
    msg.set_boundary("signed-boundary")
    body = EmailMessage(policy=policy.default)
    body.set_content("Hola firmado")
    sig = EmailMessage(policy=policy.default)
    sig.set_type("application/pgp-signature")
    sig.set_payload("fake-signature-bytes")
    msg.attach(body)
    msg.attach(sig)
    return msg


def make_multipart_encrypted() -> EmailMessage:
    msg = EmailMessage(policy=policy.default)
    msg.set_type("multipart/encrypted")
    msg.set_param("protocol", "application/pgp-encrypted")
    msg.set_boundary("enc-boundary")
    version = EmailMessage(policy=policy.default)
    version.set_type("application/pgp-encrypted")
    version.set_content("Version: 1")
    payload = EmailMessage(policy=policy.default)
    payload.set_type("application/octet-stream")
    payload.set_payload("ciphertext-bytes")
    msg.attach(version)
    msg.attach(payload)
    return msg


def make_inline_encrypted(*, complete: bool = True) -> EmailMessage:
    msg = EmailMessage(policy=policy.default)
    armor = "-----BEGIN PGP MESSAGE-----\n\ndGVzdA==\n"
    if complete:
        armor += "-----END PGP MESSAGE-----"
    msg.set_content(armor)
    return msg


def make_inline_signed(*, complete: bool = True) -> EmailMessage:
    msg = EmailMessage(policy=policy.default)
    text = (
        "-----BEGIN PGP SIGNED MESSAGE-----\n"
        "Hash: SHA256\n"
        "\n"
        "Hola\n"
        "-----BEGIN PGP SIGNATURE-----\n"
        "sig\n"
    )
    if complete:
        text += "-----END PGP SIGNATURE-----\n"
    msg.set_content(text)
    return msg


def make_message_without_content_type() -> Message:
    return Message()


@pytest.fixture
def mock_gpg(monkeypatch: pytest.MonkeyPatch) -> MockGpg:
    from pyqorreos.core import openpgp as mod

    gpg = MockGpg()
    monkeypatch.setattr(mod, "get_gpg", lambda *_a, **_k: gpg)
    monkeypatch.setattr(mod, "openpgp_available", lambda: True)
    return gpg
