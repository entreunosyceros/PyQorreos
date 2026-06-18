"""
Exportación de correos a .eml y .mbox.
"""

from __future__ import annotations

import mailbox
from email.utils import formatdate, parsedate_to_datetime
from pathlib import Path


def save_eml(raw_message: bytes, path: Path) -> None:
    """Guarda un mensaje RFC822 en un archivo .eml."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw_message)


def save_mbox(
    messages: list[tuple[bytes, str | None]],
    path: Path,
) -> int:
    """
    Exporta varios mensajes a un archivo mbox.

    Cada entrada es (bytes RFC822, fecha opcional para la línea From).
    Devuelve el número de mensajes escritos.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    mbox = mailbox.mbox(str(path), create=True)
    mbox.lock()
    try:
        count = 0
        for raw, _date_hint in messages:
            if not raw:
                continue
            mbox.add(raw)
            count += 1
        mbox.flush()
    finally:
        mbox.unlock()
        mbox.close()
    return count


def format_from_line(raw_message: bytes) -> str:
    """Genera una línea From mbox a partir del mensaje."""
    import email

    msg = email.message_from_bytes(raw_message)
    date_hdr = msg.get("Date")
    try:
        when = parsedate_to_datetime(date_hdr) if date_hdr else None
    except (TypeError, ValueError, IndexError):
        when = None
    if when is None:
        return formatdate(localtime=True)
    return formatdate(when.timestamp(), localtime=True)
