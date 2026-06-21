"""
Exportación de correos a .eml y .mbox.
"""

from __future__ import annotations

import mailbox
from pathlib import Path


def save_eml(raw_message: bytes, path: Path) -> None:
    """Guarda un mensaje RFC822 en un archivo .eml."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw_message)


def save_mbox(messages: list[bytes], path: Path) -> int:
    """
    Exporta varios mensajes a un archivo mbox.

    Devuelve el número de mensajes escritos.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    mbox = mailbox.mbox(str(path), create=True)
    mbox.lock()
    try:
        count = 0
        for raw in messages:
            if not raw:
                continue
            mbox.add(raw)
            count += 1
        mbox.flush()
    finally:
        mbox.unlock()
        mbox.close()
    return count
