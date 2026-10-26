"""Clasificación MIME OpenPGP (sin GnuPG real)."""

from __future__ import annotations

from email import policy
from email.message import EmailMessage

import pytest

from pyqorreos.core.openpgp import classify_mime_message
from tests.conftest import (
    make_inline_encrypted,
    make_inline_signed,
    make_message_without_content_type,
    make_multipart_encrypted,
    make_multipart_signed,
)


def test_multipart_encrypted_valid_protocol() -> None:
    assert classify_mime_message(make_multipart_encrypted()) == "encrypted"


def test_multipart_encrypted_wrong_protocol() -> None:
    msg = EmailMessage(policy=policy.default)
    msg.set_type("multipart/encrypted")
    msg.set_param("protocol", "text/plain")
    assert classify_mime_message(msg) == "none"


def test_multipart_signed_valid_protocol() -> None:
    assert classify_mime_message(make_multipart_signed()) == "signed"


def test_multipart_signed_wrong_protocol_text_plain() -> None:
    msg = make_multipart_signed(protocol="text/plain")
    assert classify_mime_message(msg) == "none"


def test_multipart_signed_missing_protocol_still_signed() -> None:
    msg = EmailMessage(policy=policy.default)
    msg.set_type("multipart/signed")
    msg.set_boundary("b")
    part = EmailMessage(policy=policy.default)
    part.set_content("cuerpo")
    msg.attach(part)
    assert classify_mime_message(msg) == "signed"


def test_inline_encrypted_well_formed() -> None:
    assert classify_mime_message(make_inline_encrypted(complete=True)) == "inline"


def test_inline_encrypted_malformed_corrupt() -> None:
    assert classify_mime_message(make_inline_encrypted(complete=False)) == "corrupt"


def test_inline_signed_well_formed() -> None:
    assert classify_mime_message(make_inline_signed(complete=True)) == "signed"


def test_inline_signed_malformed_corrupt() -> None:
    assert classify_mime_message(make_inline_signed(complete=False)) == "corrupt"


def test_plain_text_none() -> None:
    msg = EmailMessage(policy=policy.default)
    msg.set_content("Hola mundo")
    assert classify_mime_message(msg) == "none"


def test_empty_message_no_exception() -> None:
    msg = EmailMessage(policy=policy.default)
    assert classify_mime_message(msg) == "none"


def test_missing_content_type_no_exception() -> None:
    msg = make_message_without_content_type()
    assert classify_mime_message(msg) == "none"


def test_application_pgp_encrypted_type() -> None:
    msg = EmailMessage(policy=policy.default)
    msg.set_type("application/pgp-encrypted")
    msg.set_payload("blob")
    assert classify_mime_message(msg) == "encrypted"


def test_application_pgp_signature_type() -> None:
    msg = EmailMessage(policy=policy.default)
    msg.set_type("application/pgp-signature")
    msg.set_payload("sig")
    assert classify_mime_message(msg) == "signed"


def test_octet_stream_with_encrypted_description() -> None:
    msg = EmailMessage(policy=policy.default)
    msg.set_type("application/octet-stream")
    msg["Content-Description"] = "OpenPGP encrypted message"
    msg.set_payload(b"cipher")
    assert classify_mime_message(msg) == "encrypted"


def test_multipart_nested_signature_part() -> None:
    outer = EmailMessage(policy=policy.default)
    outer.set_type("multipart/mixed")
    outer.set_boundary("mix")
    inner = EmailMessage(policy=policy.default)
    inner.set_type("application/pgp-signature")
    inner.set_payload("sig")
    outer.attach(inner)
    assert classify_mime_message(outer) == "signed"


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("", "none"),
        ("   \n\t  ", "none"),
        ("Not PGP at all", "none"),
        ("-----BEGIN PGP MESSAGE-----\nfoo\n-----END PGP MESSAGE-----", "inline"),
    ],
)
def test_classify_text_payload_variants(body: str, expected: str) -> None:
    msg = EmailMessage(policy=policy.default)
    msg.set_content(body)
    assert classify_mime_message(msg) == expected
