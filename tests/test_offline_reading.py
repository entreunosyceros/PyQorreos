"""Lectura y actualización sin sesión IMAP activa."""

from __future__ import annotations

import os
from datetime import datetime
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pyqorreos.core.mail_service import MailMessage, MailSummary  # noqa: E402
from pyqorreos.ui.main_window import MainWindow  # noqa: E402


class _Label:
    def __init__(self) -> None:
        self.text = ""

    def setText(self, value: str) -> None:
        self.text = value


class _StatusBar:
    def __init__(self) -> None:
        self.message = ""

    def showMessage(self, message: str, *_args) -> None:
        self.message = message


class _Viewer:
    def __init__(self) -> None:
        self.plain = ""

    def show_plain(self, text: str) -> None:
        self.plain = text

    def clear(self) -> None:
        self.plain = ""

    def prepare_for_new_message(self) -> None:
        pass


class _Panel:
    def clear(self) -> None:
        pass


class _FolderTree:
    """Árbol de carpetas sin selección activa."""

    def currentItem(self):
        return None


def _summary(uid: str) -> MailSummary:
    return MailSummary(
        uid=uid,
        subject=f"Asunto {uid}",
        sender="alguien@example.com",
        date=datetime(2026, 7, 1, 12, 0),
        seen=False,
        flagged=False,
    )


def _offline_window(cached_body: MailMessage | None) -> MainWindow:
    window = MainWindow.__new__(MainWindow)
    window.mail_service = None
    window.current_account = SimpleNamespace(id="acc-1", email="yo@example.com")
    window.mail_cache = SimpleNamespace(
        load_message_body=lambda *_args, **_kwargs: cached_body
    )
    window._all_messages = [_summary("10")]
    window._message_uids = ["10"]
    window._fetch_generation = 3
    window._pending_fetch_uid = "10"
    window._current_message = None
    window.subject_label = _Label()
    window.meta_label = _Label()
    window.message_viewer = _Viewer()
    window.attachment_panel = _Panel()
    window.status_bar = _StatusBar()
    window._update_message_actions = lambda: None
    return window


def test_offline_double_click_shows_cached_body() -> None:
    """Sin conexión, abrir un mensaje muestra la copia guardada en la caché."""
    cached = MailMessage(
        uid="10",
        subject="Asunto 10",
        sender="alguien@example.com",
        recipients="yo@example.com",
        date=datetime(2026, 7, 1, 12, 0),
        body_text="Contenido guardado",
        body_html="",
    )
    window = _offline_window(cached)
    shown: list[MailMessage] = []
    window._display_message = lambda message, _gen=None: shown.append(message)

    window._display_offline_message("10", "INBOX", 3)

    assert shown == [cached]
    assert "copia guardada" in window.status_bar.message


def test_offline_double_click_without_cache_explains_why() -> None:
    """Si el cuerpo no está en caché se avisa en vez de dejar la vista vacía."""
    window = _offline_window(None)

    window._display_offline_message("10", "INBOX", 3)

    assert window._pending_fetch_uid is None
    assert window.subject_label.text == "Asunto 10"
    assert "no está descargado" in window.message_viewer.plain
    assert "caché local" in window.status_bar.message


def test_refresh_without_service_reconnects_and_queues_sync() -> None:
    """«Actualizar» sin sesión IMAP reconecta y deja pendiente la sincronización."""
    window = MainWindow.__new__(MainWindow)
    window.mail_service = None
    window.current_account = SimpleNamespace(id="acc-1", email="yo@example.com")
    window.folder_tree = _FolderTree()
    window._current_folder = "INBOX"
    window._pending_manual_refresh = False
    window._connection_status = "error"
    window.status_bar = _StatusBar()
    calls: list[dict] = []
    window._connect_account = lambda account, **kwargs: calls.append(
        {"account": account, **kwargs}
    )

    window._refresh()

    assert window._pending_manual_refresh is True
    assert calls and calls[0]["preload_cache"] is False
    assert "Reconectando" in window.status_bar.message


def test_refresh_with_service_forces_fresh_mailbox() -> None:
    """Con sesión activa, «Actualizar» pide una lectura fresca del buzón."""
    window = MainWindow.__new__(MainWindow)
    window.mail_service = object()
    window.current_account = SimpleNamespace(id="acc-1", email="yo@example.com")
    window.folder_tree = _FolderTree()
    window._current_folder = "INBOX"
    window._pending_manual_refresh = False
    window._refresh_folder_tree = lambda **_kwargs: None
    syncs: list[tuple[str, bool]] = []
    window._start_folder_sync = lambda folder, *, manual_refresh=False: syncs.append(
        (folder, manual_refresh)
    )

    window._refresh()

    assert syncs == [("INBOX", True)]


def test_refresh_while_connecting_does_not_restart_the_attempt() -> None:
    """Pulsar «Actualizar» durante la conexión no reinicia el intento en curso."""
    window = MainWindow.__new__(MainWindow)
    window.mail_service = None
    window.current_account = SimpleNamespace(id="acc-1", email="yo@example.com")
    window.folder_tree = _FolderTree()
    window._current_folder = "INBOX"
    window._pending_manual_refresh = False
    window._connection_status = "connecting"
    window.status_bar = _StatusBar()
    calls: list[object] = []
    window._connect_account = lambda account, **_kwargs: calls.append(account)

    window._refresh()

    assert calls == []
    assert window._pending_manual_refresh is True


@pytest.mark.parametrize("folder", ["INBOX", "INBOX.Archive"])
def test_folder_sync_offline_skips_network(folder: str) -> None:
    """Cambiar de carpeta sin conexión carga la caché sin lanzar sincronización."""
    window = MainWindow.__new__(MainWindow)
    window.mail_service = None
    window.current_account = SimpleNamespace(id="acc-1", email="yo@example.com")
    window.settings = SimpleNamespace(set_last_folder=lambda *_a: None)
    window.mail_cache = SimpleNamespace(
        load_folder=lambda *_a: [],
        folder_count=lambda *_a: 5,
    )
    window._current_folder = "INBOX"
    window._current_page = 0
    window._all_messages = []
    window._current_message = None
    window._pending_fetch_uid = None
    window._manual_refresh_active = False
    window._sync_generation = 0
    window._load_folder_generation = 0
    window._load_folder_worker = None
    window.status_bar = _StatusBar()
    window.subject_label = _Label()
    window.meta_label = _Label()
    window.message_viewer = _Viewer()
    window.attachment_panel = _Panel()
    window.btn_cancel_sync = SimpleNamespace(setVisible=lambda _v: None)
    window.sync_progress = SimpleNamespace(
        setVisible=lambda _v: None,
        setRange=lambda *_a: None,
        setValue=lambda _v: None,
    )
    window._cancel_sync = lambda: None
    window._stop_load_folder_worker = lambda **_k: None
    window._cancel_message_fetch = lambda: None
    window._set_message_actions_enabled = lambda _v: None
    window._render_message_table = lambda: None
    window._update_connection_status = lambda _s: pytest.fail("no debe tocar la red")
    window._track_worker = lambda _w: None
    started: list[object] = []

    blockers = SimpleNamespace(
        blockSignals=lambda _v: None,
        clear=lambda: None,
        text=lambda: "",
        setChecked=lambda _v: None,
        isChecked=lambda: False,
    )
    window.search_edit = blockers
    window.search_body_check = blockers
    window.flag_filter_check = blockers

    import pyqorreos.ui.main_window as mw

    class _NoSync:
        def __init__(self, *_a, **_k) -> None:
            started.append(self)

    original = mw.SyncFolderWorker
    mw.SyncFolderWorker = _NoSync
    try:
        window._start_folder_sync(folder)
    finally:
        mw.SyncFolderWorker = original

    assert started == []
    assert window._current_folder == folder
    assert "Sin conexión" in window.status_bar.message
