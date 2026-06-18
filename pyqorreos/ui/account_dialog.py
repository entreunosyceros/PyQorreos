"""
Diálogo de configuración de cuentas de correo.

Permite introducir los datos IMAP/SMTP, elegir un preset de proveedor
y probar la conexión antes de guardar.
"""

from __future__ import annotations

import uuid

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from pyqorreos.core.account import PROVIDER_PRESETS, MailAccount
from pyqorreos.core.mail_service import MailService
from pyqorreos.core.settings import Settings


class AccountDialog(QDialog):
    """Diálogo para añadir o editar una cuenta de correo."""

    def __init__(
        self,
        settings: Settings,
        account: MailAccount | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.account = account
        self._password = ""
        self.setWindowTitle("Editar cuenta" if account else "Nueva cuenta")
        self.setMinimumWidth(420)
        self._build_ui()
        if account:
            self._load_account(account)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        provider_row = QHBoxLayout()
        provider_row.addWidget(QLabel("Proveedor:"))
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(PROVIDER_PRESETS.keys())
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        provider_row.addWidget(self.provider_combo)
        layout.addLayout(provider_row)

        form = QFormLayout()
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("usuario@ejemplo.com")
        form.addRow("Correo:", self.email_edit)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Tu nombre")
        form.addRow("Nombre:", self.name_edit)

        self.imap_host_edit = QLineEdit()
        form.addRow("Servidor IMAP:", self.imap_host_edit)

        self.imap_port_spin = QSpinBox()
        self.imap_port_spin.setRange(1, 65535)
        self.imap_port_spin.setValue(993)
        form.addRow("Puerto IMAP:", self.imap_port_spin)

        self.smtp_host_edit = QLineEdit()
        form.addRow("Servidor SMTP:", self.smtp_host_edit)

        self.smtp_port_spin = QSpinBox()
        self.smtp_port_spin.setRange(1, 65535)
        self.smtp_port_spin.setValue(587)
        form.addRow("Puerto SMTP:", self.smtp_port_spin)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText(
            "Dejar vacío para mantener la actual" if self.account else ""
        )
        form.addRow("Contraseña:", self.password_edit)

        self.auth_combo = QComboBox()
        self.auth_combo.addItems(["Contraseña / app password", "OAuth2 (próximamente)"])
        form.addRow("Autenticación:", self.auth_combo)

        self.signature_edit = QPlainTextEdit()
        self.signature_edit.setPlaceholderText("Firma al pie de los correos redactados…")
        self.signature_edit.setMaximumHeight(80)
        form.addRow("Firma:", self.signature_edit)

        layout.addLayout(form)

        self.test_btn = QPushButton("Probar conexión")
        self.test_btn.clicked.connect(self._test_connection)
        layout.addWidget(self.test_btn)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._on_provider_changed(self.provider_combo.currentText())

    def _on_provider_changed(self, provider: str) -> None:
        """Rellena automáticamente los campos al elegir un proveedor conocido."""
        preset = PROVIDER_PRESETS.get(provider, {})
        if not preset:
            return
        self.imap_host_edit.setText(preset.get("imap_host", ""))
        self.imap_port_spin.setValue(preset.get("imap_port", 993))
        self.smtp_host_edit.setText(preset.get("smtp_host", ""))
        self.smtp_port_spin.setValue(preset.get("smtp_port", 587))

    def _load_account(self, account: MailAccount) -> None:
        self.email_edit.setText(account.email)
        self.name_edit.setText(account.display_name)
        self.imap_host_edit.setText(account.imap_host)
        self.imap_port_spin.setValue(account.imap_port)
        self.smtp_host_edit.setText(account.smtp_host)
        self.smtp_port_spin.setValue(account.smtp_port)
        self.provider_combo.setCurrentText("Personalizado")
        if account.auth_method == "oauth2":
            self.auth_combo.setCurrentIndex(1)
        self.signature_edit.setPlainText(account.signature)

    def _get_account(self) -> MailAccount:
        return MailAccount(
            id=self.account.id if self.account else str(uuid.uuid4()),
            email=self.email_edit.text().strip(),
            display_name=self.name_edit.text().strip(),
            imap_host=self.imap_host_edit.text().strip(),
            imap_port=self.imap_port_spin.value(),
            smtp_host=self.smtp_host_edit.text().strip(),
            smtp_port=self.smtp_port_spin.value(),
            use_ssl=True,
            auth_method="oauth2" if self.auth_combo.currentIndex() == 1 else "password",
            signature=self.signature_edit.toPlainText().strip(),
        )

    def _get_password(self) -> str:
        pwd = self.password_edit.text()
        if pwd:
            return pwd
        if self.account:
            return self.settings.get_password(self.account.id) or ""
        return ""

    def _test_connection(self) -> None:
        account = self._get_account()
        password = self._get_password()
        if not account.email or not password:
            QMessageBox.warning(self, "Datos incompletos", "Indica correo y contraseña.")
            return

        self.test_btn.setEnabled(False)
        self.test_btn.setText("Probando…")
        service = MailService(account, password)
        ok, message = service.test_connection()
        self.test_btn.setEnabled(True)
        self.test_btn.setText("Probar conexión")

        if ok:
            QMessageBox.information(self, "Conexión OK", message)
        else:
            QMessageBox.critical(self, "Error de conexión", message)

    def _on_accept(self) -> None:
        account = self._get_account()
        if not account.email:
            QMessageBox.warning(self, "Error", "El correo es obligatorio.")
            return
        password = self.password_edit.text()
        if not self.account and not password:
            QMessageBox.warning(self, "Error", "La contraseña es obligatoria.")
            return
        self._result_account = account
        self._password = password
        self.accept()

    def get_result(self) -> tuple[MailAccount, str]:
        """Devuelve la cuenta configurada y la contraseña introducida."""
        return self._result_account, self._password
