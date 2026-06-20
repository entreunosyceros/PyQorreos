"""
Autenticación OAuth2 para Gmail y Outlook (IMAP/SMTP vía XOAUTH2).
"""

from __future__ import annotations

import base64
import json
import secrets
import hashlib
import socketserver
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import asdict, dataclass
from enum import Enum
from http.server import BaseHTTPRequestHandler
from typing import Callable

import keyring

from pyqorreos.core.account import MailAccount
from pyqorreos.core.oauth_clients import (
    OAuthClientCredentials,
    load_oauth_client,
    oauth_clients_configured,
    oauth_setup_instructions,
)
from pyqorreos.core.settings import SERVICE_NAME


class AuthMethod(str, Enum):
    # Método de autenticación por contraseña
    PASSWORD = "password"
    # Método de autenticación por OAuth2
    OAUTH2 = "oauth2"

# Error de configuración o autorización OAuth
class OAuthError(Exception):
    """Error de configuración o autorización OAuth."""


@dataclass
class OAuthProvider:
    name: str
    auth_url: str
    token_url: str
    scopes: tuple[str, ...]

# Proveedores de OAuth2
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
            "https://outlook.office365.com/IMAP.AccessAsUser.All",
            "https://outlook.office365.com/SMTP.Send",
            "offline_access",
        ),
    ),
}

# Token de autenticación OAuth2
@dataclass
class OAuthToken:
    provider: str
    access_token: str
    refresh_token: str = ""
    expires_at: float = 0.0
    token_type: str = "Bearer"
    # Verifica si el token ha expirado
    def is_expired(self, *, skew_sec: int = 120) -> bool:
        if not self.expires_at:
            return False
        return time.time() >= self.expires_at - skew_sec
    # Convierte el token a JSON
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    # Reconstruye el token desde un JSON
    @classmethod
    def from_json(cls, raw: str) -> OAuthToken:
        data = json.loads(raw)
        return cls(
            provider=str(data.get("provider", "")),
            access_token=str(data.get("access_token", "")),
            refresh_token=str(data.get("refresh_token", "")),
            expires_at=float(data.get("expires_at", 0) or 0),
            token_type=str(data.get("token_type", "Bearer") or "Bearer"),
        )


def oauth_token_key(account_id: str) -> str:
    """Clave legada (token JSON completo); se migra al guardar de nuevo."""
    return f"oauth:{account_id}"


def oauth_refresh_key(account_id: str) -> str:
    return f"oauth:refresh:{account_id}"


def oauth_access_key(account_id: str) -> str:
    return f"oauth:access:{account_id}"


def _load_legacy_token(account_id: str) -> OAuthToken | None:
    raw = keyring.get_password(SERVICE_NAME, oauth_token_key(account_id))
    if not raw:
        return None
    try:
        return OAuthToken.from_json(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def store_oauth_tokens(account_id: str, token: OAuthToken) -> None:
    """Guarda refresh_token (persistente) y access_token (caduca) por separado."""
    if token.refresh_token:
        keyring.set_password(
            SERVICE_NAME, oauth_refresh_key(account_id), token.refresh_token
        )
    access_blob = json.dumps(
        {
            "access_token": token.access_token,
            "expires_at": token.expires_at,
            "provider": token.provider,
            "token_type": token.token_type,
        }
    )
    keyring.set_password(SERVICE_NAME, oauth_access_key(account_id), access_blob)
    # Eliminar formato legado si existía.
    try:
        keyring.delete_password(SERVICE_NAME, oauth_token_key(account_id))
    except keyring.errors.PasswordDeleteError:
        pass


def get_oauth_token(account_id: str) -> OAuthToken | None:
    """Reconstruye el token a partir del llavero (refresh + access)."""
    refresh = keyring.get_password(SERVICE_NAME, oauth_refresh_key(account_id))
    access_raw = keyring.get_password(SERVICE_NAME, oauth_access_key(account_id))
    if refresh or access_raw:
        access_token = ""
        expires_at = 0.0
        provider = ""
        token_type = "Bearer"
        if access_raw:
            try:
                data = json.loads(access_raw)
                access_token = str(data.get("access_token", ""))
                expires_at = float(data.get("expires_at", 0) or 0)
                provider = str(data.get("provider", ""))
                token_type = str(data.get("token_type", "Bearer") or "Bearer")
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        return OAuthToken(
            provider=provider,
            access_token=access_token,
            refresh_token=refresh or "",
            expires_at=expires_at,
            token_type=token_type,
        )
    return _load_legacy_token(account_id)


def store_oauth_token(account_id: str, token: OAuthToken) -> None:
    """Alias de store_oauth_tokens (compatibilidad)."""
    store_oauth_tokens(account_id, token)

# Elimina el token de autenticación OAuth2
def delete_oauth_token(account_id: str) -> None:
    for key in (
        oauth_refresh_key(account_id),
        oauth_access_key(account_id),
        oauth_token_key(account_id),
    ):
        # Elimina el token de autenticación OAuth2
        try:
            keyring.delete_password(SERVICE_NAME, key)
        except keyring.errors.PasswordDeleteError:
            pass

# Verifica si el token de autenticación OAuth2 existe
def has_oauth_token(account_id: str) -> bool:
    refresh = keyring.get_password(SERVICE_NAME, oauth_refresh_key(account_id))
    # Si existe un refresh_token, devuelve True
    if refresh:
        # Si existe un legacy_token, devuelve True
        return True
    legacy = _load_legacy_token(account_id)
    return legacy is not None and bool(legacy.refresh_token or legacy.access_token)

# Detecta el proveedor de OAuth2
def detect_oauth_provider(email: str, imap_host: str) -> str | None:
    host = imap_host.lower()
    addr = email.strip().lower()
    if "gmail" in host or addr.endswith("@gmail.com") or addr.endswith("@googlemail.com"):
        return "gmail"
    if (
        "office365" in host
        or "outlook" in host
        or "hotmail" in host
        or addr.endswith("@outlook.com")
        or addr.endswith("@hotmail.com")
        or addr.endswith("@live.com")
    ):
        return "outlook"
    return None

# Mensaje de error si no hay sesión OAuth activa
def oauth_not_configured_message(provider_key: str | None) -> str:
    if provider_key and oauth_clients_configured(provider_key):
        return (
            f"No hay sesión OAuth activa para "
            f"{OAUTH_PROVIDERS.get(provider_key, OAuthProvider('', '', '', ())).name}.\n\n"
            "Edita la cuenta y pulsa «Identificarse con Google/Microsoft»."
        )
    return oauth_setup_instructions(provider_key or "gmail")

# Genera un par de verificador y desafío de PKCE
def generate_pkce_pair() -> tuple[str, str]:
    verifier = (
        base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")
    )
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode("ascii")
        .rstrip("=")
    )
    return verifier, challenge

# Construye la URL de autorización OAuth2
def build_authorization_url(
    provider_key: str,
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    state: str,
) -> str:
    provider = OAUTH_PROVIDERS[provider_key]
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(provider.scopes),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    if provider_key == "gmail":
        params["access_type"] = "offline"
        params["prompt"] = "consent"
    query = urllib.parse.urlencode(params)
    return f"{provider.auth_url}?{query}"

# Realiza una solicitud POST para obtener un token OAuth2
def _post_token_request(provider_key: str, payload: dict[str, str]) -> OAuthToken:
    provider = OAUTH_PROVIDERS[provider_key]
    body = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(
        provider.token_url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    # Realiza una solicitud POST para obtener un token OAuth2
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise OAuthError(f"Error al obtener token ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise OAuthError(f"No se pudo contactar con el proveedor: {exc}") from exc

    # Obtiene el access_token
    access = data.get("access_token")
    if not access:
        raise OAuthError(f"Respuesta OAuth sin access_token: {data}")
    expires_in = int(data.get("expires_in", 3600) or 3600)
    return OAuthToken(
        provider=provider_key,
        access_token=str(access),
        refresh_token=str(data.get("refresh_token", "") or ""),
        expires_at=time.time() + expires_in,
        token_type=str(data.get("token_type", "Bearer") or "Bearer"),
    )

# Intercambia un código de autorización por un token OAuth2
def exchange_authorization_code(
    provider_key: str,
    client: OAuthClientCredentials,
    code: str,
    redirect_uri: str,
    code_verifier: str,
) -> OAuthToken:
    payload = {
        "client_id": client.client_id,
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
        "code_verifier": code_verifier,
    }
    if client.client_secret:
        payload["client_secret"] = client.client_secret
    return _post_token_request(provider_key, payload)

# Refresca un token OAuth2
def refresh_oauth_token(
    provider_key: str,
    client: OAuthClientCredentials,
    token: OAuthToken,
) -> OAuthToken:
    # Verifica si hay un refresh_token
    if not token.refresh_token:
        raise OAuthError("No hay refresh_token; vuelve a iniciar sesión OAuth.")
    # Construye el payload para la solicitud POST
    payload = {
        "client_id": client.client_id,
        "refresh_token": token.refresh_token,
        "grant_type": "refresh_token",
    }
    # Si hay un client_secret, añade el client_secret al payload
    if client.client_secret:
        payload["client_secret"] = client.client_secret
    refreshed = _post_token_request(provider_key, payload)
    # Si no hay un refresh_token, crea un nuevo token con el refresh_token del token original
    if not refreshed.refresh_token:
        refreshed = OAuthToken(
            provider=refreshed.provider,
            access_token=refreshed.access_token,
            refresh_token=token.refresh_token,
            expires_at=refreshed.expires_at,
            token_type=refreshed.token_type,
        )
    return refreshed

# Devuelve un access_token válido, renovándolo si hace falta
def ensure_valid_access_token(account: MailAccount) -> str:
    """Devuelve un access_token válido, renovándolo si hace falta."""
    provider_key = detect_oauth_provider(account.email, account.imap_host)
    if not provider_key:
        raise OAuthError("Esta cuenta no admite OAuth2 (solo Gmail u Outlook).")
    token = get_oauth_token(account.id)
    if not token:
        raise OAuthError(oauth_not_configured_message(provider_key))
    if not token.is_expired() and token.access_token:
        return token.access_token
    client = load_oauth_client(provider_key)
    if not client:
        raise OAuthError(oauth_setup_instructions(provider_key))
    refreshed = refresh_oauth_token(provider_key, client, token)
    store_oauth_tokens(account.id, refreshed)
    return refreshed.access_token

# Construye una cadena SASL XOAUTH2 (base64) para IMAP/SMTP
def build_xoauth2_string(email: str, access_token: str) -> str:
    """Cadena SASL XOAUTH2 (base64) para IMAP/SMTP."""
    auth_str = f"user={email}\x01auth=Bearer {access_token}\x01\x01"
    return base64.b64encode(auth_str.encode("utf-8")).decode("ascii")

# Manejador de callback OAuth2
class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    server_version = "PyQorreosOAuth/1.0"

    def do_GET(self) -> None:
        # Analiza la URL y obtiene los parámetros
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        self.server.auth_code = params.get("code", [None])[0]  # type: ignore[attr-defined]
        self.server.auth_error = params.get("error", [None])[0]  # type: ignore[attr-defined]
        self.server.auth_state = params.get("state", [None])[0]  # type: ignore[attr-defined]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h1>Autorizaci\xc3\xb3n completada</h1>"
            b"<p>Puedes cerrar esta ventana y volver a PyQorreos.</p></body></html>"
        )
    # Maneja los mensajes de log
    def log_message(self, format: str, *args) -> None:
        return

# Servidor de red para el callback OAuth2
class _OAuthRedirectServer(socketserver.TCPServer):
    allow_reuse_address = True
    # Inicializa el servidor de red para el callback OAuth2
    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _OAuthCallbackHandler)
        self.auth_code: str | None = None
        self.auth_error: str | None = None
        self.auth_state: str | None = None


class OAuthFlow:
    """
    Flujo OAuth2 interactivo (navegador + callback local).

    Ejecutar run_flow() desde un hilo en segundo plano; no bloquea la interfaz.
    """

    def __init__(
        self,
        provider_key: str,
        *,
        open_browser: Callable[[str], None] | None = None,
        timeout_sec: int = 300,
    ) -> None:
        self.provider_key = provider_key
        self._open_browser = open_browser or webbrowser.open
        self.timeout_sec = timeout_sec
    # Abre el navegador, espera el callback y devuelve los tokens (sin guardar).
    def run_flow(self) -> OAuthToken:
        """Abre el navegador, espera el callback y devuelve los tokens (sin guardar)."""
        client = load_oauth_client(self.provider_key)
        if not client:
            raise OAuthError(oauth_setup_instructions(self.provider_key))
        # Genera un par de verificador y desafío de PKCE
        verifier, challenge = generate_pkce_pair()
        state = secrets.token_urlsafe(24)
        server = _OAuthRedirectServer()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        redirect_uri = f"http://127.0.0.1:{port}/"
        # Construye la URL de autorización OAuth2
        auth_url = build_authorization_url(
            self.provider_key, client.client_id, redirect_uri, challenge, state
        )
        if not self._open_browser(auth_url):
            server.shutdown()
            raise OAuthError("No se pudo abrir el navegador web.")
        # Establece un tiempo de espera para la autorización
        deadline = time.time() + self.timeout_sec
        try:
            while time.time() < deadline:
                if server.auth_code or server.auth_error:
                    break
                time.sleep(0.05)
        finally:
            server.shutdown()
            thread.join(timeout=2)
        # Si hay un error de autorización, lanza un error
        if server.auth_error:
            raise OAuthError(f"Autorización rechazada: {server.auth_error}")
        if not server.auth_code:
            raise OAuthError("Tiempo de espera agotado al autorizar en el navegador.")
        if server.auth_state != state:
            raise OAuthError("Estado OAuth inválido (posible ataque CSRF).")

        token = exchange_authorization_code(
            self.provider_key, client, server.auth_code, redirect_uri, verifier
        )
        # Si no hay un refresh_token, lanza un error
        if not token.refresh_token:
            raise OAuthError(
                "El proveedor no devolvió refresh_token. "
                "Vuelve a autorizar (en Google usa prompt=consent)."
            )
        return token

# Atajo síncrono (bloquea el hilo llamador). Preferir OAuthFlowWorker en la UI.
def run_oauth_authorization(
    provider_key: str,
    account_id: str,
    *,
    open_browser: Callable[[str], None] | None = None,
    process_events: Callable[[], None] | None = None,
    timeout_sec: int = 300,
) -> OAuthToken:
    """
    Atajo síncrono (bloquea el hilo llamador). Preferir OAuthFlowWorker en la UI.
    """
    del process_events  # compatibilidad con llamadas antiguas
    flow = OAuthFlow(
        provider_key,
        open_browser=open_browser,
        timeout_sec=timeout_sec,
    )
    token = flow.run_flow()
    store_oauth_tokens(account_id, token)
    return token
