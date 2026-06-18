"""
Visor de mensajes con motor HTML (Qt WebEngine).

Ofrece maquetado fiel al correo original, a diferencia de QTextBrowser.
"""

from __future__ import annotations

import json

from PySide6.QtCore import QUrl, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from pyqorreos.core.link_safety import is_suspicious_link

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
    link_hover_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._view_mode = "html"  # html | reading | plain
        self._stored_html = ""
        self._stored_plain = ""
        self._stored_base_url = ""
        self._remote_blocked = False
        self._hovered_link_url = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        toolbar = QHBoxLayout()
        self._btn_load_images = QPushButton("🖼 Mostrar imágenes remotas")
        self._btn_load_images.setVisible(False)
        self._btn_load_images.clicked.connect(self.load_remote_images_requested.emit)
        toolbar.addWidget(self._btn_load_images)

        self._btn_view_mode = QPushButton("📄 Modo lectura")
        self._btn_view_mode.setVisible(False)
        self._btn_view_mode.clicked.connect(self._toggle_view_mode)
        toolbar.addWidget(self._btn_view_mode)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._link_warning = QLabel()
        self._link_warning.setWordWrap(True)
        self._link_warning.setVisible(False)
        self._link_warning.setStyleSheet(
            "background: #fff3cd; color: #664d03; border: 1px solid #ffc107; "
            "border-radius: 4px; padding: 6px 10px; font-size: 10pt;"
        )
        layout.addWidget(self._link_warning)

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
            page = self._web.page()
            if page is not None and hasattr(page, "linkHovered"):
                page.linkHovered.connect(self._on_link_hovered)
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

    def _clear_link_hover(self) -> None:
        self._hovered_link_url = ""
        self._link_warning.hide()
        self.link_hover_changed.emit("")

    def _on_link_hovered(self, url: str) -> None:
        if not _HAS_WEBENGINE:
            return
        if not url:
            self._clear_link_hover()
            return
        self._hovered_link_url = url
        self.link_hover_changed.emit(url)
        page = self._web.page()
        if page is None:
            return
        target = json.dumps(url)
        script = f"""
        (function() {{
            var target = {target};
            var links = document.querySelectorAll('a[href]');
            for (var i = 0; i < links.length; i++) {{
                try {{
                    if (links[i].href === target) {{
                        return (links[i].textContent || '').replace(/\\s+/g, ' ').trim();
                    }}
                }} catch (e) {{}}
            }}
            return '';
        }})()
        """
        try:
            page.runJavaScript(script, self._apply_link_warning)
        except Exception:
            self._link_warning.hide()

    def _apply_link_warning(self, visible_text) -> None:
        url = self._hovered_link_url
        if not url:
            self._link_warning.hide()
            return
        text = visible_text if isinstance(visible_text, str) else ""
        if is_suspicious_link(text, url):
            from urllib.parse import urlparse

            host = urlparse(url).hostname or url
            shown = text if len(text) <= 80 else text[:77] + "…"
            self._link_warning.setText(
                f"⚠ Enlace sospechoso: el texto muestra «{shown}» pero apunta a {host}"
            )
            self._link_warning.setVisible(True)
        else:
            self._link_warning.hide()

    def _toggle_view_mode(self) -> None:
        if not self._stored_html and not self._stored_plain:
            return
        self._clear_link_hover()
        if self._view_mode == "html":
            self._view_mode = "reading"
            self._btn_view_mode.setText("📝 Texto plano")
            self._render_current()
        elif self._view_mode == "reading":
            self._view_mode = "plain"
            self._btn_view_mode.setText("🌐 HTML original")
            self._render_current()
        else:
            self._view_mode = "html"
            self._btn_view_mode.setText("📄 Modo lectura")
            self._render_current()

    def _render_current(self) -> None:
        if self._view_mode == "plain":
            self.show_plain(self._stored_plain or "(Mensaje vacío)")
            return
        if not self._stored_html.strip():
            self.show_plain(self._stored_plain or "(Mensaje vacío)")
            return
        html = self._stored_html
        if self._view_mode == "reading":
            from pyqorreos.core.email_html import apply_reading_mode_styles

            html = apply_reading_mode_styles(html)
        base = QUrl(self._stored_base_url) if self._stored_base_url else QUrl("about:blank")
        if _HAS_WEBENGINE:
            self._web.setHtml(sanitize_email_html_for_viewer(html), base)
            self._stack.setCurrentWidget(self._web)
        else:
            self._fallback.document().setBaseUrl(base)
            self._fallback.setHtml(html)
            self._stack.setCurrentWidget(self._fallback)

    def show_html(self, html: str, base_url: str = "", *, remote_blocked: bool = False) -> None:
        if not html.strip():
            self.show_plain("(Mensaje vacío)")
            return
        self._clear_link_hover()
        self._stored_html = html
        self._stored_base_url = base_url
        self._remote_blocked = remote_blocked
        self._view_mode = "html"
        self._btn_view_mode.setText("📄 Modo lectura")
        self._btn_view_mode.setVisible(True)
        self._btn_load_images.setVisible(remote_blocked)
        self._render_current()

    def show_plain(self, text: str) -> None:
        self._clear_link_hover()
        self._stored_plain = text or ""
        self._btn_load_images.setVisible(False)
        self._text.setPlainText(text or "(Mensaje vacío)")
        self._stack.setCurrentWidget(self._text)

    def set_plain_fallback(self, text: str) -> None:
        """Guarda texto plano alternativo (p. ej. al cargar un mensaje HTML)."""
        self._stored_plain = text or ""

    def clear(self) -> None:
        self._btn_load_images.setVisible(False)
        self._btn_view_mode.setVisible(False)
        self._clear_link_hover()
        self._stored_html = ""
        self._stored_plain = ""
        self._stored_base_url = ""
        self._view_mode = "html"
        self.show_plain("")
