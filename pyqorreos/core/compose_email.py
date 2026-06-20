"""
Utilidades para componer y enviar correos con HTML y adjuntos.
"""

from __future__ import annotations

import base64
import mimetypes
import re
from dataclasses import dataclass
from email.message import EmailMessage, Message
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, getaddresses
from pathlib import Path

_READ_RECEIPT_HEADERS = (
    "Disposition-Notification-To",
    "Return-Receipt-To",
    "X-Confirm-Reading-To",
)


# Cabeceras estándar para solicitar acuse de lectura al destinatario.
def apply_read_receipt_headers(
    msg: EmailMessage,
    receipt_to: str,
    *,
    display_name: str = "",
) -> None:
    """Añade cabecera MDN (RFC 3798). El cliente del destinatario decide si responde."""
    address = receipt_to.strip()
    if not address:
        return
    formatted = (
        formataddr((display_name.strip(), address))
        if display_name.strip()
        else address
    )
    # Solo Disposition-Notification-To (estándar). Return-Receipt-To es legado y
    # algunos servidores SMTP (p. ej. Microsoft) lo rechazan o malinterpretan.
    msg["Disposition-Notification-To"] = formatted


def parse_read_receipt_request(msg: Message) -> str:
    """Devuelve la dirección que solicita acuse de recibo, si existe."""
    for header in _READ_RECEIPT_HEADERS:
        raw = msg.get(header)
        if not raw:
            continue
        for _name, addr in getaddresses([str(raw)]):
            if addr:
                return addr
    return ""


def build_read_receipt_bytes(
    *,
    from_email: str,
    display_name: str,
    receipt_to: str,
    original_subject: str,
    original_message_id: str = "",
) -> bytes:
    """Construye un MDN (acuse de lectura) para enviar por SMTP."""
    from_header = (
        f"{display_name} <{from_email}>" if display_name else from_email
    )
    subject = original_subject or "(Sin asunto)"
    human = (
        f"El mensaje con asunto «{subject}» ha sido leído.\n"
        "Este es un acuse de recibo automático enviado por PyQorreos."
    )
    notification_lines = [
        "Reporting-UA: PyQorreos; Python",
        f"Final-Recipient: rfc822; {from_email}",
    ]
    if original_message_id:
        notification_lines.append(f"Original-Message-ID: {original_message_id}")
    notification_lines.append(
        "Disposition: automatic-action/MDN-sent-automatically; displayed"
    )
    notification = "\r\n".join(notification_lines) + "\r\n"

    outer = MIMEMultipart("report", report_type="disposition-notification")
    outer["From"] = from_header
    outer["To"] = receipt_to
    outer["Subject"] = f"Leído: {subject}"
    outer.attach(MIMEText(human, "plain", "utf-8"))
    outer.attach(MIMEText(notification, _subtype="disposition-notification"))
    return outer.as_bytes()


@dataclass
class EmailAttachment:
    """Archivo adjunto listo para enviar por SMTP."""

    path: str
    filename: str

    @classmethod
    def from_path(cls, path: str) -> EmailAttachment:
        p = Path(path)
        return cls(path=str(p), filename=p.name)

# Expresiones regulares para encontrar URLs de imágenes y archivos
_IMG_SRC = re.compile(r"""src=["']([^"']+)["']""", re.IGNORECASE)
_FILE_URL = re.compile(r"^file://+", re.IGNORECASE)

# Convierte una URL de imagen en un objeto Path
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


# Prepara el HTML generado por QTextEdit para envío por correo
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

# Construye un mensaje RFC822 para guardar como borrador IMAP
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
    request_read_receipt: bool = False,
) -> bytes:
    """Construye un mensaje RFC822 para guardar como borrador IMAP."""
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
    if request_read_receipt:
        apply_read_receipt_headers(msg, from_email, display_name=display_name)
    html = (body_html or "").strip()
    plain = body_plain or ""
    if html:
        # Si hay HTML, añade el contenido plano y el HTML
        msg.set_content(plain, subtype="plain", charset="utf-8")
        msg.add_alternative(html, subtype="html", charset="utf-8")
    else:
        # Si no hay HTML, añade el contenido plano
        msg.set_content(plain, charset="utf-8")
    return msg.as_bytes()
