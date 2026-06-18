"""
Preparación del HTML de correos para mostrarlo en el visor.

Resuelve imágenes embebidas (cid:) y descarga imágenes remotas http(s)
en atributos src y en reglas CSS (background, background-image, url()).
"""

from __future__ import annotations

import base64
import email.message
import re
import urllib.error
import urllib.request
from email.utils import parseaddr

MAX_REMOTE_IMAGES = 25
MAX_IMAGE_BYTES = 1_500_000
_USER_AGENT = "Mozilla/5.0 (compatible; PyQorreos/1.0)"

_BASE_STYLES = """
body, div, p, td, th, li, span {
    color: #1a1a1a !important;
    font-family: sans-serif;
}
body {
    background: #ffffff !important;
    margin: 8px;
    line-height: 1.45;
}
img {
    max-width: 100% !important;
    height: auto !important;
}
table { max-width: 100% !important; }
a { color: #2d7dd2 !important; }
"""

_CID_IN_ATTR = re.compile(
    r"""(src|background|href)\s*=\s*["']?cid:([^"'\s>]+)["']?""",
    re.IGNORECASE,
)
_REMOTE_IMG_SRC = re.compile(
    r"""src\s*=\s*["']([^"']+)["']""",
    re.IGNORECASE,
)
_CSS_URL = re.compile(
    r"""url\(\s*['"]?([^'")]+?)['"]?\s*\)""",
    re.IGNORECASE,
)
_BLOCKED_IMG_PLACEHOLDER = (
    "data:image/svg+xml;base64,"
    "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyMDAiIGhlaWdodD0iNDAi"
    "PjxyZWN0IHdpZHRoPSIyMDAiIGhlaWdodD0iNDAiIGZpbGw9IiNlZWVlZWUiLz48dGV4dCB4PSI1MCUi"
    "IHk9IjUwJSIgZG9taW5hbnQtYmFzZWxpbmU9Im1pZGRsZSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZmlsbD0i"
    "Izk5OSIgZm9udC1zaXplPSIxMCI+SW3DoWdlbiBibG9xdWVhZGE8L3RleHQ+PC9zdmc+"
)
_BLOCKED_IMG_SRC = re.compile(
    r'\ssrc="[^"]*"\s*data-blocked-src="([^"]+)"',
    re.IGNORECASE,
)
_HAS_HTML_TAG = re.compile(r"<html[\s>]", re.IGNORECASE)
_HAS_HEAD_CLOSE = re.compile(r"</head>", re.IGNORECASE)
_HAS_BODY_TAG = re.compile(r"<body[\s>]", re.IGNORECASE)


class _RemoteImageEmbedder:
    def __init__(self, max_count: int = MAX_REMOTE_IMAGES) -> None:
        self._count = 0
        self._max_count = max_count
        self._cache: dict[str, str] = {}

    def embed(self, url: str) -> str:
        url = url.strip().strip('"').strip("'")
        if not url or url.startswith("data:"):
            return url
        if url.lower().startswith("cid:"):
            return url
        if not url.startswith(("http://", "https://")):
            return url
        if url in self._cache:
            return self._cache[url]
        if self._count >= self._max_count:
            return url
        try:
            request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(request, timeout=10) as response:
                data = response.read(MAX_IMAGE_BYTES)
                content_type = response.headers.get_content_type() or "image/jpeg"
            self._count += 1
            encoded = base64.b64encode(data).decode("ascii")
            data_url = f"data:{content_type};base64,{encoded}"
            self._cache[url] = data_url
            return data_url
        except (urllib.error.URLError, OSError, ValueError):
            return url


def _collect_cid_images(msg: email.message.Message) -> dict[str, str]:
    cid_map: dict[str, str] = {}
    for part in msg.walk():
        content_id = part.get("Content-ID")
        if not content_id:
            continue
        cid = content_id.strip().strip("<>").strip()
        if not cid:
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        mime = part.get_content_type()
        if not mime.startswith("image/"):
            continue
        data_url = f"data:{mime};base64,{base64.b64encode(payload).decode('ascii')}"
        cid_map[cid] = data_url
        cid_map[cid.lower()] = data_url
    return cid_map


def _replace_cid_references(html: str, cid_map: dict[str, str]) -> str:
    if not cid_map:
        return html

    def attr_replacer(match: re.Match[str]) -> str:
        attr, cid = match.group(1), match.group(2)
        url = cid_map.get(cid) or cid_map.get(cid.lower())
        if url:
            return f'{attr}="{url}"'
        return match.group(0)

    html = _CID_IN_ATTR.sub(attr_replacer, html)
    for cid, data_url in cid_map.items():
        html = re.sub(rf"cid:{re.escape(cid)}", data_url, html, flags=re.IGNORECASE)
    return html


def _embed_remote_img_src(html: str, embedder: _RemoteImageEmbedder) -> str:
    def replacer(match: re.Match[str]) -> str:
        return f'src="{embedder.embed(match.group(1))}"'

    return _REMOTE_IMG_SRC.sub(replacer, html)


def _embed_remote_css_urls(html: str, embedder: _RemoteImageEmbedder) -> str:
    def replacer(match: re.Match[str]) -> str:
        return f'url("{embedder.embed(match.group(1))}")'

    return _CSS_URL.sub(replacer, html)


def _embed_remote_images(html: str) -> str:
    embedder = _RemoteImageEmbedder()
    html = _embed_remote_img_src(html, embedder)
    html = _embed_remote_css_urls(html, embedder)
    return html


def block_remote_images_in_html(html: str) -> str:
    """Sustituye imágenes http(s) por un marcador de bloqueo."""

    def src_replacer(match: re.Match[str]) -> str:
        url = match.group(1).strip()
        if url.startswith(("http://", "https://")):
            return f'src="{_BLOCKED_IMG_PLACEHOLDER}" data-blocked-src="{url}"'
        return match.group(0)

    def css_replacer(match: re.Match[str]) -> str:
        url = match.group(1).strip().strip('"').strip("'")
        if url.startswith(("http://", "https://")):
            return f'url("{_BLOCKED_IMG_PLACEHOLDER}")'
        return match.group(0)

    html = _REMOTE_IMG_SRC.sub(src_replacer, html)
    html = _CSS_URL.sub(css_replacer, html)
    return html


def restore_blocked_remote_images(html: str) -> str:
    """Restaura las URLs http(s) sustituidas por el bloqueador de privacidad."""
    return _BLOCKED_IMG_SRC.sub(r' src="\1"', html)


def load_remote_images_in_html(html: str) -> str:
    """Restaura y descarga imágenes remotas en HTML ya mostrado al usuario."""
    if not html.strip():
        return html
    html = restore_blocked_remote_images(html)
    html = _embed_remote_images(html)
    from pyqorreos.ui.webengine_setup import sanitize_email_html_for_viewer

    return sanitize_email_html_for_viewer(html)


def _inject_base_styles(html: str) -> str:
    """Inserta estilos de legibilidad sin romper documentos HTML completos."""
    style_block = f"<style type='text/css'>{_BASE_STYLES}</style>"
    if _HAS_HTML_TAG.search(html):
        if _HAS_HEAD_CLOSE.search(html):
            return _HAS_HEAD_CLOSE.sub(style_block + "</head>", html, count=1)
        if _HAS_BODY_TAG.search(html):
            return _HAS_BODY_TAG.sub(style_block + "<body", html, count=1)
        return re.sub(
            r"<html([^>]*)>",
            rf"<html\1><head>{style_block}</head>",
            html,
            count=1,
            flags=re.IGNORECASE,
        )
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"{style_block}</head><body>{html}</body></html>"
    )


def _base_url_from_sender(sender: str) -> str:
    _name, addr = parseaddr(sender)
    if "@" in addr:
        return f"https://{addr.split('@', 1)[1]}/"
    return "https://localhost/"


def prepare_html_for_display(
    msg: email.message.Message,
    html: str,
    sender: str = "",
    load_remote_images: bool = True,
) -> str:
    if not html.strip():
        return ""

    html = _replace_cid_references(html, _collect_cid_images(msg))
    if load_remote_images:
        html = _embed_remote_images(html)
    else:
        html = block_remote_images_in_html(html)
    html = _inject_base_styles(html)
    from pyqorreos.ui.webengine_setup import (
        inject_link_safety_overlay,
        sanitize_email_html_for_viewer,
    )

    html = sanitize_email_html_for_viewer(html)
    return inject_link_safety_overlay(html)


def embed_remote_images_in_html(html: str) -> str:
    """Descarga imágenes http(s) en un HTML ya preparado (sin volver a leer IMAP)."""
    return load_remote_images_in_html(html)


def base_url_for_message(sender: str) -> str:
    return _base_url_from_sender(sender)


_READING_MODE_STYLES = """
body {
    max-width: 42rem !important;
    margin: 0 auto !important;
    padding: 1rem 1.25rem !important;
    font: 1.05rem/1.65 Georgia, "Times New Roman", serif !important;
    color: #1a1a1a !important;
    background: #fafafa !important;
}
img, video, iframe { display: none !important; }
table { width: 100% !important; border-collapse: collapse !important; }
td, th { padding: 0.25rem 0 !important; }
a { color: #1a5fb4 !important; text-decoration: underline !important; }
blockquote {
    border-left: 3px solid #ccc !important;
    margin-left: 0 !important;
    padding-left: 1rem !important;
    color: #444 !important;
}
"""


def apply_reading_mode_styles(html: str) -> str:
    """Aplica estilos mínimos de lectura sobre el HTML del mensaje."""
    if not html.strip():
        return html
    style_block = f"<style>{_READING_MODE_STYLES}</style>"
    if _HAS_HEAD_CLOSE.search(html):
        return _HAS_HEAD_CLOSE.sub(f"{style_block}</head>", html, count=1)
    if _HAS_HTML_TAG.search(html):
        return _HAS_HTML_TAG.sub(
            rf"<html\1><head><meta charset='utf-8'>{style_block}</head>",
            html,
            count=1,
            flags=re.IGNORECASE,
        )
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"{style_block}</head><body>{html}</body></html>"
    )


def html_to_plain_text(html: str) -> str:
    """Extrae texto legible del HTML sin dependencias externas."""
    from html import unescape

    if not html.strip():
        return ""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = re.sub(r"(?i)</div\s*>", "\n", text)
    text = re.sub(r"(?i)</tr\s*>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "• ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
