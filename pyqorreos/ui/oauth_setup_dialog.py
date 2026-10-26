"""
Asistente para registrar el cliente OAuth de PyQorreos (una sola vez).

El usuario final no debería ver esto si el .deb ya trae el cliente embebido.
Sirve al empaquetador o a quien instala desde código sin Client ID incluido.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from pyqorreos.core.oauth_clients import (
    GOOGLE_CREDENTIALS_URL,
    GOOGLE_GMAIL_API_URL,
    oauth_redirect_help,
    OAUTH_PROVIDER_KEYS,
    AZURE_APP_REGISTRATIONS_URL,
    persist_oauth_clients,
)
from pyqorreos.ui.flow_layout import flow_button, scrolling_body, wrapping_form
from pyqorreos.ui.theme import mark_role, prevent_context_menu


class OAuthSetupDialog(QDialog):
    """Pide Client ID/secret y los guarda como override + cliente embebido."""

    def __init__(
        self,
        provider_key: str = "gmail",
        parent=None,
        *,
        announce: bool = True,
    ) -> None:
        super().__init__(parent)
        self._provider = (
            provider_key if provider_key in OAUTH_PROVIDER_KEYS else "gmail"
        )
        self._announce = announce
        title = "Gmail / Google" if self._provider == "gmail" else "Outlook / Microsoft"
        self.setWindowTitle(f"Configurar OAuth — {title}")
        self.setMinimumSize(400, 320)
        prevent_context_menu(self)

        layout = QVBoxLayout(self)
        body = scrolling_body(layout)

        intro = QLabel(
            "PyQorreos necesita el <b>Client ID de la aplicación</b> (el de este "
            "programa, no el de tu cuenta personal) para abrir el inicio de sesión "
            "en el navegador.<br><br>"
            "Solo hay que hacerlo <b>una vez</b>. Después, tú y quien instale el "
            ".deb podrán usar «Identificarse con Google/Microsoft» sin repetir "
            "estos pasos."
        )
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.RichText)
        mark_role(intro, "hint")
        body.addWidget(intro)

        if self._provider == "gmail":
            steps = QLabel(
                "<b>Pasos en Google Cloud</b> (5 minutos):<br>"
                f'1. Abre <a href="{GOOGLE_GMAIL_API_URL}">Gmail API</a> y actívala '
                "en un proyecto (puedes crear uno llamado «PyQorreos»).<br>"
                f'2. Ve a <a href="{GOOGLE_CREDENTIALS_URL}">Credenciales</a> → '
                "<b>Crear credenciales</b> → <b>ID de cliente de OAuth</b>.<br>"
                "3. Tipo: <b>Aplicación de escritorio</b>. Nombre: PyQorreos.<br>"
                f"4. Si pide URI de redirección, usa <code>{oauth_redirect_help()}</code>.<br>"
                "5. Copia el <b>Client ID</b> y el <b>Client secret</b> abajo.<br>"
                "6. En la pantalla de consentimiento, si está en modo prueba, "
                "añade tu Gmail como usuario de prueba."
            )
        else:
            steps = QLabel(
                "<b>Pasos en Azure / Entra</b>:<br>"
                f'1. Abre <a href="{AZURE_APP_REGISTRATIONS_URL}">Registros de '
                "aplicaciones</a> → Nueva inscripción.<br>"
                "2. Tipo: aplicaciones móviles y de escritorio. URI: "
                f"<code>{oauth_redirect_help()}</code>.<br>"
                "3. Permisos: IMAP.AccessAsUser.All, SMTP.Send, offline_access.<br>"
                "4. Crea un secreto y pega ID + secreto abajo."
            )
        steps.setWordWrap(True)
        steps.setTextFormat(Qt.TextFormat.RichText)
        steps.setOpenExternalLinks(True)
        mark_role(steps, "hint")
        body.addWidget(steps)

        open_btn = flow_button(
            QPushButton(
                "Abrir consola de Google…"
                if self._provider == "gmail"
                else "Abrir portal de Azure…"
            )
        )
        open_btn.clicked.connect(self._open_provider_console)
        body.addWidget(open_btn)

        form = wrapping_form(QFormLayout())
        self.client_id = QLineEdit()
        self.client_id.setPlaceholderText("xxxxx.apps.googleusercontent.com")
        self.client_secret = QLineEdit()
        self.client_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.client_secret.setPlaceholderText("Client secret (GOCSPX-…)")
        form.addRow("Client ID:", self.client_id)
        form.addRow("Client secret:", self.client_secret)
        body.addLayout(form)

        note = QLabel(
            f"Se guardará en Preferencias y como cliente embebido de esta "
            f"instalación. URI: <code>{oauth_redirect_help()}</code>"
        )
        note.setWordWrap(True)
        note.setTextFormat(Qt.TextFormat.RichText)
        mark_role(note, "hint")
        body.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _open_provider_console(self) -> None:
        url = (
            GOOGLE_CREDENTIALS_URL
            if self._provider == "gmail"
            else AZURE_APP_REGISTRATIONS_URL
        )
        QDesktopServices.openUrl(QUrl(url))

    def _save(self) -> None:
        client_id = self.client_id.text().strip()
        client_secret = self.client_secret.text().strip()
        if not client_id:
            QMessageBox.warning(self, "OAuth", "Indica el Client ID.")
            return
        data = {
            "gmail": {"client_id": "", "client_secret": ""},
            "outlook": {"client_id": "", "client_secret": ""},
        }
        # Conserva el otro proveedor si ya estaba configurado.
        from pyqorreos.core.oauth_clients import load_oauth_clients_data, load_builtin_oauth_clients_data

        existing = load_oauth_clients_data()
        builtin = load_builtin_oauth_clients_data()
        for key in OAUTH_PROVIDER_KEYS:
            block = existing.get(key) or {}
            if not block.get("client_id"):
                block = builtin.get(key) or {}
            data[key] = {
                "client_id": str(block.get("client_id", "")).strip(),
                "client_secret": str(block.get("client_secret", "")).strip(),
            }
        data[self._provider] = {
            "client_id": client_id,
            "client_secret": client_secret,
        }
        try:
            path = persist_oauth_clients(data)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "OAuth", f"No se pudieron guardar las credenciales:\n{exc}")
            return
        if self._announce:
            QMessageBox.information(
                self,
                "OAuth listo",
                "Cliente OAuth guardado en este equipo.\n\n"
                "El siguiente paso abre el navegador para identificarte.\n\n"
                f"{path}",
            )
        self.accept()
