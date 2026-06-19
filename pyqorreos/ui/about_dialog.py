"""
Diálogo «Acerca de» de PyQorreos.

Muestra el logo, una breve descripción del programa, el listado de
funcionalidades y un enlace al repositorio en GitHub.
"""

from __future__ import annotations

import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pyqorreos import __version__
from pyqorreos.ui.theme import about_features_html, mark_role, prevent_context_menu, resolve_theme_from_parent

LOGO_PATH = Path(__file__).resolve().parent.parent / "img" / "logos.png"
GITHUB_URL = "https://github.com/entreunosyceros/pyqorreos"

DESCRIPTION = (
    "PyQorreos es un gestor de correo electrónico para escritorio. "
    "Conecta varias cuentas IMAP/SMTP, sincroniza tu bandeja con caché local "
    "y lee o redacta mensajes con un visor y editor enriquecidos."
)


class AboutDialog(QDialog):
    """Ventana con información del programa, logo y enlace al repositorio."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._theme = resolve_theme_from_parent(parent)
        self.setWindowTitle("Acerca de PyQorreos")
        self.setMinimumWidth(460)
        self.setMinimumHeight(520)
        self.setModal(True)
        self._build_ui()
        prevent_context_menu(self)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(10)
        layout.setContentsMargins(8, 8, 8, 8)

        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if LOGO_PATH.exists():
            pixmap = QPixmap(str(LOGO_PATH))
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    160,
                    160,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                logo_label.setPixmap(scaled)
            else:
                logo_label.setText("PyQorreos")
        else:
            logo_label.setText("PyQorreos")
        layout.addWidget(logo_label)

        title = QLabel(f"<b>PyQorreos</b>  v{__version__}")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(DESCRIPTION)
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        features_title = QLabel("<b>Funcionalidades</b>")
        layout.addWidget(features_title)

        features = QLabel(about_features_html(self._theme))
        features.setWordWrap(True)
        features.setTextFormat(Qt.TextFormat.RichText)
        features.setOpenExternalLinks(False)
        layout.addWidget(features)

        scroll.setWidget(content)

        github_btn = QPushButton("Ver en GitHub")
        mark_role(github_btn, "secondary")
        github_btn.clicked.connect(self._open_github)
        outer.addWidget(github_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        outer.addWidget(buttons)

    def _open_github(self) -> None:
        webbrowser.open(GITHUB_URL)
