"""
Clasificación automática de correos: spam, normal e importante.

Combina señales del servidor IMAP (carpeta, flags, cabeceras) con reglas
locales configurables y aprendizaje básico a partir del feedback del usuario.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from email.utils import parseaddr
from enum import Enum
from typing import Any

# Palabras clave en nombres de carpeta IMAP (sin distinguir mayúsculas).
SPAM_FOLDER_KEYWORDS = ("spam", "junk", "basura", "no deseado", "correo no deseado")
IMPORTANT_FOLDER_KEYWORDS = (
    "important",
    "importante",
    "starred",
    "destacado",
    "priorit",
)

# Palabras sospechosas habituales en asuntos de spam.
DEFAULT_SPAM_KEYWORDS = (
    "ganador",
    "lotería",
    "loteria",
    "premio",
    "viagra",
    "casino",
    "oferta imperdible",
    "click aquí",
    "click aqui",
    "urgente: actúa",
    "herencia",
    "bitcoin gratis",
    "crédito aprobado",
    "credito aprobado",
)

# Palabras que suelen indicar correos relevantes.
DEFAULT_IMPORTANT_KEYWORDS = (
    "factura",
    "pedido",
    "confirmación",
    "confirmacion",
    "contrato",
    "reunión",
    "reunion",
    "entrevista",
    "urgente",
)


class MailCategory(str, Enum):
    """Categorías de correo soportadas por el clasificador."""

    NORMAL = "normal"
    IMPORTANT = "important"
    SPAM = "spam"

    @property
    def label(self) -> str:
        return {
            MailCategory.NORMAL: "Normal",
            MailCategory.IMPORTANT: "Importante",
            MailCategory.SPAM: "Spam",
        }[self]

    @property
    def icon(self) -> str:
        return {
            MailCategory.NORMAL: "●",
            MailCategory.IMPORTANT: "★",
            MailCategory.SPAM: "⚠",
        }[self]


@dataclass
class ClassificationRules:
    """Reglas locales persistidas para refinar la clasificación."""

    important_senders: list[str] = field(default_factory=list)
    spam_senders: list[str] = field(default_factory=list)
    important_keywords: list[str] = field(default_factory=lambda: list(DEFAULT_IMPORTANT_KEYWORDS))
    spam_keywords: list[str] = field(default_factory=lambda: list(DEFAULT_SPAM_KEYWORDS))

    def to_dict(self) -> dict[str, Any]:
        return {
            "important_senders": self.important_senders,
            "spam_senders": self.spam_senders,
            "important_keywords": self.important_keywords,
            "spam_keywords": self.spam_keywords,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClassificationRules:
        return cls(
            important_senders=[s.lower() for s in data.get("important_senders", [])],
            spam_senders=[s.lower() for s in data.get("spam_senders", [])],
            important_keywords=data.get("important_keywords") or list(DEFAULT_IMPORTANT_KEYWORDS),
            spam_keywords=data.get("spam_keywords") or list(DEFAULT_SPAM_KEYWORDS),
        )


def extract_email_address(raw: str) -> str:
    """Extrae la dirección de correo de un campo From/To."""
    _, addr = parseaddr(raw)
    return addr.lower().strip()


def _folder_matches(name: str, keywords: tuple[str, ...]) -> bool:
    lowered = name.lower()
    return any(kw in lowered for kw in keywords)


def _text_contains_keyword(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(kw in lowered for kw in keywords)


def _is_high_priority(headers: dict[str, str]) -> bool:
    importance = headers.get("importance", "").lower()
    if importance in ("high", "urgent"):
        return True

    priority = headers.get("x-priority", "")
    if priority and priority[0] in ("1", "2"):
        return True

    ms_priority = headers.get("x-msmail-priority", "").lower()
    return ms_priority == "high"


def _is_spam_header(headers: dict[str, str]) -> bool:
    spam_status = headers.get("x-spam-status", "").lower()
    if spam_status.startswith("yes"):
        return True

    spam_flag = headers.get("x-spam-flag", "").lower()
    return spam_flag in ("yes", "true")


class MailClassifier:
    """Clasifica mensajes según carpeta, cabeceras, flags y reglas locales."""

    def __init__(self, rules: ClassificationRules | None = None) -> None:
        self.rules = rules or ClassificationRules()

    def classify(
        self,
        *,
        folder: str,
        subject: str,
        sender: str,
        flagged: bool,
        headers: dict[str, str] | None = None,
    ) -> MailCategory:
        """
        Determina la categoría de un mensaje.

        Orden de prioridad:
          1. Remitentes marcados por el usuario (spam / importante)
          2. Carpeta IMAP (Spam, Important, etc.)
          3. Flag \\Flagged o cabeceras de alta prioridad
          4. Palabras clave en asunto
          5. Cabeceras anti-spam del servidor
        """
        headers = {k.lower(): v for k, v in (headers or {}).items()}
        sender_email = extract_email_address(sender)

        if sender_email and sender_email in self.rules.spam_senders:
            return MailCategory.SPAM
        if sender_email and sender_email in self.rules.important_senders:
            return MailCategory.IMPORTANT

        if _folder_matches(folder, SPAM_FOLDER_KEYWORDS):
            return MailCategory.SPAM
        if _folder_matches(folder, IMPORTANT_FOLDER_KEYWORDS):
            return MailCategory.IMPORTANT

        if flagged or _is_high_priority(headers):
            return MailCategory.IMPORTANT

        combined = f"{subject} {sender}"
        if _text_contains_keyword(combined, self.rules.spam_keywords):
            return MailCategory.SPAM
        if _text_contains_keyword(combined, self.rules.important_keywords):
            return MailCategory.IMPORTANT

        if _is_spam_header(headers):
            return MailCategory.SPAM

        return MailCategory.NORMAL

    def learn_sender(self, sender: str, category: MailCategory) -> None:
        """Registra el feedback del usuario asociando un remitente a una categoría."""
        email = extract_email_address(sender)
        if not email:
            return

        self.rules.spam_senders = [s for s in self.rules.spam_senders if s != email]
        self.rules.important_senders = [
            s for s in self.rules.important_senders if s != email
        ]

        if category == MailCategory.SPAM:
            self.rules.spam_senders.append(email)
        elif category == MailCategory.IMPORTANT:
            self.rules.important_senders.append(email)

    def parse_headers_from_message(self, msg: Any) -> dict[str, str]:
        """Convierte las cabeceras relevantes de un email.message a dict."""
        keys = (
            "Importance",
            "X-Priority",
            "X-MSMail-Priority",
            "X-Spam-Status",
            "X-Spam-Flag",
            "Precedence",
        )
        return {k: (msg.get(k) or "") for k in keys if msg.get(k)}
