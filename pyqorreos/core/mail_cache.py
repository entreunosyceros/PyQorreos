"""
Caché local SQLite de cabeceras y cuerpos de correo.

Permite mostrar mensajes al instante, reabrir correos sin IMAP
y sincronizar solo mensajes nuevos con el servidor.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from pyqorreos.core.classifier import MailCategory
from pyqorreos.core.mail_service import MailMessage, MailSummary, normalize_mail_datetime
from pyqorreos.core.message_attachments import MailAttachmentInfo
from pyqorreos.core.openpgp import PgpStatus
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

CREATE TABLE IF NOT EXISTS account_folders (
    account_id TEXT PRIMARY KEY,
    folders_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class MailCache:
    """Almacén local de resúmenes y cuerpos de correo por cuenta y carpeta."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or CACHE_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._fts_available = False
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        # WAL permite lectura concurrente mientras se escribe, pero en ráfagas de escrituras
        # desde varios hilos SQLite puede necesitar esperar al lock. Un timeout alto evita
        # fallos esporádicos de "database is locked" sin penalizar el caso normal.
        conn = sqlite3.connect(self.db_path, timeout=20.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=20000")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA cache_size=-64000")
        return conn

    @staticmethod
    def _summary_from_row(row: sqlite3.Row, *, folder: str = "") -> MailSummary:
        date_val = None
        if row["date_iso"]:
            try:
                date_val = normalize_mail_datetime(
                    datetime.fromisoformat(row["date_iso"])
                )
            except ValueError:
                pass
        row_folder = folder
        if not row_folder and "folder" in row.keys():
            row_folder = row["folder"] or ""
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
            folder=row_folder,
        )

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            self._migrate_schema(conn)
            self._init_fts(conn)

    def _init_fts(self, conn: sqlite3.Connection) -> None:
        """Crea el índice FTS5 para buscar en el cuerpo (si el motor lo soporta)."""
        try:
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS message_fts USING fts5(
                    account_id UNINDEXED,
                    folder UNINDEXED,
                    uid UNINDEXED,
                    subject,
                    sender,
                    body,
                    tokenize = 'unicode61 remove_diacritics 2'
                )
                """
            )
            self._fts_available = True
        except sqlite3.OperationalError:
            # SQLite compilado sin FTS5: la búsqueda en el cuerpo usará LIKE.
            self._fts_available = False

    @staticmethod
    def _fts_match_query(query: str) -> str:
        """Convierte el texto del usuario en una consulta MATCH segura para FTS5."""
        terms = [t for t in re.split(r"\s+", query.strip()) if t]
        parts: list[str] = []
        for term in terms:
            escaped = term.replace('"', '""')
            parts.append(f'"{escaped}"*')
        return " ".join(parts)

    def _fts_upsert(
        self, conn: sqlite3.Connection, account_id: str, folder: str, message: MailMessage
    ) -> None:
        if not self._fts_available:
            return
        conn.execute(
            "DELETE FROM message_fts WHERE account_id = ? AND folder = ? AND uid = ?",
            (account_id, folder, message.uid),
        )
        conn.execute(
            """
            INSERT INTO message_fts (account_id, folder, uid, subject, sender, body)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                account_id,
                folder,
                message.uid,
                message.subject or "",
                message.sender or "",
                message.body_text or "",
            ),
        )

    def _fts_delete(
        self,
        conn: sqlite3.Connection,
        account_id: str,
        folder: str | None = None,
        uids: set[str] | None = None,
    ) -> None:
        if not self._fts_available:
            return
        sql = "DELETE FROM message_fts WHERE account_id = ?"
        params: list[object] = [account_id]
        if folder is not None:
            sql += " AND folder = ?"
            params.append(folder)
        if uids:
            placeholders = ",".join("?" * len(uids))
            sql += f" AND uid IN ({placeholders})"
            params.extend(uids)
        conn.execute(sql, params)

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
            ("read_receipt_to", "TEXT NOT NULL DEFAULT ''"),
            ("pgp_json", "TEXT NOT NULL DEFAULT ''"),
        ):
            if col not in body_cols:
                conn.execute(f"ALTER TABLE message_bodies ADD COLUMN {col} {ddl}")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS account_folders (
                account_id TEXT PRIMARY KEY,
                folders_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    def save_account_folders(self, account_id: str, folders: list[str]) -> None:
        """Guarda la lista de carpetas IMAP conocidas para una cuenta."""
        names = sorted({f.strip() for f in folders if f and f.strip()})
        if "INBOX" not in names:
            names.insert(0, "INBOX")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO account_folders
                (account_id, folders_json, updated_at)
                VALUES (?, ?, ?)
                """,
                (
                    account_id,
                    json.dumps(names, ensure_ascii=False),
                    datetime.now().isoformat(),
                ),
            )

    def load_account_folders(self, account_id: str) -> list[str]:
        """Devuelve carpetas en caché (lista guardada o inferida de mensajes locales)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT folders_json FROM account_folders WHERE account_id = ?",
                (account_id,),
            ).fetchone()
        folders: list[str] = []
        if row and row["folders_json"]:
            try:
                raw = json.loads(row["folders_json"])
                if isinstance(raw, list):
                    folders = [str(name) for name in raw if str(name).strip()]
            except (json.JSONDecodeError, TypeError):
                folders = []
        if not folders:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT DISTINCT folder FROM messages WHERE account_id = ?
                    UNION
                    SELECT DISTINCT folder FROM message_bodies WHERE account_id = ?
                    """,
                    (account_id, account_id),
                ).fetchall()
            folders = [row["folder"] for row in rows if row["folder"]]
        names = sorted({name.strip() for name in folders if name and name.strip()})
        if "INBOX" not in names:
            names.insert(0, "INBOX")
        return names

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
            self._fts_delete(conn, account_id, folder)

    def rename_folder(self, account_id: str, old_folder: str, new_folder: str) -> None:
        """Actualiza la ruta de una carpeta en la caché local (mensajes y cuerpos)."""
        if not old_folder or not new_folder or old_folder == new_folder:
            return
        with self._connect() as conn:
            for table in ("messages", "message_bodies"):
                conn.execute(
                    f"UPDATE {table} SET folder = ? "
                    f"WHERE account_id = ? AND folder = ?",
                    (new_folder, account_id, old_folder),
                )
            if self._fts_available:
                conn.execute(
                    "UPDATE message_fts SET folder = ? "
                    "WHERE account_id = ? AND folder = ?",
                    (new_folder, account_id, old_folder),
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
            self._fts_delete(conn, account_id, folder, set(uids))

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
        return [self._summary_from_row(row, folder=folder) for row in rows]

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

    def folder_unread_counts(
        self, account_id: str, folders: list[str] | None = None
    ) -> dict[str, int]:
        """Devuelve no leídos por carpeta desde la caché local (por cuenta)."""
        with self._connect() as conn:
            if folders:
                placeholders = ",".join("?" * len(folders))
                rows = conn.execute(
                    f"""
                    SELECT folder, COUNT(*) AS n FROM messages
                    WHERE account_id = ? AND seen = 0 AND folder IN ({placeholders})
                    GROUP BY folder
                    """,
                    [account_id, *folders],
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT folder, COUNT(*) AS n FROM messages
                    WHERE account_id = ? AND seen = 0
                    GROUP BY folder
                    """,
                    (account_id,),
                ).fetchall()
        return {str(row["folder"]): int(row["n"]) for row in rows}

    def folder_total_counts(
        self, account_id: str, folders: list[str] | None = None
    ) -> dict[str, int]:
        """Devuelve el total de mensajes por carpeta desde la caché local (por cuenta)."""
        with self._connect() as conn:
            if folders:
                placeholders = ",".join("?" * len(folders))
                rows = conn.execute(
                    f"""
                    SELECT folder, COUNT(*) AS n FROM messages
                    WHERE account_id = ? AND folder IN ({placeholders})
                    GROUP BY folder
                    """,
                    [account_id, *folders],
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT folder, COUNT(*) AS n FROM messages
                    WHERE account_id = ?
                    GROUP BY folder
                    """,
                    (account_id,),
                ).fetchall()
        return {str(row["folder"]): int(row["n"]) for row in rows}

    def _search_body_keys(
        self, account_id: str, folder: str | None, query: str
    ) -> list[tuple[str, str]]:
        """Devuelve pares (carpeta, uid) cuyo cuerpo/asunto/remitente coincide.

        Usa FTS5 cuando está disponible y, si falla o no existe, recurre a LIKE
        sobre la tabla de cuerpos en caché.
        """
        q = query.strip()
        if not q:
            return []
        if self._fts_available:
            match = self._fts_match_query(q)
            if match:
                sql = (
                    "SELECT folder, uid FROM message_fts "
                    "WHERE message_fts MATCH ? AND account_id = ?"
                )
                params: list[object] = [match, account_id]
                if folder is not None:
                    sql += " AND folder = ?"
                    params.append(folder)
                try:
                    with self._connect() as conn:
                        rows = conn.execute(sql, params).fetchall()
                    return [(str(r["folder"]), str(r["uid"])) for r in rows]
                except sqlite3.OperationalError:
                    pass
        like = f"%{q}%"
        sql = (
            "SELECT folder, uid FROM message_bodies WHERE account_id = ? "
            "AND (subject LIKE ? COLLATE NOCASE OR sender LIKE ? COLLATE NOCASE "
            "OR body_text LIKE ? COLLATE NOCASE)"
        )
        params = [account_id, like, like, like]
        if folder is not None:
            sql += " AND folder = ?"
            params.append(folder)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [(str(r["folder"]), str(r["uid"])) for r in rows]

    def query_summaries(
        self,
        account_id: str,
        folder: str | None,
        *,
        query: str = "",
        category: str | None = None,
        unread_only: bool = False,
        flagged_only: bool = False,
        sort_by: str = "date_desc",
        search_body: bool = False,
    ) -> list[MailSummary]:
        """Filtra y ordena en SQLite (búsqueda rápida sin recorrer toda la lista en Python)."""
        clauses = ["account_id = ?"]
        params: list[object] = [account_id]
        if folder is not None:
            clauses.append("folder = ?")
            params.append(folder)
        q = query.strip()
        if q and search_body:
            keys = self._search_body_keys(account_id, folder, q)
            if not keys:
                return []
            tuples_sql = ",".join(["(?,?)"] * len(keys))
            clauses.append(f"(folder, uid) IN (VALUES {tuples_sql})")
            for key_folder, key_uid in keys:
                params.extend([key_folder, key_uid])
        elif q:
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
        if flagged_only:
            clauses.append("flagged = 1")
        order_sql = {
            "date_asc": "COALESCE(date_iso, '') ASC, sort_index ASC",
            "sender": "LOWER(sender) ASC, sort_index ASC",
            "subject": "LOWER(subject) ASC, sort_index ASC",
        }.get(sort_by, "COALESCE(date_iso, '') DESC, sort_index ASC")
        folder_col = ", folder" if folder is None else ""
        sql = f"""
            SELECT uid, subject, sender, date_iso, seen, flagged, category,
                   has_attachments, message_id, thread_key{folder_col}
            FROM messages
            WHERE {' AND '.join(clauses)}
            ORDER BY {order_sql}
        """
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        default_folder = folder or ""
        return [
            self._summary_from_row(row, folder=default_folder) for row in rows
        ]

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

    def mark_folder_seen(self, account_id: str, folder: str, seen: bool = True) -> int:
        """Marca como leídos (o no leídos) todos los mensajes de una carpeta.

        Devuelve el número de mensajes cuyo estado cambió.
        """
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE messages SET seen = ?
                WHERE account_id = ? AND folder = ? AND seen = ?
                """,
                (int(seen), account_id, folder, int(not seen)),
            )
            return cursor.rowcount or 0

    def update_flagged(
        self, account_id: str, folder: str, uid: str, flagged: bool
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE messages SET flagged = ?
                WHERE account_id = ? AND folder = ? AND uid = ?
                """,
                (int(flagged), account_id, folder, uid),
            )

    def save_message_body(
        self, account_id: str, folder: str, message: MailMessage
    ) -> None:
        date_iso = message.date.isoformat() if message.date else None
        att_json = json.dumps(
            [a.to_dict() for a in (message.attachments or [])],
            ensure_ascii=False,
        )
        pgp_json = (
            json.dumps(message.pgp.to_dict(), ensure_ascii=False)
            if message.pgp
            else ""
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO message_bodies
                (account_id, folder, uid, subject, sender, recipients, date_iso,
                 body_text, body_html, category, attachments_json, message_id,
                 read_receipt_to, fetched_at, pgp_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    message.read_receipt_to or "",
                    datetime.now().isoformat(),
                    pgp_json,
                ),
            )
            self._fts_upsert(conn, account_id, folder, message)

    def load_message_body(
        self, account_id: str, folder: str, uid: str
    ) -> MailMessage | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT uid, subject, sender, recipients, date_iso,
                       body_text, body_html, category, attachments_json, message_id,
                       read_receipt_to, pgp_json
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
        pgp = None
        if "pgp_json" in row.keys() and row["pgp_json"]:
            try:
                pgp = PgpStatus.from_dict(json.loads(row["pgp_json"]))
            except (json.JSONDecodeError, TypeError):
                pgp = None
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
            read_receipt_to=row["read_receipt_to"] or "",
            pgp=pgp,
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
            self._fts_delete(conn, account_id, folder, {uid})

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
            conn.execute(
                "DELETE FROM account_folders WHERE account_id = ?",
                (account_id,),
            )
            self._fts_delete(conn, account_id)
