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
                if service.wait_for_idle_updates(
                    self.folder,
                    self.timeout_sec,
                    cancelled=lambda: self._stop,
                    poll_sec=1,
                ):
                    if self._stop:
                        break
                    self.activity_detected.emit()
                    self.msleep(500)
            except Exception:
                if self._stop:
                    break
                self.msleep(30_000)
            finally:
                service.disconnect()
            if self._stop:
                break


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
        self._idle_account_id: str | None = None
        self._sync_threads: list[AccountSyncThread] = []
        self._thread_refs: list[QThread] = []
        self._active_sync_keys: set[tuple[str, str]] = set()
        self._accounts: list[MailAccount] = []
        self._active_account_id: str | None = None
        self._prefs = load_preferences()
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_all_accounts)
        self._modal_pause_depth = 0

    def pause_for_modal(self) -> None:
        """Pausa solo el polling mientras hay un diálogo modal (no toca IDLE ni sync)."""
        self._modal_pause_depth += 1
        if self._modal_pause_depth == 1:
            self._poll_timer.stop()

    def resume_after_modal(self) -> None:
        """Reanuda el polling tras cerrar un diálogo modal."""
        if self._modal_pause_depth <= 0:
            return
        self._modal_pause_depth -= 1
        if self._modal_pause_depth > 0:
            return
        if not self._prefs.background_sync_enabled or not self._accounts:
            return
        interval_ms = max(60, self._prefs.background_sync_interval_sec) * 1000
        if not self._poll_timer.isActive():
            self._poll_timer.start(interval_ms)

    def _prune_dead_thread_refs(self) -> None:
        alive: list[QThread] = []
        for thread in self._thread_refs:
            try:
                thread.isRunning()
                alive.append(thread)
            except RuntimeError:
                if self._idle_thread is thread:
                    self._idle_thread = None
                    self._idle_account_id = None
        self._thread_refs = alive

    def _stop_idle_thread(self, *, wait_ms: int = 0) -> None:
        idle = self._idle_thread
        self._idle_thread = None
        self._idle_account_id = None
        if idle is None:
            return
        try:
            idle.activity_detected.disconnect(self._on_idle_cycle)
        except (RuntimeError, TypeError):
            pass
        try:
            idle.stop()
        except RuntimeError:
            pass
        self._release_thread(idle, wait_ms=wait_ms)

    def update_preferences(self, prefs: UserPreferences) -> None:
        self._prefs = prefs

    def set_accounts(self, accounts: list[MailAccount], active_id: str | None) -> None:
        self._accounts = accounts
        self._active_account_id = active_id

    def _own_thread(self, thread: QThread) -> None:
        """Mantiene la referencia Python hasta que Qt destruya el objeto."""
        if thread in self._thread_refs:
            return
        self._thread_refs.append(thread)
        thread.destroyed.connect(lambda *_a, t=thread: self._drop_thread_ref(t))

    def _drop_thread_ref(self, thread: QThread) -> None:
        try:
            self._thread_refs.remove(thread)
        except ValueError:
            pass
        if self._idle_thread is thread:
            self._idle_thread = None
            self._idle_account_id = None

    def start(self, *, wait_ms: int = 0) -> None:
        self.stop(wait_ms=wait_ms)
        if not self._prefs.background_sync_enabled or not self._accounts:
            return
        active = next(
            (a for a in self._accounts if a.id == self._active_account_id),
            self._accounts[0] if self._accounts else None,
        )
        if active and self._prefs.use_imap_idle:
            password = self.settings.get_auth_secret(active)
            if password:
                self._prune_dead_thread_refs()
                idle = IdleMonitorThread(active, password, timeout_sec=120)
                self._own_thread(idle)
                self._idle_account_id = active.id
                idle.activity_detected.connect(self._on_idle_cycle)
                idle.finished.connect(idle.deleteLater)
                idle.start()
                self._idle_thread = idle
        self.sync_all_accounts_now()
        if self._modal_pause_depth <= 0:
            interval_ms = max(60, self._prefs.background_sync_interval_sec) * 1000
            self._poll_timer.start(interval_ms)

    def sync_all_accounts_now(self, *, exclude_account_id: str | None = None) -> None:
        """Descarga cabeceras nuevas de INBOX en todas las cuentas (p. ej. al arrancar)."""
        if not self._accounts:
            return
        for account in self._accounts:
            if exclude_account_id and account.id == exclude_account_id:
                continue
            self._sync_account_by_id(account.id, "INBOX")

    def stop(self, *, wait_ms: int = 5000) -> None:
        """Detiene IDLE y polling. Con wait_ms=0 solo pausa (sin bloquear la UI)."""
        self._poll_timer.stop()
        self._stop_idle_thread(wait_ms=wait_ms)

        if wait_ms <= 0:
            # Pausa rápida (p. ej. diálogos modales): no tocar sync en curso.
            return

        for thread in list(self._sync_threads):
            self._release_sync_thread(thread, wait_ms=wait_ms)
        self._active_sync_keys.clear()

    def _forget_sync_thread(self, thread: AccountSyncThread) -> None:
        try:
            self._sync_threads.remove(thread)
        except ValueError:
            pass

    @staticmethod
    def _release_thread(thread: QThread, *, wait_ms: int) -> None:
        if thread is None:
            return
        try:
            running = thread.isRunning()
        except RuntimeError:
            return
        if wait_ms > 0 and running:
            thread.wait(wait_ms)
            try:
                running = thread.isRunning()
            except RuntimeError:
                return
            if running:
                thread.terminate()
                thread.wait(300)
        try:
            running = thread.isRunning()
        except RuntimeError:
            return
        if running:
            thread.finished.connect(thread.deleteLater)
        else:
            thread.deleteLater()

    def _release_sync_thread(self, thread: AccountSyncThread, *, wait_ms: int) -> None:
        self._release_thread(thread, wait_ms=wait_ms)

    def _on_idle_cycle(self) -> None:
        if self._active_account_id:
            self._sync_account_by_id(self._active_account_id, "INBOX")

    def _poll_all_accounts(self) -> None:
        self.sync_all_accounts_now()

    def _sync_account_by_id(self, account_id: str, folder: str) -> None:
        key = (account_id, folder)
        if key in self._active_sync_keys:
            return
        account = next((a for a in self._accounts if a.id == account_id), None)
        if not account:
            return
        auth_secret = self.settings.get_auth_secret(account)
        if not auth_secret:
            return
        self._active_sync_keys.add(key)
        thread = AccountSyncThread(
            account,
            auth_secret,
            folder,
            self.cache,
            self.settings.get_classifier(),
        )
        thread.finished.connect(
            lambda: self._on_sync_done(account_id, folder, thread)
        )
        thread.finished.connect(thread.deleteLater)
        thread.destroyed.connect(lambda *_a, t=thread: self._forget_sync_thread(t))
        self._own_thread(thread)
        thread.start()
        self._sync_threads.append(thread)

    def _on_sync_done(
        self, account_id: str, folder: str, thread: AccountSyncThread
    ) -> None:
        self._active_sync_keys.discard((account_id, folder))
        new_summaries = list(thread.new_summaries)
        self.signals.folder_updated.emit(account_id, folder)
        if new_summaries and self._prefs.notify_new_mail:
            self.signals.new_mail.emit(account_id, folder, new_summaries)
