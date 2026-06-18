"""
Detección básica de enlaces engañosos (texto visible vs URL real).
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

_DOMAIN_IN_TEXT = re.compile(
    r"(?:https?://)?(?:www\.)?([a-z0-9][-a-z0-9]*(?:\.[a-z0-9][-a-z0-9]*)+)",
    re.IGNORECASE,
)


def _normalize_host(host: str) -> str:
    return host.lower().removeprefix("www.")


def _hosts_match(real: str, claimed: str) -> bool:
    if not real or not claimed:
        return True
    return real == claimed or real.endswith("." + claimed) or claimed.endswith("." + real)


def domains_in_visible_text(text: str) -> list[str]:
    if not text:
        return []
    return [_normalize_host(m.group(1)) for m in _DOMAIN_IN_TEXT.finditer(text)]


def is_suspicious_link(visible_text: str, href: str) -> bool:
    """True si el texto del enlace sugiere un dominio distinto al de destino."""
    if not href or not href.lower().startswith(("http://", "https://")):
        return False
    visible = (visible_text or "").strip()
    if not visible or len(visible) > 200:
        return False
    try:
        real = _normalize_host(urlparse(href).hostname or "")
    except Exception:
        return False
    if not real:
        return False
    claimed_domains = domains_in_visible_text(visible)
    if not claimed_domains:
        return False
    return any(not _hosts_match(real, claimed) for claimed in claimed_domains)
