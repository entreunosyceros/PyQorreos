"""
Utilidades para poblar el árbol de carpetas.

El árbol admite varias cuentas: cada cuenta es un nodo raíz desplegable con sus
carpetas debajo. Los elementos de carpeta guardan la ruta IMAP en `UserRole` y
el identificador de su cuenta en `ACCOUNT_ROLE`; los nodos de cuenta solo
guardan el identificador, de modo que `selected_folder_path` devuelve `None`
cuando la selección es una cuenta.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from pyqorreos.core.folder_utils import FolderTreeNode, build_folder_tree
from pyqorreos.ui.action_icons import action_icon
from pyqorreos.ui.folder_icons import icon_for_folder

FOLDER_ROLE = Qt.ItemDataRole.UserRole
ACCOUNT_ROLE = Qt.ItemDataRole.UserRole + 1


@dataclass
class AccountFolders:
    """Carpetas y contadores de una cuenta para pintarlas en el árbol."""

    account_id: str
    label: str
    folders: list[str]
    counts: dict[str, int] = field(default_factory=dict)


@dataclass
class TreeExpansion:
    """Nodos desplegados, para conservarlos al repintar el árbol."""

    accounts: set[str] = field(default_factory=set)
    folders: set[tuple[str, str]] = field(default_factory=set)

    def is_empty(self) -> bool:
        return not self.accounts and not self.folders


def _add_folder_nodes(
    parent_item: QTreeWidgetItem,
    node: FolderTreeNode,
    account_id: str,
    index_map: dict[str, QTreeWidgetItem],
    expanded_folders: set[tuple[str, str]],
    default_expand: bool,
) -> QTreeWidgetItem:
    label = f"{node.name} ({node.unread})" if node.unread > 0 else node.name
    item = QTreeWidgetItem(parent_item, [label])
    item.setIcon(0, icon_for_folder(node.full_path))
    item.setData(0, ACCOUNT_ROLE, account_id)
    if node.exists:
        # Los nodos intermedios que el servidor no lista no se pueden abrir:
        # sin ruta, el árbol los trata como simples agrupadores.
        item.setData(0, FOLDER_ROLE, node.full_path)
        item.setToolTip(0, node.full_path)
        index_map[node.full_path] = item
    else:
        item.setToolTip(0, f"{node.full_path} (agrupación)")
    for child in node.children:
        _add_folder_nodes(
            item, child, account_id, index_map, expanded_folders, False
        )
    if node.children:
        key = (account_id, node.full_path)
        item.setExpanded(key in expanded_folders or default_expand)
    return item


def populate_accounts_tree(
    tree: QTreeWidget,
    accounts: list[AccountFolders],
    *,
    active_account_id: str | None = None,
    select_folder: str | None = None,
    expansion: TreeExpansion | None = None,
) -> None:
    """Pinta todas las cuentas, cada una como un nodo raíz desplegable."""
    tree.clear()
    if not accounts:
        return

    active_id = str(active_account_id) if active_account_id else ""
    state = expansion or TreeExpansion()
    first_paint = state.is_empty()
    active_index: dict[str, QTreeWidgetItem] = {}

    for account in accounts:
        account_id = str(account.account_id)
        account_item = QTreeWidgetItem([account.label])
        account_item.setIcon(0, action_icon("account"))
        account_item.setData(0, ACCOUNT_ROLE, account_id)
        account_item.setToolTip(0, account.label)
        is_active = account_id == active_id
        if is_active:
            font = QFont(account_item.font(0))
            font.setBold(True)
            account_item.setFont(0, font)
        tree.addTopLevelItem(account_item)

        index_map: dict[str, QTreeWidgetItem] = {}
        # En el primer pintado se despliegan las raíces de la cuenta activa
        # para que sus carpetas queden a la vista sin más clics.
        default_expand = is_active and first_paint
        for root in build_folder_tree(account.folders, account.counts):
            _add_folder_nodes(
                account_item,
                root,
                account_id,
                index_map,
                state.folders,
                default_expand,
            )
        if is_active:
            active_index = index_map

        if not account.folders:
            placeholder = QTreeWidgetItem(account_item, ["(sin carpetas guardadas)"])
            placeholder.setData(0, ACCOUNT_ROLE, account_id)
            placeholder.setFlags(Qt.ItemFlag.ItemIsEnabled)

        account_item.setExpanded(
            account_id in state.accounts or (is_active and first_paint)
        )

    if not _select_folder_item(tree, active_index, select_folder):
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            if str(item.data(0, ACCOUNT_ROLE) or "") == active_id:
                tree.setCurrentItem(item)
                break


def _select_folder_item(
    tree: QTreeWidget,
    index_map: dict[str, QTreeWidgetItem],
    select_folder: str | None,
) -> bool:
    """Selecciona la carpeta indicada (o INBOX) y despliega sus ancestros."""
    item = index_map.get(select_folder) if select_folder else None
    if item is None:
        item = index_map.get("INBOX")
    if item is None:
        return False
    tree.setCurrentItem(item)
    parent = item.parent()
    while parent:
        parent.setExpanded(True)
        parent = parent.parent()
    return True


def selected_folder_path(tree: QTreeWidget) -> str | None:
    item = tree.currentItem()
    if not item:
        return None
    path = item.data(0, FOLDER_ROLE)
    return str(path) if path else None


def item_account_id(item: QTreeWidgetItem | None) -> str:
    """Identificador de la cuenta a la que pertenece un elemento del árbol."""
    if item is None:
        return ""
    account_id = item.data(0, ACCOUNT_ROLE)
    return str(account_id) if account_id else ""


def item_folder_path(item: QTreeWidgetItem | None) -> str:
    """Ruta IMAP del elemento, o cadena vacía si es un nodo de cuenta."""
    if item is None:
        return ""
    path = item.data(0, FOLDER_ROLE)
    return str(path) if path else ""


def current_expansion(tree: QTreeWidget) -> TreeExpansion:
    """Estado de despliegue actual del árbol (cuentas y carpetas)."""
    state = TreeExpansion()

    def walk(item: QTreeWidgetItem) -> None:
        if item.isExpanded():
            account_id = item_account_id(item)
            folder = item_folder_path(item)
            if folder and account_id:
                state.folders.add((account_id, folder))
        for i in range(item.childCount()):
            walk(item.child(i))

    for i in range(tree.topLevelItemCount()):
        top = tree.topLevelItem(i)
        account_id = item_account_id(top)
        if top.isExpanded() and account_id:
            state.accounts.add(account_id)
        walk(top)
    return state
