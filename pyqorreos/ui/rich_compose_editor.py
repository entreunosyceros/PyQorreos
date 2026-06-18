"""
Editor de texto enriquecido para redactar correos.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QTextCharFormat,
    QTextCursor,
    QTextImageFormat,
    QTextListFormat,
)
from PySide6.QtWidgets import (
    QColorDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QMessageBox,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

_COMPOSE_DOC_STYLE = """
body {
    background-color: #ffffff;
    color: #1a1a1a;
    font-family: sans-serif;
    font-size: 11pt;
}
p, div, li, td, th, span {
    color: #1a1a1a;
}
#pyqorreos-reply-area {
    background-color: #ffffff !important;
    color: #1a1a1a !important;
    min-height: 100px;
}
"""

_EDITOR_STYLE = """
QTextEdit {
    background-color: #ffffff;
    color: #1a1a1a;
    border: 1px solid #cccccc;
    border-radius: 4px;
    padding: 6px;
    selection-background-color: #2d7dd2;
    selection-color: #ffffff;
}
"""

_TOOLBAR_STYLE = """
QToolBar {
    background-color: #f0f4f8;
    border: 1px solid #c8d0d8;
    border-radius: 5px;
    padding: 4px 6px;
    spacing: 5px;
}
QToolButton {
    background-color: #e3ebf3;
    color: #1a1a1a;
    border: 1px solid #b8c4d0;
    border-radius: 4px;
    padding: 5px 11px;
    font-size: 10pt;
    font-weight: 600;
    min-height: 28px;
}
QToolButton:hover {
    background-color: #d5e3f0;
    border-color: #2d7dd2;
    color: #1a1a1a;
}
QToolButton:pressed {
    background-color: #c5d8eb;
    border-color: #1f5fa8;
}
"""


class RichComposeEditor(QWidget):
    """Área de edición con barra de formato (negrita, enlaces, imágenes…)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.toolbar = QToolBar("Formato")
        self.toolbar.setMovable(False)
        self.toolbar.setStyleSheet(_TOOLBAR_STYLE)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        layout.addWidget(self.toolbar)

        self.editor = QTextEdit()
        self.editor.setAcceptRichText(True)
        self.editor.setPlaceholderText("Escribe tu mensaje aquí…")
        self.editor.setMinimumHeight(220)
        self.editor.setStyleSheet(_EDITOR_STYLE)
        self.editor.document().setDefaultStyleSheet(_COMPOSE_DOC_STYLE)
        layout.addWidget(self.editor)

        self._add_format_actions()

    def _add_format_actions(self) -> None:
        specs = (
            ("B", "Negrita", self._toggle_bold, "Ctrl+B"),
            ("I", "Cursiva", self._toggle_italic, "Ctrl+I"),
            ("U", "Subrayado", self._toggle_underline, "Ctrl+U"),
        )
        for label, tip, slot, shortcut in specs:
            action = QAction(label, self)
            action.setToolTip(tip)
            action.setShortcut(shortcut)
            action.triggered.connect(slot)
            self.toolbar.addAction(action)

        self.toolbar.addSeparator()

        for label, tip, slot in (
            ("• Lista", "Lista con viñetas", self._bullet_list),
            ("1. Lista", "Lista numerada", self._numbered_list),
        ):
            action = QAction(label, self)
            action.setToolTip(tip)
            action.triggered.connect(slot)
            self.toolbar.addAction(action)

        self.toolbar.addSeparator()

        link_action = QAction("🔗 Enlace", self)
        link_action.setToolTip("Insertar o editar enlace")
        link_action.triggered.connect(self._insert_link)
        self.toolbar.addAction(link_action)

        image_action = QAction("🖼 Imagen", self)
        image_action.setToolTip("Insertar imagen en el cuerpo")
        image_action.triggered.connect(self._insert_image)
        self.toolbar.addAction(image_action)

        color_action = QAction("A", self)
        color_action.setToolTip("Color del texto")
        color_action.triggered.connect(self._pick_color)
        self.toolbar.addAction(color_action)

        self.toolbar.addSeparator()

        clear_action = QAction("T×", self)
        clear_action.setToolTip("Quitar formato de la selección")
        clear_action.triggered.connect(self._clear_format)
        self.toolbar.addAction(clear_action)

    def _cursor(self) -> QTextCursor:
        return self.editor.textCursor()

    def _merge_format(self, fmt: QTextCharFormat) -> None:
        cursor = self._cursor()
        cursor.mergeCharFormat(fmt)
        self.editor.mergeCurrentCharFormat(fmt)

    def _toggle_bold(self) -> None:
        fmt = self._cursor().charFormat()
        weight = QFont.Weight.Normal if fmt.fontWeight() == QFont.Weight.Bold else QFont.Weight.Bold
        new_fmt = QTextCharFormat()
        new_fmt.setFontWeight(weight)
        self._merge_format(new_fmt)

    def _toggle_italic(self) -> None:
        fmt = self._cursor().charFormat()
        new_fmt = QTextCharFormat()
        new_fmt.setFontItalic(not fmt.fontItalic())
        self._merge_format(new_fmt)

    def _toggle_underline(self) -> None:
        fmt = self._cursor().charFormat()
        new_fmt = QTextCharFormat()
        new_fmt.setFontUnderline(not fmt.fontUnderline())
        self._merge_format(new_fmt)

    def _bullet_list(self) -> None:
        self._apply_list(QTextListFormat.Style.ListDisc)

    def _numbered_list(self) -> None:
        self._apply_list(QTextListFormat.Style.ListDecimal)

    def _apply_list(self, style: QTextListFormat.Style) -> None:
        cursor = self._cursor()
        fmt = QTextListFormat()
        fmt.setStyle(style)
        cursor.createList(fmt)

    def _insert_link(self) -> None:
        cursor = self._cursor()
        url, ok = QInputDialog.getText(
            self,
            "Insertar enlace",
            "URL (https://…):",
            text="https://",
        )
        if not ok or not url.strip():
            return
        url = url.strip()
        if not url.startswith(("http://", "https://", "mailto:")):
            url = "https://" + url

        fmt = QTextCharFormat()
        fmt.setAnchor(True)
        fmt.setAnchorHref(url)
        fmt.setForeground(QColor("#2d7dd2"))
        fmt.setFontUnderline(True)

        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
        else:
            cursor.insertText(url, fmt)

    def _insert_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Insertar imagen",
            "",
            "Imágenes (*.png *.jpg *.jpeg *.gif *.webp *.bmp);;Todos (*.*)",
        )
        if not path:
            return
        cursor = self._cursor()
        image_fmt = QTextImageFormat()
        image_fmt.setName(path)
        image_fmt.setWidth(480)
        cursor.insertImage(image_fmt)

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(
            self._cursor().charFormat().foreground().color(),
            self,
            "Color del texto",
        )
        if not color.isValid():
            return
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        self._merge_format(fmt)

    def _clear_format(self) -> None:
        cursor = self._cursor()
        if not cursor.hasSelection():
            return
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Normal)
        fmt.setFontItalic(False)
        fmt.setFontUnderline(False)
        fmt.setForeground(QColor("#1a1a1a"))
        cursor.mergeCharFormat(fmt)

    def _reset_cursor_style(self) -> None:
        """Fuerza fondo blanco y texto oscuro donde se escribe la respuesta."""
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#1a1a1a"))
        fmt.setBackground(QColor("#ffffff"))
        self.editor.setCurrentCharFormat(fmt)
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.editor.setTextCursor(cursor)

    def set_plain_text(self, text: str) -> None:
        self.editor.setPlainText(text)
        self._reset_cursor_style()

    def set_html(self, html: str) -> None:
        if html.strip():
            self.editor.setHtml(html)
        else:
            self.editor.clear()
        self._reset_cursor_style()

    def plain_text(self) -> str:
        return self.editor.toPlainText()

    def html(self) -> str:
        return self.editor.toHtml()

    def insert_text(self, text: str) -> None:
        """Inserta texto en la posición actual del cursor."""
        if not text:
            return
        cursor = self.editor.textCursor()
        cursor.insertText(text)
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()
