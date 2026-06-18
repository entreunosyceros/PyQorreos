"""
Preferencias de usuario persistidas en ~/.config/pyqorreos/preferences.json
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

PREFERENCES_FILE = Path.home() / ".config" / "pyqorreos" / "preferences.json"
LARGE_FOLDER_THRESHOLD = 5000


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

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> UserPreferences:
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


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


def save_preferences(prefs: UserPreferences) -> None:
    PREFERENCES_FILE.parent.mkdir(parents=True, exist_ok=True)
    PREFERENCES_FILE.write_text(
        json.dumps(prefs.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
