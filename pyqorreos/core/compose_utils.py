"""
Utilidades al redactar correos.
"""

from __future__ import annotations

import re
from pathlib import Path

# Límites orientativos para adjuntos (el servidor puede imponer otros).
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024
MAX_ATTACHMENTS_TOTAL_BYTES = 50 * 1024 * 1024
WARN_ATTACHMENT_BYTES = 10 * 1024 * 1024

_ATTACHMENT_HINT = re.compile(
    r"\b("
    r"adjunto|adjunt[oa]s?|archivo adjunto|en el pdf|adjunto captura|"
    r"te adjunto|les adjunto|va adjunto|documento adjunto|"
    r"attached|attachment|see attached|file attached"
    r")\b",
    re.IGNORECASE,
)


def body_mentions_attachment(text: str) -> bool:
    """Detecta si el cuerpo sugiere que hay un archivo adjunto."""
    return bool(_ATTACHMENT_HINT.search(text or ""))


def attachment_size_bytes(path: str | Path) -> int:
    try:
        return Path(path).stat().st_size
    except OSError:
        return 0


def format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def validate_attachments(paths: list[str | Path]) -> tuple[bool, str]:
    """
    Comprueba tamaños de adjuntos antes de enviar.
    Devuelve (ok, mensaje de error si no ok).
    """
    total = 0
    for path in paths:
        p = Path(path)
        if not p.is_file():
            continue
        size = p.stat().st_size
        if size > MAX_ATTACHMENT_BYTES:
            return (
                False,
                f"«{p.name}» pesa {format_bytes(size)}. "
                f"Máximo por archivo: {format_bytes(MAX_ATTACHMENT_BYTES)}.",
            )
        total += size
    if total > MAX_ATTACHMENTS_TOTAL_BYTES:
        return (
            False,
            f"Los adjuntos suman {format_bytes(total)}. "
            f"Máximo total: {format_bytes(MAX_ATTACHMENTS_TOTAL_BYTES)}.",
        )
    return True, ""


def large_attachment_warning(paths: list[str | Path]) -> str | None:
    """Aviso no bloqueante si algún adjunto es muy grande."""
    names: list[str] = []
    for path in paths:
        p = Path(path)
        if not p.is_file():
            continue
        size = p.stat().st_size
        if size >= WARN_ATTACHMENT_BYTES:
            names.append(f"«{p.name}» ({format_bytes(size)})")
    if not names:
        return None
    return (
        "Adjuntos grandes: " + ", ".join(names) + ".\n"
        "El envío puede tardar o fallar con redes lentas."
    )
