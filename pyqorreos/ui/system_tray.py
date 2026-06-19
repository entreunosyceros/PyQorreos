"""
Icono de bandeja del sistema (system tray) de PyQorreos.

Muestra logos.png en la bandeja y un menú contextual alineado con las
opciones de la ventana principal.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget


class SystemTray:
    """Gestiona el icono y el menú contextual en la bandeja del sistema."""

    def __init__(self, parent: QWidget, logo_path: Path, tooltip: str = "PyQorreos") -> None:
        self._parent = parent
        self._icon = QSystemTrayIcon(parent)
        self._icon.setToolTip(tooltip)

        if logo_path.exists():
            self._icon.setIcon(QIcon(str(logo_path)))

        self._icon.activated.connect(self._on_activated)

    def set_menu(self, menu: QMenu) -> None:
        """Asigna el menú contextual (mismas acciones que el menú superior)."""
        self._icon.setContextMenu(menu)

    def show(self) -> None:
        """Muestra el icono en la bandeja del sistema."""
        self._icon.show()

    def hide(self) -> None:
        """Oculta el icono de la bandeja."""
        self._icon.hide()

    def show_message(self, title: str, message: str, msecs: int = 3000) -> None:
        """Muestra una notificación breve junto al icono."""
        self._icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, msecs)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        # Doble clic (o clic simple en algunos entornos) restaura la ventana principal.
        if reason in (
            QSystemTrayIcon.ActivationReason.DoubleClick,
            QSystemTrayIcon.ActivationReason.MiddleClick,
        ):
            self._parent.show_main_window()

    @staticmethod
    def is_available() -> bool:
        """Indica si el entorno de escritorio soporta bandeja del sistema."""
        return QSystemTrayIcon.isSystemTrayAvailable()
