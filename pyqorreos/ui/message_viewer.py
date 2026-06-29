"""
Visor de mensajes con motor HTML (Qt WebEngine).

Ofrece maquetado fiel al correo original, a diferencia de QTextBrowser.
"""

from __future__ import annotations

import json

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices
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

from pyqorreos.core.link_safety import is_suspicious_link, url_from_loose_text
from pyqorreos.ui.theme import apply_message_viewer_theme, mark_object, mark_role

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView

    from pyqorreos.ui.webengine_setup import (
        MailWebEngineView,
        QuietWebEnginePage,
        sanitize_email_html_for_viewer,
    )

    _HAS_WEBENGINE = True
except ImportError:
    _HAS_WEBENGINE = False
    MailWebEngineView = None  # type: ignore[misc, assignment]

    def sanitize_email_html_for_viewer(html: str) -> str:
        return html


class MessageViewer(QWidget):
    """Muestra el cuerpo de un correo en HTML o texto plano."""

    load_remote_images_requested = Signal()
    translate_requested = Signal()
    restore_original_requested = Signal()
    send_read_receipt_requested = Signal()
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
        self._showing_translation = False
        self._compact_toolbar = False
        self._read_receipt_to = ""
        self._theme = "light"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._toolbar = QWidget()
        self._toolbar.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        toolbar = QHBoxLayout(self._toolbar)
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(6)
        self._btn_load_images = QPushButton("🖼 Mostrar imágenes remotas")
        self._btn_load_images.setToolTip("Mostrar imágenes remotas del mensaje")
        self._btn_load_images.setVisible(False)
        self._btn_load_images.clicked.connect(self.load_remote_images_requested.emit)
        toolbar.addWidget(self._btn_load_images)

        self._btn_view_mode = QPushButton("📄 Modo lectura")
        self._btn_view_mode.setToolTip("Alternar entre HTML, modo lectura y texto plano")
        self._btn_view_mode.setVisible(False)
        self._btn_view_mode.clicked.connect(self._toggle_view_mode)
        toolbar.addWidget(self._btn_view_mode)

        self._btn_translate = QPushButton("🌐 Traducir")
        self._btn_translate.setVisible(False)
        self._btn_translate.setToolTip(
            "Traducir el mensaje al idioma configurado en Preferencias"
        )
        self._btn_translate.clicked.connect(self._on_translate_button_clicked)
        toolbar.addWidget(self._btn_translate)
        toolbar.addStretch(1)
        for btn in (
            self._btn_load_images,
            self._btn_view_mode,
            self._btn_translate,
        ):
            mark_role(btn, "secondary")

        layout.addWidget(self._toolbar)

        self._link_warning = QLabel()
        self._link_warning.setWordWrap(True)
        self._link_warning.setVisible(False)
        mark_role(self._link_warning, "link-warning")
        layout.addWidget(self._link_warning)

        self._read_receipt_bar = QWidget()
        receipt_layout = QHBoxLayout(self._read_receipt_bar)
        receipt_layout.setContentsMargins(0, 0, 0, 0)
        receipt_layout.setSpacing(8)
        self._read_receipt_label = QLabel()
        self._read_receipt_label.setWordWrap(True)
        mark_role(self._read_receipt_label, "hint")
        receipt_layout.addWidget(self._read_receipt_label, 1)
        self._btn_send_receipt = QPushButton("Enviar acuse")
        self._btn_send_receipt.setToolTip(
            "Confirma al remitente que has leído este mensaje"
        )
        self._btn_send_receipt.clicked.connect(self.send_read_receipt_requested.emit)
        mark_role(self._btn_send_receipt, "secondary")
        receipt_layout.addWidget(self._btn_send_receipt)
        self._btn_dismiss_receipt = QPushButton("Descartar")
        self._btn_dismiss_receipt.setToolTip("Ocultar este aviso sin enviar acuse")
        self._btn_dismiss_receipt.clicked.connect(self._dismiss_read_receipt)
        mark_role(self._btn_dismiss_receipt, "default")
        receipt_layout.addWidget(self._btn_dismiss_receipt)
        self._read_receipt_bar.setVisible(False)
        layout.addWidget(self._read_receipt_bar)

        self._stack = QStackedWidget()
        self._stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._stack, 1)

        if _HAS_WEBENGINE:
            view_cls = MailWebEngineView if MailWebEngineView is not None else QWebEngineView
            self._web = view_cls()
            self._web.setMinimumSize(0, 0)
            self._web.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            if QuietWebEnginePage is not None:
                self._web.setPage(QuietWebEnginePage(self._web))
            page = self._web.page()
            if page is not None and hasattr(page, "linkHovered"):
                page.linkHovered.connect(self._on_link_hovered)
            self._stack.addWidget(self._web)
            self._fallback = QTextBrowser()
            self._fallback.setOpenExternalLinks(True)
            self._fallback.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self._fallback.customContextMenuRequested.connect(
                lambda pos: self._show_text_browser_link_menu(self._fallback, pos)
            )
            self._stack.addWidget(self._fallback)
            self._html_widget = self._web
        else:
            self._fallback = QTextBrowser()
            self._fallback.setOpenExternalLinks(True)
            self._fallback.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self._fallback.customContextMenuRequested.connect(
                lambda pos: self._show_text_browser_link_menu(self._fallback, pos)
            )
            self._stack.addWidget(self._fallback)
            self._html_widget = self._fallback

        self._text = QTextBrowser()
        self._text.setOpenExternalLinks(True)
        self._text.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._text.customContextMenuRequested.connect(
            lambda pos: self._show_text_browser_link_menu(self._text, pos)
        )
        mark_object(self._text, "pyqMessageSurface")
        self._stack.addWidget(self._text)

        from pyqorreos.core.user_preferences import load_preferences

        self._theme = load_preferences().theme
        apply_message_viewer_theme(self, self._theme)

    def apply_theme(self, theme: str) -> None:
        self._theme = theme
        apply_message_viewer_theme(self, theme)
        if self._showing_translation:
            return
        if self._view_mode == "plain":
            return
        if self._stored_html.strip():
            self._render_current()

    def set_compact_toolbar(self, compact: bool) -> None:
        if compact == self._compact_toolbar:
            return
        self._compact_toolbar = compact
        self._btn_load_images.setText(
            "🖼 Imágenes" if compact else "🖼 Mostrar imágenes remotas"
        )
        self._btn_view_mode.setText("📄 Lectura" if compact else "📄 Modo lectura")

    def sync_toolbar_strip(self) -> None:
        pass

    def set_viewer_updates_enabled(self, enabled: bool) -> None:
        """Activa o pausa repintados del visor (p. ej. al mover el divisor)."""
        self.setUpdatesEnabled(enabled)
        if _HAS_WEBENGINE and hasattr(self, "_web"):
            self._web.setUpdatesEnabled(enabled)
        self._stack.setUpdatesEnabled(enabled)

    def _clear_link_hover(self) -> None:
        self._hovered_link_url = ""
        self._link_warning.hide()
        self.link_hover_changed.emit("")

    def _show_text_browser_link_menu(self, browser: QTextBrowser, pos) -> None:
        menu = browser.createStandardContextMenu(pos)
        if menu is None:
            return
        url = browser.anchorAt(pos)
        if not url:
            selected = browser.textCursor().selectedText().strip()
            url = url_from_loose_text(selected) or ""
        if url:
            open_action = QAction("Abrir enlace en el navegador", menu)
            open_action.triggered.connect(
                lambda _checked=False, link=url: QDesktopServices.openUrl(QUrl(link))
            )
            first = menu.actions()[0] if menu.actions() else None
            menu.insertAction(first, open_action)
            if first is not None:
                menu.insertSeparator(first)
        menu.exec(browser.mapToGlobal(pos))

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

    def is_showing_translation(self) -> bool:
        return self._showing_translation

    def prepare_for_new_message(self) -> None:
        """Restaura el estado del visor al cambiar de mensaje."""
        self._reset_translation_state()
        self._clear_link_hover()
        self._read_receipt_to = ""
        self._read_receipt_bar.setVisible(False)

    def set_read_receipt_request(self, receipt_to: str) -> None:
        """Muestra aviso si el remitente pidió acuse de recibo."""
        self._read_receipt_to = receipt_to.strip()
        if self._read_receipt_to:
            self._read_receipt_label.setText(
                f"El remitente solicita un acuse de recibo ({self._read_receipt_to})."
            )
            self._read_receipt_bar.setVisible(True)
        else:
            self._read_receipt_bar.setVisible(False)

    def clear_read_receipt_request(self) -> None:
        self._read_receipt_to = ""
        self._read_receipt_bar.setVisible(False)

    def _dismiss_read_receipt(self) -> None:
        self.clear_read_receipt_request()

    def _on_translate_button_clicked(self) -> None:
        if self._showing_translation:
            self.restore_original_requested.emit()
        else:
            self.translate_requested.emit()

    def set_translate_available(self, available: bool) -> None:
        self._btn_translate.setVisible(available)

    def show_translated(self, text: str, language_label: str = "") -> None:
        """Muestra la traducción con maquetado de lectura en el visor HTML."""
        from pyqorreos.core.translate import translated_text_to_html

        self._clear_link_hover()
        self._showing_translation = True
        self._btn_translate.setText("↩ Ver original")
        self._btn_translate.setVisible(True)
        self._btn_view_mode.setVisible(False)
        self._btn_load_images.setVisible(False)

        html = translated_text_to_html(text, language_label, theme=self._theme)
        base = QUrl(self._stored_base_url) if self._stored_base_url else QUrl("about:blank")
        if _HAS_WEBENGINE:
            page = self._web.page()
            if page is not None:
                try:
                    page.loadFinished.disconnect(self._scroll_content_to_top)
                except (RuntimeError, TypeError):
                    pass
                page.loadFinished.connect(self._scroll_content_to_top)
            self._web.setHtml(sanitize_email_html_for_viewer(html), base)
            self._stack.setCurrentWidget(self._web)
        else:
            self._fallback.document().setBaseUrl(base)
            self._fallback.setHtml(html)
            self._fallback.verticalScrollBar().setValue(0)
            self._stack.setCurrentWidget(self._fallback)

    def _scroll_content_to_top(self, ok: bool = True) -> None:
        if not ok or not _HAS_WEBENGINE:
            return
        page = self._web.page()
        if page is None:
            return
        try:
            page.runJavaScript("window.scrollTo(0, 0);")
        except Exception:
            pass

    def restore_from_stored(self) -> None:
        """Vuelve al contenido original del mensaje."""
        self._showing_translation = False
        self._btn_translate.setText("🌐 Traducir")
        self._clear_link_hover()
        if self._stored_html.strip():
            self._view_mode = "html"
            self._btn_view_mode.setText("📄 Modo lectura")
            self._btn_view_mode.setVisible(True)
            self._btn_load_images.setVisible(self._remote_blocked)
            self._render_current()
        else:
            self._btn_view_mode.setVisible(bool(self._stored_plain.strip()))
            self._btn_load_images.setVisible(False)
            self._text.setPlainText(self._stored_plain or "(Mensaje vacío)")
            self._stack.setCurrentWidget(self._text)
        self.set_translate_available(
            bool(self._stored_html.strip() or self._stored_plain.strip())
        )

    def html_source_for_load(self) -> str:
        """HTML base para descargar imágenes remotas (con metadatos de bloqueo)."""
        if not self._stored_html.strip():
            return self._stored_html
        if self._remote_blocked:
            from pyqorreos.core.email_html import block_remote_images_in_html

            return block_remote_images_in_html(self._stored_html)
        return self._stored_html

    def _html_for_viewer(self) -> str:
        from pyqorreos.core.email_html import (
            apply_viewer_theme_styles,
            block_remote_images_in_html,
        )

        html = self._stored_html
        if self._remote_blocked:
            html = block_remote_images_in_html(html)
        return apply_viewer_theme_styles(
            html,
            self._theme,
            reading_mode=self._view_mode == "reading",
        )

    def _reset_translation_state(self) -> None:
        self._showing_translation = False
        self._btn_translate.setText("🌐 Traducir")

    def _toggle_view_mode(self) -> None:
        if self._showing_translation:
            return
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
        html = self._html_for_viewer()
        base = QUrl(self._stored_base_url) if self._stored_base_url else QUrl("about:blank")
        if _HAS_WEBENGINE:
            self._web.setHtml(sanitize_email_html_for_viewer(html), base)
            self._stack.setCurrentWidget(self._web)
        else:
            self._fallback.document().setBaseUrl(base)
            self._fallback.setHtml(html)
            self._stack.setCurrentWidget(self._fallback)

    def apply_remote_image(self, original_url: str, data_url: str) -> None:
        """Actualiza una imagen remota en el visor sin recargar todo el HTML."""
        from pyqorreos.core.email_html import apply_data_url_to_html

        if not data_url:
            return
        self._stored_html = apply_data_url_to_html(
            self._stored_html, original_url, data_url
        )
        if _HAS_WEBENGINE and self._stack.currentWidget() is self._web:
            page = self._web.page()
            if page is None:
                return
            remote = json.dumps(original_url)
            embedded = json.dumps(data_url)
            script = f"""
            (function() {{
                var remote = {remote};
                var dataUrl = {embedded};
                document.querySelectorAll('img').forEach(function(img) {{
                    var blocked = img.getAttribute('data-blocked-src');
                    if (blocked === remote) {{
                        img.src = dataUrl;
                        img.removeAttribute('data-blocked-src');
                    }}
                    var blockedSet = img.getAttribute('data-blocked-srcset');
                    if (blockedSet && blockedSet.indexOf(remote) >= 0) {{
                        img.removeAttribute('data-blocked-srcset');
                    }}
                }});
                document.querySelectorAll('[background]').forEach(function(el) {{
                    var blocked = el.getAttribute('data-blocked-background');
                    if (blocked === remote) {{
                        el.setAttribute('background', dataUrl);
                        el.removeAttribute('data-blocked-background');
                    }}
                }});
            }})();
            """
            try:
                page.runJavaScript(script)
            except Exception:
                self._render_current()
        elif self._view_mode != "plain" and self._stored_html.strip():
            self._render_current()

    def mark_remote_images_unblocked(self) -> None:
        """El usuario pidió cargar imágenes; oculta el botón de bloqueo."""
        self._remote_blocked = False
        self._btn_load_images.setVisible(False)

    def set_remote_load_finished(self, still_blocked: bool) -> None:
        """Actualiza el estado tras cargar imágenes (sin recargar todo el HTML)."""
        self._remote_blocked = still_blocked
        self._btn_load_images.setVisible(still_blocked)

    @property
    def stored_html(self) -> str:
        return self._stored_html

    def show_html(self, html: str, base_url: str = "", *, remote_blocked: bool = False) -> None:
        if not html.strip():
            self.show_plain("(Mensaje vacío)")
            return
        self.prepare_for_new_message()
        self._stored_html = html
        self._stored_base_url = base_url
        self._remote_blocked = remote_blocked
        self._view_mode = "html"
        self._btn_view_mode.setText("📄 Modo lectura")
        self._btn_view_mode.setVisible(True)
        self._btn_load_images.setVisible(remote_blocked)
        self._btn_translate.setVisible(True)
        self._render_current()

    def show_plain(self, text: str) -> None:
        self._reset_translation_state()
        self._clear_link_hover()
        self._stored_plain = text or ""
        self._btn_load_images.setVisible(False)
        non_translatable = (
            "",
            "(Mensaje vacío)",
            "(Sin contenido)",
            "Doble clic en el mensaje para abrirlo.",
            "Cargando mensaje…",
        )
        has_content = bool(text and text.strip() not in non_translatable)
        self._btn_translate.setVisible(has_content)
        self._btn_view_mode.setVisible(False)
        self._text.setPlainText(text or "(Mensaje vacío)")
        self._stack.setCurrentWidget(self._text)

    def set_plain_fallback(self, text: str) -> None:
        """Guarda texto plano alternativo (p. ej. al cargar un mensaje HTML)."""
        self._stored_plain = text or ""

    def clear(self) -> None:
        self._btn_load_images.setVisible(False)
        self._btn_view_mode.setVisible(False)
        self._btn_translate.setVisible(False)
        self._reset_translation_state()
        self._clear_link_hover()
        self.clear_read_receipt_request()
        self._stored_html = ""
        self._stored_plain = ""
        self._stored_base_url = ""
        self._view_mode = "html"
        self.show_plain("")

    def shutdown_engine(self) -> None:
        """Libera Qt WebEngine antes de salir (evita procesos huérfanos)."""
        if not _HAS_WEBENGINE or not hasattr(self, "_web"):
            return
        try:
            self._web.setHtml("")
            page = self._web.page()
            self._web.setPage(None)
            if page is not None:
                page.deleteLater()
            self._web.hide()
            self._web.deleteLater()
        except RuntimeError:
            pass
