"""
Diálogo de preferencias de PyQorreos.
"""

from __future__ import annotations

import copy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pyqorreos.core.oauth_clients import (
    OAUTH_CLIENTS_FILE,
    oauth_redirect_help,
    embed_oauth_clients,
    gmail_oauth_setup_html,
    load_oauth_clients_data,
    oauth_client_source,
    oauth_clients_configured,
    outlook_oauth_setup_html,
    save_oauth_clients_data,
    validate_oauth_clients_data,
)
from pyqorreos.core.openpgp import openpgp_available, openpgp_unavailable_reason
from pyqorreos.core.settings import Settings
from pyqorreos.core.user_preferences import (
    DEFAULT_COMPOSE_SNIPPETS,
    UserPreferences,
    normalize_compose_snippets,
)
from pyqorreos.core.translate import TRANSLATION_LANGUAGES, language_label
from pyqorreos.ui.flow_layout import (
    FlowLayout,
    enable_height_for_width,
    flow_button,
    wrapping_combo,
    wrapping_form,
)
from pyqorreos.ui.theme import mark_role, prevent_context_menu
from pyqorreos.ui.classification_rules_widget import ClassificationRulesWidget
from pyqorreos.ui.openpgp_keys_dialog import OpenPgpKeysDialog


_PREFERENCES_TAB_INDEX = {
    "general": 0,
    "snippets": 1,
    "plantillas": 1,
    "classification": 2,
    "clasificacion": 2,
    "oauth": 3,
}


class PreferencesDialog(QDialog):
    def __init__(
        self,
        prefs: UserPreferences,
        parent=None,
        *,
        initial_tab: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferencias de PyQorreos")
        self.setMinimumSize(480, 400)
        self._prefs = prefs
        self._oauth_data = load_oauth_clients_data()
        self._snippets: list[dict[str, str]] = copy.deepcopy(
            normalize_compose_snippets(prefs.compose_snippets)
        )
        self._snippet_sync_blocked = False
        self._settings = Settings()
        self._classification_rules = self._settings.load_classification_rules()
        self._build_ui()
        prevent_context_menu(self)
        self._reload_snippet_list()
        if initial_tab:
            tab_idx = _PREFERENCES_TAB_INDEX.get(initial_tab.lower())
            if tab_idx is not None:
                self.tabs.setCurrentIndex(tab_idx)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_general_tab(), "General")
        self.tabs.addTab(self._build_snippets_tab(), "Plantillas")
        self.tabs.addTab(self._build_classification_tab(), "Clasificación")
        self.tabs.addTab(self._build_oauth_tab(), "OAuth")
        layout.addWidget(self.tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_preferences)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_general_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        page = QWidget()
        layout = QVBoxLayout(page)

        sync_group = QGroupBox("Sincronización con el servidor")
        sync_form = wrapping_form(QFormLayout(sync_group))

        self.bg_sync = QCheckBox("Sincronizar cuentas en segundo plano")
        self.bg_sync.setChecked(self._prefs.background_sync_enabled)
        sync_form.addRow(self.bg_sync)

        self.sync_interval = QSpinBox()
        self.sync_interval.setRange(1, 120)
        self.sync_interval.setSuffix(" min")
        self.sync_interval.setSingleStep(1)
        self.sync_interval.setToolTip(
            "Cada cuántos minutos se comprueba si hay correo nuevo en el servidor"
        )
        self.sync_interval.setValue(
            max(1, round(self._prefs.background_sync_interval_sec / 60))
        )
        sync_form.addRow("Intervalo de sincronización (minutos):", self.sync_interval)

        self.use_idle = QCheckBox("Usar IMAP IDLE en la cuenta activa (más rápido)")
        self.use_idle.setChecked(self._prefs.use_imap_idle)
        sync_form.addRow(self.use_idle)

        self.notify = QCheckBox("Mostrar notificación al llegar correo nuevo")
        self.notify.setChecked(self._prefs.notify_new_mail)
        sync_form.addRow(self.notify)

        layout.addWidget(sync_group)

        compose_group = QGroupBox("Redacción")
        compose_form = wrapping_form(QFormLayout(compose_group))

        self.compose_read_receipt = QCheckBox(
            "Solicitar acuse de recibo al enviar por defecto"
        )
        self.compose_read_receipt.setToolTip(
            "Marca la casilla «Solicitar acuse de recibo» al abrir el editor de correo. "
            "El destinatario decide si responde."
        )
        self.compose_read_receipt.setChecked(self._prefs.compose_request_read_receipt)
        compose_form.addRow(self.compose_read_receipt)

        layout.addWidget(compose_group)

        openpgp_group = QGroupBox("OpenPGP (cifrado de extremo a extremo)")
        openpgp_form = wrapping_form(QFormLayout(openpgp_group))

        self.openpgp_enabled = QCheckBox("Activar OpenPGP (solo al leer o enviar mensajes protegidos)")
        self.openpgp_enabled.setChecked(self._prefs.openpgp_enabled)
        self.openpgp_enabled.setToolTip(
            "No afecta a la sincronización ni a la velocidad de la bandeja. "
            "Requiere GnuPG (gpg) instalado en el sistema."
        )
        openpgp_form.addRow(self.openpgp_enabled)

        if not openpgp_available():
            pgp_warn = QLabel(openpgp_unavailable_reason())
            pgp_warn.setWordWrap(True)
            mark_role(pgp_warn, "hint")
            openpgp_form.addRow(pgp_warn)

        self.openpgp_auto_decrypt = QCheckBox("Descifrar automáticamente al abrir")
        self.openpgp_auto_decrypt.setChecked(self._prefs.openpgp_auto_decrypt)
        openpgp_form.addRow(self.openpgp_auto_decrypt)

        self.openpgp_sign_default = QCheckBox("Firmar al enviar por defecto")
        self.openpgp_sign_default.setChecked(self._prefs.openpgp_sign_by_default)
        openpgp_form.addRow(self.openpgp_sign_default)

        self.openpgp_encrypt_default = QCheckBox("Cifrar al enviar por defecto")
        self.openpgp_encrypt_default.setChecked(self._prefs.openpgp_encrypt_by_default)
        openpgp_form.addRow(self.openpgp_encrypt_default)

        self.openpgp_use_system_home = QCheckBox(
            "Usar claves del sistema (~/.gnupg) en lugar del almacén de PyQorreos"
        )
        self.openpgp_use_system_home.setChecked(self._prefs.openpgp_use_system_gnupg_home)
        openpgp_form.addRow(self.openpgp_use_system_home)

        self.openpgp_cache_decrypted = QCheckBox(
            "Guardar cuerpos descifrados en la caché local (más rápido al reabrir)"
        )
        self.openpgp_cache_decrypted.setChecked(self._prefs.openpgp_cache_decrypted_bodies)
        openpgp_form.addRow(self.openpgp_cache_decrypted)

        self.openpgp_signing_key = QLineEdit(self._prefs.openpgp_signing_key_id)
        self.openpgp_signing_key.setPlaceholderText("Huella o ID de clave (vacío = predeterminada)")
        openpgp_form.addRow("Clave para firmar:", self.openpgp_signing_key)

        keys_btn = QPushButton("Gestionar claves…")
        keys_btn.clicked.connect(self._open_openpgp_keys)
        openpgp_form.addRow(keys_btn)

        layout.addWidget(openpgp_group)

        download_group = QGroupBox("Descarga de mensajes")
        download_form = wrapping_form(QFormLayout(download_group))

        self.delete_after_download = QCheckBox(
            "Eliminar del servidor al descargar el mensaje completo"
        )
        self.delete_after_download.setToolTip(
            "Tras abrir un correo y guardarlo en local, se borra del servidor IMAP. "
            "El mensaje seguirá disponible en este equipo."
        )
        self.delete_after_download.setChecked(
            self._prefs.delete_from_server_after_download
        )
        download_form.addRow(self.delete_after_download)

        layout.addWidget(download_group)

        view_group = QGroupBox("Lista y lectura")
        view_form = wrapping_form(QFormLayout(view_group))

        self.block_images = QCheckBox("Bloquear imágenes remotas al leer")
        self.block_images.setChecked(self._prefs.block_remote_images)
        view_form.addRow(self.block_images)

        self.thread_view = QCheckBox("Vista de conversaciones (agrupar hilos)")
        self.thread_view.setToolTip(
            "Muestra un mensaje por hilo (el más reciente). "
            "El número entre paréntesis indica cuántos hay en el hilo."
        )
        self.thread_view.setChecked(self._prefs.thread_view)
        view_form.addRow(self.thread_view)

        self.search_all_folders = QCheckBox(
            "Buscar en todas las carpetas de la cuenta (solo cabeceras en caché)"
        )
        self.search_all_folders.setChecked(self._prefs.search_all_folders)
        view_form.addRow(self.search_all_folders)

        self.large_headers = QCheckBox("Solo cabeceras en carpetas muy grandes")
        self.large_headers.setChecked(self._prefs.headers_only_large_folders)
        view_form.addRow(self.large_headers)

        self.page_size = QSpinBox()
        self.page_size.setRange(10, 200)
        self.page_size.setValue(self._prefs.page_size)
        view_form.addRow("Correos por página:", self.page_size)

        self.sort_combo = wrapping_combo(QComboBox(), 14)
        self.sort_combo.addItems(
            ["Fecha (recientes)", "Fecha (antiguos)", "Remitente", "Asunto"]
        )
        sort_map = {
            "date_desc": 0,
            "date_asc": 1,
            "sender": 2,
            "subject": 3,
        }
        self.sort_combo.setCurrentIndex(sort_map.get(self._prefs.sort_by, 0))
        view_form.addRow("Ordenar por:", self.sort_combo)

        self.translate_lang = wrapping_combo(QComboBox(), 12)
        for code, label in TRANSLATION_LANGUAGES:
            self.translate_lang.addItem(label, code)
        target = self._prefs.translate_target_language
        idx = self.translate_lang.findData(target)
        self.translate_lang.setCurrentIndex(idx if idx >= 0 else 0)
        self.translate_lang.setToolTip(
            "Idioma al que se traducirán los correos al pulsar «Traducir» en el visor"
        )
        view_form.addRow("Traducir correos al:", self.translate_lang)

        translate_note = QLabel(
            "La traducción envía el texto del mensaje a un servicio en línea gratuito. "
            "Solo se traduce cuando pulsas el botón en el visor."
        )
        translate_note.setWordWrap(True)
        mark_role(translate_note, "hint")
        view_form.addRow(translate_note)

        layout.addWidget(view_group)

        appearance_group = QGroupBox("Apariencia")
        appearance_form = wrapping_form(QFormLayout(appearance_group))

        self.theme_combo = wrapping_combo(QComboBox(), 8)
        self.theme_combo.addItem("Claro", "light")
        self.theme_combo.addItem("Oscuro", "dark")
        theme_idx = self.theme_combo.findData(self._prefs.theme)
        self.theme_combo.setCurrentIndex(theme_idx if theme_idx >= 0 else 0)
        self.theme_combo.setToolTip("Tema de la interfaz de la aplicación")
        appearance_form.addRow("Tema:", self.theme_combo)

        layout.addWidget(appearance_group)

        hint = QLabel(
            "Los cambios de sincronización se aplican al guardar. "
            "El intervalo mínimo recomendado es 2–5 minutos."
        )
        hint.setWordWrap(True)
        mark_role(hint, "hint")
        layout.addWidget(hint)
        layout.addStretch()

        scroll.setWidget(page)
        return scroll

    def _open_openpgp_keys(self) -> None:
        dialog = OpenPgpKeysDialog(
            self,
            use_system_home=self.openpgp_use_system_home.isChecked(),
        )
        dialog.exec()

    def _build_classification_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        page = QWidget()
        layout = QVBoxLayout(page)
        self._classification_widget = ClassificationRulesWidget(
            copy.deepcopy(self._classification_rules),
            parent=page,
        )
        layout.addWidget(self._classification_widget)
        scroll.setWidget(page)
        return scroll

    def _build_oauth_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        page = QWidget()
        layout = QVBoxLayout(page)

        intro = QLabel(
            "PyQorreos incluye inicio de sesión OAuth integrado para Gmail y "
            "Microsoft (como Thunderbird): al añadir una cuenta basta con "
            "«Identificarse con Google/Microsoft», sin registrar nada en Cloud Console.\n\n"
            "Los campos de abajo son opcionales: solo rellénalos si quieres usar "
            "tu propia aplicación OAuth en lugar de la incluida. Los tokens de "
            "cada cuenta se guardan en el llavero del sistema."
        )
        intro.setWordWrap(True)
        mark_role(intro, "hint")
        layout.addWidget(intro)

        status_lines: list[str] = []
        for key, label in (("gmail", "Gmail"), ("outlook", "Outlook")):
            source = oauth_client_source(key)
            if source == "builtin":
                status_lines.append(f"• {label}: cliente incluido de PyQorreos (listo)")
            elif source == "user":
                status_lines.append(f"• {label}: usando tu Client ID de Preferencias")
            elif source == "env":
                status_lines.append(f"• {label}: usando variables de entorno")
            else:
                status_lines.append(
                    f"• {label}: sin cliente — configura abajo o usa contraseña de aplicación"
                )
        status = QLabel("Estado actual:\n" + "\n".join(status_lines))
        status.setWordWrap(True)
        mark_role(status, "hint")
        layout.addWidget(status)

        redirect_note = QLabel(
            f"URI de redirección (solo si registras tu propia app): "
            f"<code>{oauth_redirect_help()}</code>"
        )
        redirect_note.setWordWrap(True)
        redirect_note.setTextFormat(Qt.TextFormat.RichText)
        mark_role(redirect_note, "hint")
        layout.addWidget(redirect_note)

        layout.addWidget(self._build_oauth_provider_group(
            "gmail",
            gmail_oauth_setup_html(),
        ))
        layout.addWidget(self._build_oauth_provider_group(
            "outlook",
            outlook_oauth_setup_html(),
        ))

        self.oauth_show_secrets = QCheckBox("Mostrar secretos de cliente")
        self.oauth_show_secrets.toggled.connect(self._toggle_oauth_secret_visibility)
        layout.addWidget(self.oauth_show_secrets)

        self.oauth_embed_check = QCheckBox(
            "Usar también como cliente embebido de esta instalación "
            "(recomendado: así OAuth funciona sin repetir la configuración)"
        )
        self.oauth_embed_check.setChecked(True)
        layout.addWidget(self.oauth_embed_check)

        file_hint = QLabel(f"Override de usuario: {OAUTH_CLIENTS_FILE}")
        file_hint.setWordWrap(True)
        mark_role(file_hint, "hint")
        layout.addWidget(file_hint)

        layout.addStretch()
        scroll.setWidget(page)
        return scroll

    def _build_oauth_provider_group(self, provider_key: str, instructions_html: str) -> QGroupBox:
        title = "Gmail" if provider_key == "gmail" else "Outlook"
        group = QGroupBox(title)
        form = QVBoxLayout(group)

        steps = QLabel(instructions_html)
        steps.setWordWrap(True)
        steps.setTextFormat(Qt.TextFormat.RichText)
        steps.setOpenExternalLinks(True)
        mark_role(steps, "hint")
        form.addWidget(steps)

        fields = wrapping_form(QFormLayout())
        client_id = QLineEdit()
        client_id.setPlaceholderText("Client ID / ID de aplicación")
        client_secret = QLineEdit()
        client_secret.setEchoMode(QLineEdit.EchoMode.Password)
        client_secret.setPlaceholderText("Client secret (opcional en algunas apps de Google)")

        block = self._oauth_data.get(provider_key, {})
        client_id.setText(str(block.get("client_id", "")))
        client_secret.setText(str(block.get("client_secret", "")))

        if provider_key == "gmail":
            self.gmail_client_id = client_id
            self.gmail_client_secret = client_secret
        else:
            self.outlook_client_id = client_id
            self.outlook_client_secret = client_secret

        fields.addRow("Client ID:", client_id)
        fields.addRow("Client secret:", client_secret)
        form.addLayout(fields)
        return group

    def _toggle_oauth_secret_visibility(self, visible: bool) -> None:
        mode = (
            QLineEdit.EchoMode.Normal
            if visible
            else QLineEdit.EchoMode.Password
        )
        self.gmail_client_secret.setEchoMode(mode)
        self.outlook_client_secret.setEchoMode(mode)

    def _collect_oauth_data(self) -> dict[str, dict[str, str]]:
        return {
            "gmail": {
                "client_id": self.gmail_client_id.text().strip(),
                "client_secret": self.gmail_client_secret.text().strip(),
            },
            "outlook": {
                "client_id": self.outlook_client_id.text().strip(),
                "client_secret": self.outlook_client_secret.text().strip(),
            },
        }

    def _build_snippets_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        page = QWidget()
        layout = QVBoxLayout(page)

        snippets_hint = QLabel(
            "Textos rápidos para insertar al redactar. Aparecen en el menú "
            "«Plantilla» del editor de correo."
        )
        snippets_hint.setWordWrap(True)
        mark_role(snippets_hint, "hint")
        layout.addWidget(snippets_hint)

        columns = QWidget()
        enable_height_for_width(columns, vertical=QSizePolicy.Policy.Expanding)
        snippets_body = FlowLayout(columns, hspacing=12, vspacing=8)

        list_col = QWidget()
        list_col.setMinimumWidth(140)
        list_layout = QVBoxLayout(list_col)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.addWidget(QLabel("Plantillas guardadas:"))
        self.snippet_list = QListWidget()
        self.snippet_list.setMinimumWidth(120)
        self.snippet_list.setMinimumHeight(140)
        self.snippet_list.currentRowChanged.connect(self._on_snippet_selected)
        list_layout.addWidget(self.snippet_list, 1)

        list_btns = FlowLayout(hspacing=8, vspacing=6)
        self.btn_snippet_add = flow_button(QPushButton("Añadir"))
        self.btn_snippet_add.clicked.connect(self._add_snippet)
        self.btn_snippet_remove = flow_button(QPushButton("Eliminar"))
        self.btn_snippet_remove.clicked.connect(self._remove_snippet)
        list_btns.addWidget(self.btn_snippet_add)
        list_btns.addWidget(self.btn_snippet_remove)
        list_layout.addLayout(list_btns)
        list_col.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        snippets_body.addWidget(list_col)

        editor_col = QWidget()
        editor_col.setMinimumWidth(180)
        editor_layout = QVBoxLayout(editor_col)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        name_form = wrapping_form(QFormLayout())
        self.snippet_name_edit = QLineEdit()
        self.snippet_name_edit.setPlaceholderText("Ej. Saludo formal")
        self.snippet_name_edit.textChanged.connect(self._on_snippet_editor_changed)
        name_form.addRow("Nombre:", self.snippet_name_edit)
        editor_layout.addLayout(name_form)

        editor_layout.addWidget(QLabel("Texto:"))
        self.snippet_text_edit = QTextEdit()
        self.snippet_text_edit.setPlaceholderText("Texto que se insertará en el mensaje…")
        self.snippet_text_edit.setMinimumHeight(160)
        self.snippet_text_edit.textChanged.connect(self._on_snippet_editor_changed)
        editor_layout.addWidget(self.snippet_text_edit, 1)

        self.btn_snippet_defaults = flow_button(
            QPushButton("Restaurar plantillas predeterminadas")
        )
        self.btn_snippet_defaults.clicked.connect(self._restore_default_snippets)
        editor_layout.addWidget(self.btn_snippet_defaults)
        editor_col.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        snippets_body.addWidget(editor_col)
        layout.addWidget(columns, 1)

        scroll.setWidget(page)
        return scroll

    def _reload_snippet_list(self, select_row: int | None = None) -> None:
        self._snippet_sync_blocked = True
        self.snippet_list.clear()
        for snippet in self._snippets:
            item = QListWidgetItem(snippet.get("name", "Sin nombre"))
            self.snippet_list.addItem(item)
        if self._snippets:
            row = select_row if select_row is not None else 0
            row = max(0, min(row, len(self._snippets) - 1))
            self.snippet_list.setCurrentRow(row)
        else:
            self.snippet_name_edit.clear()
            self.snippet_text_edit.clear()
            self.snippet_name_edit.setEnabled(False)
            self.snippet_text_edit.setEnabled(False)
            self.btn_snippet_remove.setEnabled(False)
        self._snippet_sync_blocked = False
        if self._snippets:
            self.snippet_name_edit.setEnabled(True)
            self.snippet_text_edit.setEnabled(True)
            self.btn_snippet_remove.setEnabled(True)
            self._load_snippet_into_editor(self.snippet_list.currentRow())

    def _load_snippet_into_editor(self, row: int) -> None:
        if row < 0 or row >= len(self._snippets):
            return
        self._snippet_sync_blocked = True
        snippet = self._snippets[row]
        self.snippet_name_edit.setText(snippet.get("name", ""))
        self.snippet_text_edit.setPlainText(snippet.get("text", ""))
        self._snippet_sync_blocked = False

    def _on_snippet_selected(self, row: int) -> None:
        if self._snippet_sync_blocked or row < 0:
            return
        self._load_snippet_into_editor(row)

    def _on_snippet_editor_changed(self) -> None:
        if self._snippet_sync_blocked:
            return
        row = self.snippet_list.currentRow()
        if row < 0 or row >= len(self._snippets):
            return
        name = self.snippet_name_edit.text().strip() or "Sin nombre"
        text = self.snippet_text_edit.toPlainText()
        self._snippets[row] = {"name": name, "text": text}
        self._snippet_sync_blocked = True
        self.snippet_list.item(row).setText(name)
        self._snippet_sync_blocked = False

    def _add_snippet(self) -> None:
        self._snippets.append({"name": "Nueva plantilla", "text": ""})
        self._reload_snippet_list(select_row=len(self._snippets) - 1)
        self.tabs.setCurrentIndex(1)
        self.snippet_name_edit.setFocus()
        self.snippet_name_edit.selectAll()

    def _remove_snippet(self) -> None:
        row = self.snippet_list.currentRow()
        if row < 0:
            return
        reply = QMessageBox.question(
            self,
            "Eliminar plantilla",
            f"¿Eliminar la plantilla «{self._snippets[row].get('name', '')}»?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        del self._snippets[row]
        self._reload_snippet_list(select_row=min(row, len(self._snippets) - 1))

    def _restore_default_snippets(self) -> None:
        reply = QMessageBox.question(
            self,
            "Restaurar plantillas",
            "¿Sustituir todas las plantillas por las predeterminadas?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._snippets = copy.deepcopy(DEFAULT_COMPOSE_SNIPPETS)
        self._reload_snippet_list()

    def _accept_preferences(self) -> None:
        oauth_data = self._collect_oauth_data()
        oauth_error = validate_oauth_clients_data(oauth_data)
        if oauth_error:
            QMessageBox.warning(self, "OAuth", oauth_error)
            self.tabs.setCurrentIndex(_PREFERENCES_TAB_INDEX["oauth"])
            return

        row = self.snippet_list.currentRow()
        if row >= 0:
            self._on_snippet_editor_changed()
        normalized = normalize_compose_snippets(self._snippets)
        if not normalized:
            QMessageBox.warning(
                self,
                "Plantillas vacías",
                "Añade al menos una plantilla con nombre y texto, "
                "o restaura las predeterminadas.",
            )
            self.tabs.setCurrentIndex(_PREFERENCES_TAB_INDEX["snippets"])
            return
        self._snippets = normalized
        self._settings.save_classification_rules(
            self._classification_widget.get_rules()
        )
        save_oauth_clients_data(oauth_data)
        self._oauth_data = oauth_data
        if self.oauth_embed_check.isChecked() and any(
            str((oauth_data.get(key) or {}).get("client_id", "")).strip()
            for key in ("gmail", "outlook")
        ):
            try:
                embed_oauth_clients(oauth_data, local=True)
            except ValueError:
                pass
        self.accept()

    def get_preferences(self) -> UserPreferences:
        sort_keys = ["date_desc", "date_asc", "sender", "subject"]
        return UserPreferences(
            block_remote_images=self.block_images.isChecked(),
            background_sync_enabled=self.bg_sync.isChecked(),
            background_sync_interval_sec=self.sync_interval.value() * 60,
            use_imap_idle=self.use_idle.isChecked(),
            notify_new_mail=self.notify.isChecked(),
            page_size=self.page_size.value(),
            thread_view=self.thread_view.isChecked(),
            sort_by=sort_keys[self.sort_combo.currentIndex()],
            headers_only_large_folders=self.large_headers.isChecked(),
            delete_from_server_after_download=self.delete_after_download.isChecked(),
            compose_snippets=copy.deepcopy(self._snippets),
            translate_target_language=self.translate_lang.currentData(),
            theme=self.theme_combo.currentData(),
            compose_request_read_receipt=self.compose_read_receipt.isChecked(),
            search_all_folders=self.search_all_folders.isChecked(),
            openpgp_enabled=self.openpgp_enabled.isChecked(),
            openpgp_auto_decrypt=self.openpgp_auto_decrypt.isChecked(),
            openpgp_sign_by_default=self.openpgp_sign_default.isChecked(),
            openpgp_encrypt_by_default=self.openpgp_encrypt_default.isChecked(),
            openpgp_use_system_gnupg_home=self.openpgp_use_system_home.isChecked(),
            openpgp_signing_key_id=self.openpgp_signing_key.text().strip(),
            openpgp_cache_decrypted_bodies=self.openpgp_cache_decrypted.isChecked(),
        )
