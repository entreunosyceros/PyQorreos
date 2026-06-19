"""
Diálogo para gestionar varias cuentas de correo.

Permite añadir, editar, eliminar y elegir la cuenta activa.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from pyqorreos.core.account import MailAccount
from pyqorreos.core.mail_cache import MailCache
from pyqorreos.core.settings import Settings
from pyqorreos.ui.account_dialog import AccountDialog
from pyqorreos.ui.theme import mark_role, prevent_context_menu


class AccountsManagerDialog(QDialog):
    """Lista y administra todas las cuentas configuradas."""

    def __init__(
        self,
        settings: Settings,
        accounts: list[MailAccount],
        current_account_id: str | None = None,
        parent=None,
        *,
        on_configure_oauth=None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.accounts = list(accounts)
        self.current_account_id = current_account_id
        self.selected_account_id: str | None = current_account_id
        self._on_configure_oauth = on_configure_oauth
        self._cache = MailCache()

        self.setWindowTitle("Cuentas de correo")
        self.setMinimumSize(480, 320)
        self._build_ui()
        prevent_context_menu(self)
        self._refresh_list()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        hint = QLabel(
            "Puedes configurar varias cuentas y cambiar entre ellas desde el selector "
            "de la ventana principal."
        )
        hint.setWordWrap(True)
        mark_role(hint, "hint")
        layout.addWidget(hint)

        self.account_list = QListWidget()
        self.account_list.itemDoubleClicked.connect(self._use_selected)
        layout.addWidget(self.account_list)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("+ Añadir")
        mark_role(self.btn_add, "primary")
        self.btn_add.clicked.connect(self._add_account)
        self.btn_edit = QPushButton("Editar")
        mark_role(self.btn_edit, "default")
        self.btn_edit.clicked.connect(self._edit_account)
        self.btn_remove = QPushButton("Eliminar")
        mark_role(self.btn_remove, "danger")
        self.btn_remove.clicked.connect(self._remove_account)
        self.btn_use = QPushButton("Usar esta cuenta")
        self.btn_use.clicked.connect(self._use_selected)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_edit)
        btn_row.addWidget(self.btn_remove)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_use)
        layout.addLayout(btn_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn:
            close_btn.setText("Cerrar")
        layout.addWidget(buttons)

    def _account_label(self, account: MailAccount) -> str:
        name = account.display_name or account.email.split("@", 1)[0]
        active = "  ★ activa" if account.id == self.current_account_id else ""
        return f"{name}  <{account.email}>{active}"

    def _refresh_list(self) -> None:
        self.account_list.clear()
        for account in self.accounts:
            item = QListWidgetItem(self._account_label(account))
            item.setData(Qt.ItemDataRole.UserRole, account.id)
            if account.id == self.current_account_id:
                item.setSelected(True)
                self.account_list.setCurrentItem(item)
            self.account_list.addItem(item)
        has_selection = self.account_list.currentItem() is not None
        self.btn_edit.setEnabled(has_selection)
        self.btn_remove.setEnabled(has_selection)
        self.btn_use.setEnabled(has_selection)

    def _selected_account(self) -> MailAccount | None:
        item = self.account_list.currentItem()
        if not item:
            return None
        account_id = item.data(Qt.ItemDataRole.UserRole)
        return next((a for a in self.accounts if a.id == account_id), None)

    def _add_account(self) -> None:
        dialog = AccountDialog(
            self.settings,
            parent=self,
            on_configure_oauth=self._on_configure_oauth,
        )
        if dialog.exec() != AccountDialog.DialogCode.Accepted:
            return
        account, password = dialog.get_result()
        duplicate = next(
            (
                a
                for a in self.accounts
                if a.email.lower() == account.email.lower() and a.id != account.id
            ),
            None,
        )
        if duplicate:
            QMessageBox.warning(
                self,
                "Correo duplicado",
                f"Ya existe una cuenta con {account.email}. Edítala en su lugar.",
            )
            return
        if password:
            self.settings.store_password(account.id, password)
        self.accounts.append(account)
        self.settings.save_accounts(self.accounts)
        self.selected_account_id = account.id
        self.current_account_id = account.id
        self._refresh_list()
        QMessageBox.information(
            self,
            "Cuenta añadida",
            f"Se añadió {account.email}. Pulsa «Usar esta cuenta» o cierra para conectar.",
        )

    def _edit_account(self) -> None:
        account = self._selected_account()
        if not account:
            return
        dialog = AccountDialog(
            self.settings,
            account=account,
            parent=self,
            on_configure_oauth=self._on_configure_oauth,
        )
        if dialog.exec() != AccountDialog.DialogCode.Accepted:
            return
        updated, password = dialog.get_result()
        idx = self.accounts.index(account)
        self.accounts[idx] = updated
        if password:
            self.settings.store_password(updated.id, password)
        self.settings.save_accounts(self.accounts)
        self._refresh_list()

    def _remove_account(self) -> None:
        account = self._selected_account()
        if not account:
            return
        reply = QMessageBox.question(
            self,
            "Eliminar cuenta",
            f"¿Eliminar la cuenta {account.email}?\n\n"
            "Se borrarán sus credenciales y la caché local de correos.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.settings.delete_account_secrets(account.id, account.auth_method)
        self._cache.delete_account(account.id)
        self.accounts = [a for a in self.accounts if a.id != account.id]
        self.settings.save_accounts(self.accounts)
        if self.selected_account_id == account.id:
            self.selected_account_id = None
        if self.current_account_id == account.id:
            self.current_account_id = None
        self._refresh_list()

    def _use_selected(self) -> None:
        account = self._selected_account()
        if not account:
            return
        self.selected_account_id = account.id
        self.current_account_id = account.id
        self.accept()

    def get_accounts(self) -> list[MailAccount]:
        return self.accounts
