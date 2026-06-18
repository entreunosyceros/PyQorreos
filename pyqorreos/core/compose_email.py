"""
Utilidades para componer y enviar correos con HTML y adjuntos.
"""

from __future__ import annotations

import base64
import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EmailAttachment:
    """Archivo adjunto listo para enviar por SMTP."""

    path: str
    filename: str

    @classmethod
    def from_path(cls, path: str) -> EmailAttachment:
        p = Path(path)
        return cls(path=str(p), filename=p.name)


_IMG_SRC = re.compile(r"""src=["']([^"']+)["']""", re.IGNORECASE)
_FILE_URL = re.compile(r"^file://+", re.IGNORECASE)


def _path_from_src(src: str) -> Path | None:
    src = src.strip()
    if not src or src.startswith("data:"):
        return None
    if _FILE_URL.match(src):
        from urllib.parse import unquote, urlparse

        parsed = urlparse(src)
        return Path(unquote(parsed.path))
    p = Path(src)
    if p.is_file():
        return p
    return None


def embed_local_images_in_html(html: str) -> str:
    """Convierte rutas locales de imágenes del editor Qt en data URLs."""
    def replacer(match: re.Match[str]) -> str:
        src = match.group(1)
        path = _path_from_src(src)
        if not path or not path.is_file():
            return match.group(0)
        mime, _ = mimetypes.guess_type(path.name)
        mime = mime or "application/octet-stream"
        try:
            data = base64.b64encode(path.read_bytes()).decode("ascii")
        except OSError:
            return match.group(0)
        return f'src="data:{mime};base64,{data}"'

    return _IMG_SRC.sub(replacer, html)


def prepare_outgoing_html(qt_html: str) -> str:
    """Prepara el HTML generado por QTextEdit para envío por correo."""
    html = qt_html.strip()
    if not html:
        return ""
    html = embed_local_images_in_html(html)
    if "<html" not in html.lower():
        html = (
            '<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
            f"<body>{html}</body></html>"
        )
    return html


def build_draft_bytes(
    *,
    from_email: str,
    display_name: str,
    to: str,
    cc: str,
    bcc: str,
    subject: str,
    body_plain: str,
    body_html: str,
) -> bytes:
    """Construye un mensaje RFC822 para guardar como borrador IMAP."""
    from email.message import EmailMessage

    msg = EmailMessage()
    from_header = (
        f"{display_name} <{from_email}>" if display_name else from_email
    )
    msg["From"] = from_header
    if to:
        msg["To"] = to
    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc
    msg["Subject"] = subject or "(Sin asunto)"
    html = (body_html or "").strip()
    plain = body_plain or ""
    if html:
        msg.set_content(plain, subtype="plain", charset="utf-8")
        msg.add_alternative(html, subtype="html", charset="utf-8")
    else:
        msg.set_content(plain, charset="utf-8")
    return msg.as_bytes()
