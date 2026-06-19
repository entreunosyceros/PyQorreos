"""
Franjas con desplazamiento horizontal para filas de controles que no caben.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QSizePolicy, QWidget


class HorizontalScrollStrip(QScrollArea):
    """Fila de widgets que muestra barra horizontal si el ancho no es suficiente."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidgetResizable(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._container = QWidget()
        self._row = QHBoxLayout(self._container)
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(6)
        self.setWidget(self._container)

    @property
    def row(self) -> QHBoxLayout:
        return self._row

    def sync_size(self) -> None:
        """Fija la altura de la fila; el ancho interno activa scroll horizontal si hace falta."""
        self._container.adjustSize()
        hint = self._container.sizeHint()
        height = max(hint.height(), 40)
        width = max(hint.width(), 1)
        self._container.setFixedSize(width, height)
        self.setFixedHeight(height)
