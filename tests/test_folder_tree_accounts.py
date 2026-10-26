"""Árbol de carpetas multicuenta y detección del separador IMAP."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTreeWidget  # noqa: E402

from pyqorreos.core.folder_utils import (  # noqa: E402
    build_folder_tree,
    detect_folder_delimiter,
    is_protected_folder,
)
from pyqorreos.core.mail_service import _parse_list_delimiter, _parse_list_flags  # noqa: E402
from pyqorreos.ui.folder_tree_widget import (  # noqa: E402
    AccountFolders,
    TreeExpansion,
    current_expansion,
    item_account_id,
    item_folder_path,
    populate_accounts_tree,
)
from pyqorreos.ui.main_window import MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def qt_app() -> QApplication:
    return QApplication.instance() or QApplication([])


DOVECOT = [
    "INBOX",
    "INBOX.Archive",
    "INBOX.Archive.2024",
    "INBOX.Drafts",
    "INBOX.Sent",
    "INBOX.Trash",
]


def test_detect_delimiter_slash() -> None:
    assert detect_folder_delimiter(["INBOX", "INBOX/Trabajo"]) == "/"


def test_detect_delimiter_dot_for_dovecot() -> None:
    assert detect_folder_delimiter(DOVECOT) == "."


def test_detect_delimiter_ignores_dots_without_parent() -> None:
    """Un nombre con punto no jerárquico no debe partirse."""
    assert detect_folder_delimiter(["INBOX", "web.dev", "Facturas"]) == "/"


def test_build_tree_nests_dot_folders() -> None:
    roots = build_folder_tree(DOVECOT)
    assert [r.name for r in roots] == ["INBOX"]
    inbox = roots[0]
    assert inbox.full_path == "INBOX"
    assert [c.name for c in inbox.children] == ["Archive", "Drafts", "Sent", "Trash"]
    archive = inbox.children[0]
    assert archive.full_path == "INBOX.Archive"
    assert [c.full_path for c in archive.children] == ["INBOX.Archive.2024"]


def test_build_tree_marks_missing_parents_as_grouping() -> None:
    """Un padre que el servidor no lista agrupa, pero no se puede abrir."""
    roots = build_folder_tree(["Proyectos/Uno", "Proyectos/Dos"])
    assert len(roots) == 1
    assert roots[0].full_path == "Proyectos"
    assert roots[0].exists is False
    assert all(child.exists for child in roots[0].children)


def test_dovecot_system_folders_are_protected() -> None:
    assert is_protected_folder("INBOX.Drafts")
    assert is_protected_folder("INBOX.Trash")
    assert is_protected_folder("INBOX.Sent")
    assert not is_protected_folder("INBOX.Trabajo")
    assert not is_protected_folder("INBOX.Archive.2024")


class _FakeImap:
    def __init__(self) -> None:
        self.renamed: tuple[str, str] | None = None
        self.created: str | None = None

    def rename(self, old: str, new: str):
        self.renamed = (old.strip('"'), new.strip('"'))
        return "OK", [b"done"]

    def create(self, path: str):
        self.created = path.strip('"')
        return "OK", [b"done"]


def _service_with_dovecot_folders() -> tuple[object, _FakeImap]:
    from pyqorreos.core.mail_service import MailService

    service = MailService.__new__(MailService)
    imap = _FakeImap()
    service._imap = imap
    service._imap_lock = __import__("threading").RLock()
    service._folder_delimiter = "."
    service._current_folder = "INBOX"
    names = [*DOVECOT, "INBOX.Trabajo", "INBOX.Trabajo.2024"]
    service.list_folders = lambda: [
        SimpleNamespace(name=name, delimiter=".") for name in names
    ]
    service._ensure_connected_unlocked = lambda: None
    service._require_imap = lambda: imap
    service._quoted_folder = lambda name: f'"{name}"'
    return service, imap


def test_rename_keeps_parent_on_dot_servers() -> None:
    """Renombrar INBOX.Trabajo no debe sacar la carpeta fuera de INBOX."""
    service, imap = _service_with_dovecot_folders()

    mapping = service.rename_folder("INBOX.Trabajo", "Proyectos")

    assert imap.renamed == ("INBOX.Trabajo", "INBOX.Proyectos")
    assert ("INBOX.Trabajo", "INBOX.Proyectos") in mapping
    # La subcarpeta se arrastra en cascada.
    assert ("INBOX.Trabajo.2024", "INBOX.Proyectos.2024") in mapping


def test_rename_rejects_names_with_the_server_delimiter() -> None:
    service, _imap = _service_with_dovecot_folders()

    with pytest.raises(ValueError, match="no puede contener"):
        service.rename_folder("INBOX.Trabajo", "Uno.Dos")


def test_create_subfolder_uses_server_delimiter() -> None:
    service, imap = _service_with_dovecot_folders()

    path = service.create_folder("Trabajo", parent="INBOX")

    assert path == "INBOX.Trabajo"
    assert imap.created == "INBOX.Trabajo"


def test_parse_list_response() -> None:
    line = '(\\HasChildren) "." "INBOX.Archive"'
    assert _parse_list_delimiter(line) == "."
    assert _parse_list_flags(line) == ("\\HasChildren",)
    assert _parse_list_delimiter('(\\HasNoChildren) "/" "INBOX/Work"') == "/"
    assert _parse_list_delimiter('(\\Noselect) NIL "Shared"') == "/"


def test_tree_shows_every_account(qt_app: QApplication) -> None:
    tree = QTreeWidget()
    populate_accounts_tree(
        tree,
        [
            AccountFolders("a1", "Uno <uno@x.com>", ["INBOX", "INBOX.Trabajo"]),
            AccountFolders("a2", "Dos <dos@x.com>", ["INBOX"]),
        ],
        active_account_id="a1",
        select_folder="INBOX",
    )

    assert tree.topLevelItemCount() == 2
    first, second = tree.topLevelItem(0), tree.topLevelItem(1)
    assert item_account_id(first) == "a1"
    assert item_folder_path(first) == ""
    assert first.isExpanded() is True
    assert second.isExpanded() is False
    inbox = first.child(0)
    assert item_folder_path(inbox) == "INBOX"
    assert item_account_id(inbox) == "a1"
    assert item_folder_path(inbox.child(0)) == "INBOX.Trabajo"


def test_tree_keeps_expansion_between_repaints(qt_app: QApplication) -> None:
    tree = QTreeWidget()
    entries = [
        AccountFolders("a1", "Uno", ["INBOX", "INBOX.Trabajo"]),
        AccountFolders("a2", "Dos", ["INBOX"]),
    ]
    populate_accounts_tree(tree, entries, active_account_id="a1")
    tree.topLevelItem(1).setExpanded(True)

    state = current_expansion(tree)
    assert state.accounts == {"a1", "a2"}
    assert ("a1", "INBOX") in state.folders

    populate_accounts_tree(tree, entries, active_account_id="a1", expansion=state)
    assert tree.topLevelItem(1).isExpanded() is True
    assert tree.topLevelItem(0).child(0).isExpanded() is True


def test_tree_collapses_folder_the_user_closed(qt_app: QApplication) -> None:
    tree = QTreeWidget()
    entries = [AccountFolders("a1", "Uno", ["INBOX", "INBOX.Trabajo"])]
    populate_accounts_tree(tree, entries, active_account_id="a1")
    tree.topLevelItem(0).child(0).setExpanded(False)

    state = current_expansion(tree)
    populate_accounts_tree(tree, entries, active_account_id="a1", expansion=state)

    assert tree.topLevelItem(0).child(0).isExpanded() is False


def _window_with_accounts() -> MainWindow:
    window = MainWindow.__new__(MainWindow)
    window.accounts = [
        SimpleNamespace(id="a1", email="uno@x.com", display_name="Uno"),
        SimpleNamespace(id="a2", email="dos@x.com", display_name="Dos"),
    ]
    window.current_account = window.accounts[0]
    window.mail_service = object()
    window._current_folder = "INBOX"
    window._pending_nav = None
    window._pending_folder_rename = None
    window.status_bar = SimpleNamespace(showMessage=lambda *_a: None)
    window.settings = SimpleNamespace(
        get_last_folder=lambda _aid: None,
        set_last_folder=lambda *_a: None,
    )
    return window


def test_clicking_other_account_folder_switches_account() -> None:
    window = _window_with_accounts()
    connected: list[object] = []
    window._connect_account = lambda account, **_k: connected.append(account)

    assert window._switch_to_account("a2", "INBOX.Trabajo") is True

    assert window._pending_nav == ("a2", "INBOX.Trabajo", None)
    assert window._current_folder == "INBOX.Trabajo"
    assert connected and connected[0].email == "dos@x.com"


def test_rename_on_other_account_switches_first_then_renames() -> None:
    window = _window_with_accounts()
    connected: list[object] = []
    window._connect_account = lambda account, **_k: connected.append(account)
    renamed: list[str] = []
    window._rename_folder = renamed.append

    window._request_folder_rename("a2", "INBOX.Trabajo")

    assert window._pending_folder_rename == ("a2", "INBOX.Trabajo")
    assert renamed == []
    assert connected and connected[0].email == "dos@x.com"

    # Ya conectado a la segunda cuenta, el renombrado pendiente se ejecuta.
    window.current_account = window.accounts[1]
    window._apply_pending_folder_rename()

    assert renamed == ["INBOX.Trabajo"]
    assert window._pending_folder_rename is None


def test_rename_on_active_account_is_immediate() -> None:
    window = _window_with_accounts()
    renamed: list[str] = []
    window._rename_folder = renamed.append

    window._request_folder_rename("a1", "INBOX.Trabajo")

    assert renamed == ["INBOX.Trabajo"]
    assert window._pending_folder_rename is None


def test_rename_refuses_system_folders() -> None:
    window = _window_with_accounts()
    renamed: list[str] = []
    window._rename_folder = renamed.append

    window._request_folder_rename("a1", "INBOX.Drafts")

    assert renamed == []
