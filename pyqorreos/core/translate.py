"""
Traducción de texto de correos mediante servicios en línea gratuitos.

Usa deep-translator (importación diferida) sin API key.
"""

from __future__ import annotations

import re

MAX_CHUNK_CHARS = 4500

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


def default_target_language() -> str:
    return _DEFAULT_LANGUAGE


def language_label(code: str) -> str:
    for lang_code, label in TRANSLATION_LANGUAGES:
        if lang_code == code:
            return label
    return code


def normalize_language_code(code: str) -> str:
    code = (code or "").strip()
    if not code:
        return _DEFAULT_LANGUAGE
    valid = {c for c, _ in TRANSLATION_LANGUAGES}
    return code if code in valid else _DEFAULT_LANGUAGE


def _get_translator(target_lang: str):
    try:
        from deep_translator import GoogleTranslator
    except ImportError as exc:
        raise RuntimeError(
            "Falta el paquete deep-translator. Instálalo con: pip install deep-translator"
        ) from exc
    return GoogleTranslator(source="auto", target=target_lang)


def _translate_chunk(translator, text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    return translator.translate(text)


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


def translate_text(text: str, target_lang: str) -> str:
    """Traduce texto plano al idioma indicado (código ISO 639-1)."""
    text = normalize_translation_source(text)
    if not text:
        return ""
    target = normalize_language_code(target_lang)
    translator = _get_translator(target)
    parts = _split_for_translation(text)
    if len(parts) == 1:
        return _translate_chunk(translator, parts[0])
    translated = [_translate_chunk(translator, part) for part in parts if part.strip()]
    return normalize_translation_source("\n\n".join(translated))


def normalize_translation_source(text: str) -> str:
    """Reduce ruido de newsletters HTML convertidas a texto (huecos y líneas vacías)."""
    text = (text or "").strip()
    if not text:
        return ""
    text = re.sub(r"[ \t]+", " ", text)
    lines = [ln.strip() for ln in text.splitlines()]
    cleaned: list[str] = []
    blank_run = 0
    for line in lines:
        if not line:
            blank_run += 1
            if blank_run <= 1:
                cleaned.append("")
            continue
        blank_run = 0
        cleaned.append(line)
    text = "\n".join(cleaned).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def translated_text_to_html(text: str, language_label: str = "") -> str:
    """Convierte la traducción en HTML legible para el visor WebEngine."""
    from html import escape

    from pyqorreos.core.email_html import apply_reading_mode_styles

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
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<style>.pyq-translation-banner {"
        "color:#555;font-size:10pt;background:#eef4fb;border-left:4px solid #2d7dd2;"
        "padding:8px 12px;margin:0 0 1rem 0;}</style>"
        f"</head><body>{banner}{body}</body></html>"
    )
    return apply_reading_mode_styles(html)
