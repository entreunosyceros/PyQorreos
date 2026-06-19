"""
Persistencia de configuración y credenciales.

Las cuentas se guardan en ~/.config/pyqorreos/accounts.json y las contraseñas
en el llavero del sistema mediante la librería keyring.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import keyring

from pyqorreos.core.account import MailAccount
from pyqorreos.core.classifier import ClassificationRules, MailClassifier

SERVICE_NAME = "PyQorreos"
CONFIG_DIR = Path.home() / ".config" / "pyqorreos"
ACCOUNTS_FILE = CONFIG_DIR / "accounts.json"
CLASSIFICATION_FILE = CONFIG_DIR / "classification.json"


class Settings:
    """Persistencia de cuentas y contraseñas."""

    def __init__(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    def _read_raw_json(self) -> dict[str, Any]:
        """Método privado auxiliar para leer el JSON base sin romper si está vacío."""
        if not ACCOUNTS_FILE.exists():
            return {"accounts": [], "last_account_id": None}
        try:
            return json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"accounts": [], "last_account_id": None}

    def load_accounts(self) -> list[MailAccount]:
        """Lee las cuentas guardadas en accounts.json."""
        data = self._read_raw_json()
        accounts = []
        for item in data.get("accounts", []):
            account = MailAccount.from_dict(item)
            # Salvavidas por si alguna cuenta migrada no tiene ID
            if not account.id:
                account.id = str(uuid.uuid4())
            accounts.append(account)
        return accounts

    def save_accounts(self, accounts: list[MailAccount]) -> None:
        """Guarda la lista de cuentas preservando otras claves de configuración."""
        data = self._read_raw_json()
        data["accounts"] = [a.to_dict() for a in accounts]
        
        ACCOUNTS_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def store_password(self, account_id: str, password: str) -> None:
        """Guarda la contraseña de una cuenta en el llavero del sistema."""
        keyring.set_password(SERVICE_NAME, account_id, password)

    def get_password(self, account_id: str) -> str | None:
        return keyring.get_password(SERVICE_NAME, account_id)

    def delete_password(self, account_id: str) -> None:
        try:
            keyring.delete_password(SERVICE_NAME, account_id)
        except keyring.errors.PasswordDeleteError:
            pass

    def get_auth_secret(self, account: MailAccount) -> str | None:
        """Contraseña o access_token OAuth listo para IMAP/SMTP."""
        from pyqorreos.core.oauth import AuthMethod, OAuthError, ensure_valid_access_token

        if account.auth_method == AuthMethod.OAUTH2.value:
            try:
                return ensure_valid_access_token(account)
            except OAuthError:
                return None
        return self.get_password(account.id)

    def delete_account_secrets(self, account_id: str, auth_method: str = "password") -> None:
        """Elimina contraseña y token OAuth de una cuenta."""
        from pyqorreos.core.oauth import AuthMethod, delete_oauth_token

        self.delete_password(account_id)
        if auth_method == AuthMethod.OAUTH2.value:
            delete_oauth_token(account_id)

    def get_last_account_id(self) -> str | None:
        data = self._read_raw_json()
        return data.get("last_account_id")

    def set_last_account_id(self, account_id: str) -> None:
        """Guarda el ID de la última cuenta usada sin machacar la lista de cuentas."""
        data = self._read_raw_json()
        data["last_account_id"] = account_id
        
        ACCOUNTS_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load_classification_rules(self) -> ClassificationRules:
        """Lee las reglas de clasificación de correo."""
        if not CLASSIFICATION_FILE.exists():
            return ClassificationRules()
        try:
            data = json.loads(CLASSIFICATION_FILE.read_text(encoding="utf-8"))
            return ClassificationRules.from_dict(data)
        except json.JSONDecodeError:
            return ClassificationRules()

    def save_classification_rules(self, rules: ClassificationRules) -> None:
        """Guarda las reglas de clasificación en disco."""
        CLASSIFICATION_FILE.write_text(
            json.dumps(rules.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def get_classifier(self) -> MailClassifier:
        """Devuelve un clasificador con las reglas guardadas."""
        return MailClassifier(self.load_classification_rules())

    def learn_sender_category(self, sender: str, category: str) -> None:
        """Aprende la categoría preferida para un remitente (feedback del usuario)."""
        from pyqorreos.core.classifier import MailCategory

        classifier = self.get_classifier()
        classifier.learn_sender(sender, MailCategory(category))
        self.save_classification_rules(classifier.rules)