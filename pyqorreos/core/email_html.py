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
import urllib.parse
import urllib.request
from email.utils import parseaddr
from html import unescape

MAX_REMOTE_IMAGES = 150
MAX_IMAGE_BYTES = 1_500_000
_USER_AGENT = "Mozilla/5.0 (compatible; PyQorreos/1.0)"

_IMG_TAG = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_IMG_URL_ATTRS = (
    "src",
    "data-src",
    "data-original",
    "data-lazy-src",
    "data-image",
    "data-bg",
    "poster",
)
_BG_ATTR = re.compile(
    r"""(?<![\w-])(background)\s*=\s*["']([^"']+)["']""",
    re.IGNORECASE,
)
_SRCSET_ATTR = re.compile(
    r"""(?<![\w-])srcset\s*=\s*["']([^"']+)["']""",
    re.IGNORECASE,
)
_ATTR_URL = re.compile(
    rf"""(?<![\w-])({'|'.join(_IMG_URL_ATTRS)})\s*=\s*["']([^"']+)["']""",
    re.IGNORECASE,
)

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
BLOCKED_IMAGE_PLACEHOLDER_MARKER = _BLOCKED_IMG_PLACEHOLDER
_BLOCKED_IMG_SRC = re.compile(
    r'\ssrc="[^"]*"\s*data-blocked-src="([^"]+)"',
    re.IGNORECASE,
)
_HAS_HTML_TAG = re.compile(r"<html[\s>]", re.IGNORECASE)
_HAS_HEAD_CLOSE = re.compile(r"</head>", re.IGNORECASE)
_HAS_BODY_TAG = re.compile(r"<body[\s>]", re.IGNORECASE)


def _normalize_remote_url(url: str) -> str:
    url = unescape(url.strip().strip('"').strip("'"))
    if url.startswith("//"):
        return "https:" + url
    return url


def _is_remote_image_url(url: str) -> bool:
    normalized = _normalize_remote_url(url)
    return normalized.startswith(("http://", "https://"))


def _is_blocked_placeholder(url: str) -> bool:
    return _BLOCKED_IMG_PLACEHOLDER in url


def _parse_srcset(value: str) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        bits = part.split()
        url = bits[0]
        descriptor = " ".join(bits[1:]) if len(bits) > 1 else ""
        items.append((url, descriptor))
    return items


def _format_srcset(items: list[tuple[str, str]]) -> str:
    parts: list[str] = []
    for url, descriptor in items:
        parts.append(f"{url} {descriptor}".strip() if descriptor else url)
    return ", ".join(parts)


def _replace_attr_url(tag: str, attr: str, new_url: str) -> str:
    pattern = re.compile(
        rf"""(?<![\w-])({re.escape(attr)})\s*=\s*["'][^"']*["']""",
        re.IGNORECASE,
    )
    if pattern.search(tag):
        return pattern.sub(f'{attr}="{new_url}"', tag, count=1)
    return tag


def _block_img_tag(tag: str) -> str:
    for match in list(_ATTR_URL.finditer(tag)):
        attr, url = match.group(1).lower(), match.group(2)
        if _is_remote_image_url(url):
            tag = _replace_attr_url(tag, attr, _BLOCKED_IMG_PLACEHOLDER)
            if attr == "src" and "data-blocked-src" not in tag.lower():
                tag = tag.replace("<img", f'<img data-blocked-src="{url}"', 1)
            elif f"data-blocked-{attr}" not in tag.lower():
                tag = tag.replace("<img", f'<img data-blocked-{attr}="{url}"', 1)

    srcset_match = _SRCSET_ATTR.search(tag)
    if srcset_match:
        original = srcset_match.group(1)
        blocked_items: list[tuple[str, str]] = []
        changed = False
        for url, descriptor in _parse_srcset(original):
            if _is_remote_image_url(url):
                blocked_items.append((_BLOCKED_IMG_PLACEHOLDER, descriptor))
                changed = True
            else:
                blocked_items.append((url, descriptor))
        if changed:
            blocked_srcset = _format_srcset(blocked_items)
            tag = _SRCSET_ATTR.sub(f'srcset="{blocked_srcset}"', tag, count=1)
            if "data-blocked-srcset" not in tag.lower():
                tag = tag.replace("<img", f'<img data-blocked-srcset="{original}"', 1)
    return tag


def _restore_img_tag(tag: str) -> str:
    for attr in _IMG_URL_ATTRS:
        blocked = re.search(
            rf"""data-blocked-{re.escape(attr)}\s*=\s*["']([^"']+)["']""",
            tag,
            re.IGNORECASE,
        )
        if blocked:
            url = unescape(blocked.group(1))
            tag = _replace_attr_url(tag, attr, url)

    blocked_src = re.search(
        r"""data-blocked-src\s*=\s*["']([^"']+)["']""",
        tag,
        re.IGNORECASE,
    )
    if blocked_src:
        url = unescape(blocked_src.group(1))
        tag = _replace_attr_url(tag, "src", url)

    blocked_srcset = re.search(
        r"""data-blocked-srcset\s*=\s*["']([^"']+)["']""",
        tag,
        re.IGNORECASE,
    )
    if blocked_srcset:
        tag = _SRCSET_ATTR.sub(
            f'srcset="{unescape(blocked_srcset.group(1))}"', tag, count=1
        )
    return tag


def _embed_img_tag(tag: str, embedder: _RemoteImageEmbedder) -> str:
    tag = _restore_img_tag(tag)
    for match in list(_ATTR_URL.finditer(tag)):
        attr, url = match.group(1).lower(), match.group(2)
        if _is_blocked_placeholder(url):
            continue
        if _is_remote_image_url(url):
            embedded = embedder.embed(url)
            tag = _replace_attr_url(tag, attr, embedded)

    srcset_match = _SRCSET_ATTR.search(tag)
    if srcset_match:
        original = srcset_match.group(1)
        embedded_items: list[tuple[str, str]] = []
        for url, descriptor in _parse_srcset(original):
            if _is_blocked_placeholder(url):
                embedded_items.append((url, descriptor))
            elif _is_remote_image_url(url):
                embedded_items.append((embedder.embed(url), descriptor))
            else:
                embedded_items.append((url, descriptor))
        tag = _SRCSET_ATTR.sub(
            f'srcset="{_format_srcset(embedded_items)}"', tag, count=1
        )
    return tag


def _unblock_remaining_placeholders(html: str) -> str:
    """Si la descarga falla, deja la URL original para que el visor intente cargarla."""

    def replacer(match: re.Match[str]) -> str:
        tag = match.group(0)
        if _BLOCKED_IMG_PLACEHOLDER not in tag:
            return tag
        blocked = re.search(
            r"""data-blocked-src\s*=\s*["']([^"']+)["']""",
            tag,
            re.IGNORECASE,
        )
        if blocked:
            url = unescape(blocked.group(1))
            return _replace_attr_url(tag, "src", url)
        for attr in _IMG_URL_ATTRS:
            if attr == "src":
                continue
            blocked_attr = re.search(
                rf"""data-blocked-{re.escape(attr)}\s*=\s*["']([^"']+)["']""",
                tag,
                re.IGNORECASE,
            )
            if blocked_attr:
                url = unescape(blocked_attr.group(1))
                tag = _replace_attr_url(tag, attr, url)
        blocked_srcset = re.search(
            r"""data-blocked-srcset\s*=\s*["']([^"']+)["']""",
            tag,
            re.IGNORECASE,
        )
        if blocked_srcset:
            tag = _SRCSET_ATTR.sub(
                f'srcset="{unescape(blocked_srcset.group(1))}"', tag, count=1
            )
        blocked_bg = re.search(
            r"""data-blocked-background\s*=\s*["']([^"']+)["']""",
            tag,
            re.IGNORECASE,
        )
        if blocked_bg and _TAG_WITH_BG.search(tag):
            tag = _BG_ATTR.sub(
                f'background="{unescape(blocked_bg.group(1))}"', tag, count=1
            )
        return tag

    html = _IMG_TAG.sub(replacer, html)
    html = _TAG_WITH_BG.sub(
        lambda m: _restore_bg_tag(m.group(0))
        if _BLOCKED_IMG_PLACEHOLDER in m.group(0)
        else m.group(0),
        html,
    )
    return html


_TAG_WITH_BG = re.compile(
    r"""<\w+\b[^>]*\bbackground\s*=\s*["'][^"']*["'][^>]*>""",
    re.IGNORECASE,
)


def _insert_before_tag_close(tag: str, fragment: str) -> str:
    if tag.endswith("/>"):
        return tag[:-2] + f" {fragment}/>"
    return tag[:-1] + f" {fragment}>"


def _block_bg_tag(tag: str) -> str:
    match = _BG_ATTR.search(tag)
    if not match or not _is_remote_image_url(match.group(2)):
        return tag
    url = match.group(2)
    tag = _BG_ATTR.sub(f'background="{_BLOCKED_IMG_PLACEHOLDER}"', tag, count=1)
    if "data-blocked-background" not in tag.lower():
        tag = _insert_before_tag_close(tag, f'data-blocked-background="{url}"')
    return tag


def _restore_bg_tag(tag: str) -> str:
    blocked = re.search(
        r"""data-blocked-background\s*=\s*["']([^"']+)["']""",
        tag,
        re.IGNORECASE,
    )
    if not blocked:
        return tag
    url = unescape(blocked.group(1))
    return _BG_ATTR.sub(f'background="{url}"', tag, count=1)


def _embed_bg_tag(tag: str, embedder: _RemoteImageEmbedder) -> str:
    tag = _restore_bg_tag(tag)
    match = _BG_ATTR.search(tag)
    if not match:
        return tag
    url = unescape(match.group(2))
    if _is_blocked_placeholder(url):
        blocked = re.search(
            r"""data-blocked-background\s*=\s*["']([^"']+)["']""",
            tag,
            re.IGNORECASE,
        )
        if blocked:
            url = unescape(blocked.group(1))
        else:
            return tag
    if _is_remote_image_url(url):
        tag = _BG_ATTR.sub(f'background="{embedder.embed(url)}"', tag, count=1)
    return tag


def _block_background_attrs(html: str) -> str:
    return _TAG_WITH_BG.sub(lambda m: _block_bg_tag(m.group(0)), html)


def _restore_background_attrs(html: str) -> str:
    return _TAG_WITH_BG.sub(lambda m: _restore_bg_tag(m.group(0)), html)


def _embed_background_attrs(html: str, embedder: _RemoteImageEmbedder) -> str:
    return _TAG_WITH_BG.sub(lambda m: _embed_bg_tag(m.group(0), embedder), html)


class _RemoteImageEmbedder:
    def __init__(
        self,
        max_count: int = MAX_REMOTE_IMAGES,
        referer: str = "",
    ) -> None:
        self._count = 0
        self._max_count = max_count
        self._cache: dict[str, str] = {}
        self._referer = referer.rstrip("/") + "/" if referer else ""

    def embed(self, url: str) -> str:
        url = _normalize_remote_url(url)
        if (
            self._referer
            and not _is_remote_image_url(url)
            and not url.lower().startswith("cid:")
            and not url.startswith("data:")
        ):
            url = urllib.parse.urljoin(self._referer, url)
        if not url or url.startswith("data:"):
            return url
        if url.lower().startswith("cid:"):
            return url
        if not _is_remote_image_url(url):
            return url
        if url in self._cache:
            return self._cache[url]
        if self._count >= self._max_count:
            return url
        try:
            headers = {
                "User-Agent": _USER_AGENT,
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            }
            if self._referer:
                headers["Referer"] = self._referer
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=15) as response:
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


def _embed_remote_img_tags(html: str, embedder: _RemoteImageEmbedder) -> str:
    return _IMG_TAG.sub(lambda m: _embed_img_tag(m.group(0), embedder), html)


def _embed_remote_css_urls(html: str, embedder: _RemoteImageEmbedder) -> str:
    def replacer(match: re.Match[str]) -> str:
        url = match.group(1)
        if _is_blocked_placeholder(url):
            return match.group(0)
        return f'url("{embedder.embed(url)}")'

    return _CSS_URL.sub(replacer, html)


def _embed_remote_images(html: str, referer: str = "") -> str:
    embedder = _RemoteImageEmbedder(referer=referer)
    html = _embed_remote_img_tags(html, embedder)
    html = _embed_background_attrs(html, embedder)
    html = _embed_remote_css_urls(html, embedder)
    return html


def block_remote_images_in_html(html: str) -> str:
    """Sustituye imágenes http(s) por un marcador de bloqueo."""

    def css_replacer(match: re.Match[str]) -> str:
        url = match.group(1).strip().strip('"').strip("'")
        if _is_remote_image_url(url):
            normalized = _normalize_remote_url(url)
            return (
                f'url("{_BLOCKED_IMG_PLACEHOLDER}") '
                f"/* pyqorreos-blocked:{normalized} */"
            )
        return match.group(0)

    html = _IMG_TAG.sub(lambda m: _block_img_tag(m.group(0)), html)
    html = _block_background_attrs(html)
    html = _CSS_URL.sub(css_replacer, html)
    return html


def restore_blocked_remote_images(html: str) -> str:
    """Restaura las URLs http(s) sustituidas por el bloqueador de privacidad."""
    html = _IMG_TAG.sub(lambda m: _restore_img_tag(m.group(0)), html)
    html = _restore_background_attrs(html)
    html = _BLOCKED_IMG_SRC.sub(r' src="\1"', html)
    placeholder_escaped = re.escape(_BLOCKED_IMG_PLACEHOLDER)
    html = re.sub(
        rf'url\(\s*["\']?{placeholder_escaped}["\']?\s*\)\s*/\*\s*pyqorreos-blocked:([^*]+?)\s*\*/',
        r'url("\1")',
        html,
        flags=re.IGNORECASE,
    )
    return html


def load_remote_images_in_html(html: str, referer: str = "") -> str:
    """Restaura y descarga imágenes remotas en HTML ya mostrado al usuario."""
    if not html.strip():
        return html
    html = restore_blocked_remote_images(html)
    html = _embed_remote_images(html, referer=referer)
    html = _unblock_remaining_placeholders(html)
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
    referer = _base_url_from_sender(sender)
    if load_remote_images:
        html = _embed_remote_images(html, referer=referer)
    else:
        html = block_remote_images_in_html(html)
    html = _inject_base_styles(html)
    from pyqorreos.ui.webengine_setup import (
        inject_link_safety_overlay,
        sanitize_email_html_for_viewer,
    )

    html = sanitize_email_html_for_viewer(html)
    return inject_link_safety_overlay(html)


def embed_remote_images_in_html(html: str, referer: str = "") -> str:
    """Descarga imágenes http(s) en un HTML ya preparado (sin volver a leer IMAP)."""
    return load_remote_images_in_html(html, referer=referer)


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
