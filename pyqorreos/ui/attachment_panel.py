"""
Panel de adjuntos bajo el visor de mensajes.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pyqorreos.core.message_attachments import MailAttachmentInfo


class AttachmentPanel(QWidget):
    save_requested = Signal(int)
    open_requested = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        self._title = QLabel("Adjuntos:")
        self._title.setVisible(False)
        layout.addWidget(self._title)
        row = QHBoxLayout()
        self.list = QListWidget()
        self.list.setMaximumHeight(72)
        self.list.setVisible(False)
        row.addWidget(self.list, 1)
        btn_col = QVBoxLayout()
        self.btn_open = QPushButton("Abrir…")
        self.btn_save = QPushButton("Guardar…")
        self.btn_open.clicked.connect(self._on_open)
        self.btn_save.clicked.connect(self._on_save)
        self.btn_open.setVisible(False)
        self.btn_save.setVisible(False)
        btn_col.addWidget(self.btn_open)
        btn_col.addWidget(self.btn_save)
        row.addLayout(btn_col)
        layout.addLayout(row)
        self._attachments: list[MailAttachmentInfo] = []
        self.setVisible(False)

    def set_attachments(self, attachments: list[MailAttachmentInfo] | None) -> None:
        self._attachments = attachments or []
        self.list.clear()
        visible = bool(self._attachments)
        self.setVisible(visible)
        if not visible:
            return
        self._title.setVisible(True)
        self.list.setVisible(True)
        self.btn_open.setVisible(True)
        self.btn_save.setVisible(True)
        for index, att in enumerate(self._attachments):
            size_kb = max(1, att.size // 1024)
            item = QListWidgetItem(f"📎 {att.filename} ({size_kb} KB)")
            item.setData(256, index)
            self.list.addItem(item)
        if visible:
            self.list.setCurrentRow(0)

    def clear(self) -> None:
        self.set_attachments([])

    def _current_index(self) -> int | None:
        item = self.list.currentItem()
        if not item:
            return None
        return int(item.data(256))

    def _on_open(self) -> None:
        index = self._current_index()
        if index is not None:
            self.open_requested.emit(index)

    def _on_save(self) -> None:
        index = self._current_index()
        if index is not None:
            self.save_requested.emit(index)

    def prompt_save_path(self, filename: str) -> str | None:
        path, _ = QFileDialog.getSaveFileName(self, "Guardar adjunto", filename)
        return path or None
