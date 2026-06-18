"""
Base para autenticación OAuth2 (Gmail / Outlook).

La implementación completa requiere registro de aplicación en el proveedor
y flujo de autorización en navegador. Este módulo define la interfaz y
almacenamiento de tokens.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import keyring

from pyqorreos.core.settings import SERVICE_NAME


class AuthMethod(str, Enum):
    PASSWORD = "password"
    OAUTH2 = "oauth2"


@dataclass
class OAuthProvider:
    name: str
    auth_url: str
    token_url: str
    scopes: tuple[str, ...]


OAUTH_PROVIDERS: dict[str, OAuthProvider] = {
    "gmail": OAuthProvider(
        name="Gmail",
        auth_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scopes=("https://mail.google.com/",),
    ),
    "outlook": OAuthProvider(
        name="Outlook",
        auth_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
        scopes=(
            "https://outlook.office.com/IMAP.AccessAsUser.All",
            "https://outlook.office.com/SMTP.Send",
            "offline_access",
        ),
    ),
}


def oauth_token_key(account_id: str) -> str:
    return f"oauth:{account_id}"


def store_oauth_token(account_id: str, token_json: str) -> None:
    keyring.set_password(SERVICE_NAME, oauth_token_key(account_id), token_json)


def get_oauth_token(account_id: str) -> str | None:
    return keyring.get_password(SERVICE_NAME, oauth_token_key(account_id))


def delete_oauth_token(account_id: str) -> None:
    try:
        keyring.delete_password(SERVICE_NAME, oauth_token_key(account_id))
    except keyring.errors.PasswordDeleteError:
        pass


def detect_oauth_provider(email: str, imap_host: str) -> str | None:
    host = imap_host.lower()
    if "gmail" in host or email.endswith("@gmail.com"):
        return "gmail"
    if "office365" in host or "outlook" in host or "hotmail" in host:
        return "outlook"
    return None


def oauth_not_configured_message(provider_key: str | None) -> str:
    name = OAUTH_PROVIDERS.get(provider_key or "", OAuthProvider("", "", "", ())).name
    if not name:
        name = "este proveedor"
    return (
        f"OAuth2 para {name} aún no está completamente integrado.\n\n"
        "Usa una contraseña de aplicación por ahora, o configura OAuth "
        "registrando la app en la consola del proveedor."
    )
