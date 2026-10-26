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
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pyqorreos.core.account import (
    AOL_APP_PASSWORD_URL,
    GMAIL_APP_PASSWORD_HELP_URL,
    GMAIL_APP_PASSWORD_URL,
    GMX_IMAP_ENABLE_URL,
    PROVIDER_PRESETS,
    MailAccount,
    detect_provider_from_email,
    detect_provider_preset,
    simple_browser_login,
    is_aol_email,
    is_gmail_account,
    is_gmx_email,
    is_microsoft_email,
)
from pyqorreos.core.mail_service import MailService
from pyqorreos.core.oauth import (
    AuthMethod,
    OAuthToken,
    detect_oauth_provider,
    oauth_flow_status_message,
    has_oauth_token,
    oauth_clients_configured,
    oauth_setup_instructions,
)
from pyqorreos.core.oauth_clients import oauth_client_source
from pyqorreos.core.settings import Settings
from pyqorreos.ui.flow_layout import (
    FlowLayout,
    enable_height_for_width,
    flow_button,
    flow_field,
    scrolling_body,
    wrapping_combo,
    wrapping_form,
)
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
        self._show_advanced = bool(
            account and account.auth_method != AuthMethod.OAUTH2.value
        )
        self.setWindowTitle("Editar cuenta" if account else "Nueva cuenta")
        self.setMinimumSize(440, 360)
        self._build_ui()
        prevent_context_menu(self)
        if account:
            self._load_account(account)
        self._on_auth_method_changed(self.auth_combo.currentIndex())

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        body = scrolling_body(layout)

        provider_host = QWidget()
        self._provider_host = provider_host
        enable_height_for_width(provider_host)
        provider_row = FlowLayout(provider_host, hspacing=8, vspacing=6)
        provider_row.addWidget(QLabel("Proveedor:"))
        self.provider_combo = wrapping_combo(QComboBox(), 16)
        self.provider_combo.blockSignals(True)
        self.provider_combo.addItems(PROVIDER_PRESETS.keys())
        self.provider_combo.blockSignals(False)
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        provider_row.addWidget(self.provider_combo)
        body.addWidget(provider_host)

        self.provider_notice = QLabel()
        self.provider_notice.setWordWrap(True)
        self.provider_notice.setTextFormat(Qt.TextFormat.RichText)
        self.provider_notice.setOpenExternalLinks(True)
        mark_role(self.provider_notice, "link-warning")
        self.provider_notice.setVisible(False)
        body.addWidget(self.provider_notice)

        self.oauth_notice = QLabel()
        self.oauth_notice.setWordWrap(True)
        mark_role(self.oauth_notice, "hint")
        self.oauth_notice.setVisible(False)
        body.addWidget(self.oauth_notice)

        self.oauth_config_btn = flow_button(
            QPushButton("Configurar inicio de sesión Google/Microsoft…")
        )
        self.oauth_config_btn.clicked.connect(self._open_oauth_setup)
        self.oauth_config_btn.setVisible(False)
        body.addWidget(self.oauth_config_btn)

        identity = QGroupBox("Identidad")
        identity_form = wrapping_form(QFormLayout(identity))
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("usuario@ejemplo.com")
        self.email_edit.textChanged.connect(self._on_identity_changed)
        identity_form.addRow("Correo:", self.email_edit)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Tu nombre")
        identity_form.addRow("Nombre:", self.name_edit)

        self.auth_combo = wrapping_combo(QComboBox(), 18)
        self.auth_combo.addItems(
            ["Contraseña / app password", "OAuth2 (Gmail / Outlook / Hotmail / MSN)"]
        )
        self.auth_combo.currentIndexChanged.connect(self._on_auth_method_changed)
        identity_form.addRow("Autenticación:", self.auth_combo)
        self._identity_form = identity_form

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText(
            "Dejar vacío para mantener la actual" if self.account else ""
        )
        self.show_password_check = QCheckBox("Mostrar contraseña")
        self.show_password_check.toggled.connect(self._toggle_password_visibility)
        self._password_row_widget = QWidget()
        enable_height_for_width(self._password_row_widget)
        password_row = FlowLayout(self._password_row_widget, hspacing=8, vspacing=4)
        flow_field(self.password_edit, 120)
        password_row.addWidget(self.password_edit)
        password_row.addWidget(self.show_password_check)
        self.password_label = QLabel("Contraseña:")
        identity_form.addRow(self.password_label, self._password_row_widget)
        body.addWidget(identity)

        reception = QGroupBox("Recepción")
        self._reception_box = reception
        reception_form = wrapping_form(QFormLayout(reception))
        self.imap_host_edit = QLineEdit()
        self.imap_host_edit.textChanged.connect(self._on_identity_changed)
        reception_form.addRow("Servidor IMAP:", self.imap_host_edit)

        self.imap_port_spin = QSpinBox()
        self.imap_port_spin.setRange(1, 65535)
        self.imap_port_spin.setValue(993)
        self.imap_port_spin.valueChanged.connect(self._suggest_tls_from_ports)
        reception_form.addRow("Puerto IMAP:", self.imap_port_spin)

        self.imap_tls_combo = wrapping_combo(QComboBox(), 14)
        self.imap_tls_combo.addItems(
            [
                "SSL/TLS (recomendado, p. ej. puerto 993)",
                "STARTTLS (p. ej. puerto 143)",
                "Sin cifrar (no recomendado)",
            ]
        )
        self.imap_tls_combo.currentIndexChanged.connect(self._on_tls_changed)
        reception_form.addRow("Seguridad IMAP:", self.imap_tls_combo)
        body.addWidget(reception)

        sending = QGroupBox("Envío")
        self._sending_box = sending
        sending_form = wrapping_form(QFormLayout(sending))
        self.smtp_host_edit = QLineEdit()
        sending_form.addRow("Servidor SMTP:", self.smtp_host_edit)

        self.smtp_port_spin = QSpinBox()
        self.smtp_port_spin.setRange(1, 65535)
        self.smtp_port_spin.setValue(587)
        self.smtp_port_spin.valueChanged.connect(self._on_smtp_port_changed)
        sending_form.addRow("Puerto SMTP:", self.smtp_port_spin)

        self.smtp_tls_combo = wrapping_combo(QComboBox(), 14)
        self.smtp_tls_combo.addItems(
            [
                "SSL/TLS (p. ej. puerto 465)",
                "STARTTLS (p. ej. puerto 587)",
                "Sin cifrar (no recomendado)",
            ]
        )
        self.smtp_tls_combo.currentIndexChanged.connect(self._on_tls_changed)
        sending_form.addRow("Seguridad SMTP:", self.smtp_tls_combo)
        body.addWidget(sending)

        self.security_summary = QLabel("")
        self.security_summary.setWordWrap(True)
        mark_role(self.security_summary, "hint")
        body.addWidget(self.security_summary)
        self._update_security_summary()

        signature_box = QGroupBox("Firma")
        self._signature_box = signature_box
        signature_layout = QVBoxLayout(signature_box)
        self.signature_edit = QPlainTextEdit()
        self.signature_edit.setPlaceholderText("Firma al pie de los correos redactados…")
        self.signature_edit.setMaximumHeight(80)
        signature_layout.addWidget(self.signature_edit)
        body.addWidget(signature_box)

        oauth_host = QWidget()
        enable_height_for_width(oauth_host)
        oauth_row = FlowLayout(oauth_host, hspacing=8, vspacing=4)
        self.oauth_btn = flow_button(QPushButton("Identificarse con Google"))
        mark_role(self.oauth_btn, "primary")
        self.oauth_btn.clicked.connect(self._oauth_sign_in)
        self.oauth_status = QLabel("")
        self.oauth_status.setWordWrap(True)
        mark_role(self.oauth_status, "hint")
        flow_field(self.oauth_status, 80)
        oauth_row.addWidget(self.oauth_btn)
        oauth_row.addWidget(self.oauth_status)
        body.addWidget(oauth_host)
        self._oauth_row_widgets = (self.oauth_btn, self.oauth_status)

        self.advanced_btn = flow_button(QPushButton("Configuración avanzada"))
        self.advanced_btn.clicked.connect(self._toggle_advanced)
        body.addWidget(self.advanced_btn)

        self.test_btn = flow_button(QPushButton("Probar conexión"))
        self.test_btn.clicked.connect(self._test_connection)
        body.addWidget(self.test_btn)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if not self.account:
            self._on_provider_changed(self.provider_combo.currentText())

    def _oauth_provider_key(self) -> str | None:
        return detect_oauth_provider(
            self.email_edit.text().strip(),
            self.imap_host_edit.text().strip(),
        )

    def _is_oauth_mode(self) -> bool:
        return self.auth_combo.currentIndex() == 1

    def _on_identity_changed(self) -> None:
        self._maybe_auto_select_provider()
        self._apply_login_mode()
        self._update_provider_notice()
        self._update_oauth_availability()

    def _in_simple_login(self) -> bool:
        return self._browser_login_available() and not self._show_advanced

    def _browser_login_available(self) -> bool:
        return simple_browser_login(
            self.provider_combo.currentText(),
            self.email_edit.text().strip(),
            outlook_ready=oauth_clients_configured("outlook"),
        )

    def _toggle_advanced(self) -> None:
        self._show_advanced = not self._show_advanced
        self._apply_login_mode()

    def _apply_login_mode(self) -> None:
        """Gmail (y Outlook si hay cliente) se reduce a correo e inicio en el navegador."""
        simple = self._in_simple_login()
        self.advanced_btn.setVisible(self._browser_login_available())
        self.advanced_btn.setText(
            "Configuración avanzada" if simple else "Inicio sencillo"
        )
        self._provider_host.setVisible(not simple)
        self._reception_box.setVisible(not simple)
        self._sending_box.setVisible(not simple)
        self.security_summary.setVisible(not simple)
        self._signature_box.setVisible(not simple)
        self.test_btn.setVisible(not simple)
        auth_label = self._identity_form.labelForField(self.auth_combo)
        self.auth_combo.setVisible(not simple)
        if auth_label is not None:
            auth_label.setVisible(not simple)
        if simple and self.auth_combo.currentIndex() != 1:
            self.auth_combo.setCurrentIndex(1)

    def _maybe_auto_select_provider(self) -> None:
        """En cuentas nuevas, elige preset según el dominio (@hotmail, @msn, @aol…)."""
        if self.account:
            return
        preset = detect_provider_from_email(self.email_edit.text().strip())
        if not preset or self.provider_combo.currentText() == preset:
            return
        self.provider_combo.setCurrentText(preset)

    def _on_auth_method_changed(self, _index: int) -> None:
        oauth_mode = self._is_oauth_mode()
        self.password_label.setVisible(not oauth_mode)
        self._password_row_widget.setVisible(not oauth_mode)
        for widget in self._oauth_row_widgets:
            widget.setVisible(oauth_mode)
        self._update_provider_notice()
        self._update_oauth_availability()
        self._refresh_oauth_status()

    def _toggle_password_visibility(self, visible: bool) -> None:
        self.password_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        )

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
            source = oauth_client_source(provider) if configured else None
            if self._in_simple_login():
                if configured:
                    self.oauth_notice.setText(
                        f"Escribe el correo y pulsa «Identificarse con {label}». "
                        "Se abrirá el navegador."
                    )
                else:
                    self.oauth_notice.setText(
                        f"Escribe el correo y pulsa «Identificarse con {label}». "
                        "La primera vez hay que pegar el Client ID de PyQorreos "
                        "(Google no acepta el de Thunderbird); después solo se abre el navegador."
                    )
            elif configured and source in ("builtin", "env"):
                self.oauth_notice.setText(
                    f"Pulsa «Identificarse con {label}». Se abrirá el navegador "
                    "para autorizar PyQorreos. Los tokens se guardan en el llavero del sistema."
                )
            elif configured:
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
                and not self._in_simple_login()
            )
            self.oauth_config_btn.setVisible(show_prefs_btn)
        else:
            self.oauth_notice.setVisible(False)
            self.oauth_config_btn.setVisible(False)

    def _open_oauth_setup(self, *, announce: bool = True) -> bool:
        from pyqorreos.ui.oauth_setup_dialog import OAuthSetupDialog

        provider = self._oauth_provider_key() or "gmail"
        dialog = OAuthSetupDialog(provider, parent=self, announce=announce)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        if accepted:
            self._update_oauth_availability()
            self._refresh_oauth_status()
        return accepted

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

    def _update_provider_notice(self) -> None:
        if self._is_oauth_mode():
            self.provider_notice.setVisible(False)
            return

        email = self.email_edit.text()
        imap_host = self.imap_host_edit.text()
        provider = self.provider_combo.currentText()

        if is_gmail_account(provider=provider, email=email, imap_host=imap_host):
            self.provider_notice.setVisible(True)
            self.provider_notice.setText(
                "<b>Cuenta Gmail</b><br>"
                "Lo más sencillo: en <b>Autenticación</b> elige <b>OAuth2</b> y "
                "pulsa <b>Identificarse con Google</b> (no hace falta crear nada "
                "en Google Cloud).<br>"
                "Alternativa: una <b>contraseña de aplicación</b> de 16 caracteres "
                "(requiere verificación en 2 pasos).<br>"
                f'<a href="{GMAIL_APP_PASSWORD_URL}">Contraseñas de aplicaciones</a> · '
                f'<a href="{GMAIL_APP_PASSWORD_HELP_URL}">Guía oficial</a>'
            )
            self.password_label.setText("Contraseña de aplicación:")
            if not self.account:
                self.password_edit.setPlaceholderText("16 caracteres, sin espacios")
            elif not self.password_edit.text():
                self.password_edit.setPlaceholderText(
                    "Dejar vacío para mantener la actual (contraseña de aplicación)"
                )
            return

        if is_aol_email(email) or provider == "AOL":
            self.provider_notice.setVisible(True)
            self.provider_notice.setText(
                "<b>Cuenta AOL</b><br>"
                "AOL suele exigir una <b>contraseña de aplicación</b> para clientes "
                "de correo de terceros (no la contraseña de la web).<br>"
                f'Créala en <a href="{AOL_APP_PASSWORD_URL}">Seguridad de la cuenta AOL</a>.'
            )
            self.password_label.setText("Contraseña de aplicación:")
            if not self.account:
                self.password_edit.setPlaceholderText("Contraseña de aplicación AOL")
            return

        if is_gmx_email(email) or provider == "GMX":
            self.provider_notice.setVisible(True)
            self.provider_notice.setText(
                "<b>Cuenta GMX</b><br>"
                "GMX <b>desactiva IMAP/POP3 por defecto</b>. Si no lo activas, el "
                "inicio de sesión falla aunque la contraseña sea correcta.<br>"
                "1. Entra en el <b>webmail de GMX</b> → <b>Ajustes</b> → "
                "<b>POP3 &amp; IMAP</b>.<br>"
                "2. Marca <b>«Habilitar el acceso a esta cuenta mediante POP3 e "
                "IMAP»</b> y guarda.<br>"
                f'<a href="{GMX_IMAP_ENABLE_URL}">Guía oficial de GMX</a><br>'
                "Nota: GMX vuelve a desactivar el acceso si no se usa durante mucho "
                "tiempo. Servidores: IMAP <code>imap.gmx.com:993</code> (SSL), "
                "SMTP <code>mail.gmx.com:587</code> (STARTTLS)."
            )
            self.password_label.setText("Contraseña:")
            if self.account:
                self.password_edit.setPlaceholderText("Dejar vacío para mantener la actual")
            else:
                self.password_edit.setPlaceholderText("")
            return

        if is_microsoft_email(email) or provider == "Outlook / Hotmail / MSN":
            self.provider_notice.setVisible(True)
            self.provider_notice.setText(
                "<b>Outlook / Hotmail / MSN</b><br>"
                "Usa tu correo completo como usuario. Recomendado: <b>OAuth2</b> "
                "(Microsoft) en Autenticación. Con contraseña, puede hacer falta una "
                "<b>contraseña de aplicación</b> si tienes verificación en dos pasos.<br>"
                "Si usas <b>VPN</b>, Microsoft puede rechazar el <b>envío</b> "
                "(error «country not allowed»). Prueba sin VPN o excluye "
                "<code>smtp.office365.com</code> del túnel VPN."
            )
            self.password_label.setText("Contraseña:")
            if self.account:
                self.password_edit.setPlaceholderText("Dejar vacío para mantener la actual")
            else:
                self.password_edit.setPlaceholderText("")
            return

        self.provider_notice.setVisible(False)
        self.password_label.setText("Contraseña:")
        if self.account:
            self.password_edit.setPlaceholderText("Dejar vacío para mantener la actual")
        else:
            self.password_edit.setPlaceholderText("")

    def _update_gmail_notice(self) -> None:
        self._update_provider_notice()

    def _on_smtp_port_changed(self, _port: int) -> None:
        self._suggest_tls_from_ports()

    def _suggest_tls_from_ports(self, *_args) -> None:
        """Sugiere el modo TLS habitual según los puertos (sin pisar elección manual)."""
        if self.imap_port_spin.value() == 993 and self.imap_tls_combo.currentIndex() == 2:
            self.imap_tls_combo.setCurrentIndex(0)
        elif self.imap_port_spin.value() == 143 and self.imap_tls_combo.currentIndex() == 0:
            self.imap_tls_combo.setCurrentIndex(1)
        if self.smtp_port_spin.value() == 465 and self.smtp_tls_combo.currentIndex() == 1:
            self.smtp_tls_combo.setCurrentIndex(0)
        elif self.smtp_port_spin.value() == 587 and self.smtp_tls_combo.currentIndex() == 0:
            self.smtp_tls_combo.setCurrentIndex(1)
        self._update_security_summary()

    def _on_tls_changed(self, _index: int) -> None:
        """Ajusta puertos típicos al elegir un modo de seguridad."""
        if self.imap_tls_combo.currentIndex() == 0 and self.imap_port_spin.value() == 143:
            self.imap_port_spin.setValue(993)
        elif self.imap_tls_combo.currentIndex() == 1 and self.imap_port_spin.value() == 993:
            self.imap_port_spin.setValue(143)
        if self.smtp_tls_combo.currentIndex() == 0 and self.smtp_port_spin.value() == 587:
            self.smtp_port_spin.setValue(465)
        elif self.smtp_tls_combo.currentIndex() == 1 and self.smtp_port_spin.value() == 465:
            self.smtp_port_spin.setValue(587)
        self._update_security_summary()

    def _security_from_combo(self, combo: QComboBox) -> str:
        return ("ssl", "starttls", "plain")[combo.currentIndex()]

    def _update_security_summary(self) -> None:
        if not hasattr(self, "security_summary"):
            return
        labels = {"ssl": "SSL", "starttls": "STARTTLS", "plain": "sin cifrado"}
        imap_mode = self._security_from_combo(self.imap_tls_combo)
        smtp_mode = self._security_from_combo(self.smtp_tls_combo)
        self.security_summary.setText(
            f"IMAP {labels[imap_mode]} en el puerto {self.imap_port_spin.value()}"
            f" · SMTP {labels[smtp_mode]} en el puerto {self.smtp_port_spin.value()}"
        )

    def _apply_tls_to_form(self, account: MailAccount) -> None:
        indexes = {"ssl": 0, "starttls": 1, "plain": 2}
        self.imap_tls_combo.blockSignals(True)
        self.smtp_tls_combo.blockSignals(True)
        self.imap_tls_combo.setCurrentIndex(indexes.get(account.imap_security, 0))
        self.smtp_tls_combo.setCurrentIndex(indexes.get(account.smtp_security, 1))
        self.imap_tls_combo.blockSignals(False)
        self.smtp_tls_combo.blockSignals(False)
        self._update_security_summary()

    def _on_provider_changed(self, provider: str) -> None:
        """Rellena automáticamente los campos al elegir un proveedor conocido."""
        preset = PROVIDER_PRESETS.get(provider, {})
        if preset:
            self.imap_host_edit.setText(preset.get("imap_host", ""))
            self.imap_port_spin.setValue(preset.get("imap_port", 993))
            self.smtp_host_edit.setText(preset.get("smtp_host", ""))
            self.smtp_port_spin.setValue(preset.get("smtp_port", 587))
            self._apply_tls_to_form(
                MailAccount(
                    email="",
                    use_ssl=bool(preset.get("use_ssl", True)),
                    use_starttls=bool(preset.get("use_starttls", True)),
                    imap_port=int(preset.get("imap_port", 993)),
                    smtp_port=int(preset.get("smtp_port", 587)),
                    imap_security=str(preset.get("imap_security", "")),
                    smtp_security=str(preset.get("smtp_security", "")),
                )
            )
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
        self.provider_combo.setCurrentText(detect_provider_preset(account))
        self.email_edit.blockSignals(False)
        self.imap_host_edit.blockSignals(False)
        self.provider_combo.blockSignals(False)
        if account.auth_method == AuthMethod.OAUTH2.value:
            self.auth_combo.setCurrentIndex(1)
        self.signature_edit.setPlainText(account.signature)
        self._apply_tls_to_form(account)
        self._on_identity_changed()

    def _get_account(self) -> MailAccount:
        imap_security = self._security_from_combo(self.imap_tls_combo)
        smtp_security = self._security_from_combo(self.smtp_tls_combo)
        return MailAccount(
            id=self._draft_account_id,
            email=self.email_edit.text().strip(),
            display_name=self.name_edit.text().strip(),
            imap_host=self.imap_host_edit.text().strip(),
            imap_port=self.imap_port_spin.value(),
            smtp_host=self.smtp_host_edit.text().strip(),
            smtp_port=self.smtp_port_spin.value(),
            use_ssl=imap_security == "ssl",
            use_starttls=imap_security == "starttls",
            imap_security=imap_security,
            smtp_security=smtp_security,
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
                "OAuth2 solo está disponible para cuentas Gmail, Outlook, Hotmail o MSN.",
            )
            return
        if not oauth_clients_configured(provider_key):
            if not self._open_oauth_setup(announce=False):
                return
            if not oauth_clients_configured(provider_key):
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
        self.oauth_status.setText(oauth_flow_status_message(message))
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
