"""
Mensajes de error legibles para fallos de red y correo.
"""

from __future__ import annotations

import imaplib
import smtplib
import socket
import ssl


def friendly_mail_error(exc: BaseException) -> str:
    """Convierte excepciones de red/IMAP/SMTP en texto útil para el usuario."""
    raw = str(exc).strip()
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
            return (
                "Usuario o contraseña incorrectos. "
                "En Gmail y Outlook usa una contraseña de aplicación, no la de la cuenta."
            )
        if "select" in lowered and "no such mailbox" in lowered:
            return "La carpeta no existe en el servidor."
        if "timeout" in lowered:
            return "El servidor IMAP no respondió a tiempo. Comprueba tu conexión."
        return raw or "Error del servidor IMAP."

    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return (
            "No se pudo autenticar en SMTP. "
            "Revisa usuario, contraseña y el puerto de envío (465 SSL o 587 STARTTLS)."
        )

    if isinstance(exc, smtplib.SMTPException):
        if "data" in lowered and ("size" in lowered or "limit" in lowered):
            return "El servidor rechazó el mensaje: demasiado grande (adjuntos o cuerpo)."
        return raw or "Error del servidor SMTP."

    if isinstance(exc, (socket.timeout, TimeoutError)):
        return "Tiempo de espera agotado. La red puede ser lenta o el servidor no responde."

    if isinstance(exc, ssl.SSLError):
        return (
            "Error de certificado o cifrado SSL/TLS. "
            "Comprueba host, puerto y si la cuenta usa SSL."
        )

    if isinstance(exc, ConnectionRefusedError):
        return "Conexión rechazada. Revisa host y puerto del servidor."

    if isinstance(exc, ConnectionResetError):
        return "El servidor cerró la conexión de forma inesperada. Vuelve a intentarlo."

    if isinstance(exc, OSError):
        if "network is unreachable" in lowered:
            return "Sin conexión de red. Comprueba tu Internet."
        if "name or service not known" in lowered or "nodename nor servname" in lowered:
            return "No se encontró el servidor. Revisa el nombre del host IMAP/SMTP."
        if "timed out" in lowered:
            return "Tiempo de espera agotado. La red puede ser lenta o el servidor no responde."

    return raw or "Error de red o de correo."
