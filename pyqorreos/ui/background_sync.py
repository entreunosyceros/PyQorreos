"""
Sincronización en segundo plano: IMAP IDLE y polling multi-cuenta.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from pyqorreos.core.account import MailAccount
from pyqorreos.core.mail_cache import MailCache
from pyqorreos.core.mail_service import MailService, MailSummary
from pyqorreos.core.user_preferences import UserPreferences, load_preferences


class BackgroundSyncSignals(QObject):
    new_mail = Signal(str, str, object)  # account_id, folder, list[MailSummary]
    folder_updated = Signal(str, str)  # account_id, folder
    error = Signal(str, str)  # account_id, message


class IdleMonitorThread(QThread):
    """Hilo que espera IMAP IDLE en INBOX de una cuenta."""

    activity_detected = Signal()

    def __init__(
        self,
        account: MailAccount,
        password: str,
        folder: str = "INBOX",
        timeout_sec: int = 300,
    ) -> None:
        super().__init__()
        self.account = account
        self.password = password
        self.folder = folder
        self.timeout_sec = timeout_sec
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        while not self._stop:
            service = MailService(self.account, self.password)
            try:
                service.connect()
                if service.wait_for_idle_updates(self.folder, self.timeout_sec):
                    self.activity_detected.emit()
                    self.msleep(500)
            except Exception:
                self.msleep(30_000)
            finally:
                service.disconnect()


class AccountSyncThread(QThread):
    """Sincroniza INBOX de una cuenta en background."""

    def __init__(
        self,
        account: MailAccount,
        password: str,
        folder: str,
        cache: MailCache,
        classifier,
    ) -> None:
        super().__init__()
        self.account = account
        self.password = password
        self.folder = folder
        self.cache = cache
        self.classifier = classifier
        self.new_summaries: list[MailSummary] = []

    def run(self) -> None:
        service = MailService(self.account, self.password, self.classifier)
        try:
            service.connect()
            service.select_folder(self.folder)
            cached = self.cache.load_folder(self.account.id, self.folder)
            cached_map = {s.uid: s for s in cached}
            initial_uids = set(cached_map.keys())

            def on_batch(batch: list[MailSummary], _done: int, _total: int) -> None:
                for summary in batch:
                    cached_map[summary.uid] = summary

            all_summaries = service.sync_folder_incremental(
                cached_map, on_batch=on_batch
            )
            removed = service.last_removed_uids
            if removed:
                self.cache.remove_uids(self.account.id, self.folder, removed)
            self.cache.save_folder_ordered(
                self.account.id, self.folder, all_summaries
            )
            self.new_summaries = [
                s for s in all_summaries if s.uid not in initial_uids
            ]
        finally:
            service.disconnect()


class BackgroundSyncManager(QObject):
    """Gestiona IDLE y sincronización periódica de todas las cuentas."""

    def __init__(
        self,
        settings,
        cache: MailCache,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.cache = cache
        self.signals = BackgroundSyncSignals()
        self._idle_thread: IdleMonitorThread | None = None
        self._sync_threads: list[AccountSyncThread] = []
        self._active_sync_keys: set[tuple[str, str]] = set()
        self._accounts: list[MailAccount] = []
        self._active_account_id: str | None = None
        self._prefs = load_preferences()
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_all_accounts)

    def update_preferences(self, prefs: UserPreferences) -> None:
        self._prefs = prefs

    def set_accounts(self, accounts: list[MailAccount], active_id: str | None) -> None:
        self._accounts = accounts
        self._active_account_id = active_id

    def start(self) -> None:
        self.stop()
        if not self._prefs.background_sync_enabled or not self._accounts:
            return
        active = next(
            (a for a in self._accounts if a.id == self._active_account_id),
            self._accounts[0] if self._accounts else None,
        )
        if active and self._prefs.use_imap_idle:
            password = self.settings.get_password(active.id)
            if password:
                self._idle_thread = IdleMonitorThread(active, password)
                self._idle_thread.activity_detected.connect(self._on_idle_cycle)
                self._idle_thread.start()
        self._poll_all_accounts()
        interval_ms = max(60, self._prefs.background_sync_interval_sec) * 1000
        self._poll_timer.start(interval_ms)

    def stop(self) -> None:
        self._poll_timer.stop()
        if self._idle_thread:
            self._idle_thread.stop()
            self._idle_thread.wait(2000)
            self._idle_thread = None
        for thread in self._sync_threads:
            thread.wait(1000)
        self._sync_threads.clear()
        self._active_sync_keys.clear()

    def _on_idle_cycle(self) -> None:
        if self._active_account_id:
            self._sync_account_by_id(self._active_account_id, "INBOX")

    def _poll_all_accounts(self) -> None:
        for account in self._accounts:
            self._sync_account_by_id(account.id, "INBOX")

    def _sync_account_by_id(self, account_id: str, folder: str) -> None:
        key = (account_id, folder)
        if key in self._active_sync_keys:
            return
        account = next((a for a in self._accounts if a.id == account_id), None)
        if not account:
            return
        password = self.settings.get_password(account.id)
        if not password:
            return
        self._active_sync_keys.add(key)
        thread = AccountSyncThread(
            account,
            password,
            folder,
            self.cache,
            self.settings.get_classifier(),
        )
        thread.finished.connect(lambda: self._on_sync_done(account_id, folder, thread))
        thread.start()
        self._sync_threads.append(thread)

    def _on_sync_done(
        self, account_id: str, folder: str, thread: AccountSyncThread
    ) -> None:
        self._active_sync_keys.discard((account_id, folder))
        if thread in self._sync_threads:
            self._sync_threads.remove(thread)
        self.signals.folder_updated.emit(account_id, folder)
        if thread.new_summaries and self._prefs.notify_new_mail:
            self.signals.new_mail.emit(account_id, folder, thread.new_summaries)
