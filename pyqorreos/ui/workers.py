"""
Hilos de trabajo (QThread) para operaciones de red.

Las llamadas IMAP/SMTP bloquean el hilo principal y congelarían la interfaz.
Cada worker ejecuta la operación en segundo plano y notifica el resultado
mediante señales Qt (finished / error / progress).
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

from pyqorreos.core.account import MailAccount
from pyqorreos.core.classifier import MailClassifier
from pyqorreos.core.mail_cache import MailCache
from pyqorreos.core.mail_service import IMAP_BATCH_SIZE, MailFolder, MailMessage, MailService, MailSummary
from pyqorreos.core.network_errors import friendly_mail_error


class WorkerSignals(QObject):
    """Señales compartidas por workers simples."""

    finished = Signal(object)
    error = Signal(str)


class SyncSignals(QObject):
    """Señales para sincronización masiva de una carpeta."""

    batch_ready = Signal(object)   # (list[MailSummary], done: int, total: int)
    progress = Signal(int, int)    # done, total
    finished = Signal(object)      # (list[MailSummary], list[MailSummary]) all, new
    error = Signal(str)


class ConnectWorker(QThread):
    """Conecta al servidor IMAP y obtiene la lista de carpetas."""

    def __init__(
        self,
        account: MailAccount,
        password: str,
        classifier: MailClassifier | None = None,
    ) -> None:
        super().__init__()
        self.account = account
        self.password = password
        self.classifier = classifier
        self.signals = WorkerSignals()

    def run(self) -> None:
        service = MailService(self.account, self.password, self.classifier)
        try:
            service.connect()
            folders = service.list_folders()
            self.signals.finished.emit((service, folders))
        except Exception as exc:
            self.signals.error.emit(friendly_mail_error(exc))


class LoadFolderWorker(QThread):
    """Carga la caché local de una carpeta sin bloquear la interfaz."""

    def __init__(self, cache: MailCache, account_id: str, folder: str) -> None:
        super().__init__()
        self.cache = cache
        self.account_id = account_id
        self.folder = folder
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            summaries = self.cache.load_folder(self.account_id, self.folder)
            self.signals.finished.emit(summaries)
        except Exception as exc:
            self.signals.error.emit(friendly_mail_error(exc))


class SyncFolderWorker(QThread):
    """
    Sincroniza una carpeta de forma incremental.

    Solo descarga cabeceras de mensajes nuevos respecto a la caché local.
    """

    def __init__(
        self,
        service: MailService,
        account_id: str,
        folder: str,
        cache: MailCache | None = None,
        batch_size: int = IMAP_BATCH_SIZE,
    ) -> None:
        super().__init__()
        self.service = service
        self.account_id = account_id
        self.folder = folder
        self.cache = cache or MailCache()
        self.batch_size = batch_size
        self.signals = SyncSignals()
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            self.service.select_folder(self.folder)
            cached = self.cache.load_folder(self.account_id, self.folder)
            cached_map = {summary.uid: summary for summary in cached}
            initial_uids = set(cached_map.keys())

            uids = self.service.search_all_uids()
            server_order = [
                uid.decode("ascii", errors="replace")
                if isinstance(uid, bytes)
                else str(uid)
                for uid in uids
            ]
            server_uid_set = set(server_order)

            def on_batch_ui(batch: list[MailSummary], done: int, total: int) -> None:
                if self._cancelled:
                    return
                for summary in batch:
                    cached_map[summary.uid] = summary
                if batch:
                    try:
                        start_index = server_order.index(batch[0].uid)
                    except ValueError:
                        start_index = max(0, done - len(batch))
                    self.cache.save_batch(
                        self.account_id, self.folder, batch, start_index
                    )
                self.signals.batch_ready.emit((batch, done, total))
                self.signals.progress.emit(done, total)

            all_summaries = self.service.sync_folder_incremental(
                cached_map,
                batch_size=self.batch_size,
                cancelled=lambda: self._cancelled,
                on_batch=on_batch_ui,
                on_progress=lambda done, total: self.signals.progress.emit(
                    done, total
                ),
            )

            if self._cancelled:
                return

            # Combinar con la caché actual (p. ej. sync en background paralelo).
            by_uid = {summary.uid: summary for summary in all_summaries}
            for summary in self.cache.load_folder(self.account_id, self.folder):
                if summary.uid in server_uid_set and summary.uid not in by_uid:
                    by_uid[summary.uid] = summary
            all_summaries = [
                by_uid[uid] for uid in server_order if uid in by_uid
            ]

            if server_order and not all_summaries:
                raise RuntimeError(
                    f"No se pudieron leer los mensajes de {self.folder}. "
                    "Pulsa F5 para reintentar."
                )

            removed = self.service.last_removed_uids
            if removed:
                self.cache.remove_uids(self.account_id, self.folder, removed)

            if all_summaries:
                self.cache.save_folder_ordered(
                    self.account_id, self.folder, all_summaries
                )
            new_summaries = [
                s for s in all_summaries if s.uid not in initial_uids
            ]
            self.signals.finished.emit((all_summaries, new_summaries))
        except Exception as exc:
            if not self._cancelled:
                self.signals.error.emit(friendly_mail_error(exc))


class FetchMessageWorker(QThread):
    def __init__(
        self,
        service: MailService,
        uid: str,
        cache: MailCache | None = None,
        account_id: str = "",
        folder: str = "",
        *,
        mark_seen: bool = True,
        delete_after_download: bool = False,
        load_remote_images: bool = False,
        refresh_from_server: bool = False,
    ) -> None:
        super().__init__()
        self.service = service
        self.uid = uid
        self.cache = cache
        self.account_id = account_id
        self.folder = folder
        self.mark_seen = mark_seen
        self.delete_after_download = delete_after_download
        self.load_remote_images = load_remote_images
        self.refresh_from_server = refresh_from_server
        self.signals = WorkerSignals()

    def _maybe_delete_from_server(self) -> None:
        if not self.delete_after_download:
            return
        self.service.delete_message(self.uid, self.folder or None)
        if self.cache and self.account_id and self.folder:
            self.cache.delete_message(self.account_id, self.folder, self.uid)

    def run(self) -> None:
        try:
            use_cache = (
                not self.refresh_from_server
                and not self.load_remote_images
                and self.cache
                and self.account_id
                and self.folder
            )
            if use_cache:
                cached = self.cache.load_message_body(
                    self.account_id, self.folder, self.uid
                )
                if cached and (
                    (cached.body_html and cached.body_html.strip())
                    or (
                        cached.body_text
                        and cached.body_text.strip()
                        not in ("", "(Sin contenido)", "(Mensaje vacío)")
                    )
                ):
                    self._maybe_delete_from_server()
                    self.signals.finished.emit(cached)
                    return

            message = self.service.fetch_message(
                self.uid,
                folder=self.folder or None,
                load_remote_images=self.load_remote_images,
                mark_seen=self.mark_seen,
            )
            if self.cache and self.account_id and self.folder:
                self.cache.save_message_body(
                    self.account_id, self.folder, message
                )
                if self.mark_seen:
                    self.cache.update_seen(
                        self.account_id, self.folder, self.uid, True
                    )
            self._maybe_delete_from_server()
            self.signals.finished.emit(message)
        except Exception as exc:
            self.signals.error.emit(friendly_mail_error(exc))


class EnhanceHtmlWorker(QThread):
    """Descarga imágenes remotas para un mensaje ya mostrado en pantalla."""

    def __init__(
        self,
        service: MailService,
        uid: str,
        html: str,
        folder: str = "",
    ) -> None:
        super().__init__()
        self.service = service
        self.uid = uid
        self.html = html
        self.folder = folder
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            enhanced = self.service.enhance_message_html(
                self.html, uid=self.uid, folder=self.folder or None
            )
            self.signals.finished.emit((self.uid, enhanced))
        except Exception as exc:
            self.signals.error.emit(friendly_mail_error(exc))


class TranslateMessageWorker(QThread):
    """Traduce el cuerpo y asunto de un mensaje en segundo plano."""

    def __init__(
        self,
        uid: str,
        body_text: str,
        subject: str,
        target_lang: str,
    ) -> None:
        super().__init__()
        self.uid = uid
        self.body_text = body_text
        self.subject = subject
        self.target_lang = target_lang
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            from pyqorreos.core.translate import translate_text

            body = translate_text(self.body_text, self.target_lang)
            subject = (
                translate_text(self.subject, self.target_lang)
                if self.subject.strip()
                else ""
            )
            self.signals.finished.emit(
                (self.uid, self.target_lang, body, subject)
            )
        except Exception as exc:
            self.signals.error.emit(friendly_mail_error(exc))


class SetSeenWorker(QThread):
    def __init__(
        self,
        service: MailService,
        uid: str,
        seen: bool,
        cache: MailCache | None = None,
        account_id: str = "",
        folder: str = "",
    ) -> None:
        super().__init__()
        self.service = service
        self.uid = uid
        self.seen = seen
        self.cache = cache
        self.account_id = account_id
        self.folder = folder
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            self.service.set_seen(self.uid, self.seen, self.folder or None)
            if self.cache and self.account_id and self.folder:
                self.cache.update_seen(
                    self.account_id, self.folder, self.uid, self.seen
                )
            self.signals.finished.emit((self.uid, self.seen))
        except Exception as exc:
            self.signals.error.emit(friendly_mail_error(exc))


class SendMailWorker(QThread):
    def __init__(
        self,
        service: MailService,
        to: str,
        subject: str,
        body: str,
        cc: str = "",
        bcc: str = "",
        body_html: str | None = None,
        attachments: list | None = None,
    ) -> None:
        super().__init__()
        self.service = service
        self.to = to
        self.subject = subject
        self.body = body
        self.cc = cc
        self.bcc = bcc
        self.body_html = body_html
        self.attachments = attachments or []
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            self.service.send_message(
                self.to,
                self.subject,
                self.body,
                self.cc,
                self.bcc,
                body_html=self.body_html,
                attachments=self.attachments,
            )
            self.signals.finished.emit(True)
        except Exception as exc:
            self.signals.error.emit(friendly_mail_error(exc))


class DeleteMessageWorker(QThread):
    def __init__(
        self,
        service: MailService,
        uid: str,
        cache: MailCache | None = None,
        account_id: str = "",
        folder: str = "",
    ) -> None:
        super().__init__()
        self.service = service
        self.uid = uid
        self.cache = cache
        self.account_id = account_id
        self.folder = folder
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            self.service.delete_message(self.uid, self.folder or None)
            if self.cache and self.account_id and self.folder:
                self.cache.delete_message(self.account_id, self.folder, self.uid)
            self.signals.finished.emit(self.uid)
        except Exception as exc:
            self.signals.error.emit(friendly_mail_error(exc))


class DeleteMessagesWorker(QThread):
    def __init__(
        self,
        service: MailService,
        uids: list[str],
        cache: MailCache | None = None,
        account_id: str = "",
        folder: str = "",
    ) -> None:
        super().__init__()
        self.service = service
        self.uids = uids
        self.cache = cache
        self.account_id = account_id
        self.folder = folder
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            self.service.delete_messages(self.uids, self.folder or None)
            if self.cache and self.account_id and self.folder:
                for uid in self.uids:
                    self.cache.delete_message(self.account_id, self.folder, uid)
            self.signals.finished.emit(self.uids)
        except Exception as exc:
            self.signals.error.emit(friendly_mail_error(exc))


class MoveMessagesWorker(QThread):
    def __init__(
        self,
        service: MailService,
        uids: list[str],
        dest_folder: str,
        cache: MailCache | None = None,
        account_id: str = "",
        source_folder: str = "",
    ) -> None:
        super().__init__()
        self.service = service
        self.uids = uids
        self.dest_folder = dest_folder
        self.cache = cache
        self.account_id = account_id
        self.source_folder = source_folder
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            self.service.move_messages(
                self.uids,
                self.dest_folder,
                source_folder=self.source_folder or None,
            )
            if self.cache and self.account_id and self.source_folder:
                for uid in self.uids:
                    self.cache.delete_message(
                        self.account_id, self.source_folder, uid
                    )
            self.signals.finished.emit((self.uids, self.dest_folder))
        except Exception as exc:
            self.signals.error.emit(friendly_mail_error(exc))


class CreateFolderWorker(QThread):
    """Crea una carpeta IMAP y devuelve la lista actualizada de carpetas."""

    def __init__(
        self,
        service: MailService,
        name: str,
        parent: str | None = None,
    ) -> None:
        super().__init__()
        self.service = service
        self.name = name
        self.parent = parent
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            created = self.service.create_folder(self.name, self.parent)
            folders = [f.name for f in self.service.list_folders()]
            self.signals.finished.emit((created, folders))
        except Exception as exc:
            self.signals.error.emit(friendly_mail_error(exc))


class DeleteFolderWorker(QThread):
    """Elimina una carpeta IMAP (opcionalmente con subcarpetas)."""

    def __init__(
        self,
        service: MailService,
        folder: str,
        cache: MailCache | None = None,
        account_id: str = "",
        *,
        recursive: bool = False,
    ) -> None:
        super().__init__()
        self.service = service
        self.folder = folder
        self.cache = cache
        self.account_id = account_id
        self.recursive = recursive
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            deleted = self.service.delete_folder(self.folder, recursive=self.recursive)
            if self.cache and self.account_id:
                for path in deleted:
                    self.cache.clear_folder(self.account_id, path)
            folders = [f.name for f in self.service.list_folders()]
            self.signals.finished.emit((deleted, folders))
        except Exception as exc:
            self.signals.error.emit(friendly_mail_error(exc))


class EmptyFolderWorker(QThread):
    def __init__(self, service: MailService, folder: str, cache: MailCache | None = None, account_id: str = "") -> None:
        super().__init__()
        self.service = service
        self.folder = folder
        self.cache = cache
        self.account_id = account_id
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            count = self.service.empty_folder(self.folder)
            if self.cache and self.account_id:
                self.cache.clear_folder(self.account_id, self.folder)
            self.signals.finished.emit((self.folder, count))
        except Exception as exc:
            self.signals.error.emit(friendly_mail_error(exc))


class FolderUnreadWorker(QThread):
    def __init__(
        self,
        account: MailAccount,
        password: str,
        folders: list[str],
    ) -> None:
        super().__init__()
        self.account = account
        self.password = password
        self.folders = folders
        self.signals = WorkerSignals()

    def run(self) -> None:
        service = MailService(self.account, self.password)
        try:
            service.connect()
            counts = service.get_folder_unread_counts(self.folders)
            self.signals.finished.emit(counts)
        except Exception as exc:
            self.signals.error.emit(friendly_mail_error(exc))
        finally:
            service.disconnect()


class FetchAttachmentWorker(QThread):
    def __init__(
        self,
        service: MailService,
        uid: str,
        part_index: int,
        folder: str = "",
    ) -> None:
        super().__init__()
        self.service = service
        self.uid = uid
        self.part_index = part_index
        self.folder = folder
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            data, filename = self.service.fetch_attachment_bytes(
                self.uid, self.part_index, self.folder or None
            )
            self.signals.finished.emit((filename, data))
        except Exception as exc:
            self.signals.error.emit(friendly_mail_error(exc))


class SaveDraftWorker(QThread):
    def __init__(self, service: MailService, folder: str, raw_message: bytes) -> None:
        super().__init__()
        self.service = service
        self.folder = folder
        self.raw_message = raw_message
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            self.service.save_draft(self.folder, self.raw_message)
            self.signals.finished.emit(True)
        except Exception as exc:
            self.signals.error.emit(friendly_mail_error(exc))


class UnsubscribeWorker(QThread):
    """Ejecuta desuscripción List-Unsubscribe y mueve el mensaje a la papelera."""

    def __init__(
        self,
        service: MailService,
        uid: str,
        source_folder: str,
        trash_folder: str,
        *,
        url: str | None,
        mailto: str | None,
        one_click: bool,
        cache: MailCache | None = None,
        account_id: str = "",
    ) -> None:
        super().__init__()
        self.service = service
        self.uid = uid
        self.source_folder = source_folder
        self.trash_folder = trash_folder
        self.url = url
        self.mailto = mailto
        self.one_click = one_click
        self.cache = cache
        self.account_id = account_id
        self.signals = WorkerSignals()

    def run(self) -> None:
        from pyqorreos.core.list_unsubscribe import perform_unsubscribe

        try:
            message = perform_unsubscribe(
                url=self.url,
                mailto=self.mailto,
                one_click=self.one_click,
            )
            self.service.move_messages([self.uid], self.trash_folder)
            if self.cache and self.account_id:
                self.cache.delete_message(
                    self.account_id, self.source_folder, self.uid
                )
            self.signals.finished.emit(message)
        except Exception as exc:
            self.signals.error.emit(friendly_mail_error(exc))


class StorageQuotaWorker(QThread):
    def __init__(self, service: MailService) -> None:
        super().__init__()
        self.service = service
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            quota = self.service.get_storage_quota()
            self.signals.finished.emit(quota)
        except Exception as exc:
            self.signals.error.emit(friendly_mail_error(exc))


class ExportMessageWorker(QThread):
    def __init__(
        self,
        service: MailService,
        uid: str,
        folder: str,
        dest_path: str,
    ) -> None:
        super().__init__()
        self.service = service
        self.uid = uid
        self.folder = folder
        self.dest_path = dest_path
        self.signals = WorkerSignals()

    def run(self) -> None:
        from pathlib import Path

        from pyqorreos.core.export_mail import save_eml

        try:
            raw = self.service.fetch_raw_bytes(self.uid, self.folder)
            save_eml(raw, Path(self.dest_path))
            self.signals.finished.emit(self.dest_path)
        except Exception as exc:
            self.signals.error.emit(friendly_mail_error(exc))


class ExportFolderWorker(QThread):
    def __init__(
        self,
        service: MailService,
        account_id: str,
        folder: str,
        uids: list[str],
        dest_path: str,
        cache: MailCache | None = None,
    ) -> None:
        super().__init__()
        self.service = service
        self.account_id = account_id
        self.folder = folder
        self.uids = uids
        self.dest_path = dest_path
        self.cache = cache
        self.signals = WorkerSignals()

    def run(self) -> None:
        from pathlib import Path

        from pyqorreos.core.export_mail import save_mbox

        try:
            messages: list[tuple[bytes, str | None]] = []
            for uid in self.uids:
                try:
                    raw = self.service.fetch_raw_bytes(uid, self.folder)
                    messages.append((raw, None))
                except Exception:
                    continue
            count = save_mbox(messages, Path(self.dest_path))
            self.signals.finished.emit((self.dest_path, count))
        except Exception as exc:
            self.signals.error.emit(friendly_mail_error(exc))


class OAuthFlowWorker(QThread):
    """Ejecuta OAuthFlow.run_flow() en segundo plano y guarda los tokens en el llavero."""

    open_url = Signal(str)

    def __init__(self, provider_key: str, account_id: str) -> None:
        super().__init__()
        self.provider_key = provider_key
        self.account_id = account_id
        self.signals = WorkerSignals()

    def run(self) -> None:
        from pyqorreos.core.oauth import OAuthFlow, OAuthError, store_oauth_tokens

        try:
            flow = OAuthFlow(self.provider_key, open_browser=self._open_browser)
            token = flow.run_flow()
            store_oauth_tokens(self.account_id, token)
            self.signals.finished.emit(token)
        except OAuthError as exc:
            self.signals.error.emit(str(exc))
        except Exception as exc:
            self.signals.error.emit(friendly_mail_error(exc))

    def _open_browser(self, url: str) -> bool:
        """Emite la URL para abrirla en el hilo principal (Qt)."""
        self.open_url.emit(url)
        return True
