"""
Diálogo de configuración de cuentas de correo.

Permite introducir los datos IMAP/SMTP, elegir un preset de proveedor,
autenticación por contraseña u OAuth2 (Gmail / Outlook) y probar la conexión.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
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

from pyqorreos.core.account import (
    GMAIL_APP_PASSWORD_HELP_URL,
    GMAIL_APP_PASSWORD_URL,
    PROVIDER_PRESETS,
    MailAccount,
    is_gmail_account,
)
from pyqorreos.core.mail_service import MailService
from pyqorreos.core.oauth import (
    AuthMethod,
    OAuthToken,
    detect_oauth_provider,
    has_oauth_token,
    oauth_clients_configured,
    oauth_setup_instructions,
)
from pyqorreos.core.settings import Settings
from pyqorreos.ui.theme import mark_role, prevent_context_menu
from pyqorreos.ui.workers import OAuthFlowWorker


class AccountDialog(QDialog):
    """Diálogo para añadir o editar una cuenta de correo."""

    def __init__(
        self,
        settings: Settings,
        account: MailAccount | None = None,
        parent=None,
        *,
        on_configure_oauth: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.account = account
        self._on_configure_oauth = on_configure_oauth
        self._password = ""
        self._draft_account_id = account.id if account else str(uuid.uuid4())
        self._oauth_ready = (
            has_oauth_token(self._draft_account_id) if account else False
        )
        self._oauth_worker: OAuthFlowWorker | None = None
        self._pending_access_token: str = ""
        self.setWindowTitle("Editar cuenta" if account else "Nueva cuenta")
        self.setMinimumWidth(460)
        self._build_ui()
        prevent_context_menu(self)
        if account:
            self._load_account(account)
        self._on_auth_method_changed(self.auth_combo.currentIndex())

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        provider_row = QHBoxLayout()
        provider_row.addWidget(QLabel("Proveedor:"))
        self.provider_combo = QComboBox()
        self.provider_combo.blockSignals(True)
        self.provider_combo.addItems(PROVIDER_PRESETS.keys())
        self.provider_combo.blockSignals(False)
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        provider_row.addWidget(self.provider_combo)
        layout.addLayout(provider_row)

        self.gmail_notice = QLabel()
        self.gmail_notice.setWordWrap(True)
        self.gmail_notice.setTextFormat(Qt.TextFormat.RichText)
        self.gmail_notice.setOpenExternalLinks(True)
        mark_role(self.gmail_notice, "link-warning")
        self.gmail_notice.setVisible(False)
        layout.addWidget(self.gmail_notice)

        self.oauth_notice = QLabel()
        self.oauth_notice.setWordWrap(True)
        mark_role(self.oauth_notice, "hint")
        self.oauth_notice.setVisible(False)
        layout.addWidget(self.oauth_notice)

        self.oauth_config_btn = QPushButton("Configurar OAuth en Preferencias…")
        self.oauth_config_btn.clicked.connect(self._open_oauth_preferences)
        self.oauth_config_btn.setVisible(False)
        layout.addWidget(self.oauth_config_btn)

        form = QFormLayout()
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("usuario@ejemplo.com")
        self.email_edit.textChanged.connect(self._on_identity_changed)
        form.addRow("Correo:", self.email_edit)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Tu nombre")
        form.addRow("Nombre:", self.name_edit)

        self.imap_host_edit = QLineEdit()
        self.imap_host_edit.textChanged.connect(self._on_identity_changed)
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
        self.password_label = QLabel("Contraseña:")
        form.addRow(self.password_label, self.password_edit)

        self.auth_combo = QComboBox()
        self.auth_combo.addItems(
            ["Contraseña / app password", "OAuth2 (Gmail / Outlook)"]
        )
        self.auth_combo.currentIndexChanged.connect(self._on_auth_method_changed)
        form.addRow("Autenticación:", self.auth_combo)

        self.signature_edit = QPlainTextEdit()
        self.signature_edit.setPlaceholderText("Firma al pie de los correos redactados…")
        self.signature_edit.setMaximumHeight(80)
        form.addRow("Firma:", self.signature_edit)

        layout.addLayout(form)

        oauth_row = QHBoxLayout()
        self.oauth_btn = QPushButton("Identificarse con Google")
        mark_role(self.oauth_btn, "primary")
        self.oauth_btn.clicked.connect(self._oauth_sign_in)
        self.oauth_status = QLabel("")
        mark_role(self.oauth_status, "hint")
        oauth_row.addWidget(self.oauth_btn)
        oauth_row.addWidget(self.oauth_status, 1)
        layout.addLayout(oauth_row)
        self._oauth_row_widgets = (self.oauth_btn, self.oauth_status)

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

    def _oauth_provider_key(self) -> str | None:
        return detect_oauth_provider(
            self.email_edit.text().strip(),
            self.imap_host_edit.text().strip(),
        )

    def _is_oauth_mode(self) -> bool:
        return self.auth_combo.currentIndex() == 1

    def _on_identity_changed(self) -> None:
        self._update_gmail_notice()
        self._update_oauth_availability()

    def _on_auth_method_changed(self, _index: int) -> None:
        oauth_mode = self._is_oauth_mode()
        self.password_label.setVisible(not oauth_mode)
        self.password_edit.setVisible(not oauth_mode)
        for widget in self._oauth_row_widgets:
            widget.setVisible(oauth_mode)
        self._update_gmail_notice()
        self._update_oauth_availability()
        self._refresh_oauth_status()

    def _update_oauth_availability(self) -> None:
        provider_key = self._oauth_provider_key()
        can_oauth = provider_key is not None
        model = self.auth_combo.model()
        if model is not None:
            item = model.item(1)
            if item is not None:
                item.setEnabled(can_oauth)
        if self._is_oauth_mode() and not can_oauth:
            self.auth_combo.setCurrentIndex(0)
            return
        if self._is_oauth_mode():
            provider = provider_key or "gmail"
            label = "Google" if provider == "gmail" else "Microsoft"
            self.oauth_btn.setText(f"Identificarse con {label}")
            configured = oauth_clients_configured(provider)
            if configured:
                self.oauth_notice.setText(
                    f"Pulsa «Identificarse con {label}». "
                    "Se abrirá el navegador; al terminar, los tokens se guardan en el llavero."
                )
            else:
                self.oauth_notice.setText(oauth_setup_instructions(provider))
            self.oauth_notice.setVisible(True)
            show_prefs_btn = (
                self._is_oauth_mode()
                and not configured
                and self._on_configure_oauth is not None
            )
            self.oauth_config_btn.setVisible(show_prefs_btn)
        else:
            self.oauth_notice.setVisible(False)
            self.oauth_config_btn.setVisible(False)

    def _open_oauth_preferences(self) -> None:
        if self._on_configure_oauth:
            self._on_configure_oauth()
            self._update_oauth_availability()

    def _refresh_oauth_status(self) -> None:
        if not self._is_oauth_mode():
            self.oauth_status.setText("")
            return
        if self._oauth_ready or has_oauth_token(self._draft_account_id):
            self.oauth_status.setText("✓ Sesión OAuth activa")
        else:
            self.oauth_status.setText("Pendiente de autorización")

    def _update_gmail_notice(self) -> None:
        if self._is_oauth_mode():
            self.gmail_notice.setVisible(False)
            return
        gmail = is_gmail_account(
            provider=self.provider_combo.currentText(),
            email=self.email_edit.text(),
            imap_host=self.imap_host_edit.text(),
        )
        self.gmail_notice.setVisible(gmail)
        if gmail:
            self.gmail_notice.setText(
                "<b>Cuenta Gmail</b><br>"
                "Google <b>no permite</b> usar la contraseña habitual de tu cuenta. "
                "Necesitas una <b>contraseña de aplicación</b> de 16 caracteres, "
                "o elige <b>OAuth</b> en la sección <b>Autenticación</b>.<br>"
                "1. Activa la <b>verificación en 2 pasos</b> en tu cuenta Google.<br>"
                f'2. Crea la contraseña en <a href="{GMAIL_APP_PASSWORD_URL}">'
                "Contraseñas de aplicaciones</a> (Seguridad de Google).<br>"
                f'<a href="{GMAIL_APP_PASSWORD_HELP_URL}">Guía oficial de Google</a>'
            )
            self.password_label.setText("Contraseña de aplicación:")
            if not self.account:
                self.password_edit.setPlaceholderText("16 caracteres, sin espacios")
            elif not self.password_edit.text():
                self.password_edit.setPlaceholderText(
                    "Dejar vacío para mantener la actual (contraseña de aplicación)"
                )
        else:
            self.password_label.setText("Contraseña:")
            if self.account:
                self.password_edit.setPlaceholderText("Dejar vacío para mantener la actual")
            else:
                self.password_edit.setPlaceholderText("")

    def _on_provider_changed(self, provider: str) -> None:
        """Rellena automáticamente los campos al elegir un proveedor conocido."""
        preset = PROVIDER_PRESETS.get(provider, {})
        if preset:
            self.imap_host_edit.setText(preset.get("imap_host", ""))
            self.imap_port_spin.setValue(preset.get("imap_port", 993))
            self.smtp_host_edit.setText(preset.get("smtp_host", ""))
            self.smtp_port_spin.setValue(preset.get("smtp_port", 587))
        self._on_identity_changed()

    def _load_account(self, account: MailAccount) -> None:
        self.email_edit.blockSignals(True)
        self.imap_host_edit.blockSignals(True)
        self.provider_combo.blockSignals(True)
        self.email_edit.setText(account.email)
        self.name_edit.setText(account.display_name)
        self.imap_host_edit.setText(account.imap_host)
        self.imap_port_spin.setValue(account.imap_port)
        self.smtp_host_edit.setText(account.smtp_host)
        self.smtp_port_spin.setValue(account.smtp_port)
        self.provider_combo.setCurrentText("Personalizado")
        self.email_edit.blockSignals(False)
        self.imap_host_edit.blockSignals(False)
        self.provider_combo.blockSignals(False)
        if account.auth_method == AuthMethod.OAUTH2.value:
            self.auth_combo.setCurrentIndex(1)
        self.signature_edit.setPlainText(account.signature)
        self._on_identity_changed()

    def _get_account(self) -> MailAccount:
        return MailAccount(
            id=self._draft_account_id,
            email=self.email_edit.text().strip(),
            display_name=self.name_edit.text().strip(),
            imap_host=self.imap_host_edit.text().strip(),
            imap_port=self.imap_port_spin.value(),
            smtp_host=self.smtp_host_edit.text().strip(),
            smtp_port=self.smtp_port_spin.value(),
            use_ssl=True,
            auth_method=(
                AuthMethod.OAUTH2.value
                if self._is_oauth_mode()
                else AuthMethod.PASSWORD.value
            ),
            signature=self.signature_edit.toPlainText().strip(),
        )

    def _get_auth_secret(self, account: MailAccount) -> str:
        if account.auth_method == AuthMethod.OAUTH2.value:
            if self._pending_access_token:
                return self._pending_access_token
            secret = self.settings.get_auth_secret(account)
            return secret or ""
        pwd = self.password_edit.text()
        if pwd:
            return pwd
        if self.account:
            return self.settings.get_password(self.account.id) or ""
        return ""

    def _oauth_sign_in(self) -> None:
        account = self._get_account()
        if not account.email:
            QMessageBox.warning(self, "Correo obligatorio", "Indica el correo antes de OAuth.")
            return
        provider_key = self._oauth_provider_key()
        if not provider_key:
            QMessageBox.warning(
                self,
                "OAuth2",
                "OAuth2 solo está disponible para cuentas Gmail u Outlook.",
            )
            return
        if not oauth_clients_configured(provider_key):
            QMessageBox.information(
                self,
                "Configurar OAuth",
                oauth_setup_instructions(provider_key),
            )
            return
        if self._oauth_worker and self._oauth_worker.isRunning():
            return

        self.oauth_btn.setEnabled(False)
        self.test_btn.setEnabled(False)
        self.oauth_status.setText("Esperando autorización en el navegador…")

        worker = OAuthFlowWorker(provider_key, self._draft_account_id)
        worker.open_url.connect(self._open_oauth_url)
        worker.signals.finished.connect(self._on_oauth_finished)
        worker.signals.error.connect(self._on_oauth_error)
        worker.finished.connect(worker.deleteLater)
        self._oauth_worker = worker
        worker.start()

    def _open_oauth_url(self, url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))

    def _on_oauth_finished(self, token: OAuthToken) -> None:
        self._oauth_worker = None
        self.oauth_btn.setEnabled(True)
        self.test_btn.setEnabled(True)
        self._oauth_ready = True
        self._pending_access_token = token.access_token
        self._refresh_oauth_status()
        QMessageBox.information(
            self,
            "Identificación correcta",
            "Sesión autorizada. El refresh_token quedó en el llavero; "
            "la conexión usará el access_token (se renueva solo al caducar).",
        )

    def _on_oauth_error(self, message: str) -> None:
        self._oauth_worker = None
        self.oauth_btn.setEnabled(True)
        self.test_btn.setEnabled(True)
        self._refresh_oauth_status()
        QMessageBox.critical(self, "Error OAuth", message)

    def reject(self) -> None:
        if self._oauth_worker and self._oauth_worker.isRunning():
            self._oauth_worker.wait(3000)
        super().reject()

    def _test_connection(self) -> None:
        account = self._get_account()
        auth_secret = self._get_auth_secret(account)
        if not account.email:
            QMessageBox.warning(self, "Datos incompletos", "Indica el correo.")
            return
        if not auth_secret:
            if account.auth_method == AuthMethod.OAUTH2.value:
                QMessageBox.warning(
                    self,
                    "OAuth2",
                    "Pulsa «Identificarse con Google/Microsoft» antes de probar la conexión.",
                )
            else:
                QMessageBox.warning(self, "Datos incompletos", "Indica correo y contraseña.")
            return

        self.test_btn.setEnabled(False)
        self.test_btn.setText("Probando…")
        service = MailService(account, auth_secret)
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
        if account.auth_method == AuthMethod.OAUTH2.value:
            if not (self._oauth_ready or has_oauth_token(self._draft_account_id)):
                QMessageBox.warning(
                    self,
                    "OAuth2",
                    "Identifícate con Google/Microsoft antes de guardar.",
                )
                return
            self._password = ""
        else:
            password = self.password_edit.text()
            if not self.account and not password:
                QMessageBox.warning(self, "Error", "La contraseña es obligatoria.")
                return
            self._password = password
        self._result_account = account
        self.accept()

    def get_result(self) -> tuple[MailAccount, str]:
        """Devuelve la cuenta configurada y la contraseña introducida (vacía si OAuth)."""
        return self._result_account, self._password
