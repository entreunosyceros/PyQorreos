"""
Diálogo de agenda de contactos de correo.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from pyqorreos.core.address_book import (
    AddressBook,
    AddressContact,
    get_address_book,
    is_valid_email,
    normalize_email,
)
from pyqorreos.ui.theme import mark_role, prevent_context_menu
from pyqorreos.ui.workers import LoadContactsWorker


class AddressBookDialog(QDialog):
    """Gestiona contactos o devuelve uno al redactar (modo selección)."""

    def __init__(
        self,
        parent=None,
        *,
        book: AddressBook | None = None,
        pick_mode: bool = False,
    ) -> None:
        super().__init__(parent)
        self._book = book or get_address_book()
        self._pick_mode = pick_mode
        self._selected_email: str | None = None
        self._load_worker: LoadContactsWorker | None = None
        self.setWindowTitle("Elegir contacto" if pick_mode else "Agenda de contactos")
        self.setMinimumSize(640, 420)
        self.resize(760, 480)
        prevent_context_menu(self)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self._reload_table)
        self._build_ui()
        if self._book.is_loaded:
            self._reload_table()
        else:
            self._status_label.setText("Cargando agenda…")
            QTimer.singleShot(0, self._start_load_worker)

    def selected_email(self) -> str | None:
        return self._selected_email

    @staticmethod
    def pick_email(parent=None, book: AddressBook | None = None) -> str | None:
        dialog = AddressBookDialog(parent, book=book, pick_mode=True)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.selected_email()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        hint = QLabel(
            "Contactos guardados localmente. Solo se cargan al abrir esta ventana "
            "o al redactar; no afectan a la sincronización del correo."
        )
        hint.setWordWrap(True)
        mark_role(hint, "hint")
        layout.addWidget(hint)

        self._status_label = QLabel("")
        mark_role(self._status_label, "hint")
        layout.addWidget(self._status_label)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Buscar:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Nombre o dirección de correo")
        self.search_edit.textChanged.connect(self._schedule_reload)
        search_row.addWidget(self.search_edit, 1)
        layout.addLayout(search_row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["★", "Nombre", "Correo"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 36)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._on_row_activated)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("Añadir…")
        self.add_btn.clicked.connect(self._add_contact)
        self.edit_btn = QPushButton("Editar…")
        self.edit_btn.clicked.connect(self._edit_contact)
        self.remove_btn = QPushButton("Eliminar")
        self.remove_btn.clicked.connect(self._remove_contact)
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.edit_btn)
        btn_row.addWidget(self.remove_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        buttons = QDialogButtonBox()
        if self._pick_mode:
            use_btn = buttons.addButton("Usar contacto", QDialogButtonBox.ButtonRole.AcceptRole)
            if use_btn:
                use_btn.clicked.connect(self._use_selected)
        buttons.addButton(QDialogButtonBox.StandardButton.Close)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn:
            close_btn.setText("Cerrar")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _start_load_worker(self) -> None:
        if self._book.is_loaded:
            self._reload_table()
            return
        worker = LoadContactsWorker()
        worker.signals.finished.connect(self._on_contacts_loaded)
        worker.signals.error.connect(self._on_contacts_load_error)
        worker.finished.connect(worker.deleteLater)
        worker.destroyed.connect(self._on_load_worker_destroyed)
        self._load_worker = worker
        worker.start()

    def _on_load_worker_destroyed(self, *_args) -> None:
        self._load_worker = None

    def _on_contacts_loaded(self, contacts: object) -> None:
        if not isinstance(contacts, list):
            self._status_label.setText("No se pudo cargar la agenda.")
            return
        self._book.set_contacts(contacts)
        self._reload_table()

    def _on_contacts_load_error(self, message: str) -> None:
        self._status_label.setText(message or "No se pudo cargar la agenda.")

    def _schedule_reload(self) -> None:
        if not self._book.is_loaded:
            return
        self._search_timer.start()

    def _filtered_contacts(self) -> list[AddressContact]:
        query = self.search_edit.text().strip()
        if query:
            return self._book.search(query, limit=500)
        return self._book.contacts()

    def _reload_table(self) -> None:
        if not self._book.is_loaded:
            return
        contacts = self._filtered_contacts()
        self._status_label.setText("")
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(len(contacts))
        for row, contact in enumerate(contacts):
            star = QTableWidgetItem("★" if contact.important else "")
            name = QTableWidgetItem(contact.name)
            email = QTableWidgetItem(contact.email)
            email.setData(Qt.ItemDataRole.UserRole, contact.id)
            self.table.setItem(row, 0, star)
            self.table.setItem(row, 1, name)
            self.table.setItem(row, 2, email)
        self.table.setUpdatesEnabled(True)

    def _selected_contact(self) -> AddressContact | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 2)
        if item is None:
            return None
        contact_id = item.data(Qt.ItemDataRole.UserRole)
        if not contact_id:
            return None
        return self._book.find_by_id(str(contact_id))

    def _on_row_activated(self, _index) -> None:
        if self._pick_mode:
            self._use_selected()
        else:
            self._edit_contact()

    def _use_selected(self) -> None:
        contact = self._selected_contact()
        if not contact:
            QMessageBox.information(self, "Agenda", "Selecciona un contacto de la lista.")
            return
        self._selected_email = contact.email
        self.accept()

    def _add_contact(self) -> None:
        dialog = _ContactEditorDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.contact_data()
        try:
            self._book.upsert(
                data["email"],
                name=data["name"],
                notes=data["notes"],
                important=data["important"],
            )
            self._book.save()
        except ValueError as exc:
            QMessageBox.warning(self, "Agenda", str(exc))
            return
        self._reload_table()

    def _edit_contact(self) -> None:
        contact = self._selected_contact()
        if not contact:
            QMessageBox.information(self, "Agenda", "Selecciona un contacto para editar.")
            return
        dialog = _ContactEditorDialog(contact=contact, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.contact_data()
        try:
            updated = AddressContact(
                id=contact.id,
                email=normalize_email(data["email"]),
                name=data["name"],
                notes=data["notes"],
                important=data["important"],
            )
            self._book.update(updated)
            self._book.save()
        except (ValueError, KeyError) as exc:
            QMessageBox.warning(self, "Agenda", str(exc))
            return
        self._reload_table()

    def _remove_contact(self) -> None:
        contact = self._selected_contact()
        if not contact:
            QMessageBox.information(self, "Agenda", "Selecciona un contacto para eliminar.")
            return
        reply = QMessageBox.question(
            self,
            "Eliminar contacto",
            f"¿Quitar de la agenda a\n{contact.display_label()}?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._book.remove(contact.id)
        self._book.save()
        self._reload_table()

    def closeEvent(self, event) -> None:
        if self._load_worker is not None:
            try:
                self._load_worker.signals.finished.disconnect(self._on_contacts_loaded)
                self._load_worker.signals.error.disconnect(self._on_contacts_load_error)
            except (RuntimeError, TypeError):
                pass
        self._book.save()
        super().closeEvent(event)


class _ContactEditorDialog(QDialog):
    def __init__(
        self,
        *,
        contact: AddressContact | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._contact = contact
        self.setWindowTitle("Editar contacto" if contact else "Nuevo contacto")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.email_edit = QLineEdit(contact.email if contact else "")
        self.email_edit.setPlaceholderText("correo@ejemplo.com")
        self.name_edit = QLineEdit(contact.name if contact else "")
        self.name_edit.setPlaceholderText("Nombre (opcional)")
        self.notes_edit = QPlainTextEdit(contact.notes if contact else "")
        self.notes_edit.setPlaceholderText("Notas (opcional)")
        self.notes_edit.setMaximumHeight(80)
        self.important_check = QCheckBox("Marcar como importante")
        self.important_check.setChecked(contact.important if contact else False)
        form.addRow("Correo:", self.email_edit)
        form.addRow("Nombre:", self.name_edit)
        form.addRow("Notas:", self.notes_edit)
        form.addRow("", self.important_check)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        if not is_valid_email(self.email_edit.text()):
            QMessageBox.warning(self, "Contacto", "Introduce una dirección de correo válida.")
            return
        self.accept()

    def contact_data(self) -> dict:
        return {
            "email": self.email_edit.text(),
            "name": self.name_edit.text(),
            "notes": self.notes_edit.toPlainText(),
            "important": self.important_check.isChecked(),
        }
