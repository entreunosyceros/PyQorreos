"""
Agenda de contactos de correo (persistencia ligera en JSON).

Se carga en memoria solo la primera vez que se abre la agenda o se redacta
un correo; no interviene en la sincronización ni en la caché de mensajes.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from email.utils import parseaddr
from pathlib import Path

CONTACTS_FILE = Path.home() / ".config" / "pyqorreos" / "contacts.json"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class AddressContact:
    id: str
    email: str
    name: str = ""
    notes: str = ""
    important: bool = False

    def display_label(self) -> str:
        if self.name.strip():
            return f"{self.name.strip()} <{self.email}>"
        return self.email

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> AddressContact | None:
        email = str(data.get("email", "")).strip()
        if not email:
            return None
        return cls(
            id=str(data.get("id") or uuid.uuid4()),
            email=email,
            name=str(data.get("name", "")).strip(),
            notes=str(data.get("notes", "")).strip(),
            important=bool(data.get("important", False)),
        )


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_valid_email(email: str) -> bool:
    addr = normalize_email(email)
    return bool(addr and _EMAIL_RE.match(addr))


def parse_sender_address(sender: str) -> tuple[str, str]:
    """Devuelve (nombre, email) a partir de una cabecera From."""
    name, addr = parseaddr(sender or "")
    return name.strip(), normalize_email(addr) if addr else ""


@dataclass
class AddressBook:
    """Lista de contactos en memoria; lectura de disco solo al primer uso."""

    _contacts: list[AddressContact] = field(default_factory=list, repr=False)
    _loaded: bool = field(default=False, repr=False)
    _dirty: bool = field(default=False, repr=False)

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._contacts = self._read_from_disk()
        self._loaded = True

    @staticmethod
    def _read_from_disk() -> list[AddressContact]:
        CONTACTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not CONTACTS_FILE.exists():
            return []
        try:
            data = json.loads(CONTACTS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, TypeError):
            return []
        items = data.get("contacts") if isinstance(data, dict) else data
        if not isinstance(items, list):
            return []
        contacts: list[AddressContact] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            contact = AddressContact.from_dict(item)
            if contact and is_valid_email(contact.email):
                contacts.append(contact)
        return _sort_contacts(contacts)

    def is_loaded(self) -> bool:
        return self._loaded

    def load_from_disk(self) -> None:
        """Carga contactos desde JSON en el hilo actual."""
        self._ensure_loaded()

    @classmethod
    def read_contacts_from_disk(cls) -> list[AddressContact]:
        """Lee contactos del disco sin modificar instancias en memoria."""
        return cls._read_from_disk()

    def set_contacts(self, contacts: list[AddressContact]) -> None:
        self._contacts = _sort_contacts(list(contacts))
        self._loaded = True

    def find_by_id(self, contact_id: str) -> AddressContact | None:
        self._ensure_loaded()
        return next((c for c in self._contacts if c.id == contact_id), None)

    def contacts(self) -> list[AddressContact]:
        self._ensure_loaded()
        return list(self._contacts)

    def search(self, query: str, *, limit: int = 50) -> list[AddressContact]:
        self._ensure_loaded()
        q = query.strip().lower()
        if not q:
            return self.contacts()[:limit]
        hits: list[AddressContact] = []
        for contact in self._contacts:
            haystack = f"{contact.name} {contact.email} {contact.notes}".lower()
            if q in haystack:
                hits.append(contact)
            if len(hits) >= limit:
                break
        return hits

    def autocomplete_strings(self) -> list[str]:
        self._ensure_loaded()
        labels: list[str] = []
        seen: set[str] = set()
        for contact in self._contacts:
            for candidate in (contact.display_label(), contact.email):
                key = candidate.lower()
                if key in seen:
                    continue
                seen.add(key)
                labels.append(candidate)
        return labels

    def find_by_email(self, email: str) -> AddressContact | None:
        self._ensure_loaded()
        key = normalize_email(email)
        if not key:
            return None
        return next((c for c in self._contacts if normalize_email(c.email) == key), None)

    def upsert(
        self,
        email: str,
        *,
        name: str = "",
        notes: str = "",
        important: bool | None = None,
    ) -> AddressContact:
        self._ensure_loaded()
        key = normalize_email(email)
        if not is_valid_email(key):
            raise ValueError("Dirección de correo no válida")
        existing = self.find_by_email(key)
        if existing:
            if name.strip():
                existing.name = name.strip()
            if notes.strip():
                existing.notes = notes.strip()
            if important is not None:
                existing.important = important
            self._contacts = _sort_contacts(self._contacts)
            self._dirty = True
            return existing
        contact = AddressContact(
            id=str(uuid.uuid4()),
            email=key,
            name=name.strip(),
            notes=notes.strip(),
            important=bool(important),
        )
        self._contacts.append(contact)
        self._contacts = _sort_contacts(self._contacts)
        self._dirty = True
        return contact

    def update(self, contact: AddressContact) -> None:
        self._ensure_loaded()
        if not is_valid_email(contact.email):
            raise ValueError("Dirección de correo no válida")
        for index, existing in enumerate(self._contacts):
            if existing.id == contact.id:
                self._contacts[index] = contact
                self._contacts = _sort_contacts(self._contacts)
                self._dirty = True
                return
        raise KeyError(contact.id)

    def remove(self, contact_id: str) -> None:
        self._ensure_loaded()
        before = len(self._contacts)
        self._contacts = [c for c in self._contacts if c.id != contact_id]
        if len(self._contacts) != before:
            self._dirty = True

    def save(self) -> None:
        if not self._dirty:
            return
        self._ensure_loaded()
        CONTACTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {"contacts": [c.to_dict() for c in self._contacts]}
        CONTACTS_FILE.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self._dirty = False


def _sort_contacts(contacts: list[AddressContact]) -> list[AddressContact]:
    return sorted(
        contacts,
        key=lambda c: (
            not c.important,
            (c.name or c.email).casefold(),
            c.email,
        ),
    )


_book: AddressBook | None = None


def get_address_book() -> AddressBook:
    """Instancia compartida; la primera llamada lee el JSON (típicamente al redactar)."""
    global _book
    if _book is None:
        _book = AddressBook()
    return _book


def reset_address_book_cache() -> None:
    """Útil en tests para no compartir estado entre casos."""
    global _book
    _book = None
