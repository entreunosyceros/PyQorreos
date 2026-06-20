"""
Diálogo para redactar, responder o reenviar un correo electrónico.

Incluye editor enriquecido, adjuntos, firma y guardado de borradores.
"""

from __future__ import annotations

import html as html_module

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from pyqorreos.core.account import is_microsoft_email
from pyqorreos.core.compose_email import EmailAttachment, build_draft_bytes, prepare_outgoing_html
from pyqorreos.core.compose_utils import (
    body_mentions_attachment,
    large_attachment_warning,
    validate_attachments,
)
from pyqorreos.core.mail_service import MailService
from pyqorreos.core.reply_utils import ComposeDraft
from pyqorreos.core.user_preferences import DEFAULT_COMPOSE_SNIPPETS
from pyqorreos.ui.rich_compose_editor import RichComposeEditor
from pyqorreos.ui.theme import mark_role, resolve_theme_from_parent
from pyqorreos.ui.workers import SaveDraftWorker, SendMailWorker

class ComposeDialog(QDialog):
    """Diálogo para redactar y enviar un correo."""

    def __init__(
        self,
        service: MailService,
        parent=None,
        draft: ComposeDraft | None = None,
        title: str = "Redactar correo",
        signature: str = "",
        drafts_folder: str | None = None,
        snippets: list[dict[str, str]] | None = None,
        request_read_receipt_default: bool = False,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.draft = draft or ComposeDraft()
        self._signature = signature.strip()
        self._drafts_folder = drafts_folder
        self._snippets = snippets or list(DEFAULT_COMPOSE_SNIPPETS)
        self._attachments: list[EmailAttachment] = []
        self._request_read_receipt_default = request_read_receipt_default
        self.setWindowTitle(title)
        self.setMinimumSize(720, 560)
        self.resize(820, 620)
        self._configure_window_flags()
        self._theme = resolve_theme_from_parent(parent)
        self._build_ui()
        self._load_draft()

    def _configure_window_flags(self) -> None:
        """Permite minimizar y maximizar como una ventana normal."""
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.to_edit = QLineEdit()
        self.to_edit.setPlaceholderText("destinatario@ejemplo.com")
        form.addRow("Para:", self.to_edit)

        self.cc_edit = QLineEdit()
        self.cc_edit.setPlaceholderText("copia@ejemplo.com (opcional)")
        form.addRow("CC:", self.cc_edit)

        self.bcc_edit = QLineEdit()
        self.bcc_edit.setPlaceholderText("copia.oculta@ejemplo.com (opcional)")
        form.addRow("CCO:", self.bcc_edit)

        self.subject_edit = QLineEdit()
        self.subject_edit.setPlaceholderText("Escribe el asunto del correo")
        form.addRow("Asunto:", self.subject_edit)

        layout.addLayout(form)

        snippet_row = QHBoxLayout()
        snippet_row.addWidget(QLabel("Plantilla:"))
        self.snippet_combo = QComboBox()
        self.snippet_combo.addItem("— Insertar plantilla —", None)
        for snippet in self._snippets:
            self.snippet_combo.addItem(snippet.get("name", "Plantilla"))
        self.snippet_combo.activated.connect(self._insert_snippet)
        snippet_row.addWidget(self.snippet_combo, 1)
        layout.addLayout(snippet_row)

        layout.addWidget(QLabel("Mensaje:"))
        self.body_editor = RichComposeEditor(theme=self._theme)
        layout.addWidget(self.body_editor)

        attach_row = QHBoxLayout()
        attach_row.addWidget(QLabel("Adjuntos:"))
        self.attach_btn = QPushButton("📎 Añadir archivos…")
        mark_role(self.attach_btn, "default")
        self.attach_btn.clicked.connect(self._add_attachments)
        self.remove_attach_btn = QPushButton("Quitar seleccionado")
        mark_role(self.remove_attach_btn, "default")
        self.remove_attach_btn.clicked.connect(self._remove_attachment)
        attach_row.addWidget(self.attach_btn)
        attach_row.addWidget(self.remove_attach_btn)
        attach_row.addStretch()
        layout.addLayout(attach_row)

        self.attach_list = QListWidget()
        self.attach_list.setMaximumHeight(72)
        layout.addWidget(self.attach_list)

        self.read_receipt_check = QCheckBox("Solicitar acuse de recibo")
        self.read_receipt_check.setChecked(self._request_read_receipt_default)
        receipt_tip = (
            "Pide al destinatario confirmar la lectura del mensaje. "
            "Muchos clientes lo ignoran o preguntan al usuario antes de enviarlo."
        )
        if is_microsoft_email(self.service.account.email):
            receipt_tip += (
                " Con cuentas Microsoft, si el envío falla suele deberse a la VPN "
                "(error «country not allowed»), no a esta casilla."
            )
        self.read_receipt_check.setToolTip(receipt_tip)
        layout.addWidget(self.read_receipt_check)

        buttons = QDialogButtonBox()
        self.draft_btn = QPushButton("Guardar borrador")
        mark_role(self.draft_btn, "default")
        self.draft_btn.clicked.connect(self._save_draft)
        if not self._drafts_folder:
            self.draft_btn.setEnabled(False)
            self.draft_btn.setToolTip("No se encontró carpeta Borradores en el servidor")
        buttons.addButton(self.draft_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(QDialogButtonBox.StandardButton.Ok)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText("Enviar")
            mark_role(ok_btn, "primary")
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            mark_role(cancel_btn, "default")
        buttons.accepted.connect(self._send)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _append_signature_html(self, html: str) -> str:
        if not self._signature:
            return html
        sig_html = (
            "<br><br>--<br>"
            f"<div>{html_module.escape(self._signature).replace(chr(10), '<br>')}</div>"
        )
        if "pyqorreos-reply-area" in html:
            return html.replace(
                "</div>",
                f"{sig_html}</div>",
                1,
            )
        return html + sig_html

    def _insert_snippet(self, index: int) -> None:
        if index <= 0 or index > len(self._snippets):
            return
        text = self._snippets[index - 1].get("text", "")
        if not text:
            return
        self.body_editor.insert_text(text)
        self.snippet_combo.blockSignals(True)
        self.snippet_combo.setCurrentIndex(0)
        self.snippet_combo.blockSignals(False)

    def _load_draft(self) -> None:
        self.to_edit.setText(self.draft.to)
        self.cc_edit.setText(self.draft.cc)
        self.bcc_edit.setText(self.draft.bcc)
        self.subject_edit.setText(self.draft.subject)
        if self.draft.body_html:
            html = self._append_signature_html(self.draft.body_html)
            self.body_editor.set_html(html)
        else:
            body = self.draft.body
            if self._signature:
                body = f"{body}\n\n--\n{self._signature}".strip()
            self.body_editor.set_plain_text(body)

    def _add_attachments(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Adjuntar archivos",
            "",
            "Todos los archivos (*.*)",
        )
        for path in paths:
            attachment = EmailAttachment.from_path(path)
            if any(a.path == attachment.path for a in self._attachments):
                continue
            self._attachments.append(attachment)
            self.attach_list.addItem(QListWidgetItem(attachment.filename))

    def _remove_attachment(self) -> None:
        row = self.attach_list.currentRow()
        if row < 0:
            return
        self.attach_list.takeItem(row)
        del self._attachments[row]

    def _save_draft(self) -> None:
        if not self._drafts_folder:
            return
        plain = self.body_editor.plain_text().strip()
        html = prepare_outgoing_html(self.body_editor.html())
        if not plain and not html:
            QMessageBox.warning(self, "Borrador vacío", "Escribe algo antes de guardar.")
            return
        raw = build_draft_bytes(
            from_email=self.service.account.email,
            display_name=self.service.account.display_name,
            to=self.to_edit.text().strip(),
            cc=self.cc_edit.text().strip(),
            bcc=self.bcc_edit.text().strip(),
            subject=self.subject_edit.text().strip(),
            body_plain=plain,
            body_html=html,
            request_read_receipt=self.read_receipt_check.isChecked(),
        )
        self.setEnabled(False)
        worker = SaveDraftWorker(self.service, self._drafts_folder, raw)
        worker.signals.finished.connect(self._on_draft_saved)
        worker.signals.error.connect(self._on_error)
        worker.start()

    def _on_draft_saved(self, _) -> None:
        QMessageBox.information(self, "Borrador", "Borrador guardado en el servidor.")
        self.accept()

    def _send(self) -> None:
        to = self.to_edit.text().strip()
        subject = self.subject_edit.text().strip()
        plain = self.body_editor.plain_text().strip()
        html = prepare_outgoing_html(self.body_editor.html())

        if not to:
            QMessageBox.warning(self, "Error", "Indica al menos un destinatario.")
            return
        if not plain and not self._attachments:
            QMessageBox.warning(self, "Error", "Escribe un mensaje o adjunta un archivo.")
            return

        if not self._attachments and body_mentions_attachment(plain):
            reply = QMessageBox.warning(
                self,
                "¿Adjunto olvidado?",
                "El mensaje menciona un adjunto, pero no has añadido ningún archivo.\n\n"
                "¿Enviar de todos modos?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        if self._attachments:
            ok, err = validate_attachments([a.path for a in self._attachments])
            if not ok:
                QMessageBox.warning(self, "Adjuntos demasiado grandes", err)
                return
            warn = large_attachment_warning([a.path for a in self._attachments])
            if warn:
                reply = QMessageBox.warning(
                    self,
                    "Adjuntos grandes",
                    warn + "\n\n¿Enviar de todos modos?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

        self.setEnabled(False)
        self.worker = SendMailWorker(
            self.service,
            to,
            subject,
            plain,
            self.cc_edit.text().strip(),
            self.bcc_edit.text().strip(),
            body_html=html,
            attachments=list(self._attachments),
            request_read_receipt=self.read_receipt_check.isChecked(),
        )
        self.worker.signals.finished.connect(self._on_sent)
        self.worker.signals.error.connect(self._on_error)
        self.worker.start()

    def _on_sent(self, _) -> None:
        QMessageBox.information(self, "Enviado", "El correo se envió correctamente.")
        self.accept()

    def _on_error(self, message: str) -> None:
        self.setEnabled(True)
        if (
            self.read_receipt_check.isChecked()
            and is_microsoft_email(self.service.account.email)
            and "country not allowed" in message.lower()
        ):
            message += (
                "\n\nEl acuse de recibo no provoca este error. "
                "Desactiva la VPN o excluye smtp.office365.com del túnel y vuelve a intentar."
            )
        QMessageBox.critical(self, "Error", message)
