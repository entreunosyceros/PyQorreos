"""
Utilidades para carpetas IMAP: árbol, papelera y contadores.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

TRASH_KEYWORDS = ("trash", "deleted", "papelera", "bin", "elementos eliminados")
DRAFTS_KEYWORDS = ("draft", "borrador")
SPAM_KEYWORDS = ("spam", "junk", "no deseado")


@dataclass
class FolderTreeNode:
    name: str
    full_path: str
    children: list[FolderTreeNode] = field(default_factory=list)
    unread: int = 0


def folder_leaf(name: str) -> str:
    return name.rsplit("/", 1)[-1].strip().lower()


def is_trash_folder(name: str) -> bool:
    leaf = folder_leaf(name)
    return any(k in leaf for k in TRASH_KEYWORDS)


def is_drafts_folder(name: str) -> bool:
    leaf = folder_leaf(name)
    return any(k in leaf for k in DRAFTS_KEYWORDS)


def find_drafts_folder(folders: list[str]) -> str | None:
    for name in folders:
        if is_drafts_folder(name):
            return name
    for name in folders:
        if folder_leaf(name) == "drafts":
            return name
    return None


def build_folder_tree(
    folders: list[str], unread_map: dict[str, int] | None = None
) -> list[FolderTreeNode]:
    """Construye un árbol a partir de rutas con delimitador /."""
    unread_map = unread_map or {}
    roots: dict[str, FolderTreeNode] = {}
    order: list[str] = []

    def get_node(path: str) -> FolderTreeNode:
        if path not in roots:
            parts = path.split("/")
            roots[path] = FolderTreeNode(
                name=parts[-1],
                full_path=path,
                unread=unread_map.get(path, 0),
            )
            order.append(path)
        return roots[path]

    for folder in sorted(folders, key=lambda f: f.upper()):
        parts = folder.split("/")
        for i in range(len(parts)):
            path = "/".join(parts[: i + 1])
            node = get_node(path)
            if i > 0:
                parent_path = "/".join(parts[:i])
                parent = get_node(parent_path)
                if node not in parent.children:
                    parent.children.append(node)

    top_level = [roots[p] for p in order if "/" not in p]
    for node in roots.values():
        node.children.sort(key=lambda n: n.name.upper())
    return sorted(top_level, key=lambda n: n.name.upper())


def normalize_thread_subject(subject: str) -> str:
    s = (subject or "").strip()
    while True:
        new = re.sub(r"^(re|fwd|fw):\s*", "", s, flags=re.IGNORECASE).strip()
        if new == s:
            break
        s = new
    return s or "(Sin asunto)"
