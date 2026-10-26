"""Cliente OAuth embebido y cadena de resolución de credenciales."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pyqorreos.core import oauth_clients as mod


@pytest.fixture(autouse=True)
def _isolate_oauth_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    user_file = tmp_path / "user_oauth.json"
    builtin_file = tmp_path / "builtin.json"
    local_file = tmp_path / "builtin.local.json"
    monkeypatch.setattr(mod, "OAUTH_CLIENTS_FILE", user_file)
    monkeypatch.setattr(mod, "OAUTH_CLIENTS_DIR", tmp_path)
    monkeypatch.setattr(mod, "BUILTIN_OAUTH_FILE", builtin_file)
    monkeypatch.setattr(mod, "BUILTIN_OAUTH_LOCAL_FILE", local_file)
    monkeypatch.setattr(mod, "SYSTEM_BUILTIN_OAUTH_FILES", ())
    for key in ("GMAIL", "OUTLOOK"):
        monkeypatch.delenv(f"PYQORREOS_OAUTH_{key}_CLIENT_ID", raising=False)
        monkeypatch.delenv(f"PYQORREOS_OAUTH_{key}_CLIENT_SECRET", raising=False)
    return tmp_path


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_user_override_wins_over_builtin(_isolate_oauth_paths: Path) -> None:
    _write(
        mod.BUILTIN_OAUTH_FILE,
        {"gmail": {"client_id": "builtin-id", "client_secret": "bsec"}},
    )
    _write(
        mod.OAUTH_CLIENTS_FILE,
        {"gmail": {"client_id": "user-id", "client_secret": "usec"}},
    )
    creds = mod.load_oauth_client("gmail")
    assert creds is not None
    assert creds.client_id == "user-id"
    assert creds.source == "user"


def test_builtin_used_when_user_empty(_isolate_oauth_paths: Path) -> None:
    _write(
        mod.BUILTIN_OAUTH_FILE,
        {"gmail": {"client_id": "embedded.apps.googleusercontent.com", "client_secret": "s"}},
    )
    creds = mod.load_oauth_client("gmail")
    assert creds is not None
    assert creds.client_id.startswith("embedded.")
    assert creds.source == "builtin"
    assert mod.uses_builtin_oauth("gmail") is True
    assert mod.oauth_clients_configured("gmail") is True


def test_placeholders_are_ignored(_isolate_oauth_paths: Path) -> None:
    _write(
        mod.BUILTIN_OAUTH_FILE,
        {
            "gmail": {
                "client_id": "TU_CLIENT_ID.apps.googleusercontent.com",
                "client_secret": "TU_CLIENT_SECRET",
            }
        },
    )
    assert mod.load_oauth_client("gmail") is None
    assert mod.oauth_clients_configured("gmail") is False


def test_env_beats_builtin(monkeypatch: pytest.MonkeyPatch, _isolate_oauth_paths: Path) -> None:
    _write(mod.BUILTIN_OAUTH_FILE, {"gmail": {"client_id": "builtin-id"}})
    monkeypatch.setenv("PYQORREOS_OAUTH_GMAIL_CLIENT_ID", "env-id")
    monkeypatch.setenv("PYQORREOS_OAUTH_GMAIL_CLIENT_SECRET", "env-secret")
    creds = mod.load_oauth_client("gmail")
    assert creds is not None
    assert creds.client_id == "env-id"
    assert creds.client_secret == "env-secret"
    assert creds.source == "env"


def test_local_builtin_preferred_over_shared(_isolate_oauth_paths: Path) -> None:
    _write(mod.BUILTIN_OAUTH_FILE, {"gmail": {"client_id": "shared-id"}})
    _write(mod.BUILTIN_OAUTH_LOCAL_FILE, {"gmail": {"client_id": "local-id"}})
    creds = mod.load_oauth_client("gmail")
    assert creds is not None
    assert creds.client_id == "local-id"


def test_install_builtin_from_user_config(_isolate_oauth_paths: Path) -> None:
    _write(
        mod.OAUTH_CLIENTS_FILE,
        {"gmail": {"client_id": "packager-id", "client_secret": "packager-sec"}},
    )
    path = mod.install_builtin_from_user_config(local=True)
    assert path == mod.BUILTIN_OAUTH_LOCAL_FILE
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["gmail"]["client_id"] == "packager-id"
    # Sin override de usuario, el cliente embebido es el que se usa.
    mod.OAUTH_CLIENTS_FILE.unlink()
    creds = mod.load_oauth_client("gmail")
    assert creds is not None
    assert creds.client_id == "packager-id"
    assert creds.source == "builtin"


def test_embed_oauth_clients_writes_local(_isolate_oauth_paths: Path) -> None:
    path = mod.embed_oauth_clients(
        {"gmail": {"client_id": "embed-id", "client_secret": "embed-sec"}},
        local=True,
    )
    assert path == mod.BUILTIN_OAUTH_LOCAL_FILE
    creds = mod.load_oauth_client("gmail")
    assert creds is not None
    assert creds.client_id == "embed-id"
    assert creds.source == "builtin"


def test_embed_oauth_clients_writes_packaged_file(_isolate_oauth_paths: Path) -> None:
    path = mod.embed_oauth_clients(
        {"gmail": {"client_id": "packaged-id", "client_secret": "packaged-sec"}},
        local=False,
    )
    assert path == mod.BUILTIN_OAUTH_FILE
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["gmail"]["client_id"] == "packaged-id"


def test_persist_oauth_clients_survives_readonly_package(
    _isolate_oauth_paths: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _readonly(*_args, **_kwargs):
        raise PermissionError("solo lectura")

    monkeypatch.setattr(mod, "embed_oauth_clients", _readonly)
    path = mod.persist_oauth_clients(
        {"gmail": {"client_id": "desktop-id", "client_secret": "desktop-sec"}}
    )
    assert path == mod.OAUTH_CLIENTS_FILE
    creds = mod.load_oauth_client("gmail")
    assert creds is not None
    assert creds.client_id == "desktop-id"
    assert creds.source == "user"


def test_install_builtin_requires_user_config(_isolate_oauth_paths: Path) -> None:
    with pytest.raises(ValueError, match="No hay Client ID"):
        mod.install_builtin_from_user_config()
