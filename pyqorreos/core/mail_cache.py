"""
Caché local SQLite de cabeceras y cuerpos de correo.

Permite mostrar mensajes al instante, reabrir correos sin IMAP
y sincronizar solo mensajes nuevos con el servidor.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from pyqorreos.core.classifier import MailCategory
from pyqorreos.core.mail_service import MailMessage, MailSummary, normalize_mail_datetime
from pyqorreos.core.message_attachments import MailAttachmentInfo
from pyqorreos.core.settings import CONFIG_DIR

CACHE_DB = CONFIG_DIR / "mail_cache.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    account_id TEXT NOT NULL,
    folder TEXT NOT NULL,
    uid TEXT NOT NULL,
    subject TEXT NOT NULL,
    sender TEXT NOT NULL,
    date_iso TEXT,
    seen INTEGER NOT NULL DEFAULT 0,
    flagged INTEGER NOT NULL DEFAULT 0,
    category TEXT NOT NULL DEFAULT 'normal',
    sort_index INTEGER NOT NULL DEFAULT 0,
    has_attachments INTEGER NOT NULL DEFAULT 0,
    message_id TEXT NOT NULL DEFAULT '',
    thread_key TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (account_id, folder, uid)
);
CREATE INDEX IF NOT EXISTS idx_messages_folder
    ON messages(account_id, folder, sort_index);

CREATE TABLE IF NOT EXISTS message_bodies (
    account_id TEXT NOT NULL,
    folder TEXT NOT NULL,
    uid TEXT NOT NULL,
    subject TEXT NOT NULL,
    sender TEXT NOT NULL,
    recipients TEXT NOT NULL DEFAULT '',
    date_iso TEXT,
    body_text TEXT NOT NULL DEFAULT '',
    body_html TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'normal',
    attachments_json TEXT NOT NULL DEFAULT '[]',
    message_id TEXT NOT NULL DEFAULT '',
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (account_id, folder, uid)
);
"""


class MailCache:
    """Almacén local de resúmenes y cuerpos de correo por cuenta y carpeta."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or CACHE_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA cache_size=-64000")
        return conn

    @staticmethod
    def _summary_from_row(row: sqlite3.Row) -> MailSummary:
        date_val = None
        if row["date_iso"]:
            try:
                date_val = normalize_mail_datetime(
                    datetime.fromisoformat(row["date_iso"])
                )
            except ValueError:
                pass
        return MailSummary(
            uid=row["uid"],
            subject=row["subject"],
            sender=row["sender"],
            date=date_val,
            seen=bool(row["seen"]),
            flagged=bool(row["flagged"]),
            category=MailCategory(row["category"]),
            has_attachments=bool(row["has_attachments"]),
            message_id=row["message_id"] or "",
            thread_key=row["thread_key"] or "",
        )

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            self._migrate_schema(conn)

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        """Añade columnas nuevas en bases de datos existentes."""
        msg_cols = {row[1] for row in conn.execute("PRAGMA table_info(messages)")}
        for col, ddl in (
            ("has_attachments", "INTEGER NOT NULL DEFAULT 0"),
            ("message_id", "TEXT NOT NULL DEFAULT ''"),
            ("thread_key", "TEXT NOT NULL DEFAULT ''"),
        ):
            if col not in msg_cols:
                conn.execute(f"ALTER TABLE messages ADD COLUMN {col} {ddl}")
        body_cols = {row[1] for row in conn.execute("PRAGMA table_info(message_bodies)")}
        for col, ddl in (
            ("attachments_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("message_id", "TEXT NOT NULL DEFAULT ''"),
        ):
            if col not in body_cols:
                conn.execute(f"ALTER TABLE message_bodies ADD COLUMN {col} {ddl}")

    def clear_folder(self, account_id: str, folder: str) -> None:
        """Elimina todos los mensajes en caché de una carpeta."""
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM messages WHERE account_id = ? AND folder = ?",
                (account_id, folder),
            )
            conn.execute(
                "DELETE FROM message_bodies WHERE account_id = ? AND folder = ?",
                (account_id, folder),
            )

    def get_cached_uids(self, account_id: str, folder: str) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT uid FROM messages WHERE account_id = ? AND folder = ?",
                (account_id, folder),
            ).fetchall()
        return {row["uid"] for row in rows}

    def remove_uids(self, account_id: str, folder: str, uids: set[str]) -> None:
        if not uids:
            return
        placeholders = ",".join("?" * len(uids))
        params = [account_id, folder, *uids]
        with self._connect() as conn:
            conn.execute(
                f"DELETE FROM messages WHERE account_id = ? AND folder = ? AND uid IN ({placeholders})",
                params,
            )
            conn.execute(
                f"DELETE FROM message_bodies WHERE account_id = ? AND folder = ? AND uid IN ({placeholders})",
                params,
            )

    def save_batch(
        self,
        account_id: str,
        folder: str,
        summaries: list[MailSummary],
        start_index: int,
    ) -> None:
        """Guarda un lote de resúmenes manteniendo el orden de sincronización."""
        rows = []
        for offset, summary in enumerate(summaries):
            date_iso = summary.date.isoformat() if summary.date else None
            rows.append(
                (
                    account_id,
                    folder,
                    summary.uid,
                    summary.subject,
                    summary.sender,
                    date_iso,
                    int(summary.seen),
                    int(summary.flagged),
                    summary.category.value,
                    start_index + offset,
                    int(summary.has_attachments),
                    summary.message_id,
                    summary.thread_key,
                )
            )
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO messages
                (account_id, folder, uid, subject, sender, date_iso,
                 seen, flagged, category, sort_index,
                 has_attachments, message_id, thread_key)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def save_folder_ordered(
        self, account_id: str, folder: str, summaries: list[MailSummary]
    ) -> None:
        """Reescribe la carpeta en caché con el orden canónico del servidor."""
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM messages WHERE account_id = ? AND folder = ?",
                (account_id, folder),
            )
            rows = []
            for index, summary in enumerate(summaries):
                date_iso = summary.date.isoformat() if summary.date else None
                rows.append(
                    (
                        account_id,
                        folder,
                        summary.uid,
                        summary.subject,
                        summary.sender,
                        date_iso,
                        int(summary.seen),
                        int(summary.flagged),
                        summary.category.value,
                        index,
                        int(summary.has_attachments),
                        summary.message_id,
                        summary.thread_key,
                    )
                )
            if rows:
                conn.executemany(
                    """
                    INSERT INTO messages
                    (account_id, folder, uid, subject, sender, date_iso,
                     seen, flagged, category, sort_index,
                     has_attachments, message_id, thread_key)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )

    def load_folder(self, account_id: str, folder: str) -> list[MailSummary]:
        """Carga todos los resúmenes de una carpeta ordenados por sort_index."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT uid, subject, sender, date_iso, seen, flagged, category,
                       has_attachments, message_id, thread_key
                FROM messages
                WHERE account_id = ? AND folder = ?
                ORDER BY sort_index ASC
                """,
                (account_id, folder),
            ).fetchall()
        return [self._summary_from_row(row) for row in rows]

    def folder_count(self, account_id: str, folder: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS n FROM messages
                WHERE account_id = ? AND folder = ?
                """,
                (account_id, folder),
            ).fetchone()
        return int(row["n"]) if row else 0

    def query_summaries(
        self,
        account_id: str,
        folder: str,
        *,
        query: str = "",
        category: str | None = None,
        unread_only: bool = False,
        sort_by: str = "date_desc",
    ) -> list[MailSummary]:
        """Filtra y ordena en SQLite (búsqueda rápida sin recorrer toda la lista en Python)."""
        clauses = ["account_id = ?", "folder = ?"]
        params: list[object] = [account_id, folder]
        q = query.strip()
        if q:
            like = f"%{q}%"
            clauses.append(
                "(subject LIKE ? COLLATE NOCASE OR sender LIKE ? COLLATE NOCASE)"
            )
            params.extend([like, like])
        if category:
            clauses.append("category = ?")
            params.append(category)
        if unread_only:
            clauses.append("seen = 0")
        order_sql = {
            "date_asc": "COALESCE(date_iso, '') ASC, sort_index ASC",
            "sender": "LOWER(sender) ASC, sort_index ASC",
            "subject": "LOWER(subject) ASC, sort_index ASC",
        }.get(sort_by, "COALESCE(date_iso, '') DESC, sort_index ASC")
        sql = f"""
            SELECT uid, subject, sender, date_iso, seen, flagged, category,
                   has_attachments, message_id, thread_key
            FROM messages
            WHERE {' AND '.join(clauses)}
            ORDER BY {order_sql}
        """
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._summary_from_row(row) for row in rows]

    def search_summaries(
        self,
        account_id: str,
        folder: str,
        query: str,
        *,
        unread_only: bool = False,
    ) -> list[MailSummary]:
        """Búsqueda simple en asunto y remitente (caché local)."""
        return self.query_summaries(
            account_id,
            folder,
            query=query,
            unread_only=unread_only,
        )

    def update_category(
        self, account_id: str, folder: str, uid: str, category: MailCategory
    ) -> None:
        """Actualiza la categoría de un mensaje en caché."""
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE messages SET category = ?
                WHERE account_id = ? AND folder = ? AND uid = ?
                """,
                (category.value, account_id, folder, uid),
            )

    def update_seen(
        self, account_id: str, folder: str, uid: str, seen: bool
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE messages SET seen = ?
                WHERE account_id = ? AND folder = ? AND uid = ?
                """,
                (int(seen), account_id, folder, uid),
            )

    def save_message_body(
        self, account_id: str, folder: str, message: MailMessage
    ) -> None:
        date_iso = message.date.isoformat() if message.date else None
        att_json = json.dumps(
            [a.to_dict() for a in (message.attachments or [])],
            ensure_ascii=False,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO message_bodies
                (account_id, folder, uid, subject, sender, recipients, date_iso,
                 body_text, body_html, category, attachments_json, message_id, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    account_id,
                    folder,
                    message.uid,
                    message.subject,
                    message.sender,
                    message.recipients,
                    date_iso,
                    message.body_text,
                    message.body_html,
                    message.category.value,
                    att_json,
                    message.message_id,
                    datetime.now().isoformat(),
                ),
            )

    def load_message_body(
        self, account_id: str, folder: str, uid: str
    ) -> MailMessage | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT uid, subject, sender, recipients, date_iso,
                       body_text, body_html, category, attachments_json, message_id
                FROM message_bodies
                WHERE account_id = ? AND folder = ? AND uid = ?
                """,
                (account_id, folder, uid),
            ).fetchone()
        if not row:
            return None
        date_val = None
        if row["date_iso"]:
            try:
                date_val = normalize_mail_datetime(
                    datetime.fromisoformat(row["date_iso"])
                )
            except ValueError:
                pass
        attachments: list[MailAttachmentInfo] = []
        try:
            raw_att = row["attachments_json"] or "[]"
            attachments = [MailAttachmentInfo.from_dict(a) for a in json.loads(raw_att)]
        except (json.JSONDecodeError, TypeError, KeyError):
            attachments = []
        return MailMessage(
            uid=row["uid"],
            subject=row["subject"],
            sender=row["sender"],
            recipients=row["recipients"],
            date=date_val,
            body_text=row["body_text"],
            body_html=row["body_html"],
            category=MailCategory(row["category"]),
            attachments=attachments,
            message_id=row["message_id"] or "",
        )

    def delete_message(self, account_id: str, folder: str, uid: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM messages WHERE account_id = ? AND folder = ? AND uid = ?",
                (account_id, folder, uid),
            )
            conn.execute(
                "DELETE FROM message_bodies WHERE account_id = ? AND folder = ? AND uid = ?",
                (account_id, folder, uid),
            )

    def delete_account(self, account_id: str) -> None:
        """Elimina toda la caché de una cuenta."""
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM messages WHERE account_id = ?",
                (account_id,),
            )
            conn.execute(
                "DELETE FROM message_bodies WHERE account_id = ?",
                (account_id,),
            )
