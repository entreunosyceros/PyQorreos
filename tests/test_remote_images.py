"""Tests para caché y extracción de imágenes remotas."""

from __future__ import annotations

from pyqorreos.core.email_html import (
    apply_data_url_to_html,
    block_remote_images_in_html,
    extract_remote_image_urls,
)
from pyqorreos.core.remote_image_cache import RemoteImageCache


def test_extract_remote_image_urls_from_blocked_html() -> None:
    html = block_remote_images_in_html(
        '<img src="https://cdn.example.com/logo.png" alt="logo">'
    )
    urls = extract_remote_image_urls(html)
    assert urls == ["https://cdn.example.com/logo.png"]


def test_apply_data_url_to_html_single_image() -> None:
    html = block_remote_images_in_html(
        '<img src="https://cdn.example.com/a.png" width="10">'
    )
    patched = apply_data_url_to_html(
        html, "https://cdn.example.com/a.png", "data:image/png;base64,AAA"
    )
    assert "data:image/png;base64,AAA" in patched
    assert "data-blocked-src" not in patched


def test_remote_image_cache_roundtrip(tmp_path) -> None:
    cache = RemoteImageCache(
        db_path=tmp_path / "cache.db",
        cache_dir=tmp_path / "files",
    )
    url = "https://example.com/pic.jpg"
    data_url = cache.put(url, b"jpeg-bytes", "image/jpeg")
    assert data_url.startswith("data:image/jpeg;base64,")
    assert cache.get_data_url(url) == data_url
