"""Regresiones de OAuth, carpetas, envío y seguridad IMAP/SMTP. Sin red."""

from __future__ import annotations

import base64
import imaplib
import stat
import tempfile
from pathlib import Path

import smtplib

from pyqorreos.core.account import MailAccount
from pyqorreos.core.classifier import MailClassifier
from pyqorreos.core.imap_utf7 import decode_imap_utf7, encode_imap_utf7
from pyqorreos.core.mail_service import (
    _summary_from_fetch,
    limit_newest_uids,
    parse_list_mailbox,
)
from pyqorreos.core.oauth import (
    build_xoauth2_string,
    oauth_flow_status_message,
    record_oauth_callback,
)
from pyqorreos.core.oauth_clients import save_oauth_clients_data
from pyqorreos.core.openpgp import parse_recipient_emails, parse_recipient_fields
import pyqorreos.core.oauth_clients as oauth_clients


def test_xoauth2_is_base64_encoded_once() -> None:
    raw = build_xoauth2_string("user@example.com", "token")
    assert "\x01" in raw
    authenticator = imaplib._Authenticator(lambda _challenge: raw)
    imap_wire = authenticator.process(b"")
    assert base64.b64decode(imap_wire) == raw.encode("utf-8")
    smtp_wire = smtplib.encode_base64(raw.encode("ascii"), eol="")
    assert base64.b64decode(smtp_wire) == raw.encode("ascii")


def test_favicon_does_not_clear_oauth_code() -> None:
    class _Server:
        auth_code = None
        auth_error = None
        auth_state = None

    server = _Server()
    record_oauth_callback(server, "/?code=abc&state=xyz")
    record_oauth_callback(server, "/favicon.ico")
    assert server.auth_code == "abc"
    assert server.auth_state == "xyz"


def test_oauth_status_labels() -> None:
    assert oauth_flow_status_message("Autorización rechazada: access_denied") == (
        "Autorización rechazada"
    )
    assert (
        oauth_flow_status_message("Tiempo de espera agotado al autorizar en el navegador.")
        == "Tiempo agotado"
    )
    assert "refresh_token" in oauth_flow_status_message(
        "El proveedor no devolvió refresh_token."
    )


def test_list_mailbox_keeps_spaces() -> None:
    assert parse_list_mailbox(r'(\HasNoChildren) "/" "INBOX"') == "INBOX"
    assert (
        parse_list_mailbox(r'(\HasNoChildren) "/" "[Gmail]/All Mail"')
        == "[Gmail]/All Mail"
    )
    assert (
        parse_list_mailbox(r'(\HasChildren) "." "INBOX.Facturas 2024"')
        == "INBOX.Facturas 2024"
    )


def test_imap_utf7_roundtrip() -> None:
    for name in ("INBOX", "Año", "a&b", "[Gmail]/All Mail"):
        assert decode_imap_utf7(encode_imap_utf7(name)) == name


def test_newest_uids_are_kept() -> None:
    uids = [str(number).encode() for number in range(10000, 0, -1)]
    kept, window = limit_newest_uids(uids, has_cache=False, threshold=5000)
    assert kept[0] == b"10000"
    assert kept[-1] == b"5001"
    assert window == (5000, 10000)
    same, unlimited = limit_newest_uids(uids, has_cache=True, threshold=5000)
    assert unlimited is None
    assert same == uids


def test_recipients_with_comma_and_semicolon() -> None:
    valid, invalid = parse_recipient_fields(
        '"Pérez, Ana" <ana@example.com>',
        "Bob <bob@example.com>; carol@example.com",
    )
    assert invalid == []
    assert valid == ["ana@example.com", "bob@example.com", "carol@example.com"]
    assert parse_recipient_emails(
        '"Pérez, Ana" <ana@example.com>',
        "bob@example.com",
    ) == ["ana@example.com", "bob@example.com"]


def test_legacy_ports_keep_imap_and_smtp_apart() -> None:
    account = MailAccount.from_dict(
        {
            "email": "a@b.c",
            "imap_port": 143,
            "smtp_port": 465,
            "use_ssl": True,
            "use_starttls": True,
        }
    )
    assert account.imap_security == "starttls"
    assert account.smtp_security == "ssl"
    gmail = MailAccount.from_dict(
        {
            "email": "a@gmail.com",
            "imap_port": 993,
            "smtp_port": 587,
            "use_ssl": True,
            "use_starttls": True,
        }
    )
    assert gmail.imap_security == "ssl"
    assert gmail.smtp_security == "starttls"


def test_summary_keeps_folder() -> None:
    summary = _summary_from_fetch(
        "42",
        r"FLAGS (\Seen)",
        b"Subject: Hola\r\nFrom: a@b.c\r\n\r\n",
        "INBOX",
        MailClassifier(),
    )
    assert summary is not None
    assert summary.folder == "INBOX"
    assert summary.subject == "Hola"


def test_oauth_clients_file_is_private(monkeypatch) -> None:
    tmp = Path(tempfile.mkdtemp())
    monkeypatch.setattr(oauth_clients, "OAUTH_CLIENTS_DIR", tmp)
    monkeypatch.setattr(oauth_clients, "OAUTH_CLIENTS_FILE", tmp / "oauth_clients.json")
    save_oauth_clients_data(
        {"gmail": {"client_id": "desktop-client-id", "client_secret": "sekret"}}
    )
    mode = stat.S_IMODE((tmp / "oauth_clients.json").stat().st_mode)
    assert mode == 0o600
