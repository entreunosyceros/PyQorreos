"""
Configuración de Qt WebEngine para reducir ruido en la terminal.

Debe llamarse antes de crear QApplication.
"""

from __future__ import annotations

import os
import re
import threading

_CHROMIUM_QUIET_FLAGS = (
    "--disable-logging",
    "--log-level=3",
    "--disable-speech-api",
)

_STDIO_NOISE = (
    "GBM is not supported with the current configuration",
    "Fallback to Vulkan rendering in Chromium",
    'The key "target-densitydpi" is not supported',
)

_stdout_filter_installed = False


def _is_noise(text: str) -> bool:
    return any(noise in text for noise in _STDIO_NOISE)


class _FilteredStream:
    """Filtra avisos inofensivos de Chromium en flujos Python."""

    def __init__(self, stream) -> None:
        self._stream = stream

    def write(self, text: str) -> int:
        if _is_noise(text):
            return len(text)
        return self._stream.write(text)

    def flush(self) -> None:
        self._stream.flush()

    def __getattr__(self, name: str):
        return getattr(self._stream, name)


def _install_stdio_fd_filter() -> None:
    """
    Redirige stderr (fd 2) para filtrar avisos de procesos hijo de Chromium.
    """
    global _stdout_filter_installed
    if _stdout_filter_installed:
        return

    read_fd, write_fd = os.pipe()
    real_stderr_fd = os.dup(2)
    os.dup2(write_fd, 2)
    os.close(write_fd)

    import sys

    sys.stderr = os.fdopen(2, "w", buffering=1, closefd=False)

    def forward() -> None:
        buffer = ""
        with os.fdopen(read_fd, "r", encoding="utf-8", errors="replace") as reader:
            while True:
                chunk = reader.read(4096)
                if not chunk:
                    break
                buffer += chunk
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line += "\n"
                    if not _is_noise(line):
                        os.write(real_stderr_fd, line.encode("utf-8", errors="replace"))
            if buffer and not _is_noise(buffer):
                os.write(real_stderr_fd, buffer.encode("utf-8", errors="replace"))

    threading.Thread(target=forward, name="stderr-filter", daemon=True).start()
    _stdout_filter_installed = True


def configure_webengine_environment() -> None:
    """Ajusta variables de entorno para acallar avisos de Chromium/Qt WebEngine."""
    import sys

    _install_stdio_fd_filter()

    if not isinstance(sys.stderr, _FilteredStream):
        pass  # ya reemplazado por fdopen tras el filtro de descriptor

    existing = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").split()
    for flag in _CHROMIUM_QUIET_FLAGS:
        if flag not in existing:
            existing.append(flag)
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(existing).strip()

    rules = os.environ.get("QT_LOGGING_RULES", "")
    for rule in ("qt.webengine*=false", "qt.webenginecontext*=false"):
        if rule.split("=")[0] not in rules:
            rules = f"{rules};{rule}" if rules else rule
    os.environ["QT_LOGGING_RULES"] = rules.strip(";")


def sanitize_email_html_for_viewer(html: str) -> str:
    """
    Elimina atributos viewport obsoletos que provocan avisos en Chromium.

    Muchos boletines incluyen target-densitydpi, deprecado en navegadores modernos.
    """
    if not html:
        return html
    html = re.sub(
        r"target-densitydpi\s*=\s*(?:device-dpi|high-dpi|medium-dpi|low-dpi|\d+)",
        "",
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(r";\s*;", ";", html)
    html = re.sub(r'content="\s*;', 'content="', html)
    html = re.sub(r';\s*"', '"', html)
    return html


try:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWebEngineCore import QWebEnginePage

    _EXTERNAL_SCHEMES = frozenset({"http", "https", "mailto"})

    class QuietWebEnginePage(QWebEnginePage):
        """Página WebEngine: sin ruido en consola y enlaces en el navegador del sistema."""

        def javaScriptConsoleMessage(
            self,
            level,
            message: str,
            lineNumber: int,
            sourceID: str,
        ) -> None:
            del level, lineNumber, sourceID
            if _is_noise(message):
                return

        def acceptNavigationRequest(
            self,
            url: QUrl,
            nav_type: QWebEnginePage.NavigationType,
            is_main_frame: bool,
        ) -> bool:
            scheme = url.scheme().lower()
            if scheme in _EXTERNAL_SCHEMES:
                QDesktopServices.openUrl(url)
                return False
            if scheme == "javascript":
                return False
            return super().acceptNavigationRequest(url, nav_type, is_main_frame)

        def createWindow(self, _type: QWebEnginePage.WebWindowType) -> QWebEnginePage:
            """Enlaces con target=_blank se abren en el navegador externo."""
            return QuietWebEnginePage(self)

    _HAS_QUIET_PAGE = True
except ImportError:
    QuietWebEnginePage = None  # type: ignore[misc, assignment]
    _HAS_QUIET_PAGE = False
