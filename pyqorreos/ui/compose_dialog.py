"""
Diálogo para redactar, responder o reenviar un correo electrónico.

Incluye editor enriquecido, adjuntos, firma y guardado de borradores.
"""

from __future__ import annotations

import html as html_module

from PySide6.QtWidgets import (
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

from pyqorreos.core.compose_email import EmailAttachment, build_draft_bytes, prepare_outgoing_html
from pyqorreos.core.mail_service import MailService
from pyqorreos.core.reply_utils import ComposeDraft
from pyqorreos.ui.rich_compose_editor import RichComposeEditor
from pyqorreos.ui.workers import SaveDraftWorker, SendMailWorker

_COMPOSE_BTN = """
QPushButton {
    background-color: #e3ebf3;
    color: #1a1a1a;
    border: 1px solid #b8c4d0;
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 10pt;
    font-weight: 600;
    min-height: 28px;
}
QPushButton:hover {
    background-color: #d5e3f0;
    border-color: #2d7dd2;
}
QPushButton:pressed {
    background-color: #c5d8eb;
}
"""

_COMPOSE_BTN_PRIMARY = """
QPushButton {
    background-color: #2d7dd2;
    color: #ffffff;
    border: 1px solid #1f5fa8;
    border-radius: 4px;
    padding: 6px 18px;
    font-size: 10pt;
    font-weight: 600;
    min-height: 28px;
}
QPushButton:hover {
    background-color: #3a8de0;
}
QPushButton:pressed {
    background-color: #1f5fa8;
}
"""

_DIALOG_STYLE = """
QDialog {
    background-color: #ffffff;
    color: #1a1a1a;
}
QLabel {
    color: #1a1a1a;
}
QLineEdit {
    background-color: #ffffff;
    color: #1a1a1a;
    border: 1px solid #cccccc;
    border-radius: 3px;
    padding: 4px;
}
"""


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
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.draft = draft or ComposeDraft()
        self._signature = signature.strip()
        self._drafts_folder = drafts_folder
        self._attachments: list[EmailAttachment] = []
        self.setWindowTitle(title)
        self.setMinimumSize(720, 560)
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui()
        self._load_draft()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.to_edit = QLineEdit()
        self.to_edit.setPlaceholderText("destinatario@ejemplo.com")
        form.addRow("Para:", self.to_edit)

        self.cc_edit = QLineEdit()
        form.addRow("CC:", self.cc_edit)

        self.bcc_edit = QLineEdit()
        form.addRow("CCO:", self.bcc_edit)

        self.subject_edit = QLineEdit()
        form.addRow("Asunto:", self.subject_edit)

        layout.addLayout(form)

        layout.addWidget(QLabel("Mensaje:"))
        self.body_editor = RichComposeEditor()
        layout.addWidget(self.body_editor)

        attach_row = QHBoxLayout()
        attach_row.addWidget(QLabel("Adjuntos:"))
        self.attach_btn = QPushButton("📎 Añadir archivos…")
        self.attach_btn.setStyleSheet(_COMPOSE_BTN)
        self.attach_btn.clicked.connect(self._add_attachments)
        self.remove_attach_btn = QPushButton("Quitar seleccionado")
        self.remove_attach_btn.setStyleSheet(_COMPOSE_BTN)
        self.remove_attach_btn.clicked.connect(self._remove_attachment)
        attach_row.addWidget(self.attach_btn)
        attach_row.addWidget(self.remove_attach_btn)
        attach_row.addStretch()
        layout.addLayout(attach_row)

        self.attach_list = QListWidget()
        self.attach_list.setMaximumHeight(72)
        layout.addWidget(self.attach_list)

        buttons = QDialogButtonBox()
        self.draft_btn = QPushButton("Guardar borrador")
        self.draft_btn.setStyleSheet(_COMPOSE_BTN)
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
            ok_btn.setStyleSheet(_COMPOSE_BTN_PRIMARY)
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setStyleSheet(_COMPOSE_BTN)
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
        )
        self.worker.signals.finished.connect(self._on_sent)
        self.worker.signals.error.connect(self._on_error)
        self.worker.start()

    def _on_sent(self, _) -> None:
        QMessageBox.information(self, "Enviado", "El correo se envió correctamente.")
        self.accept()

    def _on_error(self, message: str) -> None:
        self.setEnabled(True)
        QMessageBox.critical(self, "Error", message)
