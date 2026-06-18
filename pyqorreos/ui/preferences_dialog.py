"""
Diálogo de preferencias de PyQorreos.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from pyqorreos.core.user_preferences import UserPreferences


class PreferencesDialog(QDialog):
    def __init__(self, prefs: UserPreferences, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferencias de PyQorreos")
        self.setMinimumWidth(480)
        self._prefs = prefs
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        sync_group = QGroupBox("Sincronización con el servidor")
        sync_form = QFormLayout(sync_group)

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

        download_group = QGroupBox("Descarga de mensajes")
        download_form = QFormLayout(download_group)

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
        view_form = QFormLayout(view_group)

        self.block_images = QCheckBox("Bloquear imágenes remotas al leer")
        self.block_images.setChecked(self._prefs.block_remote_images)
        view_form.addRow(self.block_images)

        self.thread_view = QCheckBox("Vista de conversaciones (agrupar hilos)")
        self.thread_view.setChecked(self._prefs.thread_view)
        view_form.addRow(self.thread_view)

        self.large_headers = QCheckBox("Solo cabeceras en carpetas muy grandes")
        self.large_headers.setChecked(self._prefs.headers_only_large_folders)
        view_form.addRow(self.large_headers)

        self.page_size = QSpinBox()
        self.page_size.setRange(10, 200)
        self.page_size.setValue(self._prefs.page_size)
        view_form.addRow("Correos por página:", self.page_size)

        self.sort_combo = QComboBox()
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

        layout.addWidget(view_group)

        hint = QLabel(
            "Los cambios de sincronización se aplican al guardar. "
            "El intervalo mínimo recomendado es 2–5 minutos."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666; font-size: 9pt;")
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

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
        )
