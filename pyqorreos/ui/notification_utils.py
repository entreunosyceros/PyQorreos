"""
Texto de notificaciones de correo nuevo para la bandeja del sistema.
"""

from __future__ import annotations

from datetime import datetime

from pyqorreos.core.mail_service import MailSummary, normalize_mail_datetime


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def format_new_mail_notification(
    summaries: list[MailSummary],
    folder: str,
    account_label: str,
) -> tuple[str, str]:
    """
    Devuelve (título, cuerpo) para showMessage de la bandeja.

    Un solo mensaje: título = asunto, cuerpo = remitente.
    Varios: título = resumen, cuerpo = lista breve.
    """
    if not summaries:
        return (
            "Correo nuevo",
            f"Nuevo mensaje en {folder} ({account_label})",
        )

    ordered = sorted(
        summaries,
        key=lambda s: normalize_mail_datetime(s.date) or datetime.min,
        reverse=True,
    )

    if len(ordered) == 1:
        summary = ordered[0]
        title = _truncate(summary.subject or "(Sin asunto)", 120)
        sender = _truncate(summary.sender or "(Sin remitente)", 80)
        body = f"De: {sender}"
        if folder.upper() != "INBOX":
            body += f"\n{folder}"
        return title, body

    title = f"{len(ordered)} correos nuevos"
    lines: list[str] = []
    for summary in ordered[:3]:
        sender = _truncate(summary.sender or "?", 40)
        subject = _truncate(summary.subject or "(Sin asunto)", 50)
        lines.append(f"{sender} — {subject}")
    if len(ordered) > 3:
        lines.append(f"y {len(ordered) - 3} más…")
    if account_label:
        lines.append(account_label)
    return title, "\n".join(lines)
