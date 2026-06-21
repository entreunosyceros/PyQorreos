"""
Gestión de claves OpenPGP (GnuPG).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from pyqorreos.core.openpgp import (
    gnupg_home,
    import_key_file,
    list_public_keys,
    list_secret_keys,
    openpgp_available,
    openpgp_unavailable_reason,
)
from pyqorreos.ui.theme import mark_role, prevent_context_menu


class OpenPgpKeysDialog(QDialog):
    """Lista e importa claves públicas/privadas."""

    def __init__(self, parent=None, *, use_system_home: bool = False) -> None:
        super().__init__(parent)
        self._use_system_home = use_system_home
        self.setWindowTitle("Claves OpenPGP")
        self.setMinimumSize(620, 420)
        prevent_context_menu(self)
        self._build_ui()
        self._reload_keys()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        if not openpgp_available():
            warn = QLabel(openpgp_unavailable_reason())
            warn.setWordWrap(True)
            mark_role(warn, "hint")
            layout.addWidget(warn)
        else:
            home = gnupg_home(self._use_system_home)
            hint = QLabel(
                f"Directorio de claves: {home}\n"
                "Las operaciones PGP solo se ejecutan al abrir o enviar mensajes cifrados."
            )
            hint.setWordWrap(True)
            mark_role(hint, "hint")
            layout.addWidget(hint)

        layout.addWidget(QLabel("Claves públicas"))
        self.pub_table = self._make_table()
        layout.addWidget(self.pub_table, 1)

        layout.addWidget(QLabel("Claves privadas (para firmar y descifrar)"))
        self.sec_table = self._make_table()
        layout.addWidget(self.sec_table, 1)

        btn_row = QHBoxLayout()
        import_btn = QPushButton("Importar clave…")
        import_btn.clicked.connect(self._import_key)
        refresh_btn = QPushButton("Actualizar")
        refresh_btn.clicked.connect(self._reload_keys)
        btn_row.addWidget(import_btn)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn:
            close_btn.clicked.connect(self.accept)
        layout.addWidget(buttons)

    @staticmethod
    def _make_table() -> QTableWidget:
        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["ID", "Huella", "Identidad"])
        table.horizontalHeader().setStretchLastSection(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        return table

    def _fill_table(self, table: QTableWidget, keys: list[dict[str, str]]) -> None:
        table.setRowCount(0)
        for key in keys:
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(key.get("keyid", "")))
            table.setItem(row, 1, QTableWidgetItem(key.get("fingerprint", "")))
            table.setItem(row, 2, QTableWidgetItem(key.get("uids", "")))

    def _reload_keys(self) -> None:
        self._fill_table(self.pub_table, list_public_keys(self._use_system_home))
        self._fill_table(self.sec_table, list_secret_keys(self._use_system_home))

    def _import_key(self) -> None:
        if not openpgp_available():
            QMessageBox.warning(self, "OpenPGP", openpgp_unavailable_reason())
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Importar clave OpenPGP",
            "",
            "Claves (*.asc *.gpg *.pgp);;Todos (*.*)",
        )
        if not path:
            return
        count, error = import_key_file(path, self._use_system_home)
        if error:
            QMessageBox.warning(self, "Importar clave", error)
            return
        QMessageBox.information(
            self, "Importar clave", f"Se importaron {count} clave(s)."
        )
        self._reload_keys()
