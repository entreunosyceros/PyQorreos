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
    # False en nodos intermedios que el servidor no lista como carpeta real
    # (agrupan visualmente, pero no se pueden abrir).
    exists: bool = True


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
    if folder_leaf(path) in _SYSTEM_LEAF_NAMES:
        return True
    # Dovecot/cPanel anidan con «.»: INBOX.Drafts, INBOX.Trash, INBOX.Sent…
    if lower.startswith("inbox."):
        segments = lower.split(".")
        return len(segments) == 2 and segments[1] in _SYSTEM_LEAF_NAMES
    return False


def can_delete_folder(name: str) -> bool:
    return not is_protected_folder(name)


def folder_descendants(
    folders: list[str], folder: str, delimiter: str = "/"
) -> list[str]:
    sep = delimiter or "/"
    prefix = folder.rstrip(sep) + sep
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


ARCHIVE_KEYWORDS = ("archive", "archivo", "archivados", "all mail", "todos")


def is_archive_folder(name: str) -> bool:
    leaf = folder_leaf(name)
    return any(k in leaf for k in ARCHIVE_KEYWORDS)


def find_archive_folder(folders: list[str]) -> str | None:
    """Busca la carpeta de archivo (Archive/Archivo/[Gmail]/All Mail)."""
    for name in folders:
        if folder_leaf(name) in ("archive", "archivo", "archivados"):
            return name
    for name in folders:
        if is_archive_folder(name):
            return name
    return None


def detect_folder_delimiter(folders: list[str]) -> str:
    """
    Deduce el separador jerárquico a partir de los nombres de carpeta.

    Dovecot/cPanel usan «.» (`INBOX.Archive`) y Gmail o Exchange usan «/».
    Solo se acepta «.» si el primer segmento existe como carpeta real, para no
    partir nombres que simplemente contienen un punto (p. ej. «web.dev»).
    """
    names = [name for name in folders if name]
    if any("/" in name for name in names):
        return "/"
    lowered = {name.lower() for name in names}
    for name in names:
        if "." not in name:
            continue
        head = name.split(".", 1)[0].lower()
        if head and head != name.lower() and head in lowered:
            return "."
    return "/"


def build_folder_tree(
    folders: list[str],
    unread_map: dict[str, int] | None = None,
    delimiter: str | None = None,
) -> list[FolderTreeNode]:
    """Construye un árbol a partir de rutas jerárquicas del servidor IMAP."""
    unread_map = unread_map or {}
    sep = delimiter or detect_folder_delimiter(folders)
    real_paths = {name for name in folders if name}
    nodes: dict[str, FolderTreeNode] = {}
    order: list[str] = []

    def get_node(path: str, name: str) -> FolderTreeNode:
        if path not in nodes:
            nodes[path] = FolderTreeNode(
                name=name,
                full_path=path,
                unread=unread_map.get(path, 0),
                exists=path in real_paths,
            )
            order.append(path)
        return nodes[path]

    for folder in sorted(real_paths, key=lambda f: f.upper()):
        parts = [part for part in folder.split(sep) if part]
        if not parts:
            continue
        for i in range(len(parts)):
            path = sep.join(parts[: i + 1])
            node = get_node(path, parts[i])
            if i > 0:
                parent = get_node(sep.join(parts[:i]), parts[i - 1])
                if node not in parent.children:
                    parent.children.append(node)

    top_level = [nodes[p] for p in order if sep not in p]
    for node in nodes.values():
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
