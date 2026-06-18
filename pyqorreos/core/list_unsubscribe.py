"""
Cabecera List-Unsubscribe (RFC 2369) y desuscripción con un clic (RFC 8058).
"""

from __future__ import annotations

import re
import ssl
import urllib.error
import urllib.parse
import urllib.request

_ANGLE = re.compile(r"<([^>]+)>")


def parse_list_unsubscribe(
    header_value: str | None,
    post_header: str | None = None,
) -> dict[str, str | bool | None]:
    """
    Devuelve url, mailto y si admite POST one-click.

    Formato habitual: <https://...>, <mailto:unsub@...>
    """
    result: dict[str, str | bool | None] = {
        "url": None,
        "mailto": None,
        "one_click": False,
    }
    if not header_value:
        return result

    for match in _ANGLE.finditer(header_value):
        target = match.group(1).strip()
        lowered = target.lower()
        if lowered.startswith("mailto:"):
            addr = target[7:].split("?")[0].strip()
            if addr:
                result["mailto"] = addr
        elif lowered.startswith(("http://", "https://")):
            result["url"] = target

    if not result["url"]:
        for part in header_value.split(","):
            part = part.strip().strip("<>")
            if part.lower().startswith(("http://", "https://")):
                result["url"] = part
                break

    if post_header:
        result["one_click"] = "list-unsubscribe=one-click" in post_header.lower()

    return result


def has_unsubscribe_option(parsed: dict[str, str | bool | None]) -> bool:
    return bool(parsed.get("url") or parsed.get("mailto"))


def perform_unsubscribe(
    *,
    url: str | None,
    mailto: str | None,
    one_click: bool = False,
    user_agent: str = "PyQorreos/1.0",
) -> str:
    """
    Ejecuta la desuscripción por HTTP(S). Devuelve un mensaje de éxito.

    Si solo hay mailto, indica que debe abrirse el cliente de correo.
    """
    if url:
        return _unsubscribe_http(url, one_click=one_click, user_agent=user_agent)
    if mailto:
        raise RuntimeError(
            f"Este boletín solo admite desuscripción por correo ({mailto}). "
            "Ábrelo en tu cliente de correo."
        )
    raise RuntimeError("No se encontró información de desuscripción en el mensaje.")


def _unsubscribe_http(url: str, *, one_click: bool, user_agent: str) -> str:
    headers = {"User-Agent": user_agent}
    context = ssl.create_default_context()

    if one_click:
        data = b"List-Unsubscribe=One-Click"
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                **headers,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
    else:
        req = urllib.request.Request(url, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=30, context=context) as resp:
            code = resp.getcode()
            if code and code >= 400:
                raise RuntimeError(f"El servidor respondió con código {code}")
    except urllib.error.HTTPError as exc:
        if exc.code in (301, 302, 303, 307, 308):
            return "Solicitud de baja enviada (redirección del servidor)."
        if exc.code >= 400:
            raise RuntimeError(f"Error HTTP {exc.code} al darse de baja") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"No se pudo contactar con el servidor: {exc.reason}") from exc

    return "Te has dado de baja correctamente."
