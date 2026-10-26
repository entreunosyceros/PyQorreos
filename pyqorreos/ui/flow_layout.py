"""
Diseño que coloca controles en fila y los baja a la línea siguiente si no caben.

Así las barras de botones y los grupos de filtros siguen siendo usables cuando
la ventana deja de estar maximizada, en lugar de pintarse unos encima de otros.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QLayout,
    QLayoutItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class FlowLayout(QLayout):
    """Coloca los elementos de izquierda a derecha y salta de línea."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        hspacing: int = 8,
        vspacing: int = 6,
    ) -> None:
        super().__init__(parent)
        self._hspacing = hspacing
        self._vspacing = vspacing
        self._items: list[QLayoutItem] = []

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientation:
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            if item.isEmpty():
                continue
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(
            margins.left() + margins.right(),
            margins.top() + margins.bottom(),
        )
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        margins = self.contentsMargins()
        left = margins.left()
        top = margins.top()
        right = margins.right()
        bottom = margins.bottom()
        effective = rect.adjusted(left, top, -right, -bottom)
        if effective.width() < 0:
            effective.setWidth(0)

        rows: list[list[QLayoutItem]] = []
        row: list[QLayoutItem] = []
        row_width = 0
        for item in self._items:
            if item.isEmpty():
                if not test_only:
                    item.setGeometry(QRect())
                continue
            width = self._item_width(item)
            gap = self._hspacing if row else 0
            overflows = (
                bool(row)
                and effective.width() > 0
                and row_width + gap + width > effective.width()
            )
            if overflows:
                rows.append(row)
                row = [item]
                row_width = width
            else:
                row.append(item)
                row_width = width if not row_width else row_width + gap + width
        if row:
            rows.append(row)

        placed: list[tuple[list[QLayoutItem], list[int], int]] = []
        for line in rows:
            widths = [self._item_width(item) for item in line]
            growers = [
                index
                for index, item in enumerate(line)
                if self._expands(item, Qt.Orientation.Horizontal)
            ]
            gaps = self._hspacing * max(0, len(line) - 1)
            extra = effective.width() - sum(widths) - gaps
            if extra > 0 and growers:
                share, remainder = divmod(extra, len(growers))
                for offset, index in enumerate(growers):
                    widths[index] += share + (1 if offset < remainder else 0)
            heights = [self._item_height(item, width) for item, width in zip(line, widths)]
            placed.append((line, widths, max(heights) if heights else 0))

        content_height = top + bottom
        if placed:
            content_height += sum(height for _line, _widths, height in placed)
            content_height += self._vspacing * (len(placed) - 1)

        if not test_only and placed:
            spare = rect.height() - content_height
            if spare > 0:
                growers = [
                    index
                    for index, (line, _widths, _height) in enumerate(placed)
                    if any(self._expands(item, Qt.Orientation.Vertical) for item in line)
                ]
                if growers:
                    share, remainder = divmod(spare, len(growers))
                    grown: list[tuple[list[QLayoutItem], list[int], int]] = []
                    for index, entry in enumerate(placed):
                        line, widths, height = entry
                        if index in growers:
                            extra_height = share + (1 if growers.index(index) < remainder else 0)
                            height += extra_height
                        grown.append((line, widths, height))
                    placed = grown

            y = effective.y()
            for line, widths, line_height in placed:
                x = effective.x()
                for item, width in zip(line, widths):
                    item.setGeometry(QRect(x, y, max(width, 0), line_height))
                    x += width + self._hspacing
                y += line_height + self._vspacing

        return max(content_height, top + bottom)

    @staticmethod
    def _item_width(item: QLayoutItem) -> int:
        return max(item.sizeHint().width(), item.minimumSize().width(), 0)

    @staticmethod
    def _item_height(item: QLayoutItem, width: int) -> int:
        if item.hasHeightForWidth():
            height = item.heightForWidth(width)
        else:
            height = max(item.sizeHint().height(), item.minimumSize().height())
        return max(height, 0)

    @staticmethod
    def _expands(item: QLayoutItem, direction: Qt.Orientation) -> bool:
        return bool(item.expandingDirections() & direction)


class _FlowHost(QWidget):
    """Contenido del scroll: su altura es la de las líneas, no la del hueco visible."""

    def __init__(self, hspacing: int, vspacing: int, margins: tuple[int, int, int, int]) -> None:
        super().__init__()
        self.flow = FlowLayout(self, hspacing=hspacing, vspacing=vspacing)
        self.flow.setContentsMargins(*margins)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self.flow.heightForWidth(width)

    def sizeHint(self) -> QSize:
        width = self.width() if self.width() > 0 else 320
        height = max(self.heightForWidth(width), self.flow.minimumSize().height())
        return QSize(max(self.flow.minimumSize().width(), 36), height)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()


class AdaptivePane(QScrollArea):
    """Da a un panel su altura natural y lo desplaza si el hueco es más bajo."""

    def __init__(self, content: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._content = content
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setWidget(content)
        enable_height_for_width(self)

    def hasHeightForWidth(self) -> bool:
        return True

    def _inner_width(self, width: int) -> int:
        # Reserva el ancho de la barra para no crear una línea de más al mostrarla.
        bar = self.verticalScrollBar().sizeHint().width()
        return max(width - bar, 1)

    def heightForWidth(self, width: int) -> int:
        inner = self._inner_width(width)
        if self._content.hasHeightForWidth():
            return self._content.heightForWidth(inner)
        return self._content.sizeHint().height()

    def sizeHint(self) -> QSize:
        width = self.width() if self.width() > 0 else 320
        return QSize(max(self._content.sizeHint().width(), 80), self.heightForWidth(width))

    def minimumSizeHint(self) -> QSize:
        # La altura de las líneas es el mínimo: la lista cede sitio antes que la cabecera.
        # Si aun así no cabe, el propio panel se desplaza.
        return QSize(80, max(self.sizeHint().height(), 72))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        width = max(self.viewport().width(), 1)
        if self._content.hasHeightForWidth():
            height = self._content.heightForWidth(width)
        else:
            height = self._content.sizeHint().height()
        if height > 0 and self._content.minimumHeight() != height:
            self._content.setMinimumHeight(height)


class FlowBar(QScrollArea):
    """Barra que crece con las líneas y, si el panel no da más alto, se desplaza."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        hspacing: int = 8,
        vspacing: int = 6,
        margins: tuple[int, int, int, int] = (0, 0, 0, 0),
    ) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._host = _FlowHost(hspacing, vspacing, margins)
        self.setWidget(self._host)
        enable_height_for_width(self)
        self.setMinimumHeight(36)

    @property
    def flow(self) -> FlowLayout:
        return self._host.flow

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._host.heightForWidth(max(width, 0))

    def sizeHint(self) -> QSize:
        width = self.width() if self.width() > 0 else 320
        return QSize(max(self.flow.minimumSize().width(), 36), self.heightForWidth(width))

    def minimumSizeHint(self) -> QSize:
        return QSize(36, max(self.flow.minimumSize().height(), 36))

    def refresh(self) -> None:
        self.setMinimumHeight(max(self.flow.minimumSize().height(), 36))
        self._host.updateGeometry()
        self.updateGeometry()


def enable_height_for_width(
    widget: QWidget,
    *,
    vertical: QSizePolicy.Policy = QSizePolicy.Policy.Minimum,
) -> None:
    """El panel reserva la altura de las líneas, en lugar de recortarlas."""
    policy = widget.sizePolicy()
    policy.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
    policy.setVerticalPolicy(vertical)
    policy.setHeightForWidth(True)
    widget.setSizePolicy(policy)


def flow_button(button: QPushButton) -> QPushButton:
    """Botón con el texto completo y un ancho mínimo que puede saltar de línea."""
    button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
    button.setMinimumWidth(36)
    if not button.toolTip():
        button.setToolTip(button.text())
    return button


def flow_field(widget: QWidget, minimum_width: int = 140) -> QWidget:
    """Campo que ocupa el hueco libre de su línea y salta si no cabe."""
    widget.setMinimumWidth(minimum_width)
    policy = widget.sizePolicy()
    policy.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
    policy.setVerticalPolicy(QSizePolicy.Policy.Preferred)
    policy.setHeightForWidth(True)
    widget.setSizePolicy(policy)
    return widget


def wrapping_form(form: QFormLayout) -> QFormLayout:
    """Si la etiqueta y el campo no caben, la etiqueta pasa encima."""
    form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
    return form


def wrapping_combo(combo: QComboBox, minimum_chars: int = 12) -> QComboBox:
    """El texto largo del combo no impone el ancho mínimo de la ventana."""
    combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    combo.setMinimumContentsLength(minimum_chars)
    combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return combo


def scrolling_body(outer: QVBoxLayout) -> QVBoxLayout:
    """Cuerpo del diálogo con scroll. La fila de botones se añade aparte."""
    page = QWidget()
    enable_height_for_width(page, vertical=QSizePolicy.Policy.Expanding)
    page_layout = QVBoxLayout(page)
    page_layout.setContentsMargins(0, 0, 0, 0)
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    area.setWidget(page)
    outer.addWidget(area, 1)
    return page_layout
