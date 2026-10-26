"""Tests para la agenda de contactos."""

from __future__ import annotations

import pytest

from pyqorreos.core import address_book as address_book_module
from pyqorreos.core.address_book import (
    AddressBook,
    AddressContact,
    is_valid_email,
    parse_sender_address,
    reset_address_book_cache,
)


@pytest.fixture(autouse=True)
def _isolated_contacts_file(tmp_path, monkeypatch):
    contacts_file = tmp_path / "contacts.json"
    monkeypatch.setattr(address_book_module, "CONTACTS_FILE", contacts_file)
    reset_address_book_cache()
    yield
    reset_address_book_cache()


def test_parse_sender_address() -> None:
    name, email = parse_sender_address("Ada Lovelace <ada@example.com>")
    assert name == "Ada Lovelace"
    assert email == "ada@example.com"


def test_upsert_and_save(tmp_path) -> None:
    book = AddressBook()
    book.upsert("bob@example.com", name="Bob", important=True)
    book.save()
    book2 = AddressBook()
    contacts = book2.contacts()
    assert len(contacts) == 1
    assert contacts[0].email == "bob@example.com"
    assert contacts[0].name == "Bob"
    assert contacts[0].important is True


def test_upsert_updates_existing() -> None:
    book = AddressBook()
    book.upsert("ana@example.com", name="Ana")
    book.upsert("ana@example.com", name="Ana García", important=True)
    contact = book.find_by_email("ana@example.com")
    assert contact is not None
    assert contact.name == "Ana García"
    assert contact.important is True


def test_search_and_autocomplete() -> None:
    book = AddressBook()
    book.upsert("zoe@example.com", name="Zoe")
    book.upsert("mario@empresa.com", name="Mario")
    hits = book.search("mario")
    assert len(hits) == 1
    labels = book.autocomplete_strings()
    assert any("mario@empresa.com" in label.lower() for label in labels)


def test_invalid_email_rejected() -> None:
    book = AddressBook()
    with pytest.raises(ValueError):
        book.upsert("no-es-correo")


def test_is_valid_email() -> None:
    assert is_valid_email("user@domain.org")
    assert not is_valid_email("invalid")


def test_read_contacts_from_disk(tmp_path, monkeypatch) -> None:
    contacts_file = tmp_path / "contacts.json"
    contacts_file.write_text(
        '{"contacts": [{"email": "a@b.com", "name": "Ana"}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(address_book_module, "CONTACTS_FILE", contacts_file)
    loaded = AddressBook.read_contacts_from_disk()
    assert len(loaded) == 1
    assert loaded[0].email == "a@b.com"


def test_set_contacts_without_disk_read() -> None:
    book = AddressBook()
    book.set_contacts(
        [
            AddressContact(id="1", email="z@z.com", name="Zoe"),
        ]
    )
    assert book.is_loaded
    assert book.contacts()[0].name == "Zoe"
