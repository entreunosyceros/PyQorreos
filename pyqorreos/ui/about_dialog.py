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

LOGO_PATH = Path(__file__).resolve().parent.parent / "img" / "logos.png"
GITHUB_URL = "https://github.com/entreunosyceros/pyqorreos"

DESCRIPTION = (
    "PyQorreos es un gestor de correo electrónico para escritorio. "
    "Conecta varias cuentas IMAP/SMTP, sincroniza tu bandeja con caché local "
    "y lee o redacta mensajes con un visor y editor enriquecidos."
)

FEATURES_HTML = """
<ul style="margin: 0; padding-left: 1.2em; line-height: 1.45; color: #ffffff;">
<li><b>Varias cuentas</b> — selector y gestor (añadir, editar, eliminar)</li>
<li><b>Bandeja del sistema</b> — minimizar sin cerrar la aplicación</li>
<li><b>Sincronización incremental</b> y caché SQLite (apertura rápida)</li>
<li><b>Clasificación</b> — normal, importante, spam (filtro y colores)</li>
<li><b>Visor HTML</b> — maquetado fiel (WebEngine, imágenes cid y remotas)</li>
<li><b>Responder / reenviar / eliminar</b> — barra de herramientas y menú contextual</li>
<li><b>Marcar leído</b>, copiar remitente, categorías desde clic derecho</li>
<li><b>Editor enriquecido</b> — negrita, cursiva, listas, enlaces, imágenes, color</li>
<li><b>Adjuntos</b> al enviar correos (HTML + texto plano)</li>
<li><b>Paginación</b> (50 mensajes/página) y operaciones en segundo plano</li>
<li><b>Contraseñas seguras</b> con keyring del sistema</li>
</ul>
"""


class AboutDialog(QDialog):
    """Ventana con información del programa, logo y enlace al repositorio."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Acerca de PyQorreos")
        self.setMinimumWidth(460)
        self.setMinimumHeight(520)
        self.setModal(True)
        self._build_ui()

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
            logo_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(logo_label)

        title = QLabel(f"<b>PyQorreos</b>  v{__version__}")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(DESCRIPTION)
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #ffffff;")
        layout.addWidget(desc)

        features_title = QLabel("<b>Funcionalidades</b>")
        layout.addWidget(features_title)

        features = QLabel(FEATURES_HTML)
        features.setWordWrap(True)
        features.setTextFormat(Qt.TextFormat.RichText)
        features.setOpenExternalLinks(False)
        features.setStyleSheet("color: #ffffff;")
        layout.addWidget(features)

        scroll.setWidget(content)

        github_btn = QPushButton("Ver en GitHub")
        github_btn.clicked.connect(self._open_github)
        outer.addWidget(github_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        outer.addWidget(buttons)

    def _open_github(self) -> None:
        webbrowser.open(GITHUB_URL)
