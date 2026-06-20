"""Normalización de juegos de caracteres en correos MIME."""

from __future__ import annotations
# Conjunto de charset MIME desconocidos
_UNKNOWN_CHARSETS = frozenset(
    {
        "unknown-8bit",
        "unknown",
        "x-unknown",
        "8bit",
        "binary",
        "default",
    }
)
# Alias de charset MIME
_CHARSET_ALIASES = {
    "windows-1252": "cp1252",
    "iso8859-1": "latin-1",
    "iso-8859-1": "latin-1",
}


def normalize_email_charset(charset: str | None) -> str:
    """Convierte nombres de charset MIME inválidos o vacíos en codecs de Python."""
    if not charset:
        return "utf-8"
    cleaned = charset.strip().strip('"').strip("'")
    if not cleaned:
        return "utf-8"
    key = cleaned.lower().replace("_", "-")
    if key in _UNKNOWN_CHARSETS or key.endswith("-8bit"):
        return "latin-1"
    return _CHARSET_ALIASES.get(key, cleaned)


def decode_email_bytes(data: bytes, charset: str | None) -> str:
    """Decodifica bytes de cabecera o cuerpo MIME con fallback seguro."""
    encoding = normalize_email_charset(charset)
    try:
        # Si el charset es válido, decodifica como el charset
        return data.decode(encoding, errors="replace")
    except LookupError:
        # Si el charset no es válido, decodifica como utf-8 y devuelve el texto decodificado
        return data.decode("utf-8", errors="replace")
