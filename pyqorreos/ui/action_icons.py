"""
Iconos SVG para acciones de menú, barra de herramientas y bandeja del sistema.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtGui import QIcon

_UI_IMG = Path(__file__).resolve().parent.parent / "img" / "ui"
_FOLDERS_IMG = Path(__file__).resolve().parent.parent / "img" / "folders"

# Claves que reutilizan iconos de carpetas IMAP.
_FOLDER_ICON_KEYS = frozenset({"inbox", "trash", "spam", "folder"})


@lru_cache(maxsize=32)
def action_icon(key: str) -> QIcon:
    """Devuelve el QIcon para una acción de menú o bandeja."""
    if key in _FOLDER_ICON_KEYS:
        path = _FOLDERS_IMG / f"{key}.svg"
    else:
        path = _UI_IMG / f"{key}.svg"
    if not path.exists():
        path = _UI_IMG / "mail.svg"
    return QIcon(str(path))


def apply_action_icon(action, key: str) -> None:
    """Asigna icono visible en menús contextuales (p. ej. bandeja del sistema)."""
    action.setIcon(action_icon(key))
    action.setIconVisibleInMenu(True)
