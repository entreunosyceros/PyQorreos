"""El alta de Gmail se reduce a correo e inicio de sesión en el navegador."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

import pytest
from PySide6.QtWidgets import QApplication

from pyqorreos.core.account import MailAccount, simple_browser_login
from pyqorreos.core.oauth import AuthMethod
from pyqorreos.core.settings import Settings
from pyqorreos.ui.account_dialog import AccountDialog


@pytest.fixture(scope="module")
def qapp():
    application = QApplication.instance() or QApplication([])
    yield application


def test_gmail_uses_browser_login() -> None:
    assert simple_browser_login("Gmail", "")
    assert simple_browser_login("Personalizado", "user@gmail.com")
    assert simple_browser_login("Personalizado", "user@googlemail.com")
    assert not simple_browser_login("Yahoo", "user@yahoo.com")
    assert not simple_browser_login("Outlook / Hotmail / MSN", "a@outlook.com")
    assert simple_browser_login(
        "Outlook / Hotmail / MSN", "a@outlook.com", outlook_ready=True
    )


def test_new_gmail_dialog_hides_servers(qapp) -> None:
    dialog = AccountDialog(Settings(), None)
    assert dialog.provider_combo.currentText() == "Gmail"
    assert dialog.auth_combo.currentIndex() == 1
    assert dialog._reception_box.isHidden()
    assert dialog._sending_box.isHidden()
    assert dialog._provider_host.isHidden()
    assert dialog._signature_box.isHidden()
    assert dialog.test_btn.isHidden()
    assert dialog.oauth_config_btn.isHidden()
    assert not dialog.oauth_btn.isHidden()
    assert not dialog.advanced_btn.isHidden()

    dialog._toggle_advanced()
    assert not dialog._reception_box.isHidden()
    assert not dialog._sending_box.isHidden()
    dialog.close()


def test_password_gmail_account_stays_advanced(qapp) -> None:
    account = MailAccount(
        email="user@gmail.com",
        imap_host="imap.gmail.com",
        auth_method=AuthMethod.PASSWORD.value,
    )
    dialog = AccountDialog(Settings(), account)
    assert not dialog._reception_box.isHidden()
    dialog.close()
