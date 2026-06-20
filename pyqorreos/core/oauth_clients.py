"""
Credenciales OAuth de aplicación (client_id / client_secret) por proveedor.

Se guardan en ~/.config/pyqorreos/oauth_clients.json (también desde Preferencias → OAuth).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

OAUTH_CLIENTS_DIR = Path.home() / ".config" / "pyqorreos"
OAUTH_CLIENTS_FILE = OAUTH_CLIENTS_DIR / "oauth_clients.json"
OAUTH_CLIENTS_EXAMPLE = Path(__file__).resolve().parents[2] / "oauth_clients.example.json"

OAUTH_PROVIDER_KEYS = ("gmail", "outlook")
OAUTH_REDIRECT_URI = "http://127.0.0.1"

GOOGLE_CLOUD_URL = "https://console.cloud.google.com/"
GOOGLE_GMAIL_API_URL = "https://console.cloud.google.com/apis/library/gmail.googleapis.com"
GOOGLE_CREDENTIALS_URL = "https://console.cloud.google.com/apis/credentials"
AZURE_APP_REGISTRATIONS_URL = (
    "https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade"
)

# Credenciales OAuth de aplicación (client_id / client_secret) por proveedor.
@dataclass(frozen=True)
class OAuthClientCredentials:
    client_id: str
    client_secret: str = ""

# Datos vacíos de OAuth de aplicación (client_id / client_secret) por proveedor.
def _empty_oauth_clients_data() -> dict[str, dict[str, str]]:
    return {
        "gmail": {"client_id": "", "client_secret": ""},
        "outlook": {"client_id": "", "client_secret": ""},
    }

# Lee el contenido completo de oauth_clients.json para el formulario de preferencias.
def load_oauth_clients_data() -> dict[str, dict[str, str]]:
    """Lee el contenido completo de oauth_clients.json para el formulario de preferencias."""
    data = _empty_oauth_clients_data()
    if not OAUTH_CLIENTS_FILE.exists():
        return data
    try:
        raw = json.loads(OAUTH_CLIENTS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return data
    if not isinstance(raw, dict):
        return data
    for key in OAUTH_PROVIDER_KEYS:
        block = raw.get(key)
        if not isinstance(block, dict):
            continue
        data[key] = {
            "client_id": str(block.get("client_id", "")).strip(),
            "client_secret": str(block.get("client_secret", "")).strip(),
        }
    return data

# Persiste las credenciales OAuth en disco.
def save_oauth_clients_data(data: dict[str, dict[str, str]]) -> None:
    """Persiste las credenciales OAuth en disco."""
    OAUTH_CLIENTS_DIR.mkdir(parents=True, exist_ok=True)
    out: dict[str, dict[str, str]] = {}
    for key in OAUTH_PROVIDER_KEYS:
        block = data.get(key) if isinstance(data.get(key), dict) else {}
        client_id = str(block.get("client_id", "")).strip()
        client_secret = str(block.get("client_secret", "")).strip()
        if not client_id:
            continue
        entry: dict[str, str] = {"client_id": client_id}
        if client_secret:
            entry["client_secret"] = client_secret
        out[key] = entry
    OAUTH_CLIENTS_FILE.write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

# Valida los datos de OAuth de aplicación (client_id / client_secret) por proveedor.
def validate_oauth_clients_data(data: dict[str, dict[str, str]]) -> str | None:
    """Devuelve un mensaje de error o None si los datos son válidos."""
    labels = {"gmail": "Gmail", "outlook": "Outlook"}
    for key in OAUTH_PROVIDER_KEYS:
        block = data.get(key) if isinstance(data.get(key), dict) else {}
        client_id = str(block.get("client_id", "")).strip()
        client_secret = str(block.get("client_secret", "")).strip()
        if client_secret and not client_id:
            return f"Indica el Client ID de {labels[key]}."
    return None

# Lee las credenciales OAuth del proveedor (gmail / outlook).
def load_oauth_client(provider_key: str) -> OAuthClientCredentials | None:
    """Lee las credenciales OAuth del proveedor (gmail / outlook)."""
    block = load_oauth_clients_data().get(provider_key, {})
    client_id = str(block.get("client_id", "")).strip()
    if not client_id:
        return None
    return OAuthClientCredentials(
        client_id=client_id,
        client_secret=str(block.get("client_secret", "")).strip(),
    )

# Verifica si las credenciales OAuth están configuradas.
def oauth_clients_configured(provider_key: str) -> bool:
    creds = load_oauth_client(provider_key)
    return creds is not None and bool(creds.client_id)

# Instrucciones de configuración de OAuth para el formulario de preferencias.
def oauth_setup_instructions(provider_key: str) -> str:
    name = "Gmail (Google Cloud)" if provider_key == "gmail" else "Outlook (Microsoft Entra)"
    return (
        f"OAuth para {name} no está configurado.\n\n"
        "Ve a Archivo → Preferencias → pestaña «OAuth» y rellena el "
        "Client ID y el Client secret de tu aplicación de escritorio.\n\n"
        f"URI de redirección obligatoria: {OAUTH_REDIRECT_URI}"
    )

# Instrucciones de configuración de OAuth para Gmail.
def gmail_oauth_setup_html() -> str:
    return (
        "<b>Gmail (Google Cloud)</b><br>"
        f'1. Abre la <a href="{GOOGLE_CLOUD_URL}">consola de Google Cloud</a> '
        "y crea o elige un proyecto.<br>"
        f'2. Activa la <a href="{GOOGLE_GMAIL_API_URL}">Gmail API</a>.<br>'
        f'3. En <a href="{GOOGLE_CREDENTIALS_URL}">Credenciales</a>, crea un '
        "<b>ID de cliente OAuth</b> de tipo <b>Aplicación de escritorio</b>.<br>"
        "4. Si usas pantalla de consentimiento en modo prueba, añade tu correo "
        "como usuario de prueba.<br>"
        f"5. Copia el <b>Client ID</b> y el <b>Client secret</b> abajo. "
        f"URI de redirección: <code>{OAUTH_REDIRECT_URI}</code>."
    )

# Instrucciones de configuración de OAuth para Outlook.
def outlook_oauth_setup_html() -> str:
    return (
        "<b>Outlook / Microsoft 365 (Entra ID)</b><br>"
        f'1. Abre el <a href="{AZURE_APP_REGISTRATIONS_URL}">portal de Azure</a> '
        "→ Registros de aplicaciones → Nueva inscripción.<br>"
        "2. Tipo: <b>Aplicaciones móviles y de escritorio</b>; URI de redirección: "
        f"<code>{OAUTH_REDIRECT_URI}</code>.<br>"
        "3. En <b>Permisos de API</b>, añade permisos delegados con los ámbitos "
        "<code>IMAP.AccessAsUser.All</code>, <code>SMTP.Send</code> y "
        "<code>offline_access</code> (recurso Office 365 / Outlook).<br>"
        "4. En <b>Certificados y secretos</b>, crea un secreto de cliente y cópialo "
        "(solo se muestra una vez).<br>"
        "5. Pega el <b>ID de aplicación (client_id)</b> y el <b>secreto</b> abajo."
    )
