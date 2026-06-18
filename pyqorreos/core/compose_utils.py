"""
Utilidades para el editor de redacción.
"""

from __future__ import annotations

import re

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
