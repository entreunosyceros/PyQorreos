"""
Credenciales OAuth de aplicación (client_id / client_secret) por proveedor.

Orden de resolución (el primero con Client ID gana):

1. ``~/.config/pyqorreos/oauth_clients.json`` — override del usuario (Preferencias)
2. Variables de entorno ``PYQORREOS_OAUTH_<PROVEEDOR>_CLIENT_ID`` / ``_CLIENT_SECRET``
3. Cliente **embebido** de PyQorreos (como Thunderbird): ficheros de recursos /
   instalación del paquete

Así el usuario final puede pulsar «Identificarse con Google» sin registrar
nada en Google Cloud. Quien empaquete la app debe proporcionar el Client ID
de la aplicación de escritorio de PyQorreos una sola vez.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

OAUTH_CLIENTS_DIR = Path.home() / ".config" / "pyqorreos"
OAUTH_CLIENTS_FILE = OAUTH_CLIENTS_DIR / "oauth_clients.json"
OAUTH_CLIENTS_EXAMPLE = Path(__file__).resolve().parents[2] / "oauth_clients.example.json"

# Recursos embebidos junto al código (desarrollo y paquete .deb).
_RESOURCES_DIR = Path(__file__).resolve().parent.parent / "resources"
BUILTIN_OAUTH_FILE = _RESOURCES_DIR / "oauth_clients.builtin.json"
BUILTIN_OAUTH_LOCAL_FILE = _RESOURCES_DIR / "oauth_clients.builtin.local.json"
BUILTIN_OAUTH_EXAMPLE_FILE = _RESOURCES_DIR / "oauth_clients.builtin.example.json"

# Copia instalada por el paquete .deb / instalación de sistema.
SYSTEM_BUILTIN_OAUTH_FILES = (
    Path("/usr/share/pyqorreos/oauth_clients.builtin.json"),
    Path("/usr/local/share/pyqorreos/oauth_clients.builtin.json"),
)

OAUTH_PROVIDER_KEYS = ("gmail", "outlook")
OAUTH_REDIRECT_URI = "http://127.0.0.1"
# La petición real añade el puerto efímero y la barra final.
OAUTH_REDIRECT_RUNTIME = "http://127.0.0.1:<puerto>/"

GOOGLE_CLOUD_URL = "https://console.cloud.google.com/"
GOOGLE_GMAIL_API_URL = "https://console.cloud.google.com/apis/library/gmail.googleapis.com"
GOOGLE_CREDENTIALS_URL = "https://console.cloud.google.com/apis/credentials"
AZURE_APP_REGISTRATIONS_URL = (
    "https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade"
)

# Marcadores del ejemplo: no cuentan como credenciales reales.
_PLACEHOLDER_MARKERS = (
    "tu_client",
    "tu_application",
    "your_client",
    "example",
    "changeme",
    "placeholder",
)


@dataclass(frozen=True)
class OAuthClientCredentials:
    client_id: str
    client_secret: str = ""
    source: str = "user"  # user | env | builtin


def _write_private_json(path: Path, text: str) -> None:
    """Escribe JSON con permisos 0600 (el Client secret no debe ser legible por otros)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(path, flags, 0o600)
    try:
        os.write(fd, text.encode("utf-8"))
    finally:
        os.close(fd)
    os.chmod(path, 0o600)


def oauth_redirect_help() -> str:
    """Texto de ayuda: URI de registro y URI real con puerto variable."""
    return (
        f"{OAUTH_REDIRECT_RUNTIME} "
        f"(el puerto lo elige PyQorreos en cada identificación; "
        f"en la consola registra {OAUTH_REDIRECT_URI} como aplicación de escritorio)"
    )


def _empty_oauth_clients_data() -> dict[str, dict[str, str]]:
    return {
        "gmail": {"client_id": "", "client_secret": ""},
        "outlook": {"client_id": "", "client_secret": ""},
    }


def _is_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    if not lowered:
        return True
    return any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


def _normalize_provider_block(block: object) -> dict[str, str]:
    if not isinstance(block, dict):
        return {"client_id": "", "client_secret": ""}
    client_id = str(block.get("client_id", "")).strip()
    client_secret = str(block.get("client_secret", "")).strip()
    if _is_placeholder(client_id):
        client_id = ""
    if _is_placeholder(client_secret):
        client_secret = ""
    return {"client_id": client_id, "client_secret": client_secret}


def _read_oauth_json(path: Path) -> dict[str, dict[str, str]]:
    data = _empty_oauth_clients_data()
    if not path.is_file():
        return data
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return data
    if not isinstance(raw, dict):
        return data
    for key in OAUTH_PROVIDER_KEYS:
        data[key] = _normalize_provider_block(raw.get(key))
    return data


def load_oauth_clients_data() -> dict[str, dict[str, str]]:
    """Datos del override de usuario para el formulario de Preferencias."""
    return _read_oauth_json(OAUTH_CLIENTS_FILE)


def save_oauth_clients_data(data: dict[str, dict[str, str]]) -> None:
    """Persiste el override del usuario. Vaciar un proveedor elimina su entrada."""
    OAUTH_CLIENTS_DIR.mkdir(parents=True, exist_ok=True)
    out: dict[str, dict[str, str]] = {}
    for key in OAUTH_PROVIDER_KEYS:
        block = data.get(key) if isinstance(data.get(key), dict) else {}
        client_id = str(block.get("client_id", "")).strip()
        client_secret = str(block.get("client_secret", "")).strip()
        if _is_placeholder(client_id):
            client_id = ""
        if not client_id:
            continue
        entry: dict[str, str] = {"client_id": client_id}
        if client_secret and not _is_placeholder(client_secret):
            entry["client_secret"] = client_secret
        out[key] = entry
    _write_private_json(
        OAUTH_CLIENTS_FILE,
        json.dumps(out, indent=2, ensure_ascii=False) + "\n",
    )


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


def _env_oauth_client(provider_key: str) -> OAuthClientCredentials | None:
    prefix = f"PYQORREOS_OAUTH_{provider_key.upper()}"
    client_id = os.environ.get(f"{prefix}_CLIENT_ID", "").strip()
    if not client_id or _is_placeholder(client_id):
        return None
    client_secret = os.environ.get(f"{prefix}_CLIENT_SECRET", "").strip()
    if _is_placeholder(client_secret):
        client_secret = ""
    return OAuthClientCredentials(
        client_id=client_id,
        client_secret=client_secret,
        source="env",
    )


def builtin_oauth_search_paths() -> tuple[Path, ...]:
    """Rutas candidatas del cliente OAuth incluido en la aplicación."""
    return (
        BUILTIN_OAUTH_LOCAL_FILE,
        *SYSTEM_BUILTIN_OAUTH_FILES,
        BUILTIN_OAUTH_FILE,
    )


def load_builtin_oauth_clients_data() -> dict[str, dict[str, str]]:
    """Lee el primer fichero embebido disponible con al menos un Client ID."""
    merged = _empty_oauth_clients_data()
    for path in builtin_oauth_search_paths():
        data = _read_oauth_json(path)
        if any(data[key]["client_id"] for key in OAUTH_PROVIDER_KEYS):
            return data
    return merged


def load_oauth_client(provider_key: str) -> OAuthClientCredentials | None:
    """
    Credenciales efectivas para el flujo OAuth.

    Preferencias del usuario > variables de entorno > cliente embebido.
    """
    key = (provider_key or "").strip().lower()
    if key not in OAUTH_PROVIDER_KEYS:
        return None

    user_block = load_oauth_clients_data().get(key, {})
    user_id = str(user_block.get("client_id", "")).strip()
    if user_id:
        return OAuthClientCredentials(
            client_id=user_id,
            client_secret=str(user_block.get("client_secret", "")).strip(),
            source="user",
        )

    env_creds = _env_oauth_client(key)
    if env_creds is not None:
        return env_creds

    builtin = load_builtin_oauth_clients_data().get(key, {})
    builtin_id = str(builtin.get("client_id", "")).strip()
    if builtin_id:
        return OAuthClientCredentials(
            client_id=builtin_id,
            client_secret=str(builtin.get("client_secret", "")).strip(),
            source="builtin",
        )
    return None


def oauth_clients_configured(provider_key: str) -> bool:
    creds = load_oauth_client(provider_key)
    return creds is not None and bool(creds.client_id)


def oauth_client_source(provider_key: str) -> str | None:
    """Origen de las credenciales: user, env, builtin o None."""
    creds = load_oauth_client(provider_key)
    return creds.source if creds else None


def uses_builtin_oauth(provider_key: str) -> bool:
    return oauth_client_source(provider_key) == "builtin"


def install_builtin_from_user_config(
    *,
    destination: Path | None = None,
    local: bool = True,
) -> Path:
    """
    Copia el override del usuario al fichero embebido (para empaquetar el .deb).

    Por defecto escribe ``oauth_clients.builtin.local.json`` (gitignored).
    """
    data = load_oauth_clients_data()
    if not any(data[key]["client_id"] for key in OAUTH_PROVIDER_KEYS):
        raise ValueError(
            "No hay Client ID en Preferencias → OAuth. "
            "Configura Gmail/Outlook una vez y vuelve a intentarlo."
        )
    return embed_oauth_clients(data, destination=destination, local=local)


def persist_oauth_clients(data: dict[str, dict[str, str]]) -> Path:
    """Guarda el Client ID para poder identificarse en este equipo.

    El override de ``~/.config`` es el que usa el botón de inicio de sesión.
    El fichero embebido se actualiza además si la carpeta del programa se
    puede escribir. Un ``.deb`` ya instalado suele tener ``/usr/share`` en
    solo lectura: eso no impide guardar la copia del usuario.
    """
    error = validate_oauth_clients_data(data)
    if error:
        raise ValueError(error)
    normalized = _empty_oauth_clients_data()
    for key in OAUTH_PROVIDER_KEYS:
        normalized[key] = _normalize_provider_block(data.get(key))
    if not any(normalized[key]["client_id"] for key in OAUTH_PROVIDER_KEYS):
        raise ValueError("No hay Client ID válido para guardar.")
    save_oauth_clients_data(normalized)
    for local in (True, False):
        try:
            embed_oauth_clients(normalized, local=local)
        except OSError:
            continue
    return OAUTH_CLIENTS_FILE


def embed_oauth_clients(
    data: dict[str, dict[str, str]],
    *,
    destination: Path | None = None,
    local: bool = True,
) -> Path:
    """Escribe un diccionario de clientes OAuth como recurso embebido."""
    dest = destination or (
        BUILTIN_OAUTH_LOCAL_FILE if local else BUILTIN_OAUTH_FILE
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    out: dict[str, dict[str, str]] = {}
    for key in OAUTH_PROVIDER_KEYS:
        block = data.get(key) if isinstance(data.get(key), dict) else {}
        client_id = str(block.get("client_id", "")).strip()
        client_secret = str(block.get("client_secret", "")).strip()
        if _is_placeholder(client_id) or not client_id:
            continue
        entry: dict[str, str] = {"client_id": client_id}
        if client_secret and not _is_placeholder(client_secret):
            entry["client_secret"] = client_secret
        out[key] = entry
    if not out:
        raise ValueError("No hay Client ID válido para embeber.")
    _write_private_json(
        dest,
        json.dumps(out, indent=2, ensure_ascii=False) + "\n",
    )
    return dest


def oauth_setup_instructions(provider_key: str) -> str:
    name = "Gmail (Google Cloud)" if provider_key == "gmail" else "Outlook (Microsoft Entra)"
    if oauth_clients_configured(provider_key):
        return (
            f"OAuth para {name} está listo.\n\n"
            "Pulsa «Identificarse» y autoriza en el navegador."
        )
    return (
        f"OAuth para {name} no está disponible en esta instalación.\n\n"
        "Pulsa «Configurar inicio de sesión Google/Microsoft…» y pega el "
        "Client ID de la aplicación de escritorio de PyQorreos (se crea una "
        "sola vez en Google Cloud / Azure).\n\n"
        "Después podrás identificarte en el navegador sin repetir esos pasos.\n\n"
        f"URI de redirección: {oauth_redirect_help()}"
    )


def gmail_oauth_setup_html() -> str:
    return (
        "<b>Gmail (Google Cloud)</b> — opcional<br>"
        "PyQorreos puede iniciar sesión con Google <b>sin que configures nada</b> "
        "si el paquete incluye el cliente OAuth de la aplicación.<br><br>"
        "Solo rellena estos campos si quieres usar <b>tu propia</b> aplicación "
        "de Google Cloud (sustituye al cliente incluido):<br>"
        f'1. <a href="{GOOGLE_CLOUD_URL}">Consola de Google Cloud</a> → proyecto.<br>'
        f'2. Activa la <a href="{GOOGLE_GMAIL_API_URL}">Gmail API</a>.<br>'
        f'3. <a href="{GOOGLE_CREDENTIALS_URL}">Credenciales</a> → ID de cliente '
        "OAuth → <b>Aplicación de escritorio</b>.<br>"
        f"4. URI de redirección: <code>{oauth_redirect_help()}</code>."
    )


def outlook_oauth_setup_html() -> str:
    return (
        "<b>Outlook / Microsoft 365</b> — opcional<br>"
        "Si el paquete incluye el cliente OAuth de PyQorreos, no hace falta "
        "registrar nada en Azure.<br><br>"
        "Solo rellena estos campos para usar <b>tu propia</b> aplicación:<br>"
        f'1. <a href="{AZURE_APP_REGISTRATIONS_URL}">Portal de Azure</a> → '
        "Registros de aplicaciones → Nueva inscripción.<br>"
        "2. Tipo: <b>Aplicaciones móviles y de escritorio</b>; URI: "
        f"<code>{oauth_redirect_help()}</code>.<br>"
        "3. Permisos: <code>IMAP.AccessAsUser.All</code>, <code>SMTP.Send</code>, "
        "<code>offline_access</code>.<br>"
        "4. Crea un secreto de cliente y pégalo abajo."
    )


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description=(
            "Gestiona el cliente OAuth embebido de PyQorreos. "
            "Copia Preferencias → OAuth al fichero incluido en el paquete."
        )
    )
    parser.add_argument(
        "command",
        choices=("install-builtin", "status"),
        help="install-builtin: copia credenciales de usuario al recurso embebido",
    )
    parser.add_argument(
        "--shared",
        action="store_true",
        help="Escribe oauth_clients.builtin.json en lugar del .local gitignored",
    )
    args = parser.parse_args()
    if args.command == "status":
        for key in OAUTH_PROVIDER_KEYS:
            source = oauth_client_source(key)
            print(f"{key}: {source or 'missing'}")
        raise SystemExit(0)
    try:
        path = install_builtin_from_user_config(local=not args.shared)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"Cliente OAuth embebido escrito en: {path}")
    print("No subas este archivo a un repositorio público si contiene secretos.")
    raise SystemExit(0)
