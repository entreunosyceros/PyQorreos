"""
Extracción de adjuntos de mensajes MIME.
"""

from __future__ import annotations

import base64
import email.message
from dataclasses import dataclass
from email.header import decode_header

from pyqorreos.core.email_charset import decode_email_bytes


@dataclass
class MailAttachmentInfo:
    filename: str
    content_type: str
    size: int
    part_index: int
    content_id: str = ""

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "content_type": self.content_type,
            "size": self.size,
            "part_index": self.part_index,
            "content_id": self.content_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MailAttachmentInfo:
        return cls(
            filename=data.get("filename", "adjunto"),
            content_type=data.get("content_type", "application/octet-stream"),
            size=int(data.get("size", 0)),
            part_index=int(data.get("part_index", 0)),
            content_id=data.get("content_id", ""),
        )


def _decode_filename(raw: str | None) -> str:
    if not raw:
        return "adjunto"
    parts: list[str] = []
    for fragment, charset in decode_header(raw):
        if isinstance(fragment, bytes):
            parts.append(decode_email_bytes(fragment, charset))
        else:
            parts.append(fragment)
    return "".join(parts).strip() or "adjunto"


def extract_attachments(msg: email.message.Message) -> list[MailAttachmentInfo]:
    """Lista metadatos de partes adjuntas o inline no-html/text."""
    attachments: list[MailAttachmentInfo] = []
    for index, part in enumerate(msg.walk()):
        if part.is_multipart():
            continue
        disposition = str(part.get("Content-Disposition", "")).lower()
        content_type = part.get_content_type()
        if content_type in ("text/plain", "text/html") and "attachment" not in disposition:
            continue
        if "attachment" not in disposition and "inline" not in disposition:
            if content_type.startswith("text/"):
                continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        filename = _decode_filename(part.get_filename())
        cid = (part.get("Content-ID") or "").strip().strip("<>")
        attachments.append(
            MailAttachmentInfo(
                filename=filename,
                content_type=content_type,
                size=len(payload),
                part_index=index,
                content_id=cid,
            )
        )
    return attachments


def get_attachment_payload(msg: email.message.Message, part_index: int) -> bytes | None:
    for index, part in enumerate(msg.walk()):
        if index == part_index:
            payload = part.get_payload(decode=True)
            return payload if payload is not None else None
    return None


def has_attachments_heuristic(content_type: str | None) -> bool:
    if not content_type:
        return False
    ct = content_type.lower()
    return "multipart/mixed" in ct or "multipart/related" in ct
