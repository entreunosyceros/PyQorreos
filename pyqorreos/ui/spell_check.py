"""
Corrección ortográfica en tiempo real para el editor de redacción.
"""

from __future__ import annotations

import re
from typing import Literal

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QMenu, QTextEdit

SpellLanguage = Literal["es", "en", "both"]

WORD_RE = re.compile(r"(?<![@./])\b[\wáéíóúüñÁÉÍÓÚÜÑ'-]+\b", re.UNICODE)


def _looks_like_url_or_email(fragment: str) -> bool:
    low = fragment.lower()
    return "://" in low or "@" in fragment or low.startswith("www.")


class ComposeSpellChecker:
    """Comprueba palabras en español, inglés o en ambos idiomas."""

    def __init__(self, language: SpellLanguage = "both") -> None:
        self._language = language
        self._en = None
        self._es = None
        self._available: bool | None = None

    @property
    def language(self) -> SpellLanguage:
        return self._language

    @property
    def available(self) -> bool:
        if self._available is None:
            try:
                from spellchecker import SpellChecker  # noqa: F401

                self._available = True
            except ImportError:
                self._available = False
        return self._available

    def set_language(self, language: SpellLanguage) -> None:
        self._language = language

    def _load(self) -> None:
        if self._en is not None:
            return
        from spellchecker import SpellChecker

        self._en = SpellChecker(language="en")
        self._es = SpellChecker(language="es")

    def is_correct(self, word: str) -> bool:
        if not self.available:
            return True
        raw = word.strip("'-")
        if len(raw) < 2:
            return True
        if raw.isdigit():
            return True
        if raw.isupper() and len(raw) <= 4:
            return True
        w = raw.lower()
        self._load()
        if self._language == "en":
            return not self._en.unknown([w])
        if self._language == "es":
            return not self._es.unknown([w])
        return not (self._en.unknown([w]) and self._es.unknown([w]))

    def suggestions(self, word: str, *, limit: int = 6) -> list[str]:
        if not self.available:
            return []
        raw = word.strip("'-")
        if not raw:
            return []
        w = raw.lower()
        self._load()
        if self._language == "en":
            pool = self._en.candidates(w) or []
        elif self._language == "es":
            pool = self._es.candidates(w) or []
        else:
            pool = set(self._en.candidates(w) or []) | set(self._es.candidates(w) or [])
        ranked = sorted(pool, key=lambda s: (s != w, len(s), s))
        return [s for s in ranked if s != w][:limit]


class ComposeSpellHighlighter(QSyntaxHighlighter):
    def __init__(self, checker: ComposeSpellChecker, parent=None) -> None:
        super().__init__(parent)
        self._checker = checker
        self._enabled = True
        self._error_fmt = QTextCharFormat()
        self._error_fmt.setUnderlineColor(QColor("#e53e3e"))
        self._error_fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        if not self._enabled or not self._checker.available:
            return
        if _looks_like_url_or_email(text):
            return
        for match in WORD_RE.finditer(text):
            word = match.group()
            if _looks_like_url_or_email(word):
                continue
            if self._checker.is_correct(word):
                continue
            self.setFormat(match.start(), match.end() - match.start(), self._error_fmt)


class SpellCheckTextEdit(QTextEdit):
    """QTextEdit con subrayado ortográfico y sugerencias en el menú contextual."""

    def __init__(self, checker: ComposeSpellChecker, parent=None) -> None:
        super().__init__(parent)
        self._checker = checker
        self._spell_enabled = True
        self._highlighter = ComposeSpellHighlighter(checker, self.document())

    def set_spell_check_enabled(self, enabled: bool) -> None:
        self._spell_enabled = enabled
        self._highlighter.set_enabled(enabled)

    def set_spell_language(self, language: SpellLanguage) -> None:
        self._checker.set_language(language)
        self._highlighter.rehighlight()

    def contextMenuEvent(self, event) -> None:
        menu = self.createStandardContextMenu()
        if self._spell_enabled and self._checker.available:
            cursor = self.cursorForPosition(event.pos())
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            word = cursor.selectedText().strip()
            if word and not self._checker.is_correct(word):
                suggestions = self._checker.suggestions(word)
                if suggestions:
                    spell_menu = QMenu("Corregir ortografía", self)
                    start = cursor.selectionStart()
                    end = cursor.selectionEnd()
                    for suggestion in suggestions:
                        action = spell_menu.addAction(suggestion)
                        action.triggered.connect(
                            lambda _checked=False, s=suggestion, a=start, b=end: self._replace_range(
                                a, b, s
                            )
                        )
                    if menu.actions():
                        menu.insertMenu(menu.actions()[0], spell_menu)
                        menu.insertSeparator(menu.actions()[1])
                    else:
                        menu.addMenu(spell_menu)
        menu.exec(event.globalPos())

    def _replace_range(self, start: int, end: int, replacement: str) -> None:
        cursor = self.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(replacement)
        self.setTextCursor(cursor)
