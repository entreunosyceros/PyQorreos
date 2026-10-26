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

SECURITY_SSL = "ssl"
SECURITY_STARTTLS = "starttls"
SECURITY_PLAIN = "plain"
_SECURITY_MODES = frozenset({SECURITY_SSL, SECURITY_STARTTLS, SECURITY_PLAIN})


def infer_imap_security(port: int, use_ssl: bool, use_starttls: bool) -> str:
    """Deduce el cifrado IMAP de cuentas guardadas antes de imap_security."""
    if port == 993:
        return SECURITY_SSL
    if port == 143:
        return SECURITY_STARTTLS if use_starttls else SECURITY_PLAIN
    if use_ssl and not use_starttls:
        return SECURITY_SSL
    if use_starttls:
        return SECURITY_STARTTLS
    if use_ssl:
        return SECURITY_SSL
    return SECURITY_PLAIN


def infer_smtp_security(port: int, use_ssl: bool, use_starttls: bool) -> str:
    """Deduce el cifrado SMTP. 465 es SSL y 587 es STARTTLS."""
    if port == 465:
        return SECURITY_SSL
    if port == 587:
        return SECURITY_STARTTLS
    if use_ssl and not use_starttls:
        return SECURITY_SSL
    if use_starttls:
        return SECURITY_STARTTLS
    if use_ssl:
        return SECURITY_SSL
    return SECURITY_PLAIN


@dataclass
class MailAccount:
    """Datos de conexión de una cuenta de correo (sin contraseña)."""

    email: str
    display_name: str = ""
    imap_host: str = ""
    imap_port: int = 993
    smtp_host: str = ""
    smtp_port: int = 587
    use_ssl: bool = True       # Reflejo histórico del modo IMAP
    use_starttls: bool = True  # Reflejo histórico del modo IMAP
    auth_method: str = "password"  # password | oauth2
    signature: str = ""
    imap_security: str = ""  # ssl | starttls | plain
    smtp_security: str = ""  # ssl | starttls | plain
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if self.imap_security not in _SECURITY_MODES:
            self.imap_security = infer_imap_security(
                self.imap_port, self.use_ssl, self.use_starttls
            )
        if self.smtp_security not in _SECURITY_MODES:
            self.smtp_security = infer_smtp_security(
                self.smtp_port, self.use_ssl, self.use_starttls
            )
        self.use_ssl = self.imap_security == SECURITY_SSL
        self.use_starttls = self.imap_security == SECURITY_STARTTLS

    def to_dict(self) -> dict[str, Any]:
        """Serializa la cuenta. Los booleanos antiguos reflejan solo IMAP."""
        data = asdict(self)
        data["use_ssl"] = self.imap_security == SECURITY_SSL
        data["use_starttls"] = self.imap_security == SECURITY_STARTTLS
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MailAccount:
        """Reconstruye una cuenta desde un diccionario guardado en disco."""
        use_ssl = bool(data.get("use_ssl", True) if data.get("use_ssl") is not None else True)
        use_starttls = bool(
            data.get("use_starttls", True) if data.get("use_starttls") is not None else True
        )
        return cls(
            email=data.get("email", ""),
            display_name=data.get("display_name", ""),
            imap_host=data.get("imap_host", ""),
            imap_port=int(data.get("imap_port") or 993),
            smtp_host=data.get("smtp_host", ""),
            smtp_port=int(data.get("smtp_port") or 587),
            use_ssl=use_ssl,
            use_starttls=use_starttls,
            auth_method=str(data.get("auth_method", "password") or "password"),
            signature=str(data.get("signature", "") or ""),
            imap_security=str(data.get("imap_security") or ""),
            smtp_security=str(data.get("smtp_security") or ""),
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
        "imap_security": "ssl",
        "smtp_security": "starttls",
    },
    "Outlook / Hotmail / MSN": {
        "imap_host": "outlook.office365.com",
        "imap_port": 993,
        "smtp_host": "smtp.office365.com",
        "smtp_port": 587,
        "use_ssl": True,
        "use_starttls": True,
        "imap_security": "ssl",
        "smtp_security": "starttls",
    },
    "Yahoo": {
        "imap_host": "imap.mail.yahoo.com",
        "imap_port": 993,
        "smtp_host": "smtp.mail.yahoo.com",
        "smtp_port": 587,
        "use_ssl": True,
        "use_starttls": True,
        "imap_security": "ssl",
        "smtp_security": "starttls",
    },
    "AOL": {
        "imap_host": "imap.aol.com",
        "imap_port": 993,
        "smtp_host": "smtp.aol.com",
        "smtp_port": 587,
        "use_ssl": True,
        "use_starttls": True,
        "imap_security": "ssl",
        "smtp_security": "starttls",
    },
    "GMX": {
        "imap_host": "imap.gmx.com",
        "imap_port": 993,
        "smtp_host": "mail.gmx.com",
        "smtp_port": 587,
        "use_ssl": True,
        "use_starttls": True,
        "imap_security": "ssl",
        "smtp_security": "starttls",
    },
    "Hosting / cPanel (Webempresa, etc.)": {
        "imap_host": "mail.tudominio.com",
        "imap_port": 993,
        "smtp_host": "mail.tudominio.com",
        "smtp_port": 465,
        "use_ssl": True,
        "use_starttls": False,
        "imap_security": "ssl",
        "smtp_security": "ssl",
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

# Servidores IMAP equivalentes al preset de GMX.
_GMX_IMAP_HOSTS = frozenset({"imap.gmx.com", "imap.gmx.net"})

# URLs de ayuda para la autenticación de Gmail
GMAIL_APP_PASSWORD_URL = "https://myaccount.google.com/apppasswords"
GMAIL_APP_PASSWORD_HELP_URL = "https://support.google.com/accounts/answer/185833"
AOL_APP_PASSWORD_URL = "https://login.aol.com/account/security"
# GMX desactiva IMAP/POP3 por defecto; hay que activarlo en los ajustes web.
GMX_IMAP_ENABLE_URL = "https://support.gmx.com/pop-imap/toggle.html"


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


def is_gmx_email(email: str) -> bool:
    """True para dominios de GMX (@gmx.com, @gmx.net, @gmx.de, @gmx.es…)."""
    domain = _email_domain(email)
    return bool(domain) and (domain == "gmx.com" or domain.startswith("gmx."))


def simple_browser_login(
    provider: str,
    email: str,
    *,
    outlook_ready: bool = False,
) -> bool:
    """True si el alta puede ser solo correo + inicio de sesión en el navegador."""
    if provider == "Gmail" or detect_provider_from_email(email) == "Gmail":
        return True
    if outlook_ready and (
        provider == "Outlook / Hotmail / MSN" or is_microsoft_email(email)
    ):
        return True
    return False


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
    if is_gmx_email(email):
        return "GMX"
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
    if imap in _GMX_IMAP_HOSTS:
        return "GMX"
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