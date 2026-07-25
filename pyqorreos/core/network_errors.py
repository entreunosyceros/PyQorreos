"""
Mensajes de error legibles para fallos de red y correo.
"""

from __future__ import annotations

import imaplib
import smtplib
import socket
import ssl


def _smtp_payload_text(payload: object) -> str:
    if isinstance(payload, bytes):
        return payload.decode("utf-8", errors="replace").strip()
    return str(payload).strip()


def _smtp_exception_detail(exc: BaseException) -> str:
    """Texto del servidor SMTP (código + mensaje) si está disponible."""
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        parts: list[str] = []
        for address, reply in exc.recipients.items():
            if isinstance(reply, tuple) and len(reply) >= 2:
                parts.append(f"{address}: {reply[0]} {_smtp_payload_text(reply[1])}")
            else:
                parts.append(f"{address}: {reply}")
        return "; ".join(parts)
    if isinstance(exc, smtplib.SMTPResponseException):
        code = getattr(exc, "smtp_code", "")
        err = _smtp_payload_text(getattr(exc, "smtp_error", ""))
        return f"{code} {err}".strip()
    return str(exc).strip()


def _auth_failed_message(email: str = "") -> str:
    """Mensaje de credenciales inválidas, adaptado al proveedor si se conoce."""
    from pyqorreos.core.account import (
        is_aol_email,
        is_gmail_account,
        is_gmx_email,
        is_microsoft_email,
    )

    addr = (email or "").strip()
    if addr:
        if is_gmx_email(addr):
            return (
                "Usuario o contraseña incorrectos en GMX. "
                "Recuerda que GMX trae IMAP/POP3 DESACTIVADO por defecto: actívalo en "
                "el webmail (Ajustes → POP3 & IMAP → «Habilitar el acceso a esta cuenta "
                "mediante POP3 e IMAP») y usa tu correo completo como usuario."
            )
        if is_gmail_account(email=addr):
            return (
                "Usuario o contraseña incorrectos en Gmail. "
                "Usa una contraseña de aplicación de 16 caracteres (con verificación en "
                "2 pasos) o autentícate con OAuth2, no la contraseña normal de la cuenta."
            )
        if is_microsoft_email(addr):
            return (
                "Usuario o contraseña incorrectos en Outlook/Hotmail/MSN. "
                "Usa OAuth2 (recomendado) o una contraseña de aplicación si tienes "
                "verificación en dos pasos; el usuario es tu correo completo."
            )
        if is_aol_email(addr):
            return (
                "Usuario o contraseña incorrectos en AOL. "
                "AOL exige una contraseña de aplicación para clientes externos, no la "
                "contraseña de la web."
            )
    return (
        "Usuario o contraseña incorrectos. "
        "En Gmail y Outlook usa una contraseña de aplicación, no la de la cuenta. "
        "En GMX, activa primero el acceso IMAP/POP3 en los ajustes del webmail."
    )


def _microsoft_country_block_message() -> str:
    return (
        "Microsoft (Outlook, Hotmail, MSN) ha rechazado el envío desde tu red actual "
        "(error «country not allowed» / país no permitido). "
        "Suele ocurrir con VPN, IP de servidor o datacenter, o al conectarte desde un país "
        "distinto al habitual de la cuenta. "
        "Prueba sin VPN, desde otra red o envía desde outlook.com en el navegador. "
        "No está causado por solicitar acuse de recibo: el bloqueo afecta a todo envío SMTP."
    )


def friendly_mail_error(exc: BaseException, *, email: str = "") -> str:
    """Convierte excepciones de red/IMAP/SMTP en texto útil para el usuario.

    Si se indica ``email``, el mensaje de credenciales inválidas se adapta al
    proveedor (Gmail/Outlook → contraseña de aplicación; GMX → activar IMAP…).
    """
    detail = _smtp_exception_detail(exc)
    raw = detail or str(exc).strip()
    lowered = raw.lower()

    if isinstance(exc, imaplib.IMAP4.error):
        if any(
            token in lowered
            for token in (
                "authentication failed",
                "invalid credentials",
                "login failed",
                "authorization failed",
                "authenticate",
            )
        ):
            return _auth_failed_message(email)
        if "select" in lowered and "no such mailbox" in lowered:
            return "La carpeta no existe en el servidor."
        if "timeout" in lowered:
            return "El servidor IMAP no respondió a tiempo. Comprueba tu conexión."
        return raw or "Error del servidor IMAP."

    # Error de autenticación SMTP.
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        base = (
            "No se pudo autenticar en SMTP. "
            "Revisa usuario, contraseña y el puerto de envío (465 SSL o 587 STARTTLS)."
        )
        if email:
            return f"{base}\n\n{_auth_failed_message(email)}"
        return base

    if "country not allowed" in lowered:
        return _microsoft_country_block_message()

    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        if "country not allowed" in lowered:
            return _microsoft_country_block_message()
        return (
            f"El servidor rechazó uno o más destinatarios:\n{raw}"
        )

    # Error de excepción SMTP.
    if isinstance(exc, smtplib.SMTPException):
        if "data" in lowered and ("size" in lowered or "limit" in lowered):
            return "El servidor rechazó el mensaje: demasiado grande (adjuntos o cuerpo)."
        if "country not allowed" in lowered:
            return _microsoft_country_block_message()
        return raw or "Error del servidor SMTP."

    # Error de tiempo de espera.
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return "Tiempo de espera agotado. La red puede ser lenta o el servidor no responde."

    # Error de certificado SSL/TLS.
    if isinstance(exc, ssl.SSLError):
        return (
            "Error de certificado o cifrado SSL/TLS. "
            "Comprueba host, puerto y si la cuenta usa SSL."
        )

    # Error de conexión rechazada.
    if isinstance(exc, ConnectionRefusedError):
        return "Conexión rechazada. Revisa host y puerto del servidor."

    # Error de conexión reseteada.
    if isinstance(exc, ConnectionResetError):
        return "El servidor cerró la conexión de forma inesperada. Vuelve a intentarlo."

    # Error de sistema operativo.
    if isinstance(exc, OSError):
        if "network is unreachable" in lowered:
            return "Sin conexión de red. Comprueba tu Internet."
        if "name or service not known" in lowered or "nodename nor servname" in lowered:
            return "No se encontró el servidor. Revisa el nombre del host IMAP/SMTP."
        if "timed out" in lowered:
            return "Tiempo de espera agotado. La red puede ser lenta o el servidor no responde."

    if "country not allowed" in lowered:
        return _microsoft_country_block_message()

    return raw or "Error de red o de correo."
