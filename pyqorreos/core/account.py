"""
Modelos de datos para cuentas de correo.

Define la estructura MailAccount y los presets de servidores IMAP/SMTP
para los proveedores más habituales (Gmail, Outlook, Yahoo, AOL, etc.).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
import uuid

from email.utils import parseaddr


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
    "Outlook / Hotmail / MSN": {
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
    "AOL": {
        "imap_host": "imap.aol.com",
        "imap_port": 993,
        "smtp_host": "smtp.aol.com",
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

# Servidores IMAP equivalentes al preset de Microsoft (Outlook, Hotmail, MSN, Live).
_MICROSOFT_IMAP_HOSTS = frozenset(
    {
        "outlook.office365.com",
        "imap-mail.outlook.com",
        "imap.outlook.com",
    }
)

# Servidores IMAP equivalentes al preset de AOL.
_AOL_IMAP_HOSTS = frozenset({"imap.aol.com"})

# URLs de ayuda para la autenticación de Gmail
GMAIL_APP_PASSWORD_URL = "https://myaccount.google.com/apppasswords"
GMAIL_APP_PASSWORD_HELP_URL = "https://support.google.com/accounts/answer/185833"
AOL_APP_PASSWORD_URL = "https://login.aol.com/account/security"


def _email_domain(email: str) -> str:
    _name, addr = parseaddr(email.strip())
    if "@" not in addr:
        return ""
    return addr.rsplit("@", 1)[-1].lower()


def is_microsoft_email(email: str) -> bool:
    """True para @hotmail.*, @outlook.*, @live.* y @msn.com."""
    domain = _email_domain(email)
    if not domain:
        return False
    if domain == "msn.com":
        return True
    return domain.startswith(("hotmail.", "outlook.", "live."))


def is_aol_email(email: str) -> bool:
    domain = _email_domain(email)
    return bool(domain) and domain.startswith("aol.")


def detect_provider_from_email(email: str) -> str | None:
    """Sugiere un preset según el dominio del correo (@hotmail, @msn, @aol, etc.)."""
    domain = _email_domain(email)
    if not domain:
        return None
    if domain in ("gmail.com", "googlemail.com"):
        return "Gmail"
    if is_microsoft_email(email):
        return "Outlook / Hotmail / MSN"
    if domain.startswith("yahoo.") or domain == "ymail.com" or domain == "rocketmail.com":
        return "Yahoo"
    if is_aol_email(email):
        return "AOL"
    return None


def detect_provider_preset(account: MailAccount) -> str:
    """Devuelve el preset de proveedor que coincide con email o servidores IMAP."""
    from_email = detect_provider_from_email(account.email)
    if from_email:
        return from_email

    imap = account.imap_host.strip().lower()
    if not imap:
        return "Personalizado"
    if imap in _MICROSOFT_IMAP_HOSTS:
        return "Outlook / Hotmail / MSN"
    if imap in _AOL_IMAP_HOSTS:
        return "AOL"
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