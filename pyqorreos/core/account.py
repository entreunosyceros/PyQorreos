"""
Modelos de datos para cuentas de correo.

Define la estructura MailAccount y los presets de servidores IMAP/SMTP
para los proveedores más habituales (Gmail, Outlook, Yahoo).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
import uuid


@dataclass
class MailAccount:
    """Datos de conexión de una cuenta de correo (sin contraseña)."""

    email: str
    display_name: str = ""
    imap_host: str = ""
    imap_port: int = 993
    smtp_host: str = ""
    smtp_port: int = 587
    use_ssl: bool = True       # Para IMAP (993) y SMTP Implícito (465)
    use_starttls: bool = True  # Para SMTP Explícito (587)
    auth_method: str = "password"  # password | oauth2
    signature: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        """Serializa la cuenta para guardarla en JSON."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MailAccount:
        """Reconstruye una cuenta desde un diccionario guardado en disco."""
        return cls(
            email=data.get("email", ""),
            display_name=data.get("display_name", ""),
            imap_host=data.get("imap_host", ""),
            imap_port=int(data.get("imap_port") or 993),
            smtp_host=data.get("smtp_host", ""),
            smtp_port=int(data.get("smtp_port") or 587),
            use_ssl=bool(data.get("use_ssl", True) if data.get("use_ssl") is not None else True),
            use_starttls=bool(data.get("use_starttls", True) if data.get("use_starttls") is not None else True),
            auth_method=str(data.get("auth_method", "password") or "password"),
            signature=str(data.get("signature", "") or ""),
            id=data.get("id") or str(uuid.uuid4()),
        )


# Presets para proveedores habituales
PROVIDER_PRESETS: dict[str, dict[str, Any]] = {
    "Gmail": {
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "use_ssl": True,
        "use_starttls": True,
    },
    "Outlook / Hotmail": {
        "imap_host": "outlook.office365.com",
        "imap_port": 993,
        "smtp_host": "smtp.office365.com",
        "smtp_port": 587,
        "use_ssl": True,
        "use_starttls": True,
    },
    "Yahoo": {
        "imap_host": "imap.mail.yahoo.com",
        "imap_port": 993,
        "smtp_host": "smtp.mail.yahoo.com",
        "smtp_port": 587,
        "use_ssl": True,
        "use_starttls": True,
    },
    "Personalizado": {},
}