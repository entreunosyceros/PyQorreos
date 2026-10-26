"""Tests para utilidades de carpetas IMAP."""

from __future__ import annotations

from pyqorreos.core.folder_utils import (
    find_drafts_folder,
    find_sent_folder,
    is_drafts_folder,
)


def test_is_drafts_folder() -> None:
    assert is_drafts_folder("Drafts")
    assert is_drafts_folder("INBOX/Borradores")
    assert not is_drafts_folder("INBOX")


def test_find_sent_folder() -> None:
    names = ["INBOX", "Sent Items", "Drafts", "Trash"]
    assert find_sent_folder(names) == "Sent Items"


def test_find_drafts_folder() -> None:
    names = ["INBOX", "Borradores", "Enviados"]
    assert find_drafts_folder(names) == "Borradores"
