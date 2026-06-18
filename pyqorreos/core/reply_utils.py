"""
Utilidades para responder y reenviar correos (estilo cliente de escritorio).

La cita del mensaje original conserva el HTML tal como se ve en el visor,
no un volcado de texto plano con líneas «>».
"""

from __future__ import annotations

import html as html_module
import re
from dataclasses import dataclass
from email.utils import getaddresses, parseaddr

from pyqorreos.core.mail_service import MailMessage

_BODY_FRAGMENT = re.compile(
    r"<body[^>]*>(.*)</body>",
    re.DOTALL | re.IGNORECASE,
)
_STRIP_TAGS = re.compile(r"<[^>]+>")


@dataclass
class ComposeDraft:
    """Borrador precargado para el diálogo de redacción."""

    to: str = ""
    cc: str = ""
    bcc: str = ""
    subject: str = ""
    body: str = ""
    body_html: str = ""


def _normalize_subject(subject: str, prefix: str) -> str:
    subject = subject.strip() or "(Sin asunto)"
    if subject.lower().startswith(prefix.lower()):
        return subject
    return f"{prefix}{subject}"


def _format_date(message: MailMessage) -> str:
    if message.date:
        return message.date.strftime("%d/%m/%Y %H:%M")
    return ""


def _quote_header_plain(message: MailMessage) -> str:
    return (
        "---------- Mensaje original ----------\n"
        f"De: {message.sender}\n"
        f"Para: {message.recipients}\n"
        f"Fecha: {_format_date(message)}\n"
        f"Asunto: {message.subject}\n"
    )


def _quote_header_html(message: MailMessage) -> str:
    return (
        '<table style="color:#666;font-size:10pt;margin:0 0 12px 0;'
        'border-collapse:collapse;" cellpadding="0" cellspacing="0">'
        f"<tr><td><b>De:</b></td><td>{html_module.escape(message.sender)}</td></tr>"
        f"<tr><td><b>Para:</b></td><td>{html_module.escape(message.recipients)}</td></tr>"
        f"<tr><td><b>Fecha:</b></td><td>{html_module.escape(_format_date(message))}</td></tr>"
        f"<tr><td><b>Asunto:</b></td><td>{html_module.escape(message.subject or '')}</td></tr>"
        "</table>"
    )


def _extract_html_body(html: str) -> str:
    """Obtiene el fragmento interior de un documento HTML completo."""
    html = html.strip()
    if not html:
        return ""
    match = _BODY_FRAGMENT.search(html)
    if match:
        return match.group(1).strip()
    return html


def _html_to_plain_fallback(html: str) -> str:
    """Texto plano aproximado cuando no hay parte text/plain."""
    text = _STRIP_TAGS.sub(" ", html)
    text = html_module.unescape(text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return re.sub(r" +", " ", text).strip()


def _quoted_content_html(message: MailMessage) -> str:
    if message.body_html.strip():
        return _extract_html_body(message.body_html)
    if message.body_text.strip():
        escaped = html_module.escape(message.body_text)
        return (
            f'<pre style="white-space:pre-wrap;font-family:sans-serif;'
            f'font-size:10pt;color:#1a1a1a;">{escaped}</pre>'
        )
    return "<p><i>(Sin contenido)</i></p>"


def _quote_plain(message: MailMessage) -> str:
    """Versión texto plano para la parte alternative del envío."""
    header = _quote_header_plain(message) + "\n"
    if message.body_text.strip():
        body = message.body_text
    elif message.body_html.strip():
        body = _html_to_plain_fallback(message.body_html)
    else:
        body = "(Sin contenido)"
    quoted = "\n".join(f"> {line}" for line in body.splitlines())
    return f"\n\n{header}{quoted}"


def _quote_html(message: MailMessage) -> str:
    """Cita HTML fiel al mensaje mostrado en el visor."""
    content = _quoted_content_html(message)
    return (
        '<br><br>'
        '<div style="border-left:3px solid #2d7dd2;padding-left:14px;margin:16px 0;">'
        '<p style="color:#888;font-size:9pt;margin:0 0 8px 0;">'
        "---------- Mensaje original ----------"
        "</p>"
        f"{_quote_header_html(message)}"
        '<div style="max-width:100%;overflow-x:auto;">'
        f"{content}"
        "</div>"
        "</div>"
    )


def _compose_html_with_room_for_reply(quote_html: str) -> str:
    """Deja un bloque blanco arriba para escribir, separado de la cita."""
    return (
        '<div id="pyqorreos-reply-area" '
        'style="background-color:#ffffff;color:#1a1a1a;'
        'font-family:sans-serif;font-size:11pt;min-height:120px;">'
        '<p style="margin:0;background-color:#ffffff;color:#1a1a1a;"><br></p>'
        "</div>"
        f"{quote_html}"
    )


def build_reply(message: MailMessage, own_email: str, reply_all: bool = False) -> ComposeDraft:
    """Crea un borrador de respuesta o respuesta a todos."""
    sender_name, sender_addr = parseaddr(message.sender)
    to_addrs: list[str] = []
    cc_addrs: list[str] = []

    if reply_all:
        own = own_email.lower()
        for _name, addr in getaddresses([message.sender, message.recipients]):
            if addr and addr.lower() != own and addr not in to_addrs:
                to_addrs.append(addr)
        if sender_addr and sender_addr.lower() != own:
            if sender_addr not in to_addrs:
                to_addrs.insert(0, sender_addr)
    else:
        if sender_addr:
            to_addrs.append(sender_addr)

    to_line = ", ".join(to_addrs)
    if sender_name and sender_addr and not reply_all:
        to_line = f"{sender_name} <{sender_addr}>"

    quote = _quote_html(message)
    return ComposeDraft(
        to=to_line,
        cc=", ".join(cc_addrs),
        subject=_normalize_subject(message.subject, "Re: "),
        body=_quote_plain(message),
        body_html=_compose_html_with_room_for_reply(quote),
    )


def build_forward(message: MailMessage) -> ComposeDraft:
    """Crea un borrador de reenvío."""
    quote = _quote_html(message)
    return ComposeDraft(
        subject=_normalize_subject(message.subject, "Fwd: "),
        body=_quote_plain(message),
        body_html=_compose_html_with_room_for_reply(quote),
    )
