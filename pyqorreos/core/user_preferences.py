"""
Preferencias de usuario persistidas en ~/.config/pyqorreos/preferences.json
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

PREFERENCES_FILE = Path.home() / ".config" / "pyqorreos" / "preferences.json"
LARGE_FOLDER_THRESHOLD = 5000
# Plantillas de composición de correo.
DEFAULT_COMPOSE_SNIPPETS: list[dict[str, str]] = [
    {"name": "Saludo formal", "text": "Estimado/a,\n\n"},
    {"name": "Saludo informal", "text": "Hola,\n\n"},
    {"name": "Gracias", "text": "Muchas gracias por su respuesta.\n\n"},
    {"name": "Despedida", "text": "\n\nUn saludo cordial,"},
    {"name": "Aviso legal", "text": "\n\nEste mensaje y sus adjuntos son confidenciales."},
]

# Preferencias de usuario.
@dataclass
class UserPreferences:
    block_remote_images: bool = True
    background_sync_enabled: bool = True
    background_sync_interval_sec: int = 900
    use_imap_idle: bool = True
    notify_new_mail: bool = True
    page_size: int = 50
    thread_view: bool = False
    sort_by: str = "date_desc"  # date_desc, date_asc, sender, subject
    headers_only_large_folders: bool = True
    delete_from_server_after_download: bool = False
    compose_snippets: list[dict[str, str]] = field(
        default_factory=lambda: list(DEFAULT_COMPOSE_SNIPPETS)
    )
    translate_target_language: str = "es"
    theme: str = "light"
    compose_request_read_receipt: bool = False
    search_all_folders: bool = False
    openpgp_enabled: bool = False
    openpgp_auto_decrypt: bool = True
    openpgp_sign_by_default: bool = False
    openpgp_encrypt_by_default: bool = False
    openpgp_use_system_gnupg_home: bool = False
    openpgp_signing_key_id: str = ""
    openpgp_cache_decrypted_bodies: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    # Reconstruye las preferencias desde un diccionario guardado en disco.
    def from_dict(cls, data: dict) -> UserPreferences:
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        if "compose_snippets" not in filtered:
            filtered["compose_snippets"] = list(DEFAULT_COMPOSE_SNIPPETS)
        else:
            filtered["compose_snippets"] = normalize_compose_snippets(
                filtered["compose_snippets"]
            )
        from pyqorreos.core.translate import normalize_language_code
        from pyqorreos.ui.theme import normalize_theme

        filtered["translate_target_language"] = normalize_language_code(
            str(filtered.get("translate_target_language", "es"))
        )
        filtered["theme"] = normalize_theme(str(filtered.get("theme", "light")))
        return cls(**filtered)

# Filtra entradas inválidas y asegura claves name/text.
def normalize_compose_snippets(
    snippets: list[dict[str, str]] | None,
) -> list[dict[str, str]]:
    """Filtra entradas inválidas y asegura claves name/text."""
    if not snippets:
        return []
    cleaned: list[dict[str, str]] = []
    for item in snippets:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        text = str(item.get("text", ""))
        if not name and not text.strip():
            continue
        cleaned.append(
            {
                "name": name or "Plantilla",
                "text": text,
            }
        )
    return cleaned

# Lee las preferencias desde disco.
def load_preferences() -> UserPreferences:
    prefs_dir = PREFERENCES_FILE.parent
    prefs_dir.mkdir(parents=True, exist_ok=True)
    if not PREFERENCES_FILE.exists():
        return UserPreferences()
    try:
        data = json.loads(PREFERENCES_FILE.read_text(encoding="utf-8"))
        return UserPreferences.from_dict(data)
    except (json.JSONDecodeError, TypeError):
        return UserPreferences()

# Guarda las preferencias en disco.
def save_preferences(prefs: UserPreferences) -> None:
    PREFERENCES_FILE.parent.mkdir(parents=True, exist_ok=True)
    PREFERENCES_FILE.write_text(
        json.dumps(prefs.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
