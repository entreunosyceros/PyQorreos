"""
Visor de documentación integrado de PyQorreos.

Muestra los documentos Markdown del proyecto (README y carpeta ``docs/``) en un
panel con índice navegable a la izquierda y el contenido renderizado a la
derecha. Permite moverse entre documentos siguiendo los enlaces internos, ir
atrás en el historial y buscar texto dentro de la página actual.
"""

from __future__ import annotations

import re
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from pyqorreos.ui.theme import (
    mark_role,
    prevent_context_menu,
    resolve_theme_from_parent,
    theme_tokens,
)

# Raíz del proyecto: .../pyqorreos/ui/documentation_dialog.py -> .../ (3 niveles).
_PKG_ROOT = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _PKG_ROOT.parent

# Orden y títulos legibles de los documentos. La ruta es relativa a la raíz
# del proyecto; se resuelve contra varias ubicaciones candidatas en tiempo de
# ejecución (código fuente o paquete instalado).
_DOC_ENTRIES: list[tuple[str, str]] = [
    ("Inicio (README)", "README.md"),
    ("Índice de documentación", "docs/README.md"),
    ("Características", "docs/features.md"),
    ("Instalación", "docs/installation.md"),
    ("Uso rápido", "docs/usage.md"),
    ("Atajos de teclado", "docs/keyboard-shortcuts.md"),
    ("Estructura del proyecto", "docs/project-structure.md"),
    ("Configuración y notas", "docs/configuration.md"),
    ("Pilares de calidad", "docs/quality-pillars.md"),
    ("Historial de cambios", "docs/changelog.md"),
]

GITHUB_DOCS_URL = "https://github.com/entreunosyceros/PyQorreos/tree/main/docs"

_IMG_HTML_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_DIV_HTML_RE = re.compile(r"</?div\b[^>]*>", re.IGNORECASE)
_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")


def _candidate_roots() -> list[Path]:
    """Posibles raíces donde encontrar la documentación (fuente o instalado)."""
    roots = [
        _PROJECT_ROOT,
        _PKG_ROOT,  # docs empaquetados dentro del paquete (pyqorreos/docs)
        Path("/usr/share/pyqorreos"),
        Path("/usr/share/doc/pyqorreos"),
    ]
    seen: list[Path] = []
    for root in roots:
        if root not in seen:
            seen.append(root)
    return seen


def _resolve_doc(rel_path: str) -> Path | None:
    """Busca un documento por su ruta relativa en las raíces candidatas."""
    for root in _candidate_roots():
        candidate = (root / rel_path).resolve()
        if candidate.is_file():
            return candidate
        # Algunos paquetes aplanan ``docs/`` (solo el nombre del archivo).
        flat = (root / Path(rel_path).name).resolve()
        if flat.is_file():
            return flat
    return None


def _clean_markdown(text: str) -> str:
    """Elimina imágenes y envoltorios HTML que no aportan en el visor."""
    text = _IMG_HTML_RE.sub("", text)
    text = _DIV_HTML_RE.sub("", text)
    text = _MD_IMAGE_RE.sub("", text)
    return text


class DocumentationDialog(QDialog):
    """Ventana con el índice y el contenido de la documentación del proyecto."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._theme = resolve_theme_from_parent(parent)
        self.setWindowTitle("Documentación de PyQorreos")
        self.setMinimumSize(860, 600)
        self.setModal(False)
        # (título, ruta resuelta) de los documentos disponibles.
        self._docs: list[tuple[str, Path]] = []
        self._by_path: dict[str, int] = {}
        self._current_path: Path | None = None
        self._history: list[Path] = []
        self._build_ui()
        self._load_doc_list()
        prevent_context_menu(self)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        toolbar = QHBoxLayout()
        self.back_btn = QPushButton("← Atrás")
        mark_role(self.back_btn, "default")
        self.back_btn.setEnabled(False)
        self.back_btn.clicked.connect(self._go_back)
        toolbar.addWidget(self.back_btn)

        toolbar.addStretch()
        toolbar.addWidget(QLabel("Buscar:"))
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("Buscar en la página…")
        self.find_edit.setMaximumWidth(260)
        self.find_edit.returnPressed.connect(self._find_next)
        self.find_edit.textChanged.connect(self._on_find_text_changed)
        toolbar.addWidget(self.find_edit)
        self.find_btn = QPushButton("Siguiente")
        mark_role(self.find_btn, "default")
        self.find_btn.clicked.connect(self._find_next)
        toolbar.addWidget(self.find_btn)
        outer.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.nav_list = QListWidget()
        self.nav_list.setMaximumWidth(260)
        self.nav_list.setMinimumWidth(180)
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        splitter.addWidget(self.nav_list)

        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.anchorClicked.connect(self._on_anchor_clicked)
        self._apply_browser_theme()
        splitter.addWidget(self.browser)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 640])
        outer.addWidget(splitter, 1)

        bottom = QHBoxLayout()
        self.github_btn = QPushButton("Ver en GitHub")
        mark_role(self.github_btn, "secondary")
        self.github_btn.clicked.connect(lambda: webbrowser.open(GITHUB_DOCS_URL))
        bottom.addWidget(self.github_btn)
        bottom.addStretch()
        close_btn = QPushButton("Cerrar")
        mark_role(close_btn, "default")
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        outer.addLayout(bottom)

    def _apply_browser_theme(self) -> None:
        t = theme_tokens(self._theme)
        palette = self.browser.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(t.bg_panel))
        palette.setColor(QPalette.ColorRole.Text, QColor(t.text))
        self.browser.setPalette(palette)
        self.browser.document().setDefaultStyleSheet(
            f"""
            body {{ color: {t.text}; }}
            a {{ color: {t.link}; }}
            h1, h2, h3, h4 {{ color: {t.text}; }}
            code, pre {{ background-color: {t.bg_muted}; color: {t.text}; }}
            th, td {{ border: 1px solid {t.border}; padding: 4px 8px; }}
            th {{ background-color: {t.bg_muted}; }}
            blockquote {{ color: {t.text_muted}; }}
            """
        )

    def _load_doc_list(self) -> None:
        self.nav_list.blockSignals(True)
        for title, rel_path in _DOC_ENTRIES:
            resolved = _resolve_doc(rel_path)
            if not resolved:
                continue
            index = len(self._docs)
            self._docs.append((title, resolved))
            self._by_path[str(resolved)] = index
            self.nav_list.addItem(QListWidgetItem(title))
        self.nav_list.blockSignals(False)

        if not self._docs:
            self.browser.setMarkdown(
                "# Documentación no encontrada\n\n"
                "No se localizaron los archivos de documentación en esta "
                "instalación. Puedes consultarla en línea pulsando "
                "**Ver en GitHub**."
            )
            self.nav_list.setEnabled(False)
            self.find_edit.setEnabled(False)
            self.find_btn.setEnabled(False)
            return

        self.nav_list.setCurrentRow(0)

    def _on_nav_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._docs):
            return
        _title, path = self._docs[row]
        self._show_path(path, record_history=True)

    def _show_path(self, path: Path, *, record_history: bool) -> None:
        if self._current_path is not None and self._current_path != path and record_history:
            self._history.append(self._current_path)
            self.back_btn.setEnabled(True)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            self.browser.setMarkdown(f"# Error\n\nNo se pudo abrir «{path.name}».")
            return
        self._current_path = path
        self.browser.setSearchPaths([str(path.parent)])
        self.browser.setMarkdown(_clean_markdown(text))
        self.browser.verticalScrollBar().setValue(0)
        self._sync_nav_selection(path)

    def _sync_nav_selection(self, path: Path) -> None:
        index = self._by_path.get(str(path))
        if index is None:
            return
        if self.nav_list.currentRow() != index:
            self.nav_list.blockSignals(True)
            self.nav_list.setCurrentRow(index)
            self.nav_list.blockSignals(False)

    def _on_anchor_clicked(self, url: QUrl) -> None:
        scheme = url.scheme().lower()
        if scheme in ("http", "https", "mailto"):
            webbrowser.open(url.toString())
            return

        fragment = url.fragment()
        rel = url.path() or url.toString()
        # Enlace solo a un ancla dentro del documento actual.
        if not rel and fragment:
            self.browser.scrollToAnchor(fragment)
            return

        base = self._current_path.parent if self._current_path else _PROJECT_ROOT
        target = (base / rel).resolve()
        if target.is_file() and target.suffix.lower() == ".md":
            self._show_path(target, record_history=True)
            if fragment:
                self.browser.scrollToAnchor(fragment)
            return
        # Cualquier otra cosa (archivo no Markdown o ruta desconocida): navegador.
        if rel.startswith(("http://", "https://")):
            webbrowser.open(rel)

    def _go_back(self) -> None:
        if not self._history:
            return
        previous = self._history.pop()
        self.back_btn.setEnabled(bool(self._history))
        self._show_path(previous, record_history=False)

    def _on_find_text_changed(self, _text: str) -> None:
        # Reinicia el cursor para que la próxima búsqueda empiece desde arriba.
        cursor = self.browser.textCursor()
        cursor.clearSelection()
        cursor.movePosition(cursor.MoveOperation.Start)
        self.browser.setTextCursor(cursor)

    def _find_next(self) -> None:
        text = self.find_edit.text().strip()
        if not text:
            return
        if not self.browser.find(text):
            cursor = self.browser.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            self.browser.setTextCursor(cursor)
            self.browser.find(text)
