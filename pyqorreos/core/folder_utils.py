"""
Utilidades para carpetas IMAP: árbol, papelera y contadores.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

TRASH_KEYWORDS = ("trash", "deleted", "papelera", "bin", "elementos eliminados")
DRAFTS_KEYWORDS = ("draft", "borrador")

# Carpetas que no deben poder eliminarse desde el cliente.
_PROTECTED_PREFIXES = ("[gmail]", "[google mail]")
_SYSTEM_LEAF_NAMES = frozenset({
    "inbox",
    "sent",
    "sent items",
    "sent mail",
    "sent messages",
    "enviados",
    "elementos enviados",
    "mensajes enviados",
    "drafts",
    "draft",
    "borradores",
    "borrador",
    "trash",
    "deleted",
    "deleted items",
    "deleted messages",
    "bin",
    "papelera",
    "elementos eliminados",
    "spam",
    "junk",
    "junk e-mail",
    "junk email",
    "bulk mail",
    "correo no deseado",
    "no deseado",
    "archive",
    "archives",
    "archivo",
    "all mail",
    "todos",
    "important",
    "starred",
    "outbox",
    "bandeja de salida",
})


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


def is_protected_folder(name: str) -> bool:
    """Carpetas del sistema (INBOX, [Gmail]/…, Enviados, etc.) que no se pueden borrar."""
    path = name.strip()
    lower = path.lower()
    if lower == "inbox":
        return True
    if any(lower.startswith(prefix) for prefix in _PROTECTED_PREFIXES):
        return True
    return folder_leaf(path) in _SYSTEM_LEAF_NAMES


def can_delete_folder(name: str) -> bool:
    return not is_protected_folder(name)


def folder_descendants(folders: list[str], folder: str) -> list[str]:
    prefix = folder.rstrip("/") + "/"
    return sorted(f for f in folders if f.startswith(prefix))


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


SENT_KEYWORDS = ("sent", "enviado", "outbox")


def is_sent_folder(name: str) -> bool:
    leaf = folder_leaf(name)
    return any(k in leaf for k in SENT_KEYWORDS) or leaf in (
        "sent items",
        "sent mail",
        "sent messages",
        "elementos enviados",
        "mensajes enviados",
    )


def find_sent_folder(folders: list[str]) -> str | None:
    for name in folders:
        if is_sent_folder(name):
            return name
    for name in folders:
        if folder_leaf(name) in ("sent", "sent items", "enviados"):
            return name
    return None


def find_trash_folder(folders: list[str]) -> str | None:
    for name in folders:
        if is_trash_folder(name):
            return name
    for name in folders:
        if folder_leaf(name) in ("trash", "deleted items", "papelera"):
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
