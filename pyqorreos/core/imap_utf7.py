"""UTF-7 modificado de IMAP (RFC 3501) para nombres de buzón."""

from __future__ import annotations

import base64


def encode_imap_utf7(text: str) -> str:
    """Codifica un nombre Unicode al UTF-7 modificado que espera IMAP."""
    result: list[str] = []
    pending: list[str] = []

    def flush() -> None:
        if not pending:
            return
        raw = "".join(pending).encode("utf-16-be")
        encoded = (
            base64.b64encode(raw).decode("ascii").rstrip("=").replace("/", ",")
        )
        result.append(f"&{encoded}-")
        pending.clear()

    for char in text:
        code = ord(char)
        if char == "&":
            flush()
            result.append("&-")
        elif 0x20 <= code <= 0x7E:
            flush()
            result.append(char)
        else:
            pending.append(char)
    flush()
    return "".join(result)


def decode_imap_utf7(text: str) -> str:
    """Decodifica un nombre IMAP. El ASCII sin «&» se deja igual."""
    if "&" not in text:
        return text
    out: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        if text[index] != "&":
            out.append(text[index])
            index += 1
            continue
        index += 1
        if index >= length:
            out.append("&")
            break
        if text[index] == "-":
            out.append("&")
            index += 1
            continue
        end = text.find("-", index)
        if end < 0:
            chunk = text[index:]
            index = length
        else:
            chunk = text[index:end]
            index = end + 1
        padding = "=" * ((4 - len(chunk) % 4) % 4)
        try:
            raw = base64.b64decode(chunk.replace(",", "/") + padding)
            out.append(raw.decode("utf-16-be"))
        except (ValueError, UnicodeDecodeError):
            out.append("&" + chunk)
    return "".join(out)
