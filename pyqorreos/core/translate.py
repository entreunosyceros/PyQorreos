"""
Traducción de texto de correos mediante servicios en línea gratuitos.

Usa deep-translator (importación diferida) sin API key.
"""

from __future__ import annotations

import re
import time

MAX_CHUNK_CHARS = 4500
# Google corta el endpoint no oficial a 5 peticiones por segundo.
_MIN_INTERVAL_SEC = 0.25
_RETRY_WAITS_SEC = (1.0, 2.0, 4.0, 8.0)
# Marca que el traductor suele conservar, para separar asunto y cuerpo en una sola petición.
_SUBJECT_MARK = "<<<PYQ>>>"
_SUBJECT_SPLIT = f"\n\n{_SUBJECT_MARK}\n\n"
_SUBJECT_MARK_RE = re.compile(r"<<<\s*PYQ\s*>>>", re.IGNORECASE)
_last_request_at = 0.0

# (código ISO 639-1, etiqueta en español)
TRANSLATION_LANGUAGES: list[tuple[str, str]] = [
    ("es", "Español"),
    ("en", "Inglés"),
    ("fr", "Francés"),
    ("de", "Alemán"),
    ("it", "Italiano"),
    ("pt", "Portugués"),
    ("ca", "Catalán"),
    ("gl", "Gallego"),
    ("eu", "Euskera"),
    ("nl", "Neerlandés"),
    ("pl", "Polaco"),
    ("ru", "Ruso"),
    ("zh-CN", "Chino (simplificado)"),
    ("ja", "Japonés"),
    ("ar", "Árabe"),
]

_DEFAULT_LANGUAGE = "es"


def language_label(code: str) -> str:
    for lang_code, label in TRANSLATION_LANGUAGES:
        if lang_code == code:
            return label
    return code

# Normaliza el código de idioma.
def normalize_language_code(code: str) -> str:
    code = (code or "").strip()
    if not code:
        return _DEFAULT_LANGUAGE
    valid = {c for c, _ in TRANSLATION_LANGUAGES}
    return code if code in valid else _DEFAULT_LANGUAGE

# Obtiene el traductor.
def _get_translator(target_lang: str):
    try:
        from deep_translator import GoogleTranslator
    except ImportError as exc:
        raise RuntimeError(
            "Falta el paquete deep-translator. Instálalo con: pip install deep-translator"
        ) from exc
    return GoogleTranslator(source="auto", target=target_lang)

def _is_rate_limited(exc: BaseException) -> bool:
    if type(exc).__name__ == "TooManyRequests":
        return True
    return "too many requests" in str(exc).lower()


def _wait_for_slot() -> None:
    """Deja pasar el intervalo mínimo desde la petición anterior."""
    elapsed = time.monotonic() - _last_request_at
    if _last_request_at and elapsed < _MIN_INTERVAL_SEC:
        time.sleep(_MIN_INTERVAL_SEC - elapsed)


def _mark_request() -> None:
    global _last_request_at
    _last_request_at = time.monotonic()


# Traduce un trozo de texto, espaciando las peticiones y reintentando un 429.
def _translate_chunk(translator, text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    attempts = len(_RETRY_WAITS_SEC) + 1
    for attempt in range(attempts):
        if attempt:
            time.sleep(_RETRY_WAITS_SEC[attempt - 1])
        _wait_for_slot()
        _mark_request()
        try:
            translated = translator.translate(text)
        except Exception as exc:
            if _is_rate_limited(exc) and attempt < attempts - 1:
                continue
            if _is_rate_limited(exc):
                raise RuntimeError(
                    "El servicio de traducción ha limitado las peticiones. "
                    "Espera un momento y vuelve a pulsar «Traducir»."
                ) from exc
            raise
        return (translated or "").strip()
    raise RuntimeError(
        "El servicio de traducción ha limitado las peticiones. "
        "Espera un momento y vuelve a pulsar «Traducir»."
    )

# Divide el texto en trozos que respetan párrafos y el límite del proveedor.
def _split_for_translation(text: str) -> list[str]:
    """Divide el texto en trozos que respetan párrafos y el límite del proveedor."""
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]

    chunks: list[str] = []
    buffer = ""
    paragraphs = re.split(r"(\n\s*\n)", text)
    for part in paragraphs:
        if not part:
            continue
        candidate = buffer + part
        if len(candidate) <= MAX_CHUNK_CHARS:
            buffer = candidate
            continue
        if buffer.strip():
            chunks.append(buffer.strip())
        if len(part) <= MAX_CHUNK_CHARS:
            buffer = part
        else:
            for i in range(0, len(part), MAX_CHUNK_CHARS):
                chunks.append(part[i : i + MAX_CHUNK_CHARS])
            buffer = ""
    if buffer.strip():
        chunks.append(buffer.strip())
    return chunks or [text]

def _translate_parts(translator, parts: list[str]) -> list[str]:
    return [_translate_chunk(translator, part) for part in parts if part.strip()]


def _split_translated_subject(translated: str) -> tuple[str, str] | None:
    """Separa asunto y cuerpo si la marca de unión sobrevivió a la traducción."""
    match = _SUBJECT_MARK_RE.search(translated)
    if not match:
        return None
    subject = translated[: match.start()].strip()
    body = translated[match.end() :].strip()
    return body, subject


# Traduce texto plano al idioma indicado (código ISO 639-1).
def translate_text(text: str, target_lang: str) -> str:
    """Traduce texto plano al idioma indicado (código ISO 639-1)."""
    body, _subject = translate_message(text, "", target_lang)
    return body


def translate_message(body: str, subject: str, target_lang: str) -> tuple[str, str]:
    """Traduce cuerpo y asunto con el menor número de peticiones posible.

    Si ambos caben en un trozo, viajan juntos. Los trozos siguientes esperan
    para no superar el límite de peticiones por segundo y, si el servicio
    responde 429, se reintenta con esperas crecientes.
    """
    body_text = normalize_translation_source(body)
    subject_text = normalize_translation_source(subject)
    if not body_text and not subject_text:
        return "", ""
    target = normalize_language_code(target_lang)
    translator = _get_translator(target)
    body_parts = _split_for_translation(body_text) if body_text else []

    if (
        subject_text
        and len(body_parts) == 1
        and len(subject_text) + len(_SUBJECT_SPLIT) + len(body_parts[0]) <= MAX_CHUNK_CHARS
    ):
        translated = _translate_chunk(
            translator,
            subject_text + _SUBJECT_SPLIT + body_parts[0],
        )
        split = _split_translated_subject(translated)
        if split is not None:
            body_out, subject_out = split
            return normalize_translation_source(body_out), subject_out
        return (
            normalize_translation_source(translated),
            _translate_chunk(translator, subject_text),
        )

    translated_body = _translate_parts(translator, body_parts)
    translated_subject = (
        _translate_chunk(translator, subject_text) if subject_text else ""
    )
    return normalize_translation_source("\n\n".join(translated_body)), translated_subject

_CSS_NOISE_RE = re.compile(
    r"(?i)(font-size|line-height|margin|padding|color\s*:|background|"
    r"!important|mso-|display\s*:|width\s*:|height\s*:)"
)
_BULLET_ONLY_RE = re.compile(r"^[\s•·\-\*\.]+$")
_CSS_UNIT_ONLY_RE = re.compile(r"^\d+(%|px|em|pt|rem)?\s*$")


def _is_junk_translation_line(line: str) -> bool:
    """Detecta restos de CSS o viñetas vacías típicas de newsletters."""
    stripped = line.strip()
    if not stripped:
        return False
    if _BULLET_ONLY_RE.match(stripped):
        return True
    if _CSS_UNIT_ONLY_RE.match(stripped):
        return True
    if "{" in stripped or "}" in stripped:
        return True
    if _CSS_NOISE_RE.search(stripped) and len(stripped) < 160:
        return True
    return False


# Reduce ruido de newsletters HTML convertidas a texto (huecos y líneas vacías).
def normalize_translation_source(text: str) -> str:
    """Reduce ruido de newsletters HTML convertidas a texto (huecos y líneas vacías)."""
    original = (text or "").strip()
    if not original:
        return ""
    text = re.sub(r"[ \t]+", " ", original)
    lines = [ln.strip() for ln in text.splitlines()]
    cleaned: list[str] = []
    blank_run = 0
    for line in lines:
        if _is_junk_translation_line(line):
            continue
        if not line:
            blank_run += 1
            if blank_run <= 1:
                cleaned.append("")
            continue
        blank_run = 0
        cleaned.append(line)
    while cleaned and not cleaned[0].strip():
        cleaned.pop(0)
    text = "\n".join(cleaned).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    if text:
        return text
    non_empty = [ln for ln in lines if ln]
    if non_empty and all(_is_junk_translation_line(ln) for ln in non_empty):
        return ""
    fallback = re.sub(r"[ \t]+", " ", original)
    return re.sub(r"\n{3,}", "\n\n", fallback).strip()

# Convierte la traducción en HTML legible para el visor WebEngine.
def translated_text_to_html(
    text: str, language_label: str = "", *, theme: str | None = None
) -> str:
    """Convierte la traducción en HTML legible para el visor WebEngine."""
    from html import escape

    from pyqorreos.core.email_html import apply_reading_mode_styles
    from pyqorreos.ui.theme import viewer_translation_banner_css

    text = normalize_translation_source(text)
    if not text:
        body = "<p><em>(Sin contenido traducible)</em></p>"
    else:
        parts: list[str] = []
        for block in re.split(r"\n\s*\n", text):
            block = block.strip()
            if not block:
                continue
            from pyqorreos.core.email_html import linkify_plain_text_line

            inner = "<br>".join(
                linkify_plain_text_line(line) for line in block.split("\n") if line.strip()
            )
            if inner:
                parts.append(f"<p>{inner}</p>")
        body = "".join(parts) if parts else "<p><em>(Sin contenido traducible)</em></p>"

    label = escape(language_label) if language_label else "automática"
    banner = (
        f'<p class="pyq-translation-banner">'
        f"Traducción {label} — el diseño original no se conserva."
        f"</p>"
    )
    banner_css = viewer_translation_banner_css(theme)
    # Construye el HTML de la traducción.
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<style>{banner_css}</style>"
        f"</head><body>{banner}{body}</body></html>"
    )
    return apply_reading_mode_styles(html, theme)
