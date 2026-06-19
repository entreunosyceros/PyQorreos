"""
Ventana principal del gestor de correo.

Layout de tres paneles: carpetas | lista de mensajes | lectura.
Toda comunicación con el servidor se delega a workers en segundo plano.
"""

from __future__ import annotations

from datetime import datetime
from email.utils import parseaddr
import subprocess
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from pyqorreos.core.account import MailAccount
from pyqorreos.core.classifier import MailCategory, extract_email_address
from pyqorreos.core.folder_utils import (
    can_delete_folder,
    find_drafts_folder,
    find_trash_folder,
    folder_descendants,
    is_trash_folder,
)
from pyqorreos.core.mail_cache import MailCache
from pyqorreos.core.mail_service import MailMessage, MailService, MailSummary, normalize_mail_datetime
from pyqorreos.core.oauth import AuthMethod, detect_oauth_provider, oauth_not_configured_message
from pyqorreos.core.reply_utils import ComposeDraft, build_forward, build_reply
from pyqorreos.core.settings import Settings
from pyqorreos.core.translate import language_label
from pyqorreos.core.user_preferences import UserPreferences, load_preferences, save_preferences
from pyqorreos.ui.about_dialog import AboutDialog, LOGO_PATH
from pyqorreos.ui.account_dialog import AccountDialog
from pyqorreos.ui.accounts_manager_dialog import AccountsManagerDialog
from pyqorreos.ui.attachment_panel import AttachmentPanel
from pyqorreos.ui.background_sync import BackgroundSyncManager
from pyqorreos.ui.compose_dialog import ComposeDialog
from pyqorreos.ui.folder_tree_widget import populate_folder_tree, selected_folder_path
from pyqorreos.ui.message_viewer import MessageViewer
from pyqorreos.ui.notification_utils import format_new_mail_notification
from pyqorreos.ui.preferences_dialog import PreferencesDialog
from pyqorreos.ui.system_tray import SystemTray
from pyqorreos.ui.workers import (
    ConnectWorker,
    CreateFolderWorker,
    DeleteFolderWorker,
    DeleteMessageWorker,
    DeleteMessagesWorker,
    EmptyFolderWorker,
    EnhanceHtmlWorker,
    ExportFolderWorker,
    ExportMessageWorker,
    FetchAttachmentWorker,
    FetchMessageWorker,
    FolderUnreadWorker,
    MoveMessagesWorker,
    SaveDraftWorker,
    SetSeenWorker,
    StorageQuotaWorker,
    SyncFolderWorker,
    TranslateMessageWorker,
    UnsubscribeWorker,
)


# Tamaño por defecto; se sobreescribe con preferencias del usuario.
DEFAULT_PAGE_SIZE = 50
TABLE_FONT_SIZE = 10


def _font_bold(base: QFont | None = None, point_size: int = TABLE_FONT_SIZE) -> QFont:
    """Fuente en negrita con tamaño válido (evita QFont::setPixelSize <= 0)."""
    font = QFont(base) if isinstance(base, QFont) else QFont()
    if font.pointSize() <= 0:
        font.setPointSize(point_size)
    font.setBold(True)
    return font


def _font_normal(base: QFont | None = None, point_size: int = TABLE_FONT_SIZE) -> QFont:
    font = QFont(base) if isinstance(base, QFont) else QFont()
    if font.pointSize() <= 0:
        font.setPointSize(point_size)
    font.setBold(False)
    return font


def _sender_address(sender: str) -> str:
    """Extrae la dirección de correo de una cabecera From."""
    _name, addr = parseaddr(sender)
    return addr


def _selected_summary(
    uid: str | None, messages: list[MailSummary]
) -> MailSummary | None:
    if not uid:
        return None
    return next((m for m in messages if m.uid == uid), None)


# Colores de fondo por categoría en la tabla de mensajes.
TEXT_COLOR = QColor("#1a1a1a")
CATEGORY_COLORS = {
    MailCategory.NORMAL: QColor(255, 255, 255),
    MailCategory.IMPORTANT: QColor(255, 248, 220),
    MailCategory.SPAM: QColor(255, 235, 235),
}

_READER_BTN_COMMON = """
QPushButton {
    border-radius: 5px;
    padding: 7px 12px;
    font-size: 10pt;
    font-weight: 600;
    min-height: 32px;
}
QPushButton:disabled {
    background-color: #ececec;
    color: #9a9a9a;
    border: 1px solid #d4d4d4;
}
"""

_READER_BTN_PRIMARY = _READER_BTN_COMMON + """
QPushButton {
    background-color: #2d7dd2;
    color: #ffffff;
    border: 1px solid #1f5fa8;
}
QPushButton:hover:!disabled {
    background-color: #3a8de0;
    border-color: #1a5496;
}
QPushButton:pressed:!disabled {
    background-color: #1f5fa8;
}
"""

_READER_BTN_SECONDARY = _READER_BTN_COMMON + """
QPushButton {
    background-color: #f0f4f8;
    color: #1a1a1a;
    border: 1px solid #b8c4d0;
}
QPushButton:hover:!disabled {
    background-color: #e3ebf3;
    border-color: #2d7dd2;
}
QPushButton:pressed:!disabled {
    background-color: #d5e3f0;
}
"""

_READER_BTN_DANGER = _READER_BTN_COMMON + """
QPushButton {
    background-color: #fff5f5;
    color: #b42318;
    border: 1px solid #f0a8a0;
}
QPushButton:hover:!disabled {
    background-color: #ffe8e6;
    border-color: #d92d20;
}
QPushButton:pressed:!disabled {
    background-color: #ffd5d2;
}
"""

_READER_BTN_CATEGORY = _READER_BTN_COMMON + """
QPushButton {
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #c8c8c8;
}
QPushButton:hover:!disabled {
    background-color: #f7f7f7;
    border-color: #888888;
}
QPushButton:pressed:!disabled {
    background-color: #ececec;
}
"""


class MainWindow(QMainWindow):
    """Ventana principal con carpetas, bandeja de entrada y lector de mensajes."""

    def __init__(self) -> None:
        super().__init__()
        self.settings = Settings()
        self.mail_cache = MailCache()
        self.accounts: list[MailAccount] = self.settings.load_accounts()
        self.current_account: MailAccount | None = None
        self.mail_service: MailService | None = None
        self._workers: list = []
        self._quitting = False
        self._tray: SystemTray | None = None
        self._all_messages: list[MailSummary] = []
        self._current_folder = "INBOX"
        self._current_page = 0
        self._sync_worker: SyncFolderWorker | None = None
        self._sync_generation = 0
        self._current_message: MailMessage | None = None
        self._message_fetch_worker: FetchMessageWorker | None = None
        self._pending_fetch_uid: str | None = None
        self._reader_buttons: list[QPushButton] = []
        self._enhance_worker: EnhanceHtmlWorker | None = None
        self._pending_enhance_uid: str | None = None
        self._enhance_generation = 0
        self._explicit_image_load = False
        self._translate_worker: TranslateMessageWorker | None = None
        self._pending_translate_uid: str | None = None
        self._translate_generation = 0
        self._translation_cache: dict[tuple[str, str], dict[str, str]] = {}
        self._original_subject = ""
        self._sync_new_total = 0
        self._account_combo_blocked = False
        self._prefs: UserPreferences = load_preferences()
        self._folder_names: list[str] = []
        self._folder_unread: dict[str, int] = {}
        self._background_sync = BackgroundSyncManager(self.settings, self.mail_cache, self)
        self._background_sync.signals.new_mail.connect(self._on_background_new_mail)
        self._background_sync.signals.folder_updated.connect(self._on_background_folder_updated)

        self.setWindowTitle("PyQorreos")
        self.setMinimumSize(1000, 650)
        self._build_actions()
        self._build_ui()
        self._build_menu()
        self._build_toolbar()
        self._build_reader_actions()
        self._build_system_tray()

        if self.accounts:
            last_id = self.settings.get_last_account_id()
            account = next(
                (a for a in self.accounts if a.id == last_id),
                self.accounts[0],
            )
            self._connect_account(account)
        else:
            self._show_welcome()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Panel de carpetas
        folder_panel = QWidget()
        folder_layout = QVBoxLayout(folder_panel)
        folder_layout.setContentsMargins(8, 8, 4, 8)
        folder_label = QLabel("Carpetas")
        folder_label.setFont(_font_bold(folder_label.font(), 11))
        folder_layout.addWidget(folder_label)

        folder_btn_row = QHBoxLayout()
        self.btn_new_folder = QPushButton("＋ Carpeta")
        self.btn_new_folder.setToolTip("Crear una carpeta nueva en el servidor")
        self.btn_new_folder.clicked.connect(lambda: self._create_folder())
        self.btn_new_subfolder = QPushButton("＋ Subcarpeta")
        self.btn_new_subfolder.setToolTip(
            "Crear una subcarpeta dentro de la carpeta seleccionada"
        )
        self.btn_new_subfolder.clicked.connect(self._create_subfolder)
        folder_btn_row.addWidget(self.btn_new_folder)
        folder_btn_row.addWidget(self.btn_new_subfolder)
        folder_btn_row.addStretch()
        folder_layout.addLayout(folder_btn_row)

        self.folder_tree = QTreeWidget()
        self.folder_tree.setHeaderHidden(True)
        self.folder_tree.setStyleSheet(
            """
            QTreeWidget {
                background-color: #f4f4f4;
                color: #1a1a1a;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QTreeWidget::item {
                padding: 6px 8px;
                color: #1a1a1a;
            }
            QTreeWidget::item:selected {
                background-color: #2d7dd2;
                color: #ffffff;
            }
            QTreeWidget::item:hover:!selected {
                background-color: #e8e8e8;
                color: #1a1a1a;
            }
            """
        )
        self.folder_tree.currentItemChanged.connect(self._on_folder_tree_changed)
        self.folder_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.folder_tree.customContextMenuRequested.connect(self._show_folder_context_menu)
        folder_layout.addWidget(self.folder_tree)

        self.quota_bar = QProgressBar()
        self.quota_bar.setMaximum(100)
        self.quota_bar.setTextVisible(False)
        self.quota_bar.setMaximumHeight(8)
        self.quota_bar.setVisible(False)
        folder_layout.addWidget(self.quota_bar)
        self.quota_label = QLabel("")
        self.quota_label.setStyleSheet("color: #666; font-size: 9pt;")
        self.quota_label.setWordWrap(True)
        self.quota_label.setVisible(False)
        folder_layout.addWidget(self.quota_label)

        splitter.addWidget(folder_panel)

        # Panel central: lista de mensajes
        message_panel = QWidget()
        message_layout = QVBoxLayout(message_panel)
        message_layout.setContentsMargins(4, 8, 4, 8)

        account_row = QHBoxLayout()
        account_row.addWidget(QLabel("Cuenta:"))
        self.account_combo = QComboBox()
        self.account_combo.setMinimumWidth(220)
        self.account_combo.currentIndexChanged.connect(self._on_account_combo_changed)
        account_row.addWidget(self.account_combo, 1)
        self.btn_manage_accounts = QPushButton("Gestionar…")
        self.btn_manage_accounts.clicked.connect(self._manage_accounts)
        account_row.addWidget(self.btn_manage_accounts)
        message_layout.addLayout(account_row)
        self._refresh_account_combo()

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Buscar:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Asunto o remitente…")
        self.search_edit.textChanged.connect(self._apply_list_filters)
        filter_row.addWidget(self.search_edit, 1)
        self.unread_only_check = QCheckBox("Solo no leídos")
        self.unread_only_check.toggled.connect(self._apply_list_filters)
        filter_row.addWidget(self.unread_only_check)
        filter_row.addWidget(QLabel("Filtrar:"))
        self.category_filter = QComboBox()
        self.category_filter.addItems(["Todos", "Normal", "Importante", "Spam"])
        self.category_filter.currentTextChanged.connect(self._apply_category_filter)
        filter_row.addWidget(self.category_filter)
        filter_row.addWidget(QLabel("Orden:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(
            ["Fecha ↓", "Fecha ↑", "Remitente", "Asunto"]
        )
        self.sort_combo.currentIndexChanged.connect(self._apply_list_filters)
        filter_row.addWidget(self.sort_combo)
        sort_map = {"date_desc": 0, "date_asc": 1, "sender": 2, "subject": 3}
        self.sort_combo.setCurrentIndex(sort_map.get(self._prefs.sort_by, 0))
        message_layout.addLayout(filter_row)

        self.message_table = QTableWidget(0, 4)
        self.message_table.setHorizontalHeaderLabels(["Tipo", "De", "Asunto", "Fecha"])
        self.message_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.message_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.message_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.message_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.message_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.message_table.setSelectionMode(
            QTableWidget.SelectionMode.ExtendedSelection
        )
        self.message_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.message_table.setAlternatingRowColors(False)
        self.message_table.setStyleSheet(
            """
            QTableWidget {
                background-color: #ffffff;
                color: #1a1a1a;
                gridline-color: #dddddd;
                selection-background-color: #2d7dd2;
                selection-color: #ffffff;
            }
            QTableWidget::item {
                color: #1a1a1a;
                padding: 2px 4px;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                color: #1a1a1a;
                padding: 4px;
                border: 1px solid #dddddd;
            }
            """
        )
        self.message_table.verticalHeader().setVisible(False)
        self.message_table.itemSelectionChanged.connect(
            self._on_message_selection_changed
        )
        self.message_table.cellDoubleClicked.connect(self._on_message_double_clicked)
        open_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), self.message_table)
        open_shortcut.activated.connect(self._open_selected_message)
        open_shortcut_enter = QShortcut(QKeySequence(Qt.Key.Key_Enter), self.message_table)
        open_shortcut_enter.activated.connect(self._open_selected_message)
        self.message_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.message_table.customContextMenuRequested.connect(
            self._show_message_context_menu
        )
        message_layout.addWidget(self.message_table)

        # Paginación (50 correos por página)
        pagination_row = QHBoxLayout()
        self.btn_delete_selected = QPushButton("🗑 Eliminar")
        self.btn_delete_selected.setToolTip(
            "Eliminar los mensajes seleccionados (Supr)"
        )
        self.btn_delete_selected.clicked.connect(self._act_delete.trigger)
        self.btn_delete_selected.setEnabled(False)
        self.btn_move_selected = QPushButton("📁 Mover a…")
        self.btn_move_selected.setToolTip("Mover los mensajes seleccionados a otra carpeta")
        self.btn_move_selected.clicked.connect(self._show_move_messages_dialog)
        self.btn_move_selected.setEnabled(False)
        self._list_action_buttons = [self.btn_delete_selected, self.btn_move_selected]
        pagination_row.addWidget(self.btn_delete_selected)
        pagination_row.addWidget(self.btn_move_selected)
        pagination_row.addSpacing(12)
        self.btn_prev_page = QPushButton("◀ Anterior")
        self.btn_prev_page.clicked.connect(self._prev_page)
        self.page_label = QLabel("Página 1 de 1")
        self.btn_next_page = QPushButton("Siguiente ▶")
        self.btn_next_page.clicked.connect(self._next_page)
        self.btn_cancel_sync = QPushButton("Cancelar sincronización")
        self.btn_cancel_sync.clicked.connect(self._cancel_sync)
        self.btn_cancel_sync.setVisible(False)
        pagination_row.addWidget(self.btn_prev_page)
        pagination_row.addWidget(self.page_label)
        pagination_row.addWidget(self.btn_next_page)
        pagination_row.addStretch()
        pagination_row.addWidget(self.btn_cancel_sync)
        message_layout.addLayout(pagination_row)

        # Barra de progreso de sincronización
        self.sync_progress = QProgressBar()
        self.sync_progress.setVisible(False)
        self.sync_progress.setTextVisible(True)
        message_layout.addWidget(self.sync_progress)

        splitter.addWidget(message_panel)

        # Panel de lectura
        reader_panel = QWidget()
        reader_layout = QVBoxLayout(reader_panel)
        reader_layout.setContentsMargins(4, 8, 8, 8)
        self.subject_label = QLabel("Selecciona un mensaje")
        self.subject_label.setFont(_font_bold(self.subject_label.font(), 13))
        self.subject_label.setWordWrap(True)
        reader_layout.addWidget(self.subject_label)

        self.meta_label = QLabel("")
        self.meta_label.setStyleSheet("color: #666;")
        self.meta_label.setWordWrap(True)
        reader_layout.addWidget(self.meta_label)

        # Botones de acción del mensaje abierto (estilo Thunderbird)
        self.reader_actions = QWidget()
        self.reader_actions.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        reader_layout.addWidget(self.reader_actions)

        self.attachment_panel = AttachmentPanel()
        self.attachment_panel.save_requested.connect(self._save_attachment)
        self.attachment_panel.open_requested.connect(self._open_attachment)
        reader_layout.addWidget(self.attachment_panel)

        self.message_viewer = MessageViewer()
        self.message_viewer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.message_viewer.load_remote_images_requested.connect(
            self._load_remote_images_for_current
        )
        self.message_viewer.translate_requested.connect(self._on_translate_requested)
        self.message_viewer.link_hover_changed.connect(self._on_viewer_link_hover)
        reader_layout.addWidget(self.message_viewer, 1)
        splitter.addWidget(reader_panel)

        splitter.setSizes([180, 380, 440])
        layout.addWidget(splitter)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Listo")

    def _page_size(self) -> int:
        return max(10, self._prefs.page_size)

    def _build_actions(self) -> None:
        """
        Define las acciones compartidas por el menú superior y la bandeja.

        Al añadir nuevas opciones al programa, regístralas aquí para que
        aparezcan automáticamente en ambos sitios.
        """
        self._act_show = QAction("Mostrar ventana", self)
        self._act_show.triggered.connect(self.show_main_window)

        self._act_tray_inbox = QAction("Bandeja de entrada", self)
        self._act_tray_inbox.triggered.connect(self._open_tray_inbox)

        self._act_quit = QAction("Salir", self)
        self._act_quit.setShortcut("Ctrl+Q")
        self._act_quit.triggered.connect(self._quit_application)

        self._act_add_account = QAction("Añadir cuenta…", self)
        self._act_add_account.triggered.connect(self._add_account)

        self._act_manage_accounts = QAction("Gestionar cuentas…", self)
        self._act_manage_accounts.triggered.connect(self._manage_accounts)

        self._act_refresh = QAction("Actualizar", self)
        self._act_refresh.setShortcut("F5")
        self._act_refresh.triggered.connect(self._refresh)

        self._act_compose = QAction("Redactar", self)
        self._act_compose.setShortcut("Ctrl+N")
        self._act_compose.triggered.connect(lambda: self._compose())

        self._act_reply = QAction("↩ Responder", self)
        self._act_reply.setShortcut("Ctrl+R")
        self._act_reply.setToolTip("Responder al remitente (Ctrl+R)")
        self._act_reply.triggered.connect(self._reply)

        self._act_reply_all = QAction("↩↩ Responder a todos", self)
        self._act_reply_all.setShortcut("Ctrl+Shift+R")
        self._act_reply_all.setToolTip("Responder a todos los destinatarios (Ctrl+Shift+R)")
        self._act_reply_all.triggered.connect(self._reply_all)

        self._act_forward = QAction("→ Reenviar", self)
        self._act_forward.setShortcut("Ctrl+L")
        self._act_forward.setToolTip("Reenviar este mensaje (Ctrl+L)")
        self._act_forward.triggered.connect(self._forward)

        self._act_delete = QAction("Eliminar", self)
        self._act_delete.setShortcut("Delete")
        self._act_delete.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self._act_delete.setToolTip("Eliminar los mensajes seleccionados (Supr)")
        self._act_delete.triggered.connect(self._delete_message)

        self._act_move_messages = QAction("Mover a otra carpeta…", self)
        self._act_move_messages.setShortcut("Ctrl+Shift+M")
        self._act_move_messages.triggered.connect(self._show_move_messages_dialog)

        self._act_new_folder = QAction("Nueva carpeta…", self)
        self._act_new_folder.triggered.connect(lambda: self._create_folder())

        self._act_new_subfolder = QAction("Nueva subcarpeta…", self)
        self._act_new_subfolder.triggered.connect(self._create_subfolder)

        self._act_mark_important = QAction("Marcar como importante", self)
        self._act_mark_important.triggered.connect(
            lambda: self._mark_selected_category(MailCategory.IMPORTANT)
        )

        self._act_mark_spam = QAction("Marcar como spam", self)
        self._act_mark_spam.triggered.connect(
            lambda: self._mark_selected_category(MailCategory.SPAM)
        )

        self._act_mark_normal = QAction("Marcar como normal", self)
        self._act_mark_normal.triggered.connect(
            lambda: self._mark_selected_category(MailCategory.NORMAL)
        )

        self._act_about = QAction("Acerca de…", self)
        self._act_about.triggered.connect(self._show_about)

        self._act_preferences = QAction("Preferencias…", self)
        self._act_preferences.setShortcut("Ctrl+,")
        self._act_preferences.triggered.connect(self._show_preferences)

        self._act_unsubscribe = QAction("Darse de baja del boletín", self)
        self._act_unsubscribe.triggered.connect(self._unsubscribe_current_message)

        self._act_export_eml = QAction("Exportar como .eml…", self)
        self._act_export_eml.triggered.connect(self._export_selected_eml)

        self._act_export_folder = QAction("Exportar carpeta a .mbox…", self)
        self._act_export_folder.triggered.connect(self._export_current_folder_mbox)

        for action in (
            self._act_reply,
            self._act_reply_all,
            self._act_forward,
            self._act_delete,
            self._act_move_messages,
            self._act_mark_important,
            self._act_mark_spam,
            self._act_mark_normal,
            self._act_unsubscribe,
        ):
            action.setEnabled(False)

        self.addAction(self._act_delete)

    def _ensure_reader_actions_layout(self) -> None:
        """Crea el layout en dos filas (evita que los botones se compriman)."""
        if hasattr(self, "_reader_row1"):
            return
        outer = QVBoxLayout(self.reader_actions)
        outer.setContentsMargins(0, 4, 0, 8)
        outer.setSpacing(6)
        self._reader_row1 = QHBoxLayout()
        self._reader_row1.setSpacing(8)
        self._reader_row2 = QHBoxLayout()
        self._reader_row2.setSpacing(8)
        outer.addLayout(self._reader_row1)
        outer.addLayout(self._reader_row2)

    def _clear_layout(self, layout: QHBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _make_reader_button(
        self, action: QAction, label: str, style: str
    ) -> QPushButton:
        btn = QPushButton(label)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(style)
        btn.setEnabled(action.isEnabled())
        btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        btn.clicked.connect(action.trigger)
        btn.setToolTip(action.toolTip() or action.text())
        return btn

    def _build_reader_actions(self) -> None:
        """Botones visibles sobre el mensaje abierto (dos filas, texto completo)."""
        self._ensure_reader_actions_layout()
        self._clear_layout(self._reader_row1)
        self._clear_layout(self._reader_row2)
        self._reader_buttons.clear()

        row1_specs = (
            (self._act_reply, "↩ Responder", _READER_BTN_PRIMARY),
            (self._act_reply_all, "↩↩ Responder a todos", _READER_BTN_PRIMARY),
            (self._act_forward, "→ Reenviar", _READER_BTN_SECONDARY),
            (self._act_delete, "🗑 Eliminar", _READER_BTN_DANGER),
        )
        row2_specs = (
            (self._act_mark_important, "★ Importante", _READER_BTN_CATEGORY),
            (self._act_mark_spam, "⚠ Spam", _READER_BTN_CATEGORY),
            (self._act_mark_normal, "● Normal", _READER_BTN_CATEGORY),
            (self._act_unsubscribe, "✉ Dar de baja", _READER_BTN_SECONDARY),
        )

        for action, label, style in row1_specs:
            btn = self._make_reader_button(action, label, style)
            self._reader_row1.addWidget(btn)
            self._reader_buttons.append(btn)
        self._reader_row1.addStretch()

        for action, label, style in row2_specs:
            btn = self._make_reader_button(action, label, style)
            self._reader_row2.addWidget(btn)
            self._reader_buttons.append(btn)
        self._reader_row2.addStretch()

    def _detach_translate_worker(self) -> None:
        self._pending_translate_uid = None
        if not self._translate_worker:
            return
        try:
            self._translate_worker.signals.finished.disconnect(self._on_message_translated)
        except (RuntimeError, TypeError):
            pass
        try:
            self._translate_worker.signals.error.disconnect(self._on_translate_error)
        except (RuntimeError, TypeError):
            pass

    def _detach_enhance_worker(self) -> None:
        """Ignora el resultado de una mejora HTML en curso (p. ej. al cambiar de mensaje)."""
        self._pending_enhance_uid = None
        if not self._enhance_worker:
            return
        try:
            self._enhance_worker.signals.finished.disconnect(self._on_html_enhanced)
        except (RuntimeError, TypeError):
            pass
        try:
            self._enhance_worker.signals.error.disconnect(self._on_enhance_error)
        except (RuntimeError, TypeError):
            pass

    def _on_message_selection_changed(self) -> None:
        selected = self._selected_message_uid()
        if self._pending_fetch_uid and selected != self._pending_fetch_uid:
            self._pending_fetch_uid = None
            if self._message_fetch_worker and self._message_fetch_worker.isRunning():
                try:
                    self._message_fetch_worker.signals.finished.disconnect(
                        self._display_message
                    )
                    self._message_fetch_worker.signals.error.disconnect(
                        self._on_fetch_error
                    )
                except (RuntimeError, TypeError):
                    pass
        self._update_message_actions()
        self._show_selection_preview()

    def _show_selection_preview(self) -> None:
        """Muestra metadatos del listado sin descargar el cuerpo (doble clic para abrir)."""
        uid = self._selected_message_uid()
        if not uid:
            return
        if self._message_loaded_for_selection():
            return

        summary = next((m for m in self._all_messages if m.uid == uid), None)
        if summary:
            self.subject_label.setText(summary.subject)
            date_str = (
                summary.date.strftime("%d/%m/%Y %H:%M") if summary.date else ""
            )
            self.meta_label.setText(
                f"De: {summary.sender}\n"
                f"Categoría: {summary.category.icon} {summary.category.label}\n"
                f"{date_str}"
            )
        else:
            self.subject_label.setText("Mensaje seleccionado")
            self.meta_label.setText("")

        if self._current_message and self._current_message.uid != uid:
            self._current_message = None

        self.message_viewer.show_plain("Doble clic en el mensaje para abrirlo.")
        self.attachment_panel.clear()

    def _update_message_actions(self) -> None:
        selected = self._selected_message_uids()
        has_row = len(selected) > 0
        has_single = len(selected) == 1
        loaded = has_single and self._message_loaded_for_selection()

        if has_row:
            if len(selected) == 1:
                tip = "Eliminar el mensaje seleccionado (Supr)"
                delete_label = "🗑 Eliminar"
            else:
                tip = f"Eliminar {len(selected)} mensajes seleccionados (Supr)"
                delete_label = f"🗑 Eliminar ({len(selected)})"
            self._act_delete.setToolTip(tip)
            if hasattr(self, "btn_delete_selected"):
                self.btn_delete_selected.setText(delete_label)
                self.btn_delete_selected.setToolTip(tip)

        for action in (
            self._act_reply,
            self._act_reply_all,
            self._act_forward,
        ):
            action.setEnabled(has_row and loaded)
        for action in (
            self._act_delete,
            self._act_move_messages,
            self._act_mark_important,
            self._act_mark_spam,
            self._act_mark_normal,
        ):
            action.setEnabled(has_row)

        for btn in getattr(self, "_list_action_buttons", []):
            btn.setEnabled(has_row)

        for index, btn in enumerate(self._reader_buttons):
            if index <= 2:
                btn.setEnabled(has_row and loaded)
            elif btn.text().startswith("✉"):
                msg = self._current_message
                can_unsub = bool(
                    loaded
                    and msg
                    and (msg.unsubscribe_url or msg.unsubscribe_mailto)
                )
                btn.setEnabled(can_unsub)
                self._act_unsubscribe.setEnabled(can_unsub)
            else:
                btn.setEnabled(has_row)

    def _set_message_actions_enabled(self, enabled: bool) -> None:
        """Compatibilidad: tras cargar mensaje o limpiar el lector."""
        if not enabled:
            for action in (
                self._act_reply,
                self._act_reply_all,
                self._act_forward,
                self._act_delete,
                self._act_mark_important,
                self._act_mark_spam,
                self._act_mark_normal,
            ):
                action.setEnabled(False)
            for btn in self._reader_buttons:
                btn.setEnabled(False)
            for btn in getattr(self, "_list_action_buttons", []):
                btn.setEnabled(False)
        else:
            self._update_message_actions()

    def _selected_message_uids(self) -> list[str]:
        if not hasattr(self, "_message_uids"):
            return []
        model = self.message_table.selectionModel()
        if model:
            rows = {idx.row() for idx in model.selectedRows()}
        else:
            rows = {idx.row() for idx in self.message_table.selectedIndexes()}
        uids: list[str] = []
        for row in sorted(rows):
            if 0 <= row < len(self._message_uids):
                uids.append(self._message_uids[row])
        return uids

    def _selected_message_uid(self) -> str | None:
        uids = self._selected_message_uids()
        return uids[0] if uids else None

    def _message_loaded_for_selection(self) -> bool:
        uid = self._selected_message_uid()
        return bool(
            uid
            and self._current_message
            and self._current_message.uid == uid
            and not self._message_body_is_empty(self._current_message)
        )

    def _message_body_is_empty(self, message: MailMessage) -> bool:
        html = (message.body_html or "").strip()
        text = (message.body_text or "").strip()
        if html:
            return False
        return not text or text in ("(Sin contenido)", "(Mensaje vacío)")

    def _show_message_context_menu(self, pos) -> None:
        """Menú contextual al clic derecho sobre un correo del listado."""
        row = self.message_table.rowAt(pos.y())
        if row < 0 or not hasattr(self, "_message_uids"):
            return

        # Seleccionar sin disparar la descarga IMAP (evita errores al abrir el menú).
        self.message_table.blockSignals(True)
        self.message_table.selectRow(row)
        self.message_table.blockSignals(False)
        self._update_message_actions()

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { padding: 4px; }"
            "QMenu::item { padding: 6px 28px 6px 16px; }"
            "QMenu::item:selected { background-color: #2d7dd2; color: white; }"
        )

        loaded = self._message_loaded_for_selection()
        open_action = menu.addAction("Abrir mensaje")
        open_action.setEnabled(not loaded)
        open_action.triggered.connect(self._open_selected_message)

        menu.addSeparator()

        for action in (self._act_reply, self._act_reply_all, self._act_forward):
            menu_action = menu.addAction(action.text())
            menu_action.setShortcut(action.shortcut())
            menu_action.setEnabled(loaded)
            menu_action.triggered.connect(action.trigger)

        menu.addSeparator()

        delete_action = menu.addAction(self._act_delete.text())
        delete_action.setShortcut(self._act_delete.shortcut())
        delete_action.triggered.connect(self._act_delete.trigger)

        if loaded and self._current_message and (
            self._current_message.unsubscribe_url or self._current_message.unsubscribe_mailto
        ):
            unsub_action = menu.addAction("Darse de baja del boletín")
            unsub_action.triggered.connect(self._unsubscribe_current_message)

        menu.addSeparator()
        category_menu = menu.addMenu("Marcar como")
        for action in (
            self._act_mark_important,
            self._act_mark_spam,
            self._act_mark_normal,
        ):
            cat_action = category_menu.addAction(action.text())
            cat_action.setEnabled(True)
            cat_action.triggered.connect(action.trigger)

        menu.addSeparator()

        uid = self._message_uids[row]
        summary = _selected_summary(uid, self._all_messages)
        if summary and not summary.seen:
            mark_read = menu.addAction("Marcar como leído")
            mark_read.triggered.connect(lambda: self._mark_selected_seen(True))
        elif summary and summary.seen:
            mark_unread = menu.addAction("Marcar como no leído")
            mark_unread.triggered.connect(lambda: self._mark_selected_seen(False))

        copy_sender = menu.addAction("Copiar dirección del remitente")
        copy_sender.triggered.connect(self._copy_sender_address)

        export_eml = menu.addAction("Exportar como .eml…")
        export_eml.triggered.connect(self._export_selected_eml)

        move_menu = menu.addMenu("Mover a…")
        move_menu.addAction("Elegir carpeta…").triggered.connect(
            self._show_move_messages_dialog
        )
        for folder_name in self._folder_names:
            if folder_name == self._current_folder:
                continue
            act = move_menu.addAction(folder_name)
            act.triggered.connect(
                lambda _checked=False, f=folder_name: self._move_selected_messages(f)
            )

        menu.addSeparator()
        refresh_action = menu.addAction("Actualizar carpeta")
        refresh_action.setShortcut(self._act_refresh.shortcut())
        refresh_action.triggered.connect(self._refresh)

        menu.exec(self.message_table.viewport().mapToGlobal(pos))

    def _build_tray_menu(self) -> QMenu:
        """Construye el menú contextual de la bandeja del sistema."""
        menu = QMenu(self)
        menu.aboutToShow.connect(self._update_tray_menu)
        menu.addAction(self._act_show)
        menu.addAction(self._act_tray_inbox)
        menu.addSeparator()

        cuenta_menu = menu.addMenu("Cuenta")
        cuenta_menu.addAction(self._act_add_account)
        cuenta_menu.addAction(self._act_manage_accounts)
        cuenta_menu.addSeparator()
        cuenta_menu.addAction(self._act_refresh)

        correo_menu = menu.addMenu("Correo")
        correo_menu.addAction(self._act_compose)
        correo_menu.addAction(self._act_reply)
        correo_menu.addAction(self._act_reply_all)
        correo_menu.addAction(self._act_forward)
        correo_menu.addSeparator()
        correo_menu.addAction(self._act_delete)
        correo_menu.addSeparator()
        correo_menu.addAction(self._act_mark_important)
        correo_menu.addAction(self._act_mark_spam)
        correo_menu.addAction(self._act_mark_normal)

        menu.addSeparator()
        menu.addAction(self._act_preferences)
        menu.addAction(self._act_quit)
        return menu

    def _update_tray_menu(self) -> None:
        """Actualiza el menú de bandeja según la cuenta seleccionada."""
        if self.current_account:
            self._act_tray_inbox.setText(
                f"Bandeja de entrada — {self.current_account.email}"
            )
            self._act_tray_inbox.setEnabled(True)
        else:
            self._act_tray_inbox.setText("Bandeja de entrada")
            self._act_tray_inbox.setEnabled(bool(self.accounts))

    def _open_tray_inbox(self) -> None:
        """Muestra la ventana y abre INBOX de la cuenta seleccionada."""
        if not self.accounts:
            self.show_main_window()
            QMessageBox.information(
                self,
                "Sin cuenta",
                "Añade una cuenta para abrir la bandeja de entrada.",
            )
            return

        account = self.current_account
        if not account:
            last_id = self.settings.get_last_account_id()
            account = next(
                (a for a in self.accounts if a.id == last_id),
                self.accounts[0],
            )

        self.show_main_window()
        if not self.current_account or self.current_account.id != account.id:
            self._connect_account(account)
            return
        if self.mail_service:
            if self._current_folder != "INBOX":
                self._refresh_folder_tree(select_folder="INBOX")
                self._start_folder_sync("INBOX")
            else:
                self._refresh_folder_tree(select_folder="INBOX")
        else:
            self._connect_account(account)

    def _build_system_tray(self) -> None:
        """Inicializa el icono en la bandeja del sistema con logos.png."""
        if not SystemTray.is_available():
            self.status_bar.showMessage("Bandeja del sistema no disponible en este entorno")
            return

        self._tray = SystemTray(self, LOGO_PATH)
        self._tray.set_menu(self._build_tray_menu())
        self._tray.show()

    def show_main_window(self) -> None:
        """Restaura y enfoca la ventana principal."""
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit_application(self) -> None:
        """Cierra la aplicación por completo (menú Archivo / bandeja)."""
        self._quitting = True
        if self.mail_service:
            self.mail_service.disconnect()
        if self._tray:
            self._tray.hide()
        QApplication.quit()

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("Archivo")
        file_menu.addAction(self._act_preferences)
        file_menu.addSeparator()
        file_menu.addAction(self._act_quit)

        cuenta_menu = self.menuBar().addMenu("Cuenta")
        cuenta_menu.addAction(self._act_add_account)
        cuenta_menu.addAction(self._act_manage_accounts)
        cuenta_menu.addSeparator()
        cuenta_menu.addAction(self._act_refresh)

        folders_menu = self.menuBar().addMenu("Carpetas")
        folders_menu.addAction(self._act_new_folder)
        folders_menu.addAction(self._act_new_subfolder)
        folders_menu.addSeparator()
        folders_menu.addAction(self._act_move_messages)

        correo_menu = self.menuBar().addMenu("Correo")
        correo_menu.addAction(self._act_compose)
        correo_menu.addAction(self._act_reply)
        correo_menu.addAction(self._act_reply_all)
        correo_menu.addAction(self._act_forward)
        correo_menu.addSeparator()
        correo_menu.addAction(self._act_delete)
        correo_menu.addAction(self._act_move_messages)
        correo_menu.addSeparator()
        correo_menu.addAction(self._act_mark_important)
        correo_menu.addAction(self._act_mark_spam)
        correo_menu.addAction(self._act_mark_normal)

        tools_menu = self.menuBar().addMenu("Herramientas")
        tools_menu.addAction(self._act_export_eml)
        tools_menu.addAction(self._act_export_folder)

        ayuda_menu = self.menuBar().addMenu("Ayuda")
        ayuda_menu.addAction(self._act_about)

    def _show_preferences(self) -> None:
        dialog = PreferencesDialog(self._prefs, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._prefs = dialog.get_preferences()
        save_preferences(self._prefs)
        self._background_sync.update_preferences(self._prefs)
        self._background_sync.set_accounts(
            self.accounts, self.current_account.id if self.current_account else None
        )
        self._background_sync.start()
        self._apply_list_filters()

    def _show_about(self) -> None:
        """Abre el diálogo con información del programa."""
        dialog = AboutDialog(parent=self)
        dialog.exec()

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Principal")
        self.addToolBar(toolbar)

        compose_btn = QAction("✉ Redactar", self)
        compose_btn.triggered.connect(lambda: self._compose())
        toolbar.addAction(compose_btn)

        refresh_btn = QAction("↻ Actualizar", self)
        refresh_btn.triggered.connect(self._refresh)
        toolbar.addAction(refresh_btn)

        toolbar.addSeparator()

        prefs_btn = QAction("⚙ Preferencias", self)
        prefs_btn.triggered.connect(self._show_preferences)
        toolbar.addAction(prefs_btn)

        account_btn = QAction("👤 Cuentas", self)
        account_btn.triggered.connect(self._manage_accounts)
        toolbar.addAction(account_btn)

    def _show_welcome(self) -> None:
        self._current_message = None
        self._set_message_actions_enabled(False)
        self.message_viewer.show_html(
            "<h2>Bienvenido a PyQorreos</h2>"
            "<p>Añade una o más cuentas de correo para empezar.</p>"
            "<p>Ve a <b>Cuenta → Gestionar cuentas</b> o usa el botón <b>Gestionar…</b>.</p>"
        )

    def _refresh_account_combo(self, select_id: str | None = None) -> None:
        """Actualiza el selector de cuentas."""
        self._account_combo_blocked = True
        self.account_combo.clear()
        if not self.accounts:
            self.account_combo.addItem("Sin cuentas configuradas")
            self.account_combo.setEnabled(False)
            self.btn_manage_accounts.setText("Añadir cuenta…")
        else:
            self.account_combo.setEnabled(True)
            self.btn_manage_accounts.setText("Gestionar…")
            for account in self.accounts:
                name = account.display_name or account.email.split("@", 1)[0]
                self.account_combo.addItem(f"{name} ({account.email})", account.id)
            target_id = select_id or (
                self.current_account.id if self.current_account else None
            )
            if target_id:
                idx = self.account_combo.findData(target_id)
                if idx >= 0:
                    self.account_combo.setCurrentIndex(idx)
        self._account_combo_blocked = False

    def _on_account_combo_changed(self, index: int) -> None:
        if self._account_combo_blocked or index < 0 or not self.accounts:
            return
        account_id = self.account_combo.itemData(index)
        if not account_id:
            return
        if self.current_account and self.current_account.id == account_id:
            return
        account = next((a for a in self.accounts if a.id == account_id), None)
        if account:
            self._connect_account(account)

    def _save_account(self, account: MailAccount, password: str) -> bool:
        """Guarda o actualiza una cuenta en la lista local."""
        if password:
            self.settings.store_password(account.id, password)
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
                f"Ya existe una cuenta con {account.email}.",
            )
            return False
        existing = next((a for a in self.accounts if a.id == account.id), None)
        if existing:
            self.accounts[self.accounts.index(existing)] = account
        else:
            self.accounts.append(account)
        self.settings.save_accounts(self.accounts)
        self._refresh_account_combo(account.id)
        return True

    def _add_account(self) -> None:
        dialog = AccountDialog(self.settings, parent=self)
        if dialog.exec() != AccountDialog.DialogCode.Accepted:
            return
        account, password = dialog.get_result()
        if not self._save_account(account, password):
            return
        self._connect_account(account)

    def _manage_accounts(self) -> None:
        if not self.accounts:
            self._add_account()
            return

        dialog = AccountsManagerDialog(
            self.settings,
            self.accounts,
            self.current_account.id if self.current_account else None,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.accounts = self.settings.load_accounts()
            if self.current_account and self.current_account.id not in {
                a.id for a in self.accounts
            }:
                self._cancel_sync()
                if self.mail_service:
                    self.mail_service.disconnect()
                    self.mail_service = None
                self.current_account = None
                self._all_messages = []
                self.folder_tree.clear()
                self.message_table.setRowCount(0)
                self._set_message_actions_enabled(False)
                self._show_welcome()
            self._refresh_account_combo()
            return

        self.accounts = dialog.get_accounts()
        if dialog.selected_account_id:
            account = next(
                (a for a in self.accounts if a.id == dialog.selected_account_id),
                None,
            )
            if account:
                self._connect_account(account)
        else:
            self._refresh_account_combo()

    def _connect_account(self, account: MailAccount) -> None:
        """Inicia la conexión IMAP en segundo plano para la cuenta indicada."""
        if account.auth_method == AuthMethod.OAUTH2.value:
            QMessageBox.information(
                self,
                "OAuth2",
                oauth_not_configured_message(
                    detect_oauth_provider(account.email, account.imap_host)
                ),
            )
            return
        password = self.settings.get_password(account.id)
        if not password:
            QMessageBox.warning(
                self, "Sin contraseña", "No hay contraseña guardada para esta cuenta."
            )
            return

        self._cancel_sync()
        if self.mail_service:
            self.mail_service.disconnect()
            self.mail_service = None

        self.current_account = account
        self.settings.set_last_account_id(account.id)
        self._refresh_account_combo(account.id)
        self.status_bar.showMessage(f"Conectando a {account.email}…")
        self.setEnabled(False)

        worker = ConnectWorker(
            account, password, self.settings.get_classifier()
        )
        worker.signals.finished.connect(self._on_connected)
        worker.signals.error.connect(self._on_connect_error)
        worker.start()
        self._workers.append(worker)

    def _on_connected(self, result) -> None:
        self.setEnabled(True)
        service, folders = result
        self.mail_service = service
        self._folder_names = [f.name for f in folders]
        self._refresh_folder_tree(select_folder="INBOX")
        self._refresh_folder_unread_counts()
        self._refresh_storage_quota()

        folder = selected_folder_path(self.folder_tree) or "INBOX"
        self._start_folder_sync(folder)
        self._background_sync.set_accounts(self.accounts, self.current_account.id if self.current_account else None)
        self._background_sync.start()

    def _refresh_folder_tree(self, select_folder: str | None = None) -> None:
        self.folder_tree.blockSignals(True)
        populate_folder_tree(
            self.folder_tree,
            self._folder_names,
            self._folder_unread,
            select_folder=select_folder or self._current_folder,
        )
        self.folder_tree.blockSignals(False)

    def _refresh_folder_unread_counts(self) -> None:
        if not self.current_account or not self._folder_names:
            return
        password = self.settings.get_password(self.current_account.id)
        if not password:
            return
        worker = FolderUnreadWorker(
            self.current_account, password, self._folder_names
        )
        worker.signals.finished.connect(self._on_folder_unread_counts)
        worker.signals.error.connect(lambda _m: None)
        worker.start()
        self._workers.append(worker)

    def _on_folder_unread_counts(self, counts: dict) -> None:
        self._folder_unread = counts
        self._refresh_folder_tree(select_folder=self._current_folder)

    def _show_folder_context_menu(self, pos) -> None:
        folder = selected_folder_path(self.folder_tree)
        if not folder or not self.mail_service:
            return
        menu = QMenu(self)

        uids = self._selected_message_uids()
        if uids and folder != self._current_folder:
            label = (
                f"Mover {len(uids)} mensaje(s) aquí"
                if len(uids) > 1
                else "Mover mensaje aquí"
            )
            move_here = menu.addAction(label)
            move_here.triggered.connect(
                lambda _checked=False, f=folder: self._move_selected_messages(f)
            )
            menu.addSeparator()

        new_sub = menu.addAction("Nueva subcarpeta…")
        new_sub.triggered.connect(
            lambda _checked=False, parent=folder: self._create_folder(parent)
        )
        menu.addSeparator()

        if is_trash_folder(folder):
            empty = menu.addAction("Vaciar papelera")
            empty.triggered.connect(lambda: self._empty_folder(folder))
        if can_delete_folder(folder):
            delete_folder = menu.addAction("Eliminar carpeta…")
            delete_folder.triggered.connect(
                lambda _checked=False, f=folder: self._delete_folder(f)
            )
        refresh = menu.addAction("Actualizar carpeta")
        refresh.triggered.connect(self._refresh)
        export_mbox = menu.addAction("Exportar carpeta a .mbox…")
        export_mbox.triggered.connect(self._export_current_folder_mbox)
        menu.exec(self.folder_tree.viewport().mapToGlobal(pos))

    def _empty_folder(self, folder: str) -> None:
        if not self.mail_service or not self.current_account:
            return
        reply = QMessageBox.question(
            self,
            "Vaciar carpeta",
            f"¿Eliminar permanentemente todos los mensajes de «{folder}»?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        worker = EmptyFolderWorker(
            self.mail_service, folder, self.mail_cache, self.current_account.id
        )
        worker.signals.finished.connect(self._on_folder_emptied)
        worker.signals.error.connect(lambda m: self._on_sync_error(m))
        worker.start()
        self._workers.append(worker)

    def _on_folder_emptied(self, payload) -> None:
        folder, count = payload
        if folder == self._current_folder:
            self._all_messages = []
            self._render_message_table()
        self._refresh_folder_unread_counts()
        self.status_bar.showMessage(f"Carpeta vaciada ({count} mensajes)")

    def _delete_folder(self, folder: str) -> None:
        if not self.mail_service or not self.current_account:
            return
        if not can_delete_folder(folder):
            QMessageBox.warning(
                self,
                "Eliminar carpeta",
                f"La carpeta «{folder}» es del sistema y no se puede eliminar.",
            )
            return

        children = folder_descendants(self._folder_names, folder)
        if children:
            child_list = "\n".join(f"  • {name}" for name in children)
            text = (
                f"¿Eliminar la carpeta «{folder}» y sus subcarpetas?\n\n"
                f"{child_list}\n\n"
                "Los mensajes que contengan se eliminarán permanentemente del servidor."
            )
        else:
            text = (
                f"¿Eliminar la carpeta «{folder}»?\n\n"
                "Los mensajes que contenga se eliminarán permanentemente del servidor."
            )
        reply = QMessageBox.question(
            self,
            "Eliminar carpeta",
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.status_bar.showMessage(f"Eliminando carpeta «{folder}»…")
        worker = DeleteFolderWorker(
            self.mail_service,
            folder,
            self.mail_cache,
            self.current_account.id,
            recursive=bool(children),
        )
        worker.signals.finished.connect(self._on_folder_deleted)
        worker.signals.error.connect(self._on_folder_delete_error)
        worker.start()
        self._workers.append(worker)

    def _on_folder_deleted(self, payload) -> None:
        deleted_paths, folders = payload
        self._folder_names = folders
        if self._current_folder in deleted_paths or any(
            self._current_folder.startswith(path + "/") for path in deleted_paths
        ):
            self._current_folder = "INBOX"
            self._all_messages = []
            self._current_message = None
            self._render_message_table()
            self.message_viewer.clear()
            self.subject_label.setText("Selecciona un mensaje")
            self.meta_label.setText("")
        self._refresh_folder_tree(select_folder=self._current_folder)
        self._refresh_folder_unread_counts()
        if len(deleted_paths) == 1:
            self.status_bar.showMessage(f"Carpeta eliminada: {deleted_paths[0]}")
        else:
            self.status_bar.showMessage(
                f"{len(deleted_paths)} carpetas eliminadas"
            )

    def _on_folder_delete_error(self, message: str) -> None:
        self.status_bar.showMessage("Error al eliminar carpeta")
        QMessageBox.warning(self, "Error al eliminar carpeta", message)

    def _on_background_new_mail(
        self, account_id: str, folder: str, summaries: list[MailSummary]
    ) -> None:
        if not summaries:
            return
        account = next((a for a in self.accounts if a.id == account_id), None)
        label = account.email if account else "Cuenta"
        if self._tray:
            title, body = format_new_mail_notification(summaries, folder, label)
            self._tray.show_message(title, body, msecs=5000)
        if (
            self.current_account
            and self.current_account.id == account_id
            and folder == self._current_folder
        ):
            self._on_background_folder_updated(account_id, folder)

    def _on_background_folder_updated(self, account_id: str, folder: str) -> None:
        if (
            self.current_account
            and self.current_account.id == account_id
            and folder == self._current_folder
        ):
            cached = self.mail_cache.load_folder(account_id, folder)
            if cached:
                self._all_messages = cached
                self._render_message_table()
        self._refresh_folder_unread_counts()

    def _start_folder_sync(self, folder: str) -> None:
        """Carga caché local al instante y sincroniza con el servidor en segundo plano."""
        if not self.mail_service or not self.current_account:
            return

        self._cancel_sync()
        generation = self._sync_generation
        self._cancel_message_fetch()
        self._current_folder = folder
        self._current_page = 0
        self._current_message = None
        self._pending_fetch_uid = None
        self._set_message_actions_enabled(False)
        self.subject_label.setText("Selecciona un mensaje")
        self.meta_label.setText("")
        self.message_viewer.clear()
        self.attachment_panel.clear()

        self.search_edit.blockSignals(True)
        self.search_edit.clear()
        self.search_edit.blockSignals(False)

        cached = self.mail_cache.load_folder(self.current_account.id, folder)
        if cached:
            self._all_messages = cached
            self._render_message_table()
            self.status_bar.showMessage(
                f"{len(cached)} en caché — sincronizando {folder}…"
            )
        else:
            self._all_messages = []
            self._render_message_table()
            self.status_bar.showMessage(f"Sincronizando {folder}…")

        self.sync_progress.setVisible(True)
        self.sync_progress.setValue(0)
        self.sync_progress.setMaximum(0)
        self.btn_cancel_sync.setVisible(True)

        worker = SyncFolderWorker(
            self.mail_service,
            self.current_account.id,
            folder,
            self.mail_cache,
        )
        worker.signals.batch_ready.connect(
            lambda payload, g=generation, f=folder: self._on_sync_batch(payload, g, f)
        )
        worker.signals.progress.connect(
            lambda done, total, g=generation, f=folder: self._on_sync_progress(
                done, total, g, f
            )
        )
        worker.signals.finished.connect(
            lambda result, g=generation, f=folder: self._on_sync_finished(
                result, g, f
            )
        )
        worker.signals.error.connect(
            lambda message, g=generation, f=folder: self._on_sync_error(message, g, f)
        )
        worker.start()
        self._sync_worker = worker
        self._workers.append(worker)

    def _cancel_message_fetch(self) -> None:
        """Cancela descargas de mensaje pendientes (p. ej. al cambiar de carpeta)."""
        self._pending_fetch_uid = None
        self._message_fetch_worker = None
        self._enhance_generation += 1
        self._detach_enhance_worker()
        self._explicit_image_load = False
        self._translate_generation += 1
        self._detach_translate_worker()

    def _cancel_sync(self) -> None:
        if self._sync_worker and self._sync_worker.isRunning():
            self._sync_worker.cancel()
        self._sync_worker = None
        self._sync_generation += 1
        self.sync_progress.setVisible(False)
        self.btn_cancel_sync.setVisible(False)

    def _sync_is_current(self, generation: int, folder: str) -> bool:
        return generation == self._sync_generation and folder == self._current_folder

    def _on_sync_batch(self, payload, generation: int, folder: str) -> None:
        if not self._sync_is_current(generation, folder):
            return
        _batch, done, total = payload
        self._sync_new_total = total
        if self.current_account:
            self._all_messages = self.mail_cache.load_folder(
                self.current_account.id, self._current_folder
            )
        self._on_sync_progress(done, total, generation, folder)
        if self._current_page == 0:
            self._render_message_table()

    def _on_sync_progress(
        self, done: int, total: int, generation: int, folder: str
    ) -> None:
        if not self._sync_is_current(generation, folder):
            return
        if total <= 0:
            self.sync_progress.setMaximum(0)
            self.sync_progress.setValue(0)
            self.sync_progress.setFormat("Comprobando mensajes nuevos…")
            self.status_bar.showMessage("Comprobando mensajes nuevos…")
            return
        self.sync_progress.setMaximum(total)
        self.sync_progress.setValue(done)
        self.sync_progress.setFormat(f"Nuevos mensajes… %v / %m")
        self.status_bar.showMessage(f"Descargando mensajes nuevos… {done} / {total}")

    def _on_sync_finished(
        self, result: tuple[list[MailSummary], list[MailSummary]], generation: int, folder: str
    ) -> None:
        if not self._sync_is_current(generation, folder):
            return
        messages, new_summaries = result
        self._sync_worker = None
        self.sync_progress.setVisible(False)
        self.btn_cancel_sync.setVisible(False)

        if (
            not messages
            and self.current_account
            and folder == self._current_folder
        ):
            cached = self.mail_cache.load_folder(self.current_account.id, folder)
            if cached:
                messages = cached

        self._all_messages = messages
        self._current_page = 0
        self._render_message_table()
        if new_summaries:
            detail = f" — {len(new_summaries)} nuevos"
            if self._prefs.notify_new_mail and self._tray:
                account_label = (
                    self.current_account.email if self.current_account else ""
                )
                title, body = format_new_mail_notification(
                    new_summaries, self._current_folder, account_label
                )
                self._tray.show_message(title, body, msecs=5000)
        else:
            detail = " — sin mensajes nuevos"
        self.status_bar.showMessage(
            f"Sincronización completa — {len(messages)} mensajes en {self._current_folder}{detail}"
        )
        self._sync_new_total = 0

    def _on_sync_error(
        self,
        message: str,
        generation: int | None = None,
        folder: str | None = None,
    ) -> None:
        if generation is not None and folder is not None:
            if not self._sync_is_current(generation, folder):
                return
        self._sync_worker = None
        self.sync_progress.setVisible(False)
        self.btn_cancel_sync.setVisible(False)
        self.status_bar.showMessage("Error de sincronización")
        if self.mail_service and self.current_account:
            try:
                self.mail_service.ensure_connected()
                self.mail_service.select_folder(self._current_folder)
            except Exception:
                pass
        QMessageBox.warning(self, "Error de sincronización", message)

    def _on_connect_error(self, message: str) -> None:
        self.setEnabled(True)
        self.status_bar.showMessage("Error de conexión")
        QMessageBox.critical(
            self,
            "Error de conexión",
            f"No se pudo conectar:\n\n{message}",
        )

    def _on_folder_tree_changed(self, current, _previous) -> None:
        if not current or not self.mail_service:
            return
        folder = selected_folder_path(self.folder_tree)
        if not folder or folder == self._current_folder:
            return
        self._start_folder_sync(folder)

    def _apply_list_filters(self) -> None:
        self._current_page = 0
        self._render_message_table()

    def _apply_category_filter(self, _text: str) -> None:
        """Aplica el filtro de categoría y vuelve a la primera página."""
        self._apply_list_filters()

    def _total_pages(self) -> int:
        total = len(self._filtered_messages())
        if total == 0:
            return 1
        page_size = self._page_size()
        return (total + page_size - 1) // page_size

    def _paginated_messages(self) -> list[MailSummary]:
        """Devuelve solo los mensajes de la página actual."""
        filtered = self._filtered_messages()
        page_size = self._page_size()
        start = self._current_page * page_size
        return filtered[start : start + page_size]

    def _prev_page(self) -> None:
        if self._current_page > 0:
            self._current_page -= 1
            self._render_message_table()

    def _next_page(self) -> None:
        if self._current_page < self._total_pages() - 1:
            self._current_page += 1
            self._render_message_table()

    def _update_pagination_controls(self, shown: int, total_filtered: int) -> None:
        pages = self._total_pages()
        self.page_label.setText(
            f"Página {self._current_page + 1} de {pages}  ({total_filtered} correos)"
        )
        self.btn_prev_page.setEnabled(self._current_page > 0)
        self.btn_next_page.setEnabled(self._current_page < pages - 1)
        self.btn_prev_page.setVisible(total_filtered > self._page_size())
        self.btn_next_page.setVisible(total_filtered > self._page_size())
        self.page_label.setVisible(total_filtered > self._page_size())

    def _sort_messages(self, messages: list[MailSummary]) -> list[MailSummary]:
        sort_map = {
            0: "date_desc",
            1: "date_asc",
            2: "sender",
            3: "subject",
        }
        sort_by = sort_map.get(self.sort_combo.currentIndex(), self._prefs.sort_by)

        def sort_date(summary: MailSummary) -> datetime:
            return normalize_mail_datetime(summary.date) or datetime.min

        if sort_by == "date_asc":
            return sorted(messages, key=sort_date)
        if sort_by == "sender":
            return sorted(messages, key=lambda m: (m.sender or "").lower())
        if sort_by == "subject":
            return sorted(messages, key=lambda m: (m.subject or "").lower())
        return sorted(messages, key=sort_date, reverse=True)

    def _apply_thread_view(self, messages: list[MailSummary]) -> list[MailSummary]:
        if not self._prefs.thread_view:
            return messages
        latest: dict[str, MailSummary] = {}
        for summary in messages:
            key = summary.thread_key or summary.uid
            existing = latest.get(key)
            summary_dt = normalize_mail_datetime(summary.date) or datetime.min
            existing_dt = (
                normalize_mail_datetime(existing.date) or datetime.min
                if existing
                else datetime.min
            )
            if not existing or summary_dt > existing_dt:
                latest[key] = summary
        return list(latest.values())

    def _filtered_messages(self) -> list[MailSummary]:
        """Filtra por categoría, búsqueda, no leídos y orden."""
        messages = list(self._all_messages)
        choice = self.category_filter.currentText()
        mapping = {
            "Normal": MailCategory.NORMAL,
            "Importante": MailCategory.IMPORTANT,
            "Spam": MailCategory.SPAM,
        }
        if choice in mapping:
            target = mapping[choice]
            messages = [m for m in messages if m.category == target]
        query = self.search_edit.text().strip().lower()
        if query:
            messages = [
                m
                for m in messages
                if query in (m.subject or "").lower()
                or query in (m.sender or "").lower()
            ]
        if self.unread_only_check.isChecked():
            messages = [m for m in messages if not m.seen]
        messages = self._apply_thread_view(messages)
        return self._sort_messages(messages)

    def _render_message_table(self) -> None:
        """Pinta la tabla con los mensajes de la página actual."""
        filtered = self._filtered_messages()
        if self._current_page >= self._total_pages():
            self._current_page = max(0, self._total_pages() - 1)
        messages = self._paginated_messages()
        self.message_table.blockSignals(True)
        self.message_table.setRowCount(0)
        self._message_uids: list[str] = []

        for summary in messages:
            row = self.message_table.rowCount()
            self.message_table.insertRow(row)
            self._message_uids.append(summary.uid)

            category_item = QTableWidgetItem(
                f"{summary.category.icon} {summary.category.label}"
            )
            sender_item = QTableWidgetItem(summary.sender)
            subject_item = QTableWidgetItem(summary.subject or "(Sin asunto)")
            if summary.has_attachments:
                subject_item.setText(f"📎 {subject_item.text()}")
            date_str = (
                summary.date.strftime("%d/%m/%Y %H:%M")
                if summary.date
                else ""
            )
            date_item = QTableWidgetItem(date_str)

            bg = QBrush(CATEGORY_COLORS.get(summary.category, QColor(255, 255, 255)))
            fg = QBrush(TEXT_COLOR)
            for item in (category_item, sender_item, subject_item, date_item):
                item.setBackground(bg)
                item.setForeground(fg)

            if not summary.seen:
                bold = _font_bold(self.message_table.font())
                sender_item.setFont(bold)
                subject_item.setFont(bold)

            self.message_table.setItem(row, 0, category_item)
            self.message_table.setItem(row, 1, sender_item)
            self.message_table.setItem(row, 2, subject_item)
            self.message_table.setItem(row, 3, date_item)

        self.message_table.clearSelection()
        self.message_table.blockSignals(False)
        self._update_pagination_controls(len(messages), len(filtered))

        counts = {
            MailCategory.NORMAL: sum(1 for m in self._all_messages if m.category == MailCategory.NORMAL),
            MailCategory.IMPORTANT: sum(1 for m in self._all_messages if m.category == MailCategory.IMPORTANT),
            MailCategory.SPAM: sum(1 for m in self._all_messages if m.category == MailCategory.SPAM),
        }
        self.status_bar.showMessage(
            f"Pág. {self._current_page + 1}/{self._total_pages()} — "
            f"{len(filtered)} correos — "
            f"★ {counts[MailCategory.IMPORTANT]} importantes, "
            f"⚠ {counts[MailCategory.SPAM]} spam — "
            f"doble clic para abrir"
        )

    def _mark_selected_category(self, category: MailCategory) -> None:
        """Aprende la categoría del remitente y actualiza la vista."""
        row = self.message_table.currentRow()
        if row < 0 or not hasattr(self, "_message_uids"):
            return

        uid = self._message_uids[row]
        summary = next((m for m in self._all_messages if m.uid == uid), None)
        if not summary:
            return

        create_rule = False
        if category in (MailCategory.SPAM, MailCategory.IMPORTANT):
            sender_email = extract_email_address(summary.sender)
            rules = self.settings.load_classification_rules()
            already = (
                sender_email in rules.spam_senders
                if category == MailCategory.SPAM
                else sender_email in rules.important_senders
            )
            if sender_email and not already:
                reply = QMessageBox.question(
                    self,
                    "Crear regla de remitente",
                    f"¿Crear regla para clasificar siempre los correos de\n"
                    f"{summary.sender}\ncomo «{category.label}»?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                create_rule = reply == QMessageBox.StandardButton.Yes
            else:
                create_rule = True
        elif category == MailCategory.NORMAL:
            create_rule = True

        if create_rule:
            self.settings.learn_sender_category(summary.sender, category.value)
            if self.mail_service:
                self.mail_service.update_classifier(self.settings.get_classifier())
            self._reclassify_by_sender(summary.sender)

        if self.mail_service:
            if category == MailCategory.IMPORTANT:
                self.mail_service.set_flagged(uid, True)
            elif category == MailCategory.NORMAL:
                self.mail_service.set_flagged(uid, False)

        summary.category = category
        if self.current_account:
            self.mail_cache.update_category(
                self.current_account.id,
                self._current_folder,
                uid,
                category,
            )
        self._render_message_table()
        if create_rule:
            detail = f" — regla guardada para {summary.sender}"
        else:
            detail = ""
        self.status_bar.showMessage(
            f"Clasificado como {category.label}{detail}"
        )

    def _reclassify_by_sender(self, sender: str) -> None:
        """Reclasifica en la carpeta actual los mensajes del mismo remitente."""
        if not self.mail_service:
            return
        classifier = self.settings.get_classifier()
        target = extract_email_address(sender)
        if not target:
            return
        changed = False
        for summary in self._all_messages:
            if extract_email_address(summary.sender) != target:
                continue
            new_cat = classifier.classify(
                folder=self._current_folder,
                subject=summary.subject,
                sender=summary.sender,
                flagged=summary.flagged,
            )
            if new_cat != summary.category:
                summary.category = new_cat
                changed = True
                if self.current_account:
                    self.mail_cache.update_category(
                        self.current_account.id,
                        self._current_folder,
                        summary.uid,
                        new_cat,
                    )
        if changed:
            self._render_message_table()

    def _on_fetch_error(self, message: str) -> None:
        if self._pending_fetch_uid is None:
            return
        self._pending_fetch_uid = None
        self.subject_label.setText("Selecciona un mensaje")
        self.meta_label.setText("")
        self.message_viewer.show_plain("")
        self.attachment_panel.clear()
        self.status_bar.showMessage("Error al cargar el mensaje")
        QMessageBox.warning(self, "Error al abrir mensaje", message)

    def _open_selected_message(self) -> None:
        """Abre el mensaje seleccionado (doble clic, Enter o menú contextual)."""
        row = self.message_table.currentRow()
        if row < 0 or not hasattr(self, "_message_uids"):
            return
        self._on_message_double_clicked(row, 0)

    def _on_message_double_clicked(self, row: int, _col: int) -> None:
        if row < 0 or not self.mail_service or not hasattr(self, "_message_uids"):
            return
        if row >= len(self._message_uids):
            return
        uid = self._message_uids[row]
        force = bool(
            self._current_message
            and self._current_message.uid == uid
            and self._message_body_is_empty(self._current_message)
        )
        if (
            not force
            and self._current_message
            and self._current_message.uid == uid
            and not self._message_body_is_empty(self._current_message)
        ):
            return
        self._fetch_selected_message(force=force)

    def _fetch_selected_message(self, *, force: bool = False) -> None:
        """Descarga y muestra el mensaje de la fila seleccionada."""
        row = self.message_table.currentRow()
        if row < 0 or not self.mail_service or not hasattr(self, "_message_uids"):
            return
        if row >= len(self._message_uids):
            return
        uid = self._message_uids[row]
        if not force and self._message_loaded_for_selection():
            return

        self._pending_fetch_uid = uid
        self._update_message_actions()
        self.subject_label.setText("Cargando…")
        self.meta_label.setText("")
        self.message_viewer.show_plain("Cargando mensaje…")
        self.attachment_panel.clear()

        if self._message_fetch_worker and self._message_fetch_worker.isRunning():
            try:
                self._message_fetch_worker.signals.finished.disconnect()
                self._message_fetch_worker.signals.error.disconnect()
            except (RuntimeError, TypeError):
                pass

        worker = FetchMessageWorker(
            self.mail_service,
            uid,
            self.mail_cache,
            self.current_account.id if self.current_account else "",
            self._current_folder,
            delete_after_download=self._prefs.delete_from_server_after_download,
            refresh_from_server=force,
        )
        worker.signals.finished.connect(self._display_message)
        worker.signals.error.connect(self._on_fetch_error)
        worker.start()
        self._message_fetch_worker = worker
        self._workers.append(worker)

    def _prefetch_message(self, uid: str) -> None:
        """Precarga en caché el siguiente mensaje de la lista."""
        if not self.mail_cache or not self.current_account:
            return
        if self.mail_cache.load_message_body(
            self.current_account.id, self._current_folder, uid
        ):
            return
        worker = FetchMessageWorker(
            self.mail_service,
            uid,
            self.mail_cache,
            self.current_account.id,
            self._current_folder,
            mark_seen=False,
        )
        worker.signals.error.connect(lambda _msg: None)
        worker.start()
        self._workers.append(worker)

    def _on_viewer_link_hover(self, url: str) -> None:
        if url:
            if not hasattr(self, "_status_before_link_hover"):
                self._status_before_link_hover = self.status_bar.currentMessage()
            self.status_bar.showMessage(url)
        elif hasattr(self, "_status_before_link_hover"):
            self.status_bar.showMessage(self._status_before_link_hover)
            del self._status_before_link_hover

    def _display_message(self, message: MailMessage) -> None:
        if getattr(self, "_pending_fetch_uid", None) != message.uid:
            return
        if message.uid not in getattr(self, "_message_uids", []):
            return

        self._enhance_generation += 1
        self._detach_enhance_worker()
        self._explicit_image_load = False
        self._translate_generation += 1
        self._detach_translate_worker()

        self._pending_fetch_uid = None
        self._current_message = message
        self._original_subject = message.subject
        self._update_message_actions()
        summary = _selected_summary(message.uid, self._all_messages)
        deleted_from_server = self._prefs.delete_from_server_after_download
        if summary and not deleted_from_server:
            if message.attachments:
                summary.has_attachments = True
            if not summary.seen:
                summary.seen = True
                if self.current_account:
                    self.mail_cache.update_seen(
                        self.current_account.id, self._current_folder, message.uid, True
                    )
                    if self.mail_service:
                        seen_worker = SetSeenWorker(
                            self.mail_service,
                            message.uid,
                            True,
                            self.mail_cache,
                            self.current_account.id,
                            self._current_folder,
                        )
                        seen_worker.start()
                        self._workers.append(seen_worker)
        elif deleted_from_server:
            self._all_messages = [
                m for m in self._all_messages if m.uid != message.uid
            ]
            self._render_message_table()

        self.subject_label.setText(message.subject)
        date_str = (
            message.date.strftime("%d/%m/%Y %H:%M") if message.date else ""
        )
        self.meta_label.setText(
            f"De: {message.sender}\n"
            f"Para: {message.recipients}\n"
            f"Categoría: {message.category.icon} {message.category.label}\n"
            f"{date_str}"
        )

        self.attachment_panel.set_attachments(message.attachments)
        from pyqorreos.core.email_html import html_to_plain_text

        plain = message.body_text or html_to_plain_text(message.body_html)
        self.message_viewer.set_plain_fallback(plain)

        if message.body_html:
            from pyqorreos.core.email_html import base_url_for_message

            base = base_url_for_message(message.sender)
            blocked = self._prefs.block_remote_images
            self.message_viewer.show_html(
                message.body_html, base, remote_blocked=blocked
            )
            if not blocked:
                self._start_html_enhance(message)
        else:
            self.message_viewer.show_plain(message.body_text or "(Mensaje vacío)")

        self._update_translate_button()

        row = self.message_table.currentRow()
        if row >= 0:
            normal = _font_normal(self.message_table.font())
            for col in range(4):
                item = self.message_table.item(row, col)
                if item:
                    item.setFont(normal)
            if row + 1 < len(self._message_uids):
                self._prefetch_message(self._message_uids[row + 1])

    def _start_html_enhance(self, message: MailMessage) -> None:
        """Descarga imágenes remotas en segundo plano sin bloquear la apertura."""
        if self._prefs.block_remote_images:
            return
        if (
            self._enhance_worker
            and self._enhance_worker.isRunning()
            and self._pending_enhance_uid == message.uid
        ):
            return
        self._detach_enhance_worker()
        generation = self._enhance_generation
        self._pending_enhance_uid = message.uid
        worker = EnhanceHtmlWorker(
            self.mail_service,
            message.uid,
            message.body_html,
            self._current_folder,
        )
        worker.signals.finished.connect(
            lambda payload, g=generation: self._on_html_enhanced(payload, g)
        )
        worker.start()
        self._enhance_worker = worker
        self._workers.append(worker)

    def _load_remote_images_for_current(self) -> None:
        if not self._current_message or not self._current_message.body_html:
            return
        uid = self._current_message.uid
        if (
            self._enhance_worker
            and self._enhance_worker.isRunning()
            and self._pending_enhance_uid == uid
        ):
            self.status_bar.showMessage("Cargando imágenes remotas…")
            return
        self._detach_enhance_worker()
        self._explicit_image_load = True
        generation = self._enhance_generation
        self._pending_enhance_uid = uid
        self.status_bar.showMessage("Cargando imágenes remotas…")
        worker = EnhanceHtmlWorker(
            self.mail_service,
            uid,
            self._current_message.body_html,
            self._current_folder,
        )
        worker.signals.finished.connect(
            lambda payload, g=generation: self._on_html_enhanced(payload, g)
        )
        worker.signals.error.connect(
            lambda message, g=generation: self._on_enhance_error(message, g)
        )
        worker.start()
        self._enhance_worker = worker
        self._workers.append(worker)

    def _on_enhance_error(self, message: str, generation: int | None = None) -> None:
        if generation is not None and generation != self._enhance_generation:
            return
        self._pending_enhance_uid = None
        self._explicit_image_load = False
        self.status_bar.showMessage("No se pudieron cargar las imágenes remotas")
        QMessageBox.warning(self, "Imágenes remotas", message)

    def _message_body_for_translation(self, message: MailMessage) -> str:
        from pyqorreos.core.email_html import html_to_plain_text
        from pyqorreos.core.translate import normalize_translation_source

        plain = (message.body_text or "").strip()
        if plain in ("", "(Sin contenido)", "(Mensaje vacío)"):
            plain = html_to_plain_text(message.body_html)
        return normalize_translation_source(plain)

    def _update_translate_button(self) -> None:
        if not self._current_message:
            self.message_viewer.set_translate_available(False)
            return
        body = self._message_body_for_translation(self._current_message)
        self.message_viewer.set_translate_available(bool(body))

    def _on_translate_requested(self) -> None:
        if self.message_viewer.is_showing_translation():
            self._restore_original_message_view()
            return
        if not self._current_message:
            return
        body = self._message_body_for_translation(self._current_message)
        if not body:
            self.status_bar.showMessage("No hay texto que traducir en este mensaje")
            return

        uid = self._current_message.uid
        target = self._prefs.translate_target_language
        cached = self._translation_cache.get((uid, target))
        if cached and cached.get("body"):
            self._apply_translation(cached["body"], cached.get("subject", ""))
            return

        if (
            self._translate_worker
            and self._translate_worker.isRunning()
            and self._pending_translate_uid == uid
        ):
            self.status_bar.showMessage(
                f"Traduciendo al {language_label(target)}…"
            )
            return

        self._detach_translate_worker()
        generation = self._translate_generation
        self._pending_translate_uid = uid
        lang_label = language_label(target)
        self.status_bar.showMessage(f"Traduciendo al {lang_label}…")
        worker = TranslateMessageWorker(
            uid,
            body,
            self._current_message.subject,
            target,
        )
        worker.signals.finished.connect(
            lambda payload, g=generation: self._on_message_translated(payload, g)
        )
        worker.signals.error.connect(
            lambda message, g=generation: self._on_translate_error(message, g)
        )
        worker.start()
        self._translate_worker = worker
        self._workers.append(worker)

    def _apply_translation(self, body: str, subject: str) -> None:
        if not self._current_message:
            return
        target = self._prefs.translate_target_language
        lang_label = language_label(target)
        self.message_viewer.show_translated(body, language_label=lang_label)
        if subject:
            self.subject_label.setText(subject)
        self.status_bar.showMessage(f"Mensaje traducido al {lang_label}")

    def _restore_original_message_view(self) -> None:
        if self._original_subject:
            self.subject_label.setText(self._original_subject)
        self.message_viewer.restore_from_stored()
        self.status_bar.showMessage("Mostrando mensaje original")

    def _on_message_translated(self, payload, generation: int | None = None) -> None:
        uid, target_lang, body, subject = payload
        if generation is not None and generation != self._translate_generation:
            return
        if self._pending_translate_uid != uid:
            return
        if not self._current_message or self._current_message.uid != uid:
            return
        self._pending_translate_uid = None
        self._translation_cache[(uid, target_lang)] = {
            "body": body,
            "subject": subject,
        }
        if target_lang != self._prefs.translate_target_language:
            return
        self._apply_translation(body, subject)

    def _on_translate_error(self, message: str, generation: int | None = None) -> None:
        if generation is not None and generation != self._translate_generation:
            return
        self._pending_translate_uid = None
        self.status_bar.showMessage("No se pudo traducir el mensaje")
        QMessageBox.warning(self, "Traducción", message)

    def _save_attachment(self, part_index: int) -> None:
        uid = self._selected_message_uid()
        if not uid or not self.mail_service or not self._current_message:
            return
        att = next(
            (a for a in (self._current_message.attachments or []) if a.part_index == part_index),
            None,
        )
        default_name = att.filename if att else "adjunto"
        path = self.attachment_panel.prompt_save_path(default_name)
        if not path:
            return
        worker = FetchAttachmentWorker(
            self.mail_service, uid, part_index, self._current_folder
        )
        worker.signals.finished.connect(
            lambda payload, p=path: self._on_attachment_saved(p, payload)
        )
        worker.signals.error.connect(self._on_fetch_error)
        worker.start()
        self._workers.append(worker)

    def _on_attachment_saved(self, path: str, payload) -> None:
        filename, data = payload
        Path(path).write_bytes(data)
        self.status_bar.showMessage(f"Adjunto guardado: {path}")

    def _open_attachment(self, part_index: int) -> None:
        uid = self._selected_message_uid()
        if not uid or not self.mail_service:
            return
        worker = FetchAttachmentWorker(
            self.mail_service, uid, part_index, self._current_folder
        )
        worker.signals.finished.connect(self._on_attachment_open)
        worker.signals.error.connect(self._on_fetch_error)
        worker.start()
        self._workers.append(worker)

    def _on_attachment_open(self, payload) -> None:
        filename, data = payload
        suffix = Path(filename).suffix or ".bin"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            subprocess.Popen(["xdg-open", tmp_path])
        except OSError:
            QMessageBox.information(self, "Adjunto", f"Guardado en: {tmp_path}")

    def _create_subfolder(self) -> None:
        parent = selected_folder_path(self.folder_tree)
        if not parent:
            QMessageBox.information(
                self,
                "Sin carpeta",
                "Selecciona la carpeta padre en el árbol antes de crear una subcarpeta.",
            )
            return
        self._create_folder(parent)

    def _create_folder(self, parent: str | None = None) -> None:
        if not self.mail_service:
            QMessageBox.information(
                self,
                "Sin conexión",
                "Conecta una cuenta antes de crear carpetas.",
            )
            return
        title = "Nueva subcarpeta" if parent else "Nueva carpeta"
        prompt = (
            f"Nombre de la subcarpeta dentro de «{parent}»:"
            if parent
            else "Nombre de la carpeta:"
        )
        name, ok = QInputDialog.getText(self, title, prompt)
        if not ok:
            return
        name = name.strip()
        if not name:
            QMessageBox.warning(self, title, "Indica un nombre para la carpeta.")
            return
        self.status_bar.showMessage(f"Creando carpeta «{name}»…")
        worker = CreateFolderWorker(self.mail_service, name, parent)
        worker.signals.finished.connect(self._on_folder_created)
        worker.signals.error.connect(self._on_folder_create_error)
        worker.start()
        self._workers.append(worker)

    def _on_folder_created(self, payload) -> None:
        created_path, folders = payload
        self._folder_names = folders
        self._refresh_folder_tree(select_folder=created_path)
        self._refresh_folder_unread_counts()
        self.status_bar.showMessage(f"Carpeta creada: {created_path}")

    def _on_folder_create_error(self, message: str) -> None:
        self.status_bar.showMessage("Error al crear carpeta")
        QMessageBox.warning(self, "Error al crear carpeta", message)

    def _show_move_messages_dialog(self) -> None:
        uids = self._selected_message_uids()
        if not uids:
            QMessageBox.information(
                self,
                "Mover mensajes",
                "Selecciona uno o más mensajes en la lista.",
            )
            return
        if not self.mail_service or not self.current_account:
            return
        dest = self._pick_destination_folder()
        if dest:
            self._move_selected_messages(dest)

    def _pick_destination_folder(self) -> str | None:
        options = sorted(
            f for f in self._folder_names if f != self._current_folder
        )
        if not options:
            QMessageBox.information(
                self,
                "Mover mensajes",
                "No hay otras carpetas disponibles.",
            )
            return None
        uids = self._selected_message_uids()
        label = (
            f"Mover {len(uids)} mensaje(s) a:"
            if len(uids) != 1
            else "Mover mensaje a:"
        )
        dest, ok = QInputDialog.getItem(
            self,
            "Mover a carpeta",
            label,
            options,
            0,
            False,
        )
        return dest if ok and dest else None

    def _move_selected_messages(self, dest_folder: str) -> None:
        uids = self._selected_message_uids()
        if not uids or not self.mail_service or not self.current_account:
            return
        worker = MoveMessagesWorker(
            self.mail_service,
            uids,
            dest_folder,
            self.mail_cache,
            self.current_account.id,
            self._current_folder,
        )
        worker.signals.finished.connect(self._on_messages_moved)
        worker.signals.error.connect(self._on_move_error)
        worker.start()
        self._workers.append(worker)

    def _on_messages_moved(self, payload) -> None:
        uids, dest = payload
        moved = set(uids)
        self._all_messages = [m for m in self._all_messages if m.uid not in moved]
        self._current_message = None
        self._set_message_actions_enabled(False)
        self.subject_label.setText("Selecciona un mensaje")
        self.meta_label.setText("")
        self.message_viewer.clear()
        self.attachment_panel.clear()
        self._render_message_table()
        self.status_bar.showMessage(f"{len(uids)} mensaje(s) movidos a {dest}")

    def _on_move_error(self, message: str) -> None:
        self.status_bar.showMessage("Error al mover mensajes")
        QMessageBox.warning(self, "Error al mover", message)

    def _on_html_enhanced(self, payload, generation: int | None = None) -> None:
        uid, html = payload
        if generation is not None and generation != self._enhance_generation:
            return
        if self._pending_enhance_uid != uid:
            return
        if not self._current_message or self._current_message.uid != uid:
            return
        self._pending_enhance_uid = None
        explicit = self._explicit_image_load
        self._explicit_image_load = False
        from pyqorreos.core.email_html import (
            BLOCKED_IMAGE_PLACEHOLDER_MARKER,
            base_url_for_message,
        )

        if html == self._current_message.body_html and not explicit:
            if BLOCKED_IMAGE_PLACEHOLDER_MARKER in html:
                self.status_bar.showMessage(
                    "No se pudieron descargar algunas imágenes remotas"
                )
            else:
                self.status_bar.showMessage(
                    "No hay imágenes remotas pendientes de cargar"
                )
            return
        if html == self._current_message.body_html and BLOCKED_IMAGE_PLACEHOLDER_MARKER in html:
            self.status_bar.showMessage(
                "No se pudieron descargar algunas imágenes remotas"
            )
            return

        self._current_message = MailMessage(
            uid=self._current_message.uid,
            subject=self._current_message.subject,
            sender=self._current_message.sender,
            recipients=self._current_message.recipients,
            date=self._current_message.date,
            body_text=self._current_message.body_text,
            body_html=html,
            category=self._current_message.category,
            attachments=self._current_message.attachments,
            message_id=self._current_message.message_id,
            in_reply_to=self._current_message.in_reply_to,
            references=self._current_message.references,
            unsubscribe_url=self._current_message.unsubscribe_url,
            unsubscribe_mailto=self._current_message.unsubscribe_mailto,
            one_click_unsubscribe=self._current_message.one_click_unsubscribe,
        )
        if self.current_account:
            self.mail_cache.save_message_body(
                self.current_account.id, self._current_folder, self._current_message
            )
        base = base_url_for_message(self._current_message.sender)
        self.message_viewer.show_html(html, base, remote_blocked=False)
        self.status_bar.showMessage("Imágenes remotas cargadas")

    def _mark_selected_seen(self, seen: bool) -> None:
        uid = self._selected_message_uid()
        if not uid or not self.mail_service or not self.current_account:
            return
        worker = SetSeenWorker(
            self.mail_service,
            uid,
            seen,
            self.mail_cache,
            self.current_account.id,
            self._current_folder,
        )
        worker.signals.finished.connect(self._on_seen_changed)
        worker.signals.error.connect(self._on_fetch_error)
        worker.start()
        self._workers.append(worker)

    def _on_seen_changed(self, payload) -> None:
        uid, seen = payload
        summary = _selected_summary(uid, self._all_messages)
        if summary:
            summary.seen = seen
        self._render_message_table()
        state = "leído" if seen else "no leído"
        self.status_bar.showMessage(f"Mensaje marcado como {state}")

    def _copy_sender_address(self) -> None:
        uid = self._selected_message_uid()
        summary = _selected_summary(uid, self._all_messages)
        if not summary:
            return
        addr = _sender_address(summary.sender)
        if not addr:
            QMessageBox.information(
                self, "Sin dirección", "No se pudo extraer la dirección del remitente."
            )
            return
        QApplication.clipboard().setText(addr)
        self.status_bar.showMessage(f"Dirección copiada: {addr}")

    @staticmethod
    def _format_bytes(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        if size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        return f"{size / (1024 * 1024 * 1024):.2f} GB"

    def _refresh_storage_quota(self) -> None:
        if not self.mail_service:
            self.quota_bar.setVisible(False)
            self.quota_label.setVisible(False)
            return
        worker = StorageQuotaWorker(self.mail_service)
        worker.signals.finished.connect(self._on_storage_quota)
        worker.signals.error.connect(lambda _m: self._hide_storage_quota())
        worker.start()
        self._workers.append(worker)

    def _hide_storage_quota(self) -> None:
        self.quota_bar.setVisible(False)
        self.quota_label.setVisible(False)

    def _on_storage_quota(self, quota) -> None:
        if not quota:
            self._hide_storage_quota()
            return
        used, limit = quota
        if limit <= 0:
            self._hide_storage_quota()
            return
        percent = min(100, max(0, int(used * 100 / limit)))
        self.quota_bar.setValue(percent)
        self.quota_bar.setVisible(True)
        self.quota_label.setText(
            f"Espacio: {self._format_bytes(used)} de {self._format_bytes(limit)}"
        )
        self.quota_label.setVisible(True)

    def _unsubscribe_current_message(self) -> None:
        if not self._message_loaded_for_selection() or not self._current_message:
            return
        if not self.mail_service or not self.current_account:
            return
        msg = self._current_message
        trash = find_trash_folder(self._folder_names)
        if not trash:
            QMessageBox.warning(
                self,
                "Sin papelera",
                "No se encontró carpeta de papelera en el servidor.",
            )
            return
        reply = QMessageBox.question(
            self,
            "Darse de baja",
            "Se enviará la solicitud de baja al remitente y el mensaje "
            f"se moverá a «{trash}».\n\n¿Continuar?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.status_bar.showMessage("Procesando baja del boletín…")
        worker = UnsubscribeWorker(
            self.mail_service,
            msg.uid,
            self._current_folder,
            trash,
            url=msg.unsubscribe_url,
            mailto=msg.unsubscribe_mailto,
            one_click=msg.one_click_unsubscribe,
            cache=self.mail_cache,
            account_id=self.current_account.id,
        )
        worker.signals.finished.connect(self._on_unsubscribed)
        worker.signals.error.connect(
            lambda m: QMessageBox.warning(self, "Error de baja", m)
        )
        worker.start()
        self._workers.append(worker)

    def _on_unsubscribed(self, message: str) -> None:
        if self._current_message:
            uid = self._current_message.uid
            self._all_messages = [m for m in self._all_messages if m.uid != uid]
            self._current_message = None
            self._render_message_table()
            self.subject_label.setText("Selecciona un mensaje")
            self.meta_label.setText("")
            self.message_viewer.clear()
            self.attachment_panel.clear()
        self.status_bar.showMessage(message)
        QMessageBox.information(self, "Baja realizada", message)

    def _export_selected_eml(self) -> None:
        uid = self._selected_message_uid()
        if not uid or not self.mail_service:
            QMessageBox.information(self, "Exportar", "Selecciona un mensaje.")
            return
        default_name = f"mensaje_{uid}.eml"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar correo",
            default_name,
            "Correo electrónico (*.eml)",
        )
        if not path:
            return
        if not path.lower().endswith(".eml"):
            path += ".eml"
        self.status_bar.showMessage("Exportando mensaje…")
        worker = ExportMessageWorker(
            self.mail_service, uid, self._current_folder, path
        )
        worker.signals.finished.connect(
            lambda p: self.status_bar.showMessage(f"Exportado: {p}")
        )
        worker.signals.error.connect(
            lambda m: QMessageBox.warning(self, "Error al exportar", m)
        )
        worker.start()
        self._workers.append(worker)

    def _export_current_folder_mbox(self) -> None:
        if not self.mail_service or not self.current_account:
            QMessageBox.information(self, "Exportar", "Conecta una cuenta primero.")
            return
        uids = [m.uid for m in self._all_messages]
        if not uids:
            QMessageBox.information(self, "Exportar", "No hay mensajes en esta carpeta.")
            return
        safe_folder = self._current_folder.replace("/", "_")
        default_name = f"{safe_folder}.mbox"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar carpeta",
            default_name,
            "Mailbox (*.mbox)",
        )
        if not path:
            return
        if not path.lower().endswith(".mbox"):
            path += ".mbox"
        reply = QMessageBox.question(
            self,
            "Exportar carpeta",
            f"Se exportarán {len(uids)} mensajes de «{self._current_folder}».\n"
            "Puede tardar varios minutos.\n\n¿Continuar?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.status_bar.showMessage(f"Exportando {len(uids)} mensajes…")
        worker = ExportFolderWorker(
            self.mail_service,
            self.current_account.id,
            self._current_folder,
            uids,
            path,
            self.mail_cache,
        )
        worker.signals.finished.connect(self._on_folder_exported)
        worker.signals.error.connect(
            lambda m: QMessageBox.warning(self, "Error al exportar", m)
        )
        worker.start()
        self._workers.append(worker)

    def _on_folder_exported(self, payload) -> None:
        path, count = payload
        self.status_bar.showMessage(f"Exportados {count} mensajes a {path}")
        QMessageBox.information(
            self,
            "Exportación completa",
            f"Se guardaron {count} mensajes en:\n{path}",
        )

    def _refresh(self) -> None:
        folder = selected_folder_path(self.folder_tree)
        if folder and self.mail_service:
            self._start_folder_sync(folder)
        elif self.current_account:
            self._connect_account(self.current_account)

    def _compose(self, draft: ComposeDraft | None = None, title: str = "Redactar correo") -> None:
        if not self.mail_service:
            QMessageBox.information(
                self, "Sin conexión", "Conecta una cuenta antes de redactar."
            )
            return
        dialog = ComposeDialog(
            self.mail_service,
            parent=self,
            draft=draft,
            title=title,
            signature=self.current_account.signature if self.current_account else "",
            drafts_folder=find_drafts_folder(self._folder_names),
            snippets=self._prefs.compose_snippets,
        )
        dialog.exec()

    def _reply(self) -> None:
        if not self._message_loaded_for_selection() or not self.current_account:
            QMessageBox.information(
                self,
                "Mensaje no cargado",
                "Espera a que termine de cargar el mensaje antes de responder.",
            )
            return
        draft = build_reply(
            self._current_message,
            self.current_account.email,
            reply_all=False,
        )
        self._compose(draft, "Responder")

    def _reply_all(self) -> None:
        if not self._message_loaded_for_selection() or not self.current_account:
            QMessageBox.information(
                self,
                "Mensaje no cargado",
                "Espera a que termine de cargar el mensaje antes de responder.",
            )
            return
        draft = build_reply(
            self._current_message,
            self.current_account.email,
            reply_all=True,
        )
        self._compose(draft, "Responder a todos")

    def _forward(self) -> None:
        if not self._message_loaded_for_selection():
            QMessageBox.information(
                self,
                "Mensaje no cargado",
                "Espera a que termine de cargar el mensaje antes de reenviar.",
            )
            return
        draft = build_forward(self._current_message)
        self._compose(draft, "Reenviar")

    def _delete_message(self) -> None:
        uids = self._selected_message_uids()
        if not uids or not self.mail_service:
            return

        label = "este mensaje" if len(uids) == 1 else f"{len(uids)} mensajes"
        reply = QMessageBox.question(
            self,
            "Eliminar",
            f"¿Eliminar {label}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if len(uids) == 1:
            worker = DeleteMessageWorker(
                self.mail_service,
                uids[0],
                self.mail_cache,
                self.current_account.id if self.current_account else "",
                self._current_folder,
            )
            worker.signals.finished.connect(self._on_message_deleted)
        else:
            worker = DeleteMessagesWorker(
                self.mail_service,
                uids,
                self.mail_cache,
                self.current_account.id if self.current_account else "",
                self._current_folder,
            )
            worker.signals.finished.connect(self._on_messages_deleted)
        worker.signals.error.connect(self._on_delete_error)
        worker.start()
        self._workers.append(worker)

    def _on_delete_error(self, message: str) -> None:
        self.status_bar.showMessage("Error al eliminar mensajes")
        QMessageBox.warning(self, "Eliminar mensajes", message)

    def _on_message_deleted(self, uid: str) -> None:
        self._on_messages_deleted([uid])

    def _on_messages_deleted(self, uids: list[str]) -> None:
        removed = set(uids)
        self._all_messages = [m for m in self._all_messages if m.uid not in removed]
        if self._current_message and self._current_message.uid in removed:
            self._current_message = None
            self._set_message_actions_enabled(False)
            self.subject_label.setText("Selecciona un mensaje")
            self.meta_label.setText("")
            self.message_viewer.clear()
            self.attachment_panel.clear()
        self._render_message_table()
        self._refresh_folder_unread_counts()
        self.status_bar.showMessage(f"{len(uids)} mensaje(s) eliminado(s)")

    def closeEvent(self, event) -> None:
        self._cancel_sync()
        if self._quitting:
            self._background_sync.stop()
            if self.mail_service:
                self.mail_service.disconnect()
            if self._tray:
                self._tray.hide()
            event.accept()
            return

        # Cerrar la ventana minimiza a la bandeja; Salir cierra del todo.
        event.ignore()
        self.hide()
        if self._tray:
            self._tray.show_message(
                "PyQorreos",
                "La aplicación sigue activa en la bandeja del sistema.",
            )


def run_app() -> None:
    """Crea la aplicación Qt y muestra la ventana principal."""
    import sys

    from pyqorreos.ui.webengine_setup import configure_webengine_environment

    configure_webengine_environment()
    app = QApplication(sys.argv)
    app.setApplicationName("PyQorreos")
    app.setStyle("Fusion")
    # Mantener la app viva en la bandeja al ocultar la ventana principal.
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
