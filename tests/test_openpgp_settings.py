"""Preferencias y resumen de estado OpenPGP."""

from __future__ import annotations

import pytest

from pyqorreos.core.openpgp import (
    OpenPgpSettings,
    PgpStatus,
    gpg_binary_available,
    openpgp_available,
    openpgp_unavailable_reason,
    pgp_status_summary,
    settings_from_user_prefs,
)
from pyqorreos.core.user_preferences import UserPreferences


def test_settings_defaults() -> None:
    prefs = UserPreferences()
    settings = settings_from_user_prefs(prefs)
    assert settings == OpenPgpSettings()


def test_settings_from_user_prefs_full() -> None:
    prefs = UserPreferences(
        openpgp_enabled=True,
        openpgp_auto_decrypt=False,
        openpgp_sign_by_default=True,
        openpgp_encrypt_by_default=True,
        openpgp_use_system_gnupg_home=True,
        openpgp_signing_key_id="ABCD1234",
        openpgp_cache_decrypted_bodies=False,
    )
    settings = settings_from_user_prefs(prefs)
    assert settings == OpenPgpSettings(
        enabled=True,
        auto_decrypt=False,
        sign_by_default=True,
        encrypt_by_default=True,
        use_system_gnupg_home=True,
        signing_key_id="ABCD1234",
        cache_decrypted_bodies=False,
    )


def test_settings_from_user_prefs_missing_attrs() -> None:
    class BarePrefs:
        pass

    settings = settings_from_user_prefs(BarePrefs())
    assert settings.enabled is False
    assert settings.auto_decrypt is True


def test_pgp_status_roundtrip_dict() -> None:
    status = PgpStatus(
        encrypted=True,
        signed=True,
        signature_valid=True,
        signer="alice@example.com",
        error="",
    )
    restored = PgpStatus.from_dict(status.to_dict())
    assert restored == status


def test_pgp_status_from_dict_none() -> None:
    assert PgpStatus.from_dict(None) == PgpStatus()
    assert PgpStatus.from_dict("bad") == PgpStatus()


def test_pgp_status_summary_encrypted_and_valid_signature() -> None:
    status = PgpStatus(
        encrypted=True,
        signed=True,
        signature_valid=True,
        signer="alice@example.com",
    )
    text = pgp_status_summary(status)
    assert "Cifrado OpenPGP" in text
    assert "firma válida" in text
    assert "alice@example.com" in text


def test_pgp_status_summary_invalid_signature() -> None:
    text = pgp_status_summary(PgpStatus(signed=True, signature_valid=False))
    assert "firma no válida" in text


def test_pgp_status_summary_appends_error() -> None:
    text = pgp_status_summary(
        PgpStatus(encrypted=True, error="Descifrado cancelado")
    )
    assert "Descifrado cancelado" in text


def test_openpgp_unavailable_reason_without_gnupg(monkeypatch: pytest.MonkeyPatch) -> None:
    from pyqorreos.core import openpgp as mod

    monkeypatch.setattr(mod, "_HAS_GNUPG", False)
    reason = openpgp_unavailable_reason()
    assert "python-gnupg" in reason
    assert not openpgp_available()


def test_openpgp_unavailable_reason_without_gpg_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    from pyqorreos.core import openpgp as mod

    monkeypatch.setattr(mod, "_HAS_GNUPG", True)
    monkeypatch.setattr(mod, "gpg_binary_available", lambda: False)
    reason = openpgp_unavailable_reason()
    assert "gpg" in reason.lower()
    assert not openpgp_available()


def test_gpg_binary_available_delegates_to_which(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pyqorreos.core.openpgp.shutil.which", lambda name: "/usr/bin/gpg" if name == "gpg" else None)
    assert gpg_binary_available()
