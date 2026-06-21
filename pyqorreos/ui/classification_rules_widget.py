"""
Editor de reglas de clasificación (remitentes importante / spam).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pyqorreos.core.classifier import ClassificationRules
from pyqorreos.ui.theme import mark_role


class ClassificationRulesWidget(QWidget):
    """Lista y edita remitentes aprendidos por el clasificador."""

    def __init__(self, rules: ClassificationRules, parent=None) -> None:
        super().__init__(parent)
        self._rules = rules
        self._build_ui()
        self._reload_lists()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        hint = QLabel(
            "Remitentes que marcaste como importante o spam. "
            "Se aplican al sincronizar y al abrir mensajes nuevos."
        )
        hint.setWordWrap(True)
        mark_role(hint, "hint")
        layout.addWidget(hint)

        columns = QHBoxLayout()
        for title, attr in (
            ("Importantes", "_important_list"),
            ("Spam", "_spam_list"),
        ):
            col = QVBoxLayout()
            col.addWidget(QLabel(title))
            lst = QListWidget()
            setattr(self, attr, lst)
            col.addWidget(lst, 1)
            btn = QPushButton("Quitar seleccionado")
            btn.clicked.connect(lambda _c=False, a=attr: self._remove_selected(a))
            col.addWidget(btn)
            columns.addLayout(col, 1)
        layout.addLayout(columns, 1)

    def _reload_lists(self) -> None:
        self._important_list.clear()
        self._spam_list.clear()
        for addr in sorted(self._rules.important_senders):
            self._important_list.addItem(addr)
        for addr in sorted(self._rules.spam_senders):
            self._spam_list.addItem(addr)

    def _remove_selected(self, list_attr: str) -> None:
        lst: QListWidget = getattr(self, list_attr)
        row = lst.currentRow()
        if row < 0:
            return
        addr = lst.item(row).text()
        category = "important" if list_attr == "_important_list" else "spam"
        reply = QMessageBox.question(
            self,
            "Quitar regla",
            f"¿Dejar de clasificar automáticamente a\n{addr}\ncomo {category}?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        if category == "important":
            self._rules.important_senders = [
                s for s in self._rules.important_senders if s != addr
            ]
        else:
            self._rules.spam_senders = [
                s for s in self._rules.spam_senders if s != addr
            ]
        self._reload_lists()

    def get_rules(self) -> ClassificationRules:
        return self._rules
