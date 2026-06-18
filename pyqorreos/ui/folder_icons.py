"""
Iconos SVG para carpetas IMAP según su nombre o tipo habitual.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtGui import QIcon

_FOLDERS_IMG = Path(__file__).resolve().parent.parent / "img" / "folders"

# Nombre normalizado (último segmento de la ruta) → archivo SVG sin extensión.
_FOLDER_ALIASES: dict[str, str] = {
    # Bandeja de entrada
    "inbox": "inbox",
    # Enviados
    "sent": "sent",
    "sent items": "sent",
    "sent messages": "sent",
    "sent mail": "sent",
    "enviados": "sent",
    "elementos enviados": "sent",
    "mensajes enviados": "sent",
    # Borradores
    "drafts": "drafts",
    "draft": "drafts",
    "borradores": "drafts",
    "borrador": "drafts",
    # Papelera
    "trash": "trash",
    "deleted": "trash",
    "deleted items": "trash",
    "deleted messages": "trash",
    "bin": "trash",
    "papelera": "trash",
    "elementos eliminados": "trash",
    # Spam / no deseado
    "spam": "spam",
    "junk": "spam",
    "junk e-mail": "spam",
    "junk email": "spam",
    "bulk mail": "spam",
    "correo no deseado": "spam",
    "no deseado": "spam",
    # Archivo
    "archive": "archive",
    "archives": "archive",
    "archivo": "archive",
    "all mail": "archive",
    "todos": "archive",
    # Bandeja de salida
    "outbox": "outbox",
    "bandeja de salida": "outbox",
}


def folder_icon_key(folder_name: str) -> str:
    """Devuelve la clave del icono (inbox, sent, drafts, …) para una carpeta."""
    leaf = folder_name.rsplit("/", 1)[-1].strip().lower()
    if leaf in _FOLDER_ALIASES:
        return _FOLDER_ALIASES[leaf]
    if leaf == "inbox":
        return "inbox"
    for token, key in _FOLDER_ALIASES.items():
        if token in leaf:
            return key
    return "folder"


@lru_cache(maxsize=16)
def _load_icon(key: str) -> QIcon:
    path = _FOLDERS_IMG / f"{key}.svg"
    if not path.exists():
        path = _FOLDERS_IMG / "folder.svg"
    return QIcon(str(path))


def icon_for_folder(folder_name: str) -> QIcon:
    """Icono QIcon para mostrar junto al nombre de la carpeta."""
    return _load_icon(folder_icon_key(folder_name))
