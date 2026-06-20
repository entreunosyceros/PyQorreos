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
    "Hosting / cPanel (Webempresa, etc.)": {
        "imap_host": "mail.tudominio.com",
        "imap_port": 993,
        "smtp_host": "mail.tudominio.com",
        "smtp_port": 465,
        "use_ssl": True,
        "use_starttls": True,
    },
    "Personalizado": {},
}
# URLs de ayuda para la autenticación de Gmail
GMAIL_APP_PASSWORD_URL = "https://myaccount.google.com/apppasswords"
GMAIL_APP_PASSWORD_HELP_URL = "https://support.google.com/accounts/answer/185833"


def detect_provider_preset(account: MailAccount) -> str:
    """Devuelve el preset de proveedor que coincide con los servidores de la cuenta."""
    imap = account.imap_host.strip().lower()
    if not imap:
        return "Personalizado"
    if imap.startswith("mail.") or imap.startswith("imap."):
        return "Hosting / cPanel (Webempresa, etc.)"
    for name, preset in PROVIDER_PRESETS.items():
        if name == "Personalizado":
            continue
        preset_host = str(preset.get("imap_host", "")).strip().lower()
        if preset_host and preset_host == imap:
            return name
    return "Personalizado"

# Verifica si la configuración apunta a una cuenta Gmail
def is_gmail_account(
    *,
    provider: str = "",
    email: str = "",
    imap_host: str = "",
) -> bool:
    """True si la configuración apunta a una cuenta Gmail."""
    if provider.strip().lower() == "gmail":
        return True
    addr = email.strip().lower()
    if addr.endswith("@gmail.com") or addr.endswith("@googlemail.com"):
        return True
    host = imap_host.strip().lower()
    return "gmail.com" in host or "googlemail.com" in host