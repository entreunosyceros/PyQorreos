"""
Visor de mensajes con motor HTML (Qt WebEngine).

Ofrece maquetado fiel al correo original, a diferencia de QTextBrowser.
"""

from __future__ import annotations

from PySide6.QtCore import QUrl, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QSizePolicy, QStackedWidget, QTextBrowser, QVBoxLayout, QWidget

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView

    from pyqorreos.ui.webengine_setup import QuietWebEnginePage, sanitize_email_html_for_viewer

    _HAS_WEBENGINE = True
except ImportError:
    _HAS_WEBENGINE = False

    def sanitize_email_html_for_viewer(html: str) -> str:
        return html


class MessageViewer(QWidget):
    """Muestra el cuerpo de un correo en HTML o texto plano."""

    load_remote_images_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        toolbar = QHBoxLayout()
        self._btn_load_images = QPushButton("🖼 Mostrar imágenes remotas")
        self._btn_load_images.setVisible(False)
        self._btn_load_images.clicked.connect(self.load_remote_images_requested.emit)
        toolbar.addWidget(self._btn_load_images)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._stack = QStackedWidget()
        self._stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._stack, 1)

        if _HAS_WEBENGINE:
            self._web = QWebEngineView()
            self._web.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            if QuietWebEnginePage is not None:
                self._web.setPage(QuietWebEnginePage(self._web))
            self._web.setStyleSheet("background: #ffffff;")
            self._stack.addWidget(self._web)
            self._fallback = QTextBrowser()
            self._fallback.setOpenExternalLinks(True)
            self._stack.addWidget(self._fallback)
            self._html_widget = self._web
        else:
            self._fallback = QTextBrowser()
            self._fallback.setOpenExternalLinks(True)
            self._stack.addWidget(self._fallback)
            self._html_widget = self._fallback

        self._text = QTextBrowser()
        self._text.setOpenExternalLinks(True)
        self._text.setStyleSheet(
            "QTextBrowser { background: #ffffff; color: #1a1a1a; font-size: 11pt; }"
        )
        self._stack.addWidget(self._text)

    def show_html(self, html: str, base_url: str = "", *, remote_blocked: bool = False) -> None:
        if not html.strip():
            self.show_plain("(Mensaje vacío)")
            return
        self._btn_load_images.setVisible(remote_blocked)
        base = QUrl(base_url) if base_url else QUrl("about:blank")
        if _HAS_WEBENGINE:
            self._web.setHtml(sanitize_email_html_for_viewer(html), base)
            self._stack.setCurrentWidget(self._web)
        else:
            self._fallback.document().setBaseUrl(base)
            self._fallback.setHtml(html)
            self._stack.setCurrentWidget(self._fallback)

    def show_plain(self, text: str) -> None:
        self._text.setPlainText(text or "(Mensaje vacío)")
        self._stack.setCurrentWidget(self._text)

    def clear(self) -> None:
        self._btn_load_images.setVisible(False)
        self.show_plain("")
