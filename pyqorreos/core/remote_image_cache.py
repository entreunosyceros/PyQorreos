"""
Caché persistente de imágenes remotas (directorio + índice SQLite).
"""

from __future__ import annotations

import base64
import hashlib
import sqlite3
import time
from pathlib import Path

from pyqorreos.core.settings import CONFIG_DIR

CACHE_DIR = CONFIG_DIR / "remote_image_cache"
DB_PATH = CONFIG_DIR / "remote_image_cache.db"

_cache: RemoteImageCache | None = None


class RemoteImageCache:
    """Almacena bytes de imágenes en disco e indexa por URL normalizada."""

    def __init__(
        self,
        db_path: Path = DB_PATH,
        cache_dir: Path = CACHE_DIR,
    ) -> None:
        self._db_path = db_path
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS remote_images (
                    url_hash TEXT PRIMARY KEY,
                    url TEXT NOT NULL UNIQUE,
                    content_type TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    fetched_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_remote_images_url ON remote_images(url)"
            )

    @staticmethod
    def url_hash(url: str) -> str:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    def _row_for_url(self, url: str) -> tuple[str, str, str] | None:
        url_hash = self.url_hash(url)
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT content_type, file_name, url FROM remote_images WHERE url_hash = ?",
                (url_hash,),
            ).fetchone()
        if not row:
            return None
        content_type, file_name, stored_url = row
        path = self._cache_dir / file_name
        if not path.is_file():
            self._delete_row(url_hash)
            return None
        return content_type, stored_url, str(path)

    def _delete_row(self, url_hash: str) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM remote_images WHERE url_hash = ?", (url_hash,))

    def get_data_url(self, url: str) -> str | None:
        row = self._row_for_url(url)
        if not row:
            return None
        content_type, _, path = row
        try:
            data = Path(path).read_bytes()
        except OSError:
            return None
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:{content_type};base64,{encoded}"

    def put(self, url: str, data: bytes, content_type: str) -> str:
        url_hash = self.url_hash(url)
        ext = _extension_for_content_type(content_type)
        file_name = f"{url_hash}{ext}"
        path = self._cache_dir / file_name
        path.write_bytes(data)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO remote_images (url_hash, url, content_type, file_name, fetched_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(url_hash) DO UPDATE SET
                    url = excluded.url,
                    content_type = excluded.content_type,
                    file_name = excluded.file_name,
                    fetched_at = excluded.fetched_at
                """,
                (url_hash, url, content_type, file_name, time.time()),
            )
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:{content_type};base64,{encoded}"


def get_remote_image_cache() -> RemoteImageCache:
    global _cache
    if _cache is None:
        _cache = RemoteImageCache()
    return _cache


def resolve_remote_image(
    url: str,
    *,
    referer: str = "",
) -> tuple[str, bool] | None:
    """
    Devuelve (data_url, from_cache) o None si la descarga falla.

    from_cache es True si no hubo que descargar de la red.
    """
    from pyqorreos.core.email_html import download_remote_image

    cache = get_remote_image_cache()
    cached = cache.get_data_url(url)
    if cached:
        return cached, True
    downloaded = download_remote_image(url, referer=referer)
    if not downloaded:
        return None
    data, content_type = downloaded
    return cache.put(url, data, content_type), False


def _extension_for_content_type(content_type: str) -> str:
    mapping = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/svg+xml": ".svg",
        "image/avif": ".avif",
    }
    return mapping.get(content_type.split(";")[0].strip().lower(), ".bin")
