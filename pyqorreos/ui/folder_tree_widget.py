"""
Utilidades para poblar el árbol de carpetas.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from pyqorreos.core.folder_utils import FolderTreeNode, build_folder_tree
from pyqorreos.ui.folder_icons import icon_for_folder


def populate_folder_tree(
    tree: QTreeWidget,
    folders: list[str],
    unread_map: dict[str, int] | None = None,
    *,
    select_folder: str | None = None,
) -> None:
    tree.clear()
    roots = build_folder_tree(folders, unread_map)

    def add_node(parent_item: QTreeWidgetItem | None, node: FolderTreeNode) -> QTreeWidgetItem:
        label = node.name
        if node.unread > 0:
            label = f"{node.name} ({node.unread})"
        if parent_item is None:
            item = QTreeWidgetItem([label])
            tree.addTopLevelItem(item)
        else:
            item = QTreeWidgetItem(parent_item, [label])
        item.setIcon(0, icon_for_folder(node.full_path))
        item.setData(0, Qt.ItemDataRole.UserRole, node.full_path)
        for child in node.children:
            add_node(item, child)
        return item

    index_map: dict[str, QTreeWidgetItem] = {}

    def collect(item: QTreeWidgetItem) -> None:
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            index_map[str(path)] = item
        for i in range(item.childCount()):
            collect(item.child(i))

    for root in roots:
        add_node(None, root)

    for i in range(tree.topLevelItemCount()):
        collect(tree.topLevelItem(i))

    if select_folder and select_folder in index_map:
        item = index_map[select_folder]
        tree.setCurrentItem(item)
        parent = item.parent()
        while parent:
            parent.setExpanded(True)
            parent = parent.parent()
    elif tree.topLevelItemCount():
        inbox = index_map.get("INBOX")
        if inbox:
            tree.setCurrentItem(inbox)
        else:
            tree.setCurrentItem(tree.topLevelItem(0))

    tree.expandToDepth(0)


def selected_folder_path(tree: QTreeWidget) -> str | None:
    item = tree.currentItem()
    if not item:
        return None
    path = item.data(0, Qt.ItemDataRole.UserRole)
    return str(path) if path else None
