"""
OpenPGP (GnuPG) para cifrado y firmas de correo.

Capa opcional: solo se activa si el usuario lo habilita en preferencias.
Requiere el binario `gpg` en el sistema y el paquete Python `python-gnupg`.
"""

from __future__ import annotations

import email
import re
import shutil
from dataclasses import dataclass, field
from email import policy
from email.message import EmailMessage, Message
from email.utils import getaddresses
from pathlib import Path
from typing import Any

from pyqorreos.core.settings import CONFIG_DIR

try:
    import gnupg  # type: ignore[import-untyped]

    _HAS_GNUPG = True
except ImportError:
    gnupg = None  # type: ignore[assignment]
    _HAS_GNUPG = False

_ARMOR_BEGIN = re.compile(
    r"-----BEGIN PGP (MESSAGE|SIGNED MESSAGE)-----",
    re.IGNORECASE,
)
_INLINE_ENCRYPTED = re.compile(
    r"-----BEGIN PGP MESSAGE-----",
    re.IGNORECASE,
)


@dataclass
class PgpStatus:
    """Estado OpenPGP de un mensaje mostrado al usuario."""

    encrypted: bool = False
    signed: bool = False
    signature_valid: bool | None = None
    signer: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "encrypted": self.encrypted,
            "signed": self.signed,
            "signature_valid": self.signature_valid,
            "signer": self.signer,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> PgpStatus:
        if not isinstance(data, dict):
            return cls()
        return cls(
            encrypted=bool(data.get("encrypted")),
            signed=bool(data.get("signed")),
            signature_valid=data.get("signature_valid"),
            signer=str(data.get("signer", "")),
            error=str(data.get("error", "")),
        )


@dataclass
class OpenPgpSettings:
    """Preferencias OpenPGP efectivas al procesar un mensaje."""

    enabled: bool = False
    auto_decrypt: bool = True
    sign_by_default: bool = False
    encrypt_by_default: bool = False
    use_system_gnupg_home: bool = False
    signing_key_id: str = ""
    cache_decrypted_bodies: bool = True


def gpg_binary_available() -> bool:
    return bool(shutil.which("gpg"))


def openpgp_available() -> bool:
    return _HAS_GNUPG and gpg_binary_available()


def openpgp_unavailable_reason() -> str:
    if not _HAS_GNUPG:
        return "Falta el paquete Python «python-gnupg». Instálalo con pip."
    if not gpg_binary_available():
        return "No se encontró el programa «gpg» (GnuPG) en el sistema."
    return ""


def gnupg_home(use_system: bool) -> Path:
    if use_system:
        return Path.home() / ".gnupg"
    path = CONFIG_DIR / "gnupg"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_gpg(use_system_home: bool = False) -> Any | None:
    if not openpgp_available():
        return None
    assert gnupg is not None
    home = gnupg_home(use_system_home)
    home.mkdir(parents=True, exist_ok=True)
    return gnupg.GPG(gnupghome=str(home), gpgbinary=shutil.which("gpg") or "gpg")


def classify_mime_message(msg: Message) -> str:
    """
    Clasifica el mensaje MIME.

    Devuelve: encrypted | signed | inline | none
    """
    ctype = (msg.get_content_type() or "").lower()
    if ctype == "multipart/encrypted":
        return "encrypted"
    if ctype == "multipart/signed":
        return "signed"
    if ctype in ("application/pgp-encrypted", "application/octet-stream"):
        return "encrypted"
    if ctype == "application/pgp-signature":
        return "signed"
    payload = _message_text_payload(msg)
    if payload and _ARMOR_BEGIN.search(payload):
        if _INLINE_ENCRYPTED.search(payload):
            return "inline"
        return "signed"
    if msg.is_multipart():
        for part in msg.walk():
            ptype = (part.get_content_type() or "").lower()
            if ptype in ("application/pgp-encrypted", "application/octet-stream"):
                if "encrypted" in str(part.get("Content-Description", "")).lower():
                    return "encrypted"
            if ptype == "application/pgp-signature":
                return "signed"
    return "none"


def _message_text_payload(msg: Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if "attachment" in str(part.get("Content-Disposition", "")).lower():
                continue
            payload = part.get_payload(decode=True)
            if payload:
                try:
                    return payload.decode("utf-8", errors="replace")
                except (AttributeError, UnicodeDecodeError):
                    continue
        return ""
    payload = msg.get_payload(decode=True)
    if not payload:
        return ""
    return payload.decode("utf-8", errors="replace")


def _extract_encrypted_bytes(msg: Message) -> bytes | None:
    if msg.get_content_type() == "multipart/encrypted":
        octet: bytes | None = None
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            subtype = (part.get_content_subtype() or "").lower()
            ptype = (part.get_content_type() or "").lower()
            if subtype == "octet-stream" or ptype == "application/octet-stream":
                data = part.get_payload(decode=True)
                if isinstance(data, bytes) and data:
                    octet = data
        return octet
    if msg.get_content_type() in ("application/pgp-encrypted", "application/octet-stream"):
        data = msg.get_payload(decode=True)
        return data if isinstance(data, bytes) else None
    text = _message_text_payload(msg)
    if text and _INLINE_ENCRYPTED.search(text):
        return text.encode("utf-8")
    return None


def _signed_parts(msg: Message) -> tuple[bytes | None, bytes | None]:
    """Devuelve (cuerpo firmado, firma detached) para multipart/signed."""
    if msg.get_content_type() != "multipart/signed":
        return None, None
    parts = [p for p in msg.iter_parts() if not p.is_multipart()]
    if len(parts) < 2:
        return None, None
    signed = parts[0].get_payload(decode=True)
    signature = parts[1].get_payload(decode=True)
    return (
        signed if isinstance(signed, bytes) else None,
        signature if isinstance(signature, bytes) else None,
    )


def verify_signed_message(
    msg: Message,
    *,
    use_system_home: bool = False,
) -> PgpStatus:
    status = PgpStatus(signed=True)
    gpg = get_gpg(use_system_home)
    if gpg is None:
        status.error = openpgp_unavailable_reason()
        status.signature_valid = False
        return status
    signed, signature = _signed_parts(msg)
    if signed is None:
        text = _message_text_payload(msg)
        if text and "BEGIN PGP SIGNED MESSAGE" in text:
            verified = gpg.verify(text)
        else:
            status.error = "No se encontró la parte firmada"
            status.signature_valid = False
            return status
    elif signature is not None:
        verified = gpg.verify(signed, signature)
    else:
        status.error = "Firma PGP incompleta"
        status.signature_valid = False
        return status
    if not hasattr(verified, "valid"):
        status.signature_valid = False
        status.error = "No se pudo verificar la firma"
        return status
    status.signature_valid = bool(verified.valid)
    if verified.valid:
        status.signer = str(getattr(verified, "username", "") or "")
    else:
        status.error = str(getattr(verified, "status", "") or "Firma no válida")
    return status


def decrypt_message(
    msg: Message,
    *,
    use_system_home: bool = False,
    passphrase: str | None = None,
) -> tuple[Message | None, PgpStatus]:
    """
    Descifra un mensaje PGP/MIME o inline.

    Devuelve (mensaje interior parseado, estado). Si falla, mensaje es None.
    """
    status = PgpStatus(encrypted=True)
    gpg = get_gpg(use_system_home)
    if gpg is None:
        status.error = openpgp_unavailable_reason()
        return None, status
    ciphertext = _extract_encrypted_bytes(msg)
    if not ciphertext:
        status.error = "No se encontró contenido cifrado"
        return None, status
    decrypted = gpg.decrypt(ciphertext, passphrase=passphrase)
    if not decrypted.ok:
        status.error = str(decrypted.status or "Error al descifrar")
        return None, status
    data = decrypted.data
    if isinstance(data, str):
        data = data.encode("utf-8")
    if not data:
        status.error = "Mensaje descifrado vacío"
        return None, status
    inner = email.message_from_bytes(data, policy=policy.default)
    status.encrypted = True
    if getattr(decrypted, "sig_info", None):
        status.signed = True
        status.signature_valid = True
        status.signer = str(decrypted.username or "")
    return inner, status


def process_incoming_message(
    raw: bytes,
    *,
    settings: OpenPgpSettings,
    passphrase: str | None = None,
) -> tuple[Message, PgpStatus]:
    """
    Procesa el RFC822 entrante: descifra/verifica si aplica.

    Si OpenPGP está desactivado, devuelve el mensaje original sin coste extra
  más allá del parseo MIME.
    """
    msg = email.message_from_bytes(raw, policy=policy.default)
    if not settings.enabled:
        return msg, PgpStatus()

    kind = classify_mime_message(msg)
    if kind == "none":
        return msg, PgpStatus()

    if kind in ("encrypted", "inline"):
        if not settings.auto_decrypt:
            status = PgpStatus(encrypted=True, error="Descifrado automático desactivado")
            return msg, status
        inner, status = decrypt_message(
            msg,
            use_system_home=settings.use_system_gnupg_home,
            passphrase=passphrase,
        )
        if inner is not None:
            if classify_mime_message(inner) == "signed":
                verify = verify_signed_message(
                    inner, use_system_home=settings.use_system_gnupg_home
                )
                status.signed = verify.signed
                status.signature_valid = verify.signature_valid
                status.signer = verify.signer or status.signer
                if verify.error and verify.signature_valid is False:
                    status.error = verify.error
            return inner, status
        return msg, status

    if kind == "signed":
        status = verify_signed_message(
            msg, use_system_home=settings.use_system_gnupg_home
        )
        return msg, status

    return msg, PgpStatus()


def parse_recipient_emails(*fields: str) -> list[str]:
    addresses: list[str] = []
    seen: set[str] = set()
    for field in fields:
        for _name, addr in getaddresses([field or ""]):
            key = addr.strip().lower()
            if key and key not in seen:
                seen.add(key)
                addresses.append(addr.strip())
    return addresses


def encrypt_outgoing_message(
    msg: EmailMessage,
    *,
    recipients: list[str],
    sign: bool,
    encrypt: bool,
    signing_key_id: str,
    use_system_home: bool = False,
) -> bytes:
    """Cifra y/o firma un mensaje saliente (PGP/MIME)."""
    if not sign and not encrypt:
        return msg.as_bytes()
    gpg = get_gpg(use_system_home)
    if gpg is None:
        raise RuntimeError(openpgp_unavailable_reason())
    if encrypt and not recipients:
        raise ValueError("No hay destinatarios para cifrar")
    sign_key = signing_key_id.strip() if sign else None
    if sign and not sign_key:
        secret = gpg.list_keys(secret=True)
        if not secret:
            raise ValueError("No hay clave privada para firmar")
        sign_key = secret[0]["fingerprint"]
    encrypted = gpg.encrypt(
        msg.as_bytes(),
        recipients=recipients if encrypt else [],
        sign=sign_key,
        armor=False,
        mime=True,
        always_trust=True,
    )
    if not encrypted.ok:
        raise RuntimeError(str(encrypted.status or "Error al cifrar o firmar"))
    data = encrypted.data
    if isinstance(data, str):
        return data.encode("utf-8")
    return bytes(data)


def list_public_keys(use_system_home: bool = False) -> list[dict[str, str]]:
    gpg = get_gpg(use_system_home)
    if gpg is None:
        return []
    keys: list[dict[str, str]] = []
    for key in gpg.list_keys():
        keys.append(
            {
                "keyid": key.get("keyid", ""),
                "fingerprint": key.get("fingerprint", ""),
                "uids": ", ".join(key.get("uids", [])),
                "expires": key.get("expires", ""),
            }
        )
    return keys


def list_secret_keys(use_system_home: bool = False) -> list[dict[str, str]]:
    gpg = get_gpg(use_system_home)
    if gpg is None:
        return []
    keys: list[dict[str, str]] = []
    for key in gpg.list_keys(secret=True):
        keys.append(
            {
                "keyid": key.get("keyid", ""),
                "fingerprint": key.get("fingerprint", ""),
                "uids": ", ".join(key.get("uids", [])),
            }
        )
    return keys


def import_key_file(path: str, use_system_home: bool = False) -> tuple[int, str]:
    gpg = get_gpg(use_system_home)
    if gpg is None:
        return 0, openpgp_unavailable_reason()
    result = gpg.import_keys(Path(path).read_text(encoding="utf-8", errors="replace"))
    count = int(getattr(result, "count", 0) or 0)
    if count <= 0:
        return 0, "No se importó ninguna clave"
    return count, ""


def pgp_status_summary(status: PgpStatus) -> str:
    parts: list[str] = []
    if status.encrypted:
        parts.append("Cifrado OpenPGP")
    if status.signed:
        if status.signature_valid is True:
            who = f" ({status.signer})" if status.signer else ""
            parts.append(f"Firmado — firma válida{who}")
        elif status.signature_valid is False:
            parts.append("Firmado — firma no válida")
        else:
            parts.append("Firmado")
    if status.error:
        parts.append(status.error)
    return " · ".join(parts) if parts else ""


def settings_from_user_prefs(prefs: object) -> OpenPgpSettings:
    """Construye OpenPgpSettings desde UserPreferences (sin import circular)."""
    return OpenPgpSettings(
        enabled=bool(getattr(prefs, "openpgp_enabled", False)),
        auto_decrypt=bool(getattr(prefs, "openpgp_auto_decrypt", True)),
        sign_by_default=bool(getattr(prefs, "openpgp_sign_by_default", False)),
        encrypt_by_default=bool(getattr(prefs, "openpgp_encrypt_by_default", False)),
        use_system_gnupg_home=bool(getattr(prefs, "openpgp_use_system_gnupg_home", False)),
        signing_key_id=str(getattr(prefs, "openpgp_signing_key_id", "") or ""),
        cache_decrypted_bodies=bool(
            getattr(prefs, "openpgp_cache_decrypted_bodies", True)
        ),
    )
