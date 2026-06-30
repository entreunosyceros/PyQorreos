"""
Cliente de correo IMAP/SMTP.

Encapsula la comunicación con el servidor: listar carpetas, leer mensajes,
enviar correos y eliminar mensajes. Usa la biblioteca estándar imaplib/smtplib.
"""

from __future__ import annotations

import email
import imaplib
import mimetypes
import re
import smtplib
import ssl
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from email.header import decode_header

from pyqorreos.core.email_charset import decode_email_bytes
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from typing import Any, Callable

from pyqorreos.core.account import MailAccount
from pyqorreos.core.oauth import AuthMethod, build_xoauth2_string
from pyqorreos.core.classifier import MailCategory, MailClassifier
from pyqorreos.core.compose_email import (
    EmailAttachment,
    apply_read_receipt_headers,
    build_read_receipt_bytes,
    parse_read_receipt_request,
)
from pyqorreos.core.email_html import prepare_html_for_display
from pyqorreos.core.network_errors import friendly_mail_error

IMAP_SOCKET_TIMEOUT = 60
SMTP_SOCKET_TIMEOUT = 120
from pyqorreos.core.folder_utils import normalize_thread_subject
from pyqorreos.core.openpgp import (
    OpenPgpSettings,
    PgpStatus,
    encrypt_outgoing_message,
    parse_recipient_emails,
    process_incoming_message,
)
from pyqorreos.core.message_attachments import (
    MailAttachmentInfo,
    extract_attachments,
    get_attachment_payload,
    has_attachments_heuristic,
)
from pyqorreos.core.user_preferences import LARGE_FOLDER_THRESHOLD

# Tamaño de lote para UID FETCH (varios mensajes por petición IMAP).
IMAP_BATCH_SIZE = 100


def _mail_ssl_context() -> ssl.SSLContext:
    """Contexto TLS con certificados del sistema (Let's Encrypt, etc.)."""
    return ssl.create_default_context()


def _imap_starttls(conn: imaplib.IMAP4, context: ssl.SSLContext) -> None:
    try:
        conn.starttls(ssl_context=context)
    except TypeError:
        conn.starttls()


def open_imap_connection(account: MailAccount) -> imaplib.IMAP4_SSL | imaplib.IMAP4:
    """Abre IMAP con SSL/TLS implícito o STARTTLS según la cuenta."""
    context = _mail_ssl_context()
    if account.use_ssl:
        return imaplib.IMAP4_SSL(
            account.imap_host,
            account.imap_port,
            ssl_context=context,
            timeout=IMAP_SOCKET_TIMEOUT,
        )
    conn = imaplib.IMAP4(
        account.imap_host,
        account.imap_port,
        timeout=IMAP_SOCKET_TIMEOUT,
    )
    if account.use_starttls:
        _imap_starttls(conn, context)
    return conn

_HEADER_FETCH = (
    "BODY.PEEK[HEADER.FIELDS "
    "(FROM SUBJECT DATE MESSAGE-ID IN-REPLY-TO REFERENCES CONTENT-TYPE "
    "IMPORTANCE X-PRIORITY X-MSMail-Priority X-Spam-Status X-Spam-Flag)]"
)
# FLAGS se pide aparte para evitar fallos de imaplib con flags personalizados (p. ej. NonJunk).
_FLAGS_FETCH = "FLAGS"
_UID_PATTERN = re.compile(rb"UID\s+(\d+)")


@dataclass
class MailFolder:
    name: str
    delimiter: str = "/"
    flags: tuple[str, ...] = ()


@dataclass
class MailSummary:
    uid: str
    subject: str
    sender: str
    date: datetime | None
    seen: bool
    flagged: bool
    category: MailCategory = MailCategory.NORMAL
    has_attachments: bool = False
    message_id: str = ""
    thread_key: str = ""
    folder: str = ""


@dataclass
class MailMessage:
    uid: str
    subject: str
    sender: str
    recipients: str
    date: datetime | None
    body_text: str
    body_html: str
    category: MailCategory = MailCategory.NORMAL
    attachments: list[MailAttachmentInfo] | None = None
    message_id: str = ""
    in_reply_to: str = ""
    references: str = ""
    unsubscribe_url: str | None = None
    unsubscribe_mailto: str | None = None
    one_click_unsubscribe: bool = False
    read_receipt_to: str = ""
    pgp: PgpStatus | None = None


def _decode_header_value(value: str | None) -> str:
    if not value:
        return ""
    parts: list[str] = []
    for fragment, charset in decode_header(value):
        if isinstance(fragment, bytes):
            parts.append(decode_email_bytes(fragment, charset))
        else:
            parts.append(fragment)
    return "".join(parts).strip()


def normalize_mail_datetime(dt: datetime | None) -> datetime | None:
    """Convierte fechas de correo a UTC naive para comparar y ordenar sin errores."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return normalize_mail_datetime(parsedate_to_datetime(raw))
    except (TypeError, ValueError, IndexError):
        return None


def _extract_body(msg: email.message.Message) -> tuple[str, str]:
    text_parts: list[str] = []
    html_parts: list[str] = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition:
                continue
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            decoded = decode_email_bytes(payload, part.get_content_charset())
            if content_type == "text/plain":
                text_parts.append(decoded)
            elif content_type == "text/html":
                html_parts.append(decoded)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            decoded = decode_email_bytes(payload, msg.get_content_charset())
            if msg.get_content_type() == "text/html":
                html_parts.append(decoded)
            else:
                text_parts.append(decoded)

    return "\n".join(text_parts), "\n".join(html_parts)


def _uid_from_fetch_meta(meta: bytes) -> str | None:
    match = _UID_PATTERN.search(meta)
    if not match:
        return None
    return match.group(1).decode("ascii", errors="replace")


def _flags_from_fetch_meta(meta: bytes) -> str:
    return meta.decode("utf-8", errors="replace") if meta else ""


def _extract_largest_payload(data: list) -> tuple[str, bytes]:
    """Obtiene flags y el bloque de bytes más grande (cuerpo del mensaje) de un FETCH."""
    flags_raw = ""
    best = b""
    for part in data or []:
        if part is None:
            continue
        if isinstance(part, tuple) and len(part) >= 2:
            meta, payload = part[0], part[1]
            if isinstance(meta, bytes):
                flags_raw += _flags_from_fetch_meta(meta)
            if isinstance(payload, bytes) and len(payload) > len(best):
                best = payload
        elif isinstance(part, bytes) and len(part) > len(best):
            # Respuestas literales sueltas de algunos servidores IMAP.
            if len(part) > 32 or part.startswith(b"From ") or b"Subject:" in part[:512]:
                best = part
    return flags_raw, best


def _extract_header_text_payload(data: list) -> tuple[str, bytes, bytes]:
    """Extrae cabecera y texto de respuestas BODY.PEEK[HEADER] + BODY.PEEK[TEXT]."""
    flags_raw = ""
    header = b""
    text = b""
    for part in data:
        if not isinstance(part, tuple):
            continue
        meta, payload = part[0], part[1]
        if not isinstance(meta, bytes) or not isinstance(payload, bytes):
            continue
        meta_s = meta.decode("utf-8", errors="replace").upper()
        flags_raw += _flags_from_fetch_meta(meta)
        if "HEADER" in meta_s and len(payload) > len(header):
            header = payload
        elif "TEXT" in meta_s and len(payload) > len(text):
            text = payload
    return flags_raw, header, text


_RAW_FETCH_SPECS = (
    "(FLAGS BODY.PEEK[])",
    "(FLAGS RFC822.PEEK)",
    "(FLAGS BODY.PEEK[HEADER] BODY.PEEK[TEXT])",
)


def _header_value(msg: email.message.Message, name: str) -> str:
    return _decode_header_value(msg.get(name))


def _thread_key_from_headers(
    subject: str, message_id: str, in_reply_to: str, references: str, uid: str
) -> str:
    if in_reply_to:
        return in_reply_to.strip().strip("<>")
    if references:
        refs = references.split()
        if refs:
            return refs[0].strip().strip("<>")
    if message_id:
        return message_id.strip().strip("<>")
    return normalize_thread_subject(subject) + f":{uid}"


def _summary_from_fetch(
    uid: str,
    flags_raw: str,
    header_bytes: bytes,
    folder: str,
    classifier: MailClassifier,
) -> MailSummary | None:
    if not header_bytes:
        return None
    msg = email.message_from_bytes(header_bytes)
    seen = "\\Seen" in flags_raw
    flagged = "\\Flagged" in flags_raw
    subject = _decode_header_value(msg.get("Subject")) or "(Sin asunto)"
    sender = _decode_header_value(msg.get("From")) or "(Sin remitente)"
    message_id = _header_value(msg, "Message-ID")
    in_reply_to = _header_value(msg, "In-Reply-To")
    references = _header_value(msg, "References")
    content_type = _header_value(msg, "Content-Type")
    thread_key = _thread_key_from_headers(
        subject, message_id, in_reply_to, references, uid
    )
    headers = classifier.parse_headers_from_message(msg)
    category = classifier.classify(
        folder=folder,
        subject=subject,
        sender=sender,
        flagged=flagged,
        headers=headers,
    )
    return MailSummary(
        uid=uid,
        subject=subject,
        sender=sender,
        date=_parse_date(msg.get("Date")),
        seen=seen,
        flagged=flagged,
        category=category,
        has_attachments=has_attachments_heuristic(content_type),
        message_id=message_id,
        thread_key=thread_key,
    )


class MailService:
    """Cliente IMAP/SMTP para operaciones de correo."""

    def __init__(
        self,
        account: MailAccount,
        password: str,
        classifier: MailClassifier | None = None,
    ) -> None:
        self.account = account
        self.password = password
        self.classifier = classifier or MailClassifier()
        self._imap: imaplib.IMAP4_SSL | imaplib.IMAP4 | None = None
        self._imap_thread_id: int | None = None
        self._current_folder = "INBOX"
        # IMAP no admite comandos concurrentes en la misma conexión.
        self._imap_lock = threading.Lock()
        self._fetch_lock = threading.Lock()

    def connect(self) -> None:
        with self._imap_lock:
            self._close_imap_unlocked()
            self._open_imap_session()

    def _open_imap_session(self) -> None:
        self._imap = open_imap_connection(self.account)
        assert self._imap is not None
        self._imap_login(self._imap)
        self._imap_thread_id = threading.current_thread().ident

    def _close_imap_unlocked(self) -> None:
        imap = self._imap
        owner = self._imap_thread_id
        self._imap = None
        self._imap_thread_id = None
        if imap is None:
            return
        if owner == threading.current_thread().ident:
            try:
                imap.logout()
            except Exception:
                pass

    def _imap_login(self, conn: imaplib.IMAP4_SSL | imaplib.IMAP4) -> None:
        if self.account.auth_method == AuthMethod.OAUTH2.value:
            auth_string = build_xoauth2_string(self.account.email, self.password)
            conn.authenticate("XOAUTH2", lambda _challenge: auth_string)
            return
        conn.login(self.account.email, self.password)

    def _smtp_login(self, server: smtplib.SMTP) -> None:
        if self.account.auth_method == AuthMethod.OAUTH2.value:
            auth_string = build_xoauth2_string(self.account.email, self.password)
            server.auth("XOAUTH2", lambda _challenge=None: auth_string)
            return
        server.login(self.account.email, self.password)

    def ensure_connected(self) -> None:
        """Reconecta si la sesión IMAP dejó de responder."""
        with self._imap_lock:
            self._ensure_connected_unlocked()

    def _ensure_connected_unlocked(self) -> None:
        folder = self._current_folder
        tid = threading.current_thread().ident
        if self._imap is not None and self._imap_thread_id != tid:
            self._close_imap_unlocked()
        if self._imap is not None:
            try:
                self._imap.noop()
                if folder:
                    self._select_on_imap(self._imap, folder)
                return
            except Exception:
                self._close_imap_unlocked()
        self._open_imap_session()
        if folder:
            self._select_on_imap(self._require_imap(), folder)

    def _ensure_selected_unlocked(
        self, imap: imaplib.IMAP4_SSL | imaplib.IMAP4, folder: str
    ) -> None:
        """Abre la carpeta en IMAP (requerido para STORE, COPY, EXPUNGE, etc.)."""
        if not folder:
            raise RuntimeError("No se indicó carpeta IMAP")
        self._select_on_imap(imap, folder)
        self._current_folder = folder

    def disconnect(self) -> None:
        with self._imap_lock:
            self._close_imap_unlocked()

    def _require_imap(self) -> imaplib.IMAP4_SSL | imaplib.IMAP4:
        if not self._imap:
            raise RuntimeError("No conectado al servidor IMAP")
        return self._imap

    def _new_imap_connection(self) -> imaplib.IMAP4_SSL | imaplib.IMAP4:
        """Abre una conexión IMAP nueva e independiente (para leer mensajes completos)."""
        conn = open_imap_connection(self.account)
        self._imap_login(conn)
        return conn

    def _quoted_folder(self, folder: str) -> str:
        if folder.startswith('"') and folder.endswith('"'):
            return folder
        return f'"{folder}"'

    def _select_on_imap(
        self, imap: imaplib.IMAP4_SSL | imaplib.IMAP4, folder: str
    ) -> None:
        status, _data = imap.select(self._quoted_folder(folder))
        if status != "OK":
            raise RuntimeError(f"No se pudo abrir la carpeta: {folder}")

    @contextmanager
    def _imap_read_session(self, folder: str) -> Iterator[imaplib.IMAP4_SSL | imaplib.IMAP4]:
        """
        Sesión IMAP efímera solo para leer un mensaje.

        Evita interferencias con la conexión principal usada en sincronización
        por lotes, que puede dejar el buffer de imaplib desincronizado.
        """
        imap = self._new_imap_connection()
        try:
            self._select_on_imap(imap, folder)
            yield imap
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    def _imap_resync(self, imap: imaplib.IMAP4_SSL | imaplib.IMAP4) -> None:
        """Intenta resincronizar el buffer del protocolo IMAP tras operaciones masivas."""
        try:
            imap.noop()
        except Exception:
            pass

    def list_folders(self) -> list[MailFolder]:
        with self._imap_lock:
            self._ensure_connected_unlocked()
            imap = self._require_imap()
            status, data = imap.list()
        if status != "OK" or not data:
            return [MailFolder(name="INBOX")]

        folders: list[MailFolder] = []
        for raw in data:
            if not raw or not isinstance(raw, bytes):
                continue
            line = raw.decode("utf-8", errors="replace")
            parts = line.rsplit(" ", 1)
            if len(parts) >= 2:
                name = parts[-1].strip().strip('"')
                folders.append(MailFolder(name=name))
        return folders or [MailFolder(name="INBOX")]

    def select_folder(self, folder: str) -> int:
        with self._imap_lock:
            self._ensure_connected_unlocked()
            imap = self._require_imap()
            status, data = imap.select(self._quoted_folder(folder))
        if status != "OK":
            raise RuntimeError(f"No se pudo abrir la carpeta: {folder}")
        self._current_folder = folder
        return int(data[0]) if data and data[0] else 0

    def poke_mailbox(self) -> None:
        """Solicita al servidor el estado actualizado del buzón abierto."""
        with self._imap_lock:
            self._ensure_connected_unlocked()
            imap = self._require_imap()
            if self._current_folder:
                self._select_on_imap(imap, self._current_folder)
            imap.noop()

    @property
    def current_folder(self) -> str:
        return self._current_folder

    def search_all_uids(self) -> list[bytes]:
        """Devuelve todos los UIDs de la carpeta activa (más recientes primero)."""
        with self._imap_lock:
            self._ensure_connected_unlocked()
            imap = self._require_imap()
            status, data = imap.uid("search", None, "ALL")
        if status != "OK" or not data or not data[0]:
            return []
        uids = list(data[0].split())
        uids.reverse()
        return uids

    def _fetch_flags_batch(
        self, imap: imaplib.IMAP4_SSL | imaplib.IMAP4, uids: list[bytes]
    ) -> dict[str, str]:
        """Obtiene flags de varios mensajes en una sola petición."""
        if not uids:
            return {}
        try:
            uid_set = b",".join(uids)
            status, data = imap.uid("fetch", uid_set, f"({_FLAGS_FETCH})")
            if status != "OK" or not data:
                return {}
            flags_map: dict[str, str] = {}
            for part in data:
                if isinstance(part, tuple) and isinstance(part[0], bytes):
                    uid = _uid_from_fetch_meta(part[0])
                    if uid:
                        flags_map[uid] = part[0].decode("utf-8", errors="replace")
            return flags_map
        except imaplib.IMAP4.error:
            return {}

    def _fetch_flags_for_uid(
        self, imap: imaplib.IMAP4_SSL | imaplib.IMAP4, uid: bytes | str
    ) -> str:
        """Obtiene los flags de un mensaje en una petición ligera."""
        try:
            status, data = imap.uid("fetch", uid, f"({_FLAGS_FETCH})")
            if status != "OK" or not data:
                return ""
            flags_raw = ""
            for part in data:
                if isinstance(part, tuple) and isinstance(part[0], bytes):
                    flags_raw += part[0].decode("utf-8", errors="replace")
            return flags_raw
        except imaplib.IMAP4.error:
            return ""

    def _parse_fetch_response(self, msg_data: list) -> list[tuple[str, str, bytes]]:
        """Extrae (uid, flags_raw, header_bytes) de una respuesta UID FETCH."""
        items: list[tuple[str, str, bytes]] = []
        for part in msg_data:
            if not isinstance(part, tuple) or len(part) < 2:
                continue
            meta = part[0]
            payload = part[1]
            if not isinstance(meta, bytes):
                continue
            if not isinstance(payload, bytes):
                continue
            uid = _uid_from_fetch_meta(meta)
            if not uid:
                continue
            flags_raw = meta.decode("utf-8", errors="replace")
            items.append((uid, flags_raw, payload))
        return items

    def _fetch_single_summary(self, uid: bytes) -> MailSummary | None:
        """Descarga cabeceras de un único mensaje (fallback si falla el lote)."""
        imap = self._require_imap()
        status, msg_data = imap.uid("fetch", uid, f"({_HEADER_FETCH})")
        if status != "OK" or not msg_data:
            return None
        parsed = self._parse_fetch_response(msg_data)
        if not parsed:
            return None
        uid_str, _meta, header_bytes = parsed[0]
        flags_raw = self._fetch_flags_for_uid(imap, uid)
        return _summary_from_fetch(
            uid_str, flags_raw, header_bytes, self._current_folder, self.classifier
        )

    def fetch_summaries_batch(self, uids: list[bytes]) -> list[MailSummary]:
        """Descarga cabeceras de varios mensajes en una sola petición IMAP."""
        if not uids:
            return []

        uid_order = {
            uid.decode() if isinstance(uid, bytes) else str(uid): i
            for i, uid in enumerate(uids)
        }

        with self._imap_lock:
            self._ensure_connected_unlocked()
            imap = self._require_imap()
            uid_set = b",".join(uids)
            try:
                status, msg_data = imap.uid("fetch", uid_set, f"({_HEADER_FETCH})")
            except imaplib.IMAP4.error:
                status, msg_data = "NO", None

            if status != "OK" or not msg_data:
                summaries = []
                for uid in uids:
                    summary = self._fetch_single_summary(uid)
                    if summary:
                        summaries.append(summary)
                summaries.sort(key=lambda s: uid_order.get(s.uid, 10**9))
                return summaries

            summaries: list[MailSummary] = []
            flags_map = self._fetch_flags_batch(imap, uids)
            for uid_str, _meta, header_bytes in self._parse_fetch_response(msg_data):
                flags_raw = flags_map.get(uid_str, "")
                summary = _summary_from_fetch(
                    uid_str,
                    flags_raw,
                    header_bytes,
                    self._current_folder,
                    self.classifier,
                )
                if summary:
                    summaries.append(summary)

            self._imap_resync(imap)

        summaries.sort(key=lambda s: uid_order.get(s.uid, 10**9))
        return summaries

    def sync_folder_batched(
        self,
        batch_size: int = IMAP_BATCH_SIZE,
        cancelled: Callable[[], bool] | None = None,
        on_batch: Callable[[list[MailSummary], int, int], None] | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> list[MailSummary]:
        """
        Sincroniza todos los mensajes de la carpeta activa en lotes.

        on_batch(summaries, done, total) y on_progress(done, total) son callbacks
        opcionales invocados durante la descarga.
        """
        uids = self.search_all_uids()
        total = len(uids)
        all_summaries: list[MailSummary] = []
        done = 0

        for start in range(0, total, batch_size):
            if cancelled and cancelled():
                break
            batch_uids = uids[start : start + batch_size]
            batch = self.fetch_summaries_batch(batch_uids)
            all_summaries.extend(batch)
            done = min(start + len(batch_uids), total)
            if on_batch:
                on_batch(batch, done, total)
            if on_progress:
                on_progress(done, total)

        return all_summaries

    def sync_folder_incremental(
        self,
        cached_map: dict[str, MailSummary],
        batch_size: int = IMAP_BATCH_SIZE,
        cancelled: Callable[[], bool] | None = None,
        on_batch: Callable[[list[MailSummary], int, int], None] | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> list[MailSummary]:
        """
        Sincroniza solo mensajes nuevos respecto a la caché local.

        Reutiliza resúmenes ya conocidos y elimina UIDs que ya no existen
        en el servidor, evitando volver a descargar toda la carpeta.
        """
        server_uids = self.search_all_uids()
        if (
            len(server_uids) > LARGE_FOLDER_THRESHOLD
            and not cached_map
        ):
            server_uids = server_uids[-LARGE_FOLDER_THRESHOLD:]
        server_uid_strs = [
            uid.decode("ascii", errors="replace")
            if isinstance(uid, bytes)
            else str(uid)
            for uid in server_uids
        ]
        server_uid_set = set(server_uid_strs)
        cached_uids = set(cached_map.keys())

        new_uid_bytes = [
            uid
            for uid, uid_str in zip(server_uids, server_uid_strs)
            if uid_str not in cached_uids
        ]
        total_new = len(new_uid_bytes)
        fetched: dict[str, MailSummary] = {}
        done_new = 0

        if on_progress:
            on_progress(0, total_new)

        for start in range(0, total_new, batch_size):
            if cancelled and cancelled():
                break
            batch_uids = new_uid_bytes[start : start + batch_size]
            batch = self.fetch_summaries_batch(batch_uids)
            for summary in batch:
                fetched[summary.uid] = summary
            done_new = min(start + len(batch_uids), total_new)
            if on_batch:
                on_batch(batch, done_new, total_new)
            if on_progress:
                on_progress(done_new, total_new)

        merged: list[MailSummary] = []
        for uid_str in server_uid_strs:
            if uid_str in fetched:
                merged.append(fetched[uid_str])
            elif uid_str in cached_map:
                merged.append(cached_map[uid_str])

        self._removed_uids = cached_uids - server_uid_set
        return merged

    @property
    def last_removed_uids(self) -> set[str]:
        """UIDs eliminados del servidor en la última sincronización incremental."""
        return getattr(self, "_removed_uids", set())

    def fetch_messages(self, limit: int | None = 50) -> list[MailSummary]:
        """Descarga resúmenes; si limit es None, sincroniza todos los mensajes."""
        if limit is None:
            return self.sync_folder_batched()
        uids = self.search_all_uids()
        if not uids:
            return []
        batch_uids = uids[:limit]
        return self.fetch_summaries_batch(batch_uids)

    def _uid_store(
        self,
        uid: str,
        op: str,
        flags: str,
        folder: str | None = None,
    ) -> None:
        """STORE en la carpeta correcta y restaura la selección previa."""
        target = folder or self._current_folder
        with self._imap_lock:
            self._ensure_connected_unlocked()
            imap = self._require_imap()
            previous = self._current_folder
            try:
                if target:
                    self._ensure_selected_unlocked(imap, target)
                imap.uid("store", uid, op, flags)
            finally:
                if previous and previous != target:
                    try:
                        self._select_on_imap(imap, previous)
                        self._current_folder = previous
                    except imaplib.IMAP4.error:
                        pass

    def _fetch_raw_message(
        self,
        uid: str,
        folder: str,
        *,
        mark_seen: bool = False,
    ) -> tuple[str, bytes]:
        """Descarga flags y cuerpo RFC822 con conexión nueva y reintento."""
        errors: list[Exception] = []
        with self._fetch_lock:
            for _attempt in range(2):
                try:
                    with self._imap_read_session(folder) as imap:
                        for spec in _RAW_FETCH_SPECS:
                            status, data = imap.uid("fetch", uid, spec)
                            if status != "OK" or not data:
                                continue
                            if "HEADER" in spec and "TEXT" in spec:
                                flags_raw, header, text = _extract_header_text_payload(
                                    data
                                )
                                if header:
                                    raw = header.rstrip(b"\r\n") + b"\r\n\r\n" + text
                                    self._imap_resync(imap)
                                    if mark_seen and "\\Seen" not in flags_raw:
                                        try:
                                            imap.uid("store", uid, "+FLAGS", "(\\Seen)")
                                        except imaplib.IMAP4.error:
                                            pass
                                    return flags_raw, raw
                                continue
                            flags_raw, raw = _extract_largest_payload(data)
                            if raw:
                                self._imap_resync(imap)
                                if mark_seen and "\\Seen" not in flags_raw:
                                    try:
                                        imap.uid("store", uid, "+FLAGS", "(\\Seen)")
                                    except imaplib.IMAP4.error:
                                        pass
                                return flags_raw, raw
                        raise RuntimeError(
                            f"Mensaje {uid} vacío o respuesta IMAP inválida"
                        )
                except (imaplib.IMAP4.error, RuntimeError, OSError) as exc:
                    errors.append(exc)
        last = errors[-1] if errors else RuntimeError("error desconocido")
        raise RuntimeError(
            f"No se pudo obtener el mensaje {uid}: {last}"
        ) from last

    def fetch_message(
        self,
        uid: str,
        *,
        folder: str | None = None,
        load_remote_images: bool = False,
        mark_seen: bool = True,
        openpgp: OpenPgpSettings | None = None,
    ) -> MailMessage:
        target_folder = folder or self._current_folder
        flags_raw, raw = self._fetch_raw_message(
            uid, target_folder, mark_seen=mark_seen
        )

        pgp_settings = openpgp or OpenPgpSettings()
        msg, pgp_status = process_incoming_message(
            raw, settings=pgp_settings
        )

        text, html = _extract_body(msg)
        if pgp_status.encrypted and pgp_status.error:
            text = f"[Mensaje cifrado OpenPGP]\n\n{pgp_status.error}"
            html = ""
        attachments = extract_attachments(msg)
        subject = _decode_header_value(msg.get("Subject")) or "(Sin asunto)"
        sender = _decode_header_value(msg.get("From")) or "(Sin remitente)"
        message_id = _header_value(msg, "Message-ID")
        in_reply_to = _header_value(msg, "In-Reply-To")
        references = _header_value(msg, "References")
        if html:
            html = prepare_html_for_display(
                msg, html, sender=sender, load_remote_images=load_remote_images
            )
        if not text.strip() and not html.strip():
            text = "(Sin contenido)"
        flagged = "\\Flagged" in flags_raw
        headers = self.classifier.parse_headers_from_message(msg)
        category = self.classifier.classify(
            folder=target_folder,
            subject=subject,
            sender=sender,
            flagged=flagged,
            headers=headers,
        )
        from pyqorreos.core.list_unsubscribe import parse_list_unsubscribe

        unsub = parse_list_unsubscribe(
            msg.get("List-Unsubscribe"),
            msg.get("List-Unsubscribe-Post"),
        )

        return MailMessage(
            uid=uid,
            subject=subject,
            sender=sender,
            recipients=_decode_header_value(msg.get("To")) or "",
            date=_parse_date(msg.get("Date")),
            body_text=text,
            body_html=html,
            category=category,
            attachments=attachments,
            message_id=message_id,
            in_reply_to=in_reply_to,
            references=references,
            unsubscribe_url=unsub.get("url") if isinstance(unsub.get("url"), str) else None,
            unsubscribe_mailto=unsub.get("mailto") if isinstance(unsub.get("mailto"), str) else None,
            one_click_unsubscribe=bool(unsub.get("one_click")),
            read_receipt_to=parse_read_receipt_request(msg),
            pgp=pgp_status if (pgp_status.encrypted or pgp_status.signed) else None,
        )

    def send_read_receipt(
        self,
        *,
        receipt_to: str,
        original_subject: str,
        original_message_id: str = "",
    ) -> None:
        """Envía un acuse de lectura (MDN) al remitente que lo solicitó."""
        address = receipt_to.strip()
        if not address:
            raise ValueError("No hay dirección de acuse de recibo")
        raw = build_read_receipt_bytes(
            from_email=self.account.email,
            display_name=self.account.display_name,
            receipt_to=address,
            original_subject=original_subject,
            original_message_id=original_message_id,
        )
        msg = email.message_from_bytes(raw)
        self._deliver_message(msg, [address])

    def _deliver_message(self, msg: email.message.Message, recipients: list[str]) -> None:
        if not recipients:
            raise ValueError("No hay destinatarios")
        context = _mail_ssl_context()

        use_smtp_ssl = self.account.smtp_port == 465 or (
            self.account.use_ssl and not self.account.use_starttls
        )
        if use_smtp_ssl:
            with smtplib.SMTP_SSL(
                self.account.smtp_host,
                self.account.smtp_port,
                context=context,
                timeout=SMTP_SOCKET_TIMEOUT,
            ) as server:
                self._smtp_login(server)
                server.send_message(msg, to_addrs=recipients)
        else:
            with smtplib.SMTP(
                self.account.smtp_host,
                self.account.smtp_port,
                timeout=SMTP_SOCKET_TIMEOUT,
            ) as server:
                server.ehlo()
                if self.account.use_starttls:
                    server.starttls(context=context)
                    server.ehlo()
                self._smtp_login(server)
                server.send_message(msg, to_addrs=recipients)

    def fetch_attachment_bytes(
        self, uid: str, part_index: int, folder: str | None = None
    ) -> tuple[bytes, str]:
        """Descarga el payload de un adjunto por índice de parte MIME."""
        target_folder = folder or self._current_folder
        _flags_raw, raw = self._fetch_raw_message(uid, target_folder)
        msg = email.message_from_bytes(raw)
        payload = get_attachment_payload(msg, part_index)
        if payload is None:
            raise RuntimeError("Adjunto no encontrado en el mensaje")
        attachments = extract_attachments(msg)
        filename = "adjunto"
        for att in attachments:
            if att.part_index == part_index:
                filename = att.filename
                break
        return payload, filename

    def enhance_message_html(
        self, html: str, *, uid: str | None = None, folder: str | None = None
    ) -> str:
        """Descarga imágenes remotas; si hay uid, reprocesa el MIME original."""
        from pyqorreos.core.email_html import (
            BLOCKED_IMAGE_PLACEHOLDER_MARKER,
            _base_url_from_sender,
            load_remote_images_in_html,
            prepare_html_for_display,
        )

        referer = ""
        candidates: list[str] = []

        if uid:
            try:
                _flags, raw = self._fetch_raw_message(
                    uid,
                    folder or self._current_folder or "INBOX",
                    mark_seen=False,
                )
                msg = email.message_from_bytes(raw)
                _text, raw_html = _extract_body(msg)
                sender = _decode_header_value(msg.get("From")) or ""
                referer = _base_url_from_sender(sender)
                if raw_html.strip():
                    candidates.append(
                        prepare_html_for_display(
                            msg,
                            raw_html,
                            sender=sender,
                            load_remote_images=True,
                        )
                    )
            except Exception:
                pass

        if not referer and html:
            referer = _base_url_from_sender("")

        candidates.append(load_remote_images_in_html(html, referer=referer))

        if not candidates:
            return html

        def _score(content: str) -> tuple[int, int]:
            blocked = content.count(BLOCKED_IMAGE_PLACEHOLDER_MARKER)
            return (-blocked, len(content))

        return max(candidates, key=_score)

    def send_message(
        self,
        to: str,
        subject: str,
        body: str,
        cc: str = "",
        bcc: str = "",
        body_html: str | None = None,
        attachments: list[EmailAttachment] | None = None,
        request_read_receipt: bool = False,
        *,
        openpgp_sign: bool = False,
        openpgp_encrypt: bool = False,
        openpgp_settings: OpenPgpSettings | None = None,
    ) -> None:
        msg = EmailMessage()
        from_header = (
            f"{self.account.display_name} <{self.account.email}>"
            if self.account.display_name
            else self.account.email
        )
        msg["From"] = from_header
        msg["To"] = to
        if cc:
            msg["Cc"] = cc
        msg["Subject"] = subject

        if request_read_receipt:
            apply_read_receipt_headers(
                msg,
                self.account.email,
                display_name=self.account.display_name,
            )

        plain = body or ""
        html = (body_html or "").strip()
        files = attachments or []

        if html or files:
            msg.set_content(plain, subtype="plain", charset="utf-8")
            if html:
                msg.add_alternative(html, subtype="html", charset="utf-8")
            for attachment in files:
                path = Path(attachment.path)
                if not path.is_file():
                    continue
                mime_type, _ = mimetypes.guess_type(path.name)
                maintype, subtype = (
                    mime_type.split("/", 1) if mime_type else ("application", "octet-stream")
                )
                msg.add_attachment(
                    path.read_bytes(),
                    maintype=maintype,
                    subtype=subtype,
                    filename=attachment.filename,
                )
        else:
            msg.set_content(plain, charset="utf-8")

        recipients = parse_recipient_emails(to, cc, bcc)
        pgp = openpgp_settings or OpenPgpSettings()
        if pgp.enabled and (openpgp_sign or openpgp_encrypt):
            raw_out = encrypt_outgoing_message(
                msg,
                recipients=recipients,
                sign=openpgp_sign,
                encrypt=openpgp_encrypt,
                signing_key_id=pgp.signing_key_id,
                use_system_home=pgp.use_system_gnupg_home,
            )
            msg = email.message_from_bytes(raw_out)

        recipients = [a.strip() for a in f"{to},{cc},{bcc}".split(",") if a.strip()]
        self._deliver_message(msg, recipients)

    def set_flagged(self, uid: str, flagged: bool = True, folder: str | None = None) -> None:
        """Marca o desmarca un mensaje con el flag \\Flagged (importante en IMAP)."""
        flag_op = "+FLAGS" if flagged else "-FLAGS"
        self._uid_store(uid, flag_op, "(\\Flagged)", folder)

    def set_seen(self, uid: str, seen: bool = True, folder: str | None = None) -> None:
        """Marca o desmarca un mensaje como leído (\\Seen) sin tocar la conexión principal."""
        target = folder or self._current_folder
        flag_op = "+FLAGS" if seen else "-FLAGS"
        try:
            with self._imap_read_session(target) as imap:
                imap.uid("store", uid, flag_op, "(\\Seen)")
        except (imaplib.IMAP4.error, OSError):
            pass

    def update_classifier(self, classifier: MailClassifier) -> None:
        """Actualiza las reglas de clasificación en caliente."""
        self.classifier = classifier

    def delete_message(self, uid: str, folder: str | None = None) -> None:
        self.delete_messages([uid], folder=folder)

    def delete_messages(self, uids: list[str], folder: str | None = None) -> None:
        if not uids:
            return
        target = folder or self._current_folder or "INBOX"
        with self._imap_lock:
            self._ensure_connected_unlocked()
            imap = self._require_imap()
            previous = self._current_folder
            try:
                self._ensure_selected_unlocked(imap, target)
                batch_size = 100
                for start in range(0, len(uids), batch_size):
                    chunk = uids[start : start + batch_size]
                    imap.uid("store", ",".join(chunk), "+FLAGS", "(\\Deleted)")
                imap.expunge()
            finally:
                if previous and previous != target:
                    try:
                        self._select_on_imap(imap, previous)
                        self._current_folder = previous
                    except imaplib.IMAP4.error:
                        pass

    def copy_message(
        self, uid: str, dest_folder: str, source_folder: str | None = None
    ) -> None:
        source = source_folder or self._current_folder or "INBOX"
        with self._imap_lock:
            self._ensure_connected_unlocked()
            imap = self._require_imap()
            self._ensure_selected_unlocked(imap, source)
            status, _ = imap.uid(
                "copy", uid, self._quoted_folder(dest_folder)
            )
            if status != "OK":
                raise RuntimeError(f"No se pudo copiar a {dest_folder}")

    def move_message(self, uid: str, dest_folder: str, source_folder: str | None = None) -> None:
        self.move_messages([uid], dest_folder, source_folder=source_folder)

    def move_messages(
        self,
        uids: list[str],
        dest_folder: str,
        *,
        source_folder: str | None = None,
    ) -> None:
        if not uids:
            return
        source = source_folder or self._current_folder or "INBOX"
        with self._imap_lock:
            self._ensure_connected_unlocked()
            imap = self._require_imap()
            previous = self._current_folder
            try:
                self._ensure_selected_unlocked(imap, source)
                for uid in uids:
                    status, _ = imap.uid(
                        "copy", uid, self._quoted_folder(dest_folder)
                    )
                    if status != "OK":
                        raise RuntimeError(f"No se pudo copiar a {dest_folder}")
                    imap.uid("store", uid, "+FLAGS", "(\\Deleted)")
                imap.expunge()
            finally:
                if previous and previous != source:
                    try:
                        self._select_on_imap(imap, previous)
                        self._current_folder = previous
                    except imaplib.IMAP4.error:
                        pass

    def create_folder(self, name: str, parent: str | None = None) -> str:
        """Crea una carpeta IMAP y devuelve su ruta completa."""
        part = name.strip().strip("/")
        if not part:
            raise ValueError("El nombre de la carpeta no puede estar vacío")
        if "/" in part or part in (".", ".."):
            raise ValueError("Nombre de carpeta no válido")
        full_path = f"{parent}/{part}" if parent else part
        with self._imap_lock:
            self._ensure_connected_unlocked()
            imap = self._require_imap()
            status, data = imap.create(self._quoted_folder(full_path))
        if status != "OK":
            detail = ""
            if data:
                raw = data[0] if isinstance(data, (list, tuple)) else data
                if isinstance(raw, bytes):
                    detail = raw.decode("utf-8", errors="replace")
                elif raw:
                    detail = str(raw)
            raise RuntimeError(
                f"No se pudo crear la carpeta «{full_path}»"
                + (f": {detail}" if detail else "")
            )
        return full_path

    def delete_folder(self, folder: str, *, recursive: bool = False) -> list[str]:
        """
        Elimina una carpeta IMAP y, si recursive, sus subcarpetas (de más profunda a raíz).

        Vacía cada carpeta antes de borrarla. Devuelve las rutas eliminadas.
        """
        from pyqorreos.core.folder_utils import folder_descendants, is_protected_folder

        path = folder.strip()
        if not path:
            raise ValueError("Indica una carpeta válida")
        if is_protected_folder(path):
            raise ValueError(f"La carpeta «{path}» es del sistema y no se puede eliminar")

        all_names = [f.name for f in self.list_folders()]
        descendants = folder_descendants(all_names, path)
        if descendants and not recursive:
            sample = ", ".join(descendants[:3])
            extra = "…" if len(descendants) > 3 else ""
            raise RuntimeError(
                f"La carpeta tiene subcarpetas ({sample}{extra}). "
                "Confirma la eliminación recursiva para borrarlas también."
            )

        targets = sorted({path, *descendants}, key=lambda p: (-p.count("/"), p))
        deleted: list[str] = []

        with self._imap_lock:
            self._ensure_connected_unlocked()
            imap = self._require_imap()
            for target in targets:
                if is_protected_folder(target):
                    continue
                self._select_on_imap(imap, target)
                status, data = imap.uid("search", None, "ALL")
                if status == "OK" and data and data[0]:
                    for uid in data[0].split():
                        imap.uid("store", uid, "+FLAGS", "(\\Deleted)")
                    imap.expunge()
                status, data = imap.delete(self._quoted_folder(target))
                if status != "OK":
                    detail = ""
                    if data:
                        raw = data[0] if isinstance(data, (list, tuple)) else data
                        if isinstance(raw, bytes):
                            detail = raw.decode("utf-8", errors="replace")
                        elif raw:
                            detail = str(raw)
                    raise RuntimeError(
                        f"No se pudo eliminar la carpeta «{target}»"
                        + (f": {detail}" if detail else "")
                    )
                deleted.append(target)

        if self._current_folder in deleted or any(
            self._current_folder.startswith(d + "/") for d in deleted
        ):
            self._current_folder = "INBOX"
        return deleted

    def rename_folder(self, folder: str, new_name: str) -> list[tuple[str, str]]:
        """
        Renombra una carpeta IMAP conservando su carpeta padre.

        Devuelve la lista de pares (ruta_antigua, ruta_nueva) afectados,
        incluidas las subcarpetas que el servidor renombra en cascada.
        """
        from pyqorreos.core.folder_utils import folder_descendants, is_protected_folder

        path = folder.strip()
        if not path:
            raise ValueError("Indica una carpeta válida")
        if is_protected_folder(path):
            raise ValueError(
                f"La carpeta «{path}» es del sistema y no se puede renombrar"
            )

        leaf = new_name.strip().strip("/")
        if not leaf:
            raise ValueError("El nombre de la carpeta no puede estar vacío")
        if "/" in leaf or leaf in (".", ".."):
            raise ValueError("Nombre de carpeta no válido")

        parent = path.rsplit("/", 1)[0] if "/" in path else ""
        new_path = f"{parent}/{leaf}" if parent else leaf
        if new_path == path:
            return []

        all_names = [f.name for f in self.list_folders()]
        if new_path in all_names:
            raise RuntimeError(f"Ya existe una carpeta «{new_path}»")

        descendants = folder_descendants(all_names, path)

        with self._imap_lock:
            self._ensure_connected_unlocked()
            imap = self._require_imap()
            status, data = imap.rename(
                self._quoted_folder(path), self._quoted_folder(new_path)
            )
            if status != "OK":
                detail = ""
                if data:
                    raw = data[0] if isinstance(data, (list, tuple)) else data
                    if isinstance(raw, bytes):
                        detail = raw.decode("utf-8", errors="replace")
                    elif raw:
                        detail = str(raw)
                raise RuntimeError(
                    f"No se pudo renombrar la carpeta «{path}»"
                    + (f": {detail}" if detail else "")
                )

        # El servidor renombra las subcarpetas en cascada; reflejamos el mismo cambio.
        mapping = [(path, new_path)]
        for child in descendants:
            mapping.append((child, new_path + child[len(path):]))

        if self._current_folder == path or self._current_folder.startswith(path + "/"):
            self._current_folder = new_path + self._current_folder[len(path):]
        return mapping

    def empty_folder(self, folder: str) -> int:
        """Marca todos los mensajes de una carpeta como eliminados y expunge."""
        with self._imap_lock:
            self._ensure_connected_unlocked()
            imap = self._require_imap()
            self._select_on_imap(imap, folder)
            status, data = imap.uid("search", None, "ALL")
            if status != "OK" or not data or not data[0]:
                return 0
            uid_list = data[0].split()
            for uid in uid_list:
                imap.uid("store", uid, "+FLAGS", "(\\Deleted)")
            imap.expunge()
            return len(uid_list)

    def get_folder_unread_counts(self, folders: list[str]) -> dict[str, int]:
        """Devuelve el número de no leídos por carpeta (IMAP STATUS)."""
        counts: dict[str, int] = {}
        with self._imap_lock:
            self._ensure_connected_unlocked()
            imap = self._require_imap()
            for folder in folders:
                try:
                    status, data = imap.status(
                        self._quoted_folder(folder), "(UNSEEN)"
                    )
                    if status == "OK" and data:
                        line = data[0].decode("utf-8", errors="replace")
                        match = re.search(r"UNSEEN\s+(\d+)", line)
                        counts[folder] = int(match.group(1)) if match else 0
                    else:
                        counts[folder] = 0
                except imaplib.IMAP4.error:
                    counts[folder] = 0
        return counts

    def get_folder_total_counts(self, folders: list[str]) -> dict[str, int]:
        """Devuelve el número total de mensajes por carpeta (IMAP STATUS MESSAGES)."""
        counts: dict[str, int] = {}
        with self._imap_lock:
            self._ensure_connected_unlocked()
            imap = self._require_imap()
            for folder in folders:
                try:
                    status, data = imap.status(
                        self._quoted_folder(folder), "(MESSAGES)"
                    )
                    if status == "OK" and data:
                        line = data[0].decode("utf-8", errors="replace")
                        match = re.search(r"MESSAGES\s+(\d+)", line)
                        counts[folder] = int(match.group(1)) if match else 0
                    else:
                        counts[folder] = 0
                except imaplib.IMAP4.error:
                    counts[folder] = 0
        return counts

    def save_draft(self, folder: str, raw_message: bytes) -> None:
        """Guarda un borrador en la carpeta IMAP indicada (APPEND)."""
        with self._imap_lock:
            self._ensure_connected_unlocked()
            imap = self._require_imap()
            status, _ = imap.append(
                self._quoted_folder(folder),
                "\\Draft",
                None,
                raw_message,
            )
            if status != "OK":
                raise RuntimeError(f"No se pudo guardar borrador en {folder}")

    def fetch_raw_bytes(self, uid: str, folder: str | None = None) -> bytes:
        """Devuelve el mensaje completo en formato RFC822."""
        target = folder or self._current_folder
        _flags, raw = self._fetch_raw_message(uid, target, mark_seen=False)
        return raw

    def get_storage_quota(self) -> tuple[int, int] | None:
        """
        Consulta cuota IMAP (GETQUOTAROOT / GETQUOTA).

        Devuelve (bytes_usados, bytes_límite) o None si el servidor no lo soporta.
        """
        with self._imap_lock:
            self._ensure_connected_unlocked()
            imap = self._require_imap()
            try:
                status, data = imap.getquotaroot(self._quoted_folder("INBOX"))
            except imaplib.IMAP4.error:
                return None
            if status != "OK" or not data:
                return None

            roots: list[str] = []
            for item in data:
                if not isinstance(item, bytes):
                    continue
                text = item.decode("utf-8", errors="replace")
                for part in text.replace("(", " ").replace(")", " ").split():
                    if part.startswith('"') and part.endswith('"'):
                        roots.append(part.strip('"'))

            for root in roots:
                try:
                    q_status, q_data = imap.getquota(f'"{root}"')
                except imaplib.IMAP4.error:
                    continue
                if q_status != "OK" or not q_data:
                    continue
                for line in q_data:
                    if not isinstance(line, bytes):
                        continue
                    decoded = line.decode("utf-8", errors="replace")
                    match = re.search(
                        r"STORAGE\s+(\d+)\s+(\d+)", decoded, re.IGNORECASE
                    )
                    if match:
                        return int(match.group(1)), int(match.group(2))
            return None

    def wait_for_idle_updates(
        self,
        folder: str,
        timeout_sec: int = 300,
        *,
        cancelled: Callable[[], bool] | None = None,
        poll_sec: int = 30,
    ) -> bool:
        """
        Espera notificaciones IMAP IDLE (nuevos mensajes).
        Devuelve True si hubo actividad, False si timeout o no soportado.
        """
        import select
        import time

        imap = self._new_imap_connection()
        try:
            self._select_on_imap(imap, folder)
            tag = imap._new_tag().decode("ascii")
            imap.send(f"{tag} IDLE\r\n".encode())
            while True:
                line = imap.readline()
                if not line:
                    return False
                if line.startswith(b"+ idling"):
                    break
            sock = imap.socket()
            if sock is None:
                imap.send(b"DONE\r\n")
                return False
            deadline = time.monotonic() + timeout_sec
            readable = False
            while time.monotonic() < deadline:
                if cancelled and cancelled():
                    break
                wait = min(poll_sec, max(1.0, deadline - time.monotonic()))
                ready, _, _ = select.select([sock], [], [], wait)
                if ready:
                    readable = True
                    break
            imap.send(b"DONE\r\n")
            while True:
                line = imap.readline()
                if not line:
                    break
                if line.startswith(tag.encode("ascii")):
                    break
            return readable
        except (imaplib.IMAP4.error, OSError, AttributeError, ValueError):
            return False
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    def test_smtp(self) -> tuple[bool, str]:
        """Comprueba login SMTP sin enviar correo."""
        context = _mail_ssl_context()
        use_smtp_ssl = self.account.smtp_port == 465 or (
            self.account.use_ssl and not self.account.use_starttls
        )
        try:
            if use_smtp_ssl:
                with smtplib.SMTP_SSL(
                    self.account.smtp_host,
                    self.account.smtp_port,
                    context=context,
                    timeout=SMTP_SOCKET_TIMEOUT,
                ) as server:
                    self._smtp_login(server)
            else:
                with smtplib.SMTP(
                    self.account.smtp_host,
                    self.account.smtp_port,
                    timeout=SMTP_SOCKET_TIMEOUT,
                ) as server:
                    server.ehlo()
                    if self.account.use_starttls:
                        server.starttls(context=context)
                        server.ehlo()
                    self._smtp_login(server)
            return True, "SMTP correcto"
        except Exception as exc:
            return False, friendly_mail_error(exc)

    def test_connection(self) -> tuple[bool, str]:
        try:
            self.connect()
            self.list_folders()
            self.disconnect()
        except Exception as exc:
            return False, f"IMAP: {friendly_mail_error(exc)}"
        smtp_ok, smtp_msg = self.test_smtp()
        if not smtp_ok:
            return False, f"IMAP correcto, pero SMTP falló: {smtp_msg}"
        return True, "Conexión IMAP y SMTP correcta"