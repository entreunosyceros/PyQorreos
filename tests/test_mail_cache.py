"""Tests para caché SQLite de mensajes."""

from __future__ import annotations

from datetime import datetime, timezone

from pyqorreos.core.classifier import MailCategory
from pyqorreos.core.mail_cache import MailCache
from pyqorreos.core.mail_service import MailSummary


def _summary(uid: str, folder: str, subject: str, sender: str) -> MailSummary:
    return MailSummary(
        uid=uid,
        subject=subject,
        sender=sender,
        date=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
        seen=False,
        flagged=False,
        category=MailCategory.NORMAL,
        has_attachments=False,
        message_id=f"mid-{uid}",
        thread_key=f"thread-{uid}",
        folder=folder,
    )


def test_query_summaries_single_folder(tmp_path) -> None:
    cache = MailCache(tmp_path / "mail.db")
    account = "acc-1"
    cache.save_folder_ordered(account, "INBOX", [_summary("1", "INBOX", "Hola", "a@test.com")])
    cache.save_folder_ordered(
        account,
        "Sent",
        [_summary("2", "Sent", "Enviado", "me@test.com")],
    )
    hits = cache.query_summaries(account, "INBOX", query="Hola")
    assert len(hits) == 1
    assert hits[0].uid == "1"


def test_query_summaries_all_folders(tmp_path) -> None:
    cache = MailCache(tmp_path / "mail.db")
    account = "acc-1"
    cache.save_folder_ordered(account, "INBOX", [_summary("1", "INBOX", "Hola", "a@test.com")])
    cache.save_folder_ordered(
        account,
        "Sent",
        [_summary("2", "Sent", "Hola enviado", "me@test.com")],
    )
    hits = cache.query_summaries(account, None, query="Hola")
    assert len(hits) == 2
    folders = {h.folder for h in hits}
    assert folders == {"INBOX", "Sent"}
