"""
Tema visual unificado de PyQorreos (claro / oscuro).

Todos los estilos de la interfaz deben definirse aquí. Los widgets marcan su rol
con mark_role() o un objectName reconocido por app_stylesheet().
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget

_UI_IMG = Path(__file__).resolve().parent.parent / "img" / "ui"


def _qss_url(name: str) -> str:
    """Ruta absoluta de un SVG en formato url() para las hojas de estilo."""
    return (_UI_IMG / name).as_posix()


THEME_LIGHT = "light"
THEME_DARK = "dark"
THEME_CHOICES = (THEME_LIGHT, THEME_DARK)

_CURRENT_THEME = THEME_LIGHT

# Tokens de colores para el tema.
@dataclass(frozen=True)
class ThemeTokens:
    bg_window: str
    bg_panel: str
    bg_input: str
    bg_muted: str
    bg_toolbar: str
    text: str
    text_muted: str
    border: str
    border_light: str
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_border: str
    danger_bg: str
    danger_hover: str
    danger_pressed: str
    danger_border: str
    danger_text: str
    warning_bg: str
    warning_text: str
    warning_border: str
    btn_bg: str
    btn_hover: str
    btn_pressed: str
    btn_border: str
    selection_bg: str
    selection_text: str
    tree_hover: str
    link: str
    focus: str
    status_online: str
    status_sync: str
    status_error: str

# Normaliza el nombre de un tema.
def normalize_theme(value: str) -> str:
    value = (value or "").strip().lower()
    return value if value in THEME_CHOICES else THEME_LIGHT


def theme_tokens(theme: str | None = None) -> ThemeTokens:
    theme = normalize_theme(theme or _CURRENT_THEME)
    if theme == THEME_DARK:
        return ThemeTokens(
            bg_window="#17191d",
            bg_panel="#202329",
            bg_input="#252930",
            bg_muted="#292d34",
            bg_toolbar="#1d2026",
            text="#f3f5f7",
            text_muted="#aeb6c2",
            border="#3b424d",
            border_light="#303640",
            accent="#60a5fa",
            accent_hover="#7db5fb",
            accent_pressed="#3b82f6",
            accent_border="#60a5fa",
            danger_bg="#482326",
            danger_hover="#5b292d",
            danger_pressed="#3b1c1f",
            danger_border="#854148",
            danger_text="#ffdadd",
            warning_bg="#443617",
            warning_text="#f8df9a",
            warning_border="#806828",
            btn_bg="#2a2f37",
            btn_hover="#353b45",
            btn_pressed="#22262d",
            btn_border="#414955",
            selection_bg="#2563a8",
            selection_text="#ffffff",
            tree_hover="#2a3039",
            link="#8bc1ff",
            focus="#78b7ff",
            status_online="#66d19e",
            status_sync="#72b7ff",
            status_error="#ff858b",
        )
    # Tokens de colores para el tema claro.
    return ThemeTokens(
        bg_window="#f3f6fa",
        bg_panel="#ffffff",
        bg_input="#ffffff",
        bg_muted="#eef2f7",
        bg_toolbar="#f8fafc",
        text="#172033",
        text_muted="#687386",
        border="#c9d2df",
        border_light="#dde4ed",
        accent="#2563a8",
        accent_hover="#3477bd",
        accent_pressed="#1d4f87",
        accent_border="#2563a8",
        danger_bg="#fff1f2",
        danger_hover="#ffe4e6",
        danger_pressed="#fecdd3",
        danger_border="#f5a3aa",
        danger_text="#a61b29",
        warning_bg="#fff8e1",
        warning_text="#705400",
        warning_border="#e2bd50",
        btn_bg="#f1f4f8",
        btn_hover="#e6ecf3",
        btn_pressed="#d8e1eb",
        btn_border="#c6d0dc",
        selection_bg="#2563a8",
        selection_text="#ffffff",
        tree_hover="#e7edf5",
        link="#1f5f9f",
        focus="#2563a8",
        status_online="#18794e",
        status_sync="#185fa5",
        status_error="#b4232d",
    )

# Obtiene el color de énfasis para un tema.
def accent_color(theme: str | None = None) -> str:
    return theme_tokens(theme).accent

# Obtiene los colores de categoría para un tema.
def category_colors(theme: str | None = None) -> dict:
    from pyqorreos.core.classifier import MailCategory

    t = normalize_theme(theme or _CURRENT_THEME)
    if t == THEME_DARK:
        return {
            MailCategory.NORMAL: QColor(43, 43, 43),
            MailCategory.IMPORTANT: QColor(58, 52, 32),
            MailCategory.SPAM: QColor(58, 38, 38),
        }
    return {
        MailCategory.NORMAL: QColor(255, 255, 255),
        MailCategory.IMPORTANT: QColor(255, 248, 220),
        MailCategory.SPAM: QColor(255, 235, 235),
    }

# Obtiene el color de texto para un tema.
def text_color(theme: str | None = None) -> QColor:
    t = theme_tokens(theme)
    return QColor(t.text)


def prevent_context_menu(widget: QWidget) -> None:
    """Evita menús contextuales del sistema que pueden cerrar la app en Linux."""
    widget.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)

# Polishes a widget.
def polish_widget(widget: QWidget) -> None:
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)

# Marca un widget con un rol.
def mark_role(widget: QWidget, role: str) -> None:
    widget.setProperty("pyqRole", role)
    polish_widget(widget)

# Marca un widget con un nombre de objeto.
def mark_object(widget: QWidget, object_name: str) -> None:
    widget.setObjectName(object_name)
    polish_widget(widget)

# Genera el bloque de estilos para un botón.
def _button_block(t: ThemeTokens, role: str) -> str:
    if role == "primary":
        return f"""
        QPushButton[pyqRole="primary"] {{
            background-color: {t.accent};
            color: {t.selection_text};
            border: 1px solid {t.accent_border};
            border-radius: 8px;
            padding: 6px 14px;
            font-size: 10pt;
            font-weight: 600;
            min-height: 30px;
        }}
        QPushButton[pyqRole="primary"]:hover:!disabled {{
            background-color: {t.accent_hover};
        }}
        QPushButton[pyqRole="primary"]:pressed:!disabled {{
            background-color: {t.accent_pressed};
        }}
        """
    if role == "danger":
        return f"""
        QPushButton[pyqRole="danger"] {{
            background-color: {t.danger_bg};
            color: {t.danger_text};
            border: 1px solid {t.danger_border};
            border-radius: 8px;
            padding: 6px 14px;
            font-size: 10pt;
            font-weight: 600;
            min-height: 30px;
        }}
        QPushButton[pyqRole="danger"]:hover:!disabled {{
            background-color: {t.danger_hover};
        }}
        QPushButton[pyqRole="danger"]:pressed:!disabled {{
            background-color: {t.danger_pressed};
        }}
        """
    if role == "category":
        return f"""
        QPushButton[pyqRole="category"] {{
            background-color: {t.bg_panel};
            color: {t.text};
            border: 1px solid {t.border};
            border-radius: 8px;
            padding: 6px 12px;
            font-size: 10pt;
            font-weight: 600;
            min-height: 30px;
        }}
        QPushButton[pyqRole="category"]:hover:!disabled {{
            background-color: {t.btn_hover};
            border-color: {t.accent};
        }}
        QPushButton[pyqRole="category"]:pressed:!disabled {{
            background-color: {t.btn_pressed};
        }}
        """
    if role == "secondary":
        return f"""
        QPushButton[pyqRole="secondary"] {{
            background-color: {t.btn_bg};
            color: {t.text};
            border: 1px solid {t.btn_border};
            border-radius: 8px;
            padding: 6px 12px;
            font-size: 10pt;
            font-weight: 600;
            min-height: 30px;
        }}
        QPushButton[pyqRole="secondary"]:hover:!disabled {{
            background-color: {t.btn_hover};
            border-color: {t.accent};
        }}
        QPushButton[pyqRole="secondary"]:pressed:!disabled {{
            background-color: {t.btn_pressed};
        }}
        """
    # Genera el bloque de estilos para un botón por defecto.
    return f"""
    QPushButton[pyqRole="default"], QPushButton {{
        background-color: {t.btn_bg};
        color: {t.text};
        border: 1px solid {t.btn_border};
        border-radius: 8px;
        padding: 6px 12px;
        font-size: 10pt;
        font-weight: 600;
        min-height: 28px;
    }}
    QPushButton:hover:!disabled {{
        background-color: {t.btn_hover};
        border-color: {t.accent};
    }}
    QPushButton:pressed:!disabled {{
        background-color: {t.btn_pressed};
    }}
    QPushButton:disabled {{
        background-color: {t.bg_muted};
        color: {t.text_muted};
        border: 1px solid {t.border_light};
    }}
    QPushButton:focus {{
        border: 2px solid {t.focus};
        padding: 5px 11px;
    }}
    """


def _reader_action_button_block() -> str:
    """Padding del lector: va al final del QSS para ganar a primary/danger."""
    return """
    QPushButton[pyqReaderAction="full"] {
        padding: 6px 12px;
        margin: 0 1px;
    }
    QPushButton[pyqReaderAction="compact"] {
        padding: 5px 8px;
        font-size: 9.5pt;
        margin: 0 1px;
    }
    QPushButton[pyqReaderAction="minimal"] {
        padding: 5px 6px;
        margin: 0 1px;
    }
    """


# Genera la hoja de estilos para la aplicación.
def app_stylesheet(theme: str) -> str:
    t = theme_tokens(theme)
    buttons = "".join(
        _button_block(t, role)
        for role in ("default", "primary", "secondary", "danger", "category")
    )
    buttons += _reader_action_button_block()
    return f"""
    QWidget {{
        background-color: {t.bg_window};
        color: {t.text};
        font-family: "Inter", "Segoe UI", "Noto Sans", sans-serif;
        font-size: 10pt;
    }}
    QMainWindow, QDialog {{
        background-color: {t.bg_window};
    }}
    QLabel {{
        color: {t.text};
        background: transparent;
    }}
    QLabel[pyqRole="hint"] {{
        color: {t.text_muted};
        font-size: 9pt;
    }}
    QLabel[pyqRole="meta"] {{
        color: {t.text_muted};
    }}
    QLabel[pyqRole="section-title"] {{
        color: {t.text};
        font-size: 11pt;
        font-weight: 700;
        padding: 2px 0;
    }}
    QLabel[pyqRole="status-online"] {{ color: {t.status_online}; font-weight: 600; }}
    QLabel[pyqRole="status-sync"] {{ color: {t.status_sync}; font-weight: 600; }}
    QLabel[pyqRole="status-error"] {{ color: {t.status_error}; font-weight: 600; }}
    QLabel[pyqRole="link-warning"] {{
        background: {t.warning_bg};
        color: {t.warning_text};
        border: 1px solid {t.warning_border};
        border-radius: 4px;
        padding: 6px 10px;
        font-size: 10pt;
    }}
    QWidget[pyqRole="connection-banner"] {{
        background: {t.warning_bg};
        border: 1px solid {t.warning_border};
        border-radius: 8px;
    }}
    QWidget[pyqRole="connection-banner"] QLabel {{
        background: transparent;
        color: {t.warning_text};
    }}
    QLineEdit, QComboBox, QSpinBox, QTextEdit, QPlainTextEdit, QListWidget {{
        background-color: {t.bg_input};
        color: {t.text};
        border: 1px solid {t.border};
        border-radius: 7px;
        padding: 5px 8px;
        min-height: 26px;
        selection-background-color: {t.selection_bg};
        selection-color: {t.selection_text};
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
    QTextEdit:focus, QPlainTextEdit:focus, QListWidget:focus {{
        border: 2px solid {t.focus};
        padding: 4px 7px;
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background: {t.bg_panel};
        color: {t.text};
        border: 1px solid {t.border};
        selection-background-color: {t.selection_bg};
        selection-color: {t.selection_text};
        padding: 4px;
    }}
    QCheckBox {{
        spacing: 7px;
        color: {t.text};
        background: transparent;
        min-height: 24px;
    }}
    QTreeWidget, QTableWidget {{
        background-color: {t.bg_panel};
        color: {t.text};
        border: 1px solid {t.border_light};
        border-radius: 9px;
        gridline-color: {t.border_light};
        alternate-background-color: {t.bg_muted};
    }}
    QTreeWidget#pyqFolderTree {{
        background-color: transparent;
        border: none;
        border-radius: 0;
    }}
    /* La selección la pinta ::item. Sin estas reglas Qt colorea también la
       columna del desplegable y la fila se ve partida en dos tonos; al tocar
       ::branch hay que redibujar las flechas a mano. */
    QTreeWidget#pyqFolderTree::branch {{
        background: transparent;
    }}
    QTreeWidget#pyqFolderTree::branch:closed:has-children {{
        image: url({_qss_url("tree-collapsed.svg")});
    }}
    QTreeWidget#pyqFolderTree::branch:open:has-children {{
        image: url({_qss_url("tree-expanded.svg")});
    }}
    QWidget#pyqFolderPanel, QWidget#pyqMailPanel, QWidget#pyqReaderPanel {{
        background-color: {t.bg_panel};
        border: 1px solid {t.border_light};
        border-radius: 10px;
    }}
    QWidget#pyqComposeHeader, QWidget#pyqComposeOptions,
    QWidget#pyqComposeAttachments {{
        background-color: {t.bg_panel};
        border: 1px solid {t.border_light};
        border-radius: 9px;
    }}
    QWidget#pyqComposeFooter {{
        background-color: {t.bg_toolbar};
        border-top: 1px solid {t.border_light};
    }}
    QTreeWidget#pyqFolderTree::item {{
        padding: 7px 8px;
        border-radius: 6px;
        margin: 1px 2px;
    }}
    QTreeWidget#pyqFolderTree::item:selected {{
        background-color: {t.accent};
        color: {t.selection_text};
    }}
    QTreeWidget#pyqFolderTree::item:hover:!selected {{
        background-color: {t.tree_hover};
    }}
    QTableWidget#pyqMessageTable::item {{
        padding: 5px 6px;
        border-bottom: 1px solid {t.border_light};
    }}
    QTableWidget#pyqMessageTable {{
        selection-background-color: {t.selection_bg};
        selection-color: {t.selection_text};
        outline: none;
    }}
    QHeaderView::section {{
        background-color: {t.bg_muted};
        color: {t.text};
        padding: 8px 8px;
        border: none;
        border-bottom: 1px solid {t.border_light};
    }}
    QToolBar {{
        background: {t.bg_toolbar};
        border-bottom: 1px solid {t.border_light};
        spacing: 4px;
        padding: 5px 8px;
    }}
    QToolBar#pyqComposeToolbar {{
        background-color: {t.bg_toolbar};
        border: 1px solid {t.btn_border};
        border-radius: 8px;
        padding: 4px 6px;
    }}
    QToolButton {{
        background-color: transparent;
        color: {t.text};
        border: 1px solid transparent;
        border-radius: 7px;
        padding: 5px 10px;
        font-size: 10pt;
        font-weight: 600;
        min-height: 28px;
    }}
    QToolButton:hover {{
        background-color: {t.btn_hover};
        border-color: {t.accent};
    }}
    QToolButton:pressed {{
        background-color: {t.btn_pressed};
        border-color: {t.accent_border};
    }}
    QToolButton:focus {{
        border: 2px solid {t.focus};
    }}
    QToolButton:checked {{
        background-color: {t.bg_muted};
        border-color: {t.accent};
    }}
    QStatusBar {{
        background: {t.bg_toolbar};
        color: {t.text_muted};
        border-top: 1px solid {t.border_light};
    }}
    QMenu {{
        background-color: {t.bg_input};
        color: {t.text};
        border: 1px solid {t.border};
        border-radius: 8px;
        padding: 6px;
    }}
    QMenu::item {{
        padding: 7px 30px 7px 12px;
        border-radius: 5px;
    }}
    QMenu::item:selected {{
        background-color: {t.accent};
        color: {t.selection_text};
    }}
    QGroupBox {{
        font-weight: 600;
        border: 1px solid {t.border_light};
        border-radius: 9px;
        margin-top: 10px;
        padding-top: 10px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 4px;
    }}
    QTabWidget::pane {{
        border: 1px solid {t.border_light};
        border-radius: 8px;
        background: {t.bg_panel};
    }}
    QTabBar::tab {{
        background: {t.bg_muted};
        color: {t.text_muted};
        padding: 8px 16px;
        border: none;
        border-bottom: 2px solid transparent;
    }}
    QTabBar::tab:selected {{
        background: {t.bg_panel};
        color: {t.text};
        border-bottom: 2px solid {t.accent};
    }}
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QProgressBar {{
        border: 1px solid {t.border_light};
        border-radius: 3px;
        background: {t.bg_muted};
    }}
    QProgressBar::chunk {{
        background: {t.accent};
        border-radius: 2px;
    }}
    QSplitter::handle {{
        background: transparent;
        width: 6px;
    }}
    QSplitter::handle:hover {{
        background: {t.accent};
    }}
    QTextBrowser#pyqMessageSurface, QTextEdit#pyqComposeEditor {{
        background-color: {t.bg_panel};
        color: {t.text};
        border: 1px solid {t.border};
        border-radius: 9px;
        padding: 8px;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {t.border};
        border-radius: 4px;
        min-height: 28px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {t.text_muted}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 10px;
        margin: 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: {t.border};
        border-radius: 4px;
        min-width: 28px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}
    {buttons}
    """

# Genera la hoja de estilos para el editor de redacción.
def compose_document_stylesheet(theme: str | None = None) -> str:
    t = theme_tokens(theme)
    return f"""
    body {{
        background-color: {t.bg_panel};
        color: {t.text};
        font-family: sans-serif;
        font-size: 11pt;
    }}
    p, div, li, td, th, span {{
        color: {t.text};
    }}
    a {{
        color: {t.link};
    }}
    #pyqorreos-reply-area {{
        background-color: {t.bg_panel} !important;
        color: {t.text} !important;
        min-height: 100px;
    }}
    """

# CSS base para correos mostrados en el visor (HTML / WebEngine).
def viewer_email_base_css(theme: str | None = None) -> str:
    """
    Hace legible el HTML del correo con el tema de la app.

    Muchos mensajes ponen fondos blancos (tablas, divs, bgcolor) y dejan el
    color del texto sin definir. Si forzamos solo el color del tema oscuro
    (texto claro), queda blanco sobre blanco. Por eso se anulan los fondos
    de los contenedores habituales para que se vea el del body, y se fuerza
    contraste en texto y enlaces.
    """
    t = theme_tokens(theme)
    return f"""
html {{
    color-scheme: {"dark" if normalize_theme(theme) == THEME_DARK else "light"};
    background: {t.bg_panel} !important;
}}
body {{
    background: {t.bg_panel} !important;
    background-color: {t.bg_panel} !important;
    color: {t.text} !important;
    margin: 8px;
    line-height: 1.45;
    font-family: sans-serif;
}}
body, div, p, td, th, li, span, font, label, center,
section, article, main, header, footer, aside, nav,
h1, h2, h3, h4, h5, h6, pre, blockquote, strong, em, b, i, u, small {{
    color: {t.text} !important;
    background: transparent !important;
    background-color: transparent !important;
    background-image: none !important;
}}
table, tbody, thead, tfoot, tr {{
    max-width: 100% !important;
    background: transparent !important;
    background-color: transparent !important;
    background-image: none !important;
    color: {t.text} !important;
}}
a, a:link, a:visited, a:hover, a:active,
a span, a font, a strong, a b, a em, a i, a u {{
    color: {t.link} !important;
    background: transparent !important;
    background-color: transparent !important;
}}
img, picture, video, svg {{
    max-width: 100% !important;
    height: auto !important;
    background: transparent !important;
}}
"""

# CSS adicional para el modo lectura del visor.
def viewer_email_reading_css(theme: str | None = None) -> str:
    t = theme_tokens(theme)
    return f"""
body {{
    max-width: 42rem !important;
    margin: 0 auto !important;
    padding: 1rem 1.25rem !important;
    font: 1.05rem/1.65 Georgia, "Times New Roman", serif !important;
    color: {t.text} !important;
    background: {t.bg_panel} !important;
    background-color: {t.bg_panel} !important;
}}
img, video, iframe {{ display: none !important; }}
table {{ width: 100% !important; border-collapse: collapse !important; }}
td, th {{ padding: 0.25rem 0 !important; }}
a, a:link, a:visited, a span {{
    color: {t.link} !important;
    text-decoration: underline !important;
}}
blockquote {{
    border-left: 3px solid {t.border} !important;
    margin-left: 0 !important;
    padding-left: 1rem !important;
    color: {t.text_muted} !important;
    background: transparent !important;
}}
"""

# CSS del aviso de traducción en el visor.
def viewer_translation_banner_css(theme: str | None = None) -> str:
    t = theme_tokens(theme)
    return f"""
.pyq-translation-banner {{
    color: {t.text_muted};
    font-size: 10pt;
    background: {t.bg_muted};
    border-left: 4px solid {t.accent};
    padding: 8px 12px;
    margin: 0 0 1rem 0;
}}
"""

# Genera la hoja de estilos para el visor de mensajes.
def message_surface_stylesheet(theme: str | None = None) -> str:
    t = theme_tokens(theme)
    return f"background: {t.bg_panel};"

# Genera el HTML de características de la aplicación.
def about_features_html(theme: str | None = None) -> str:
    t = theme_tokens(theme)
    return f"""
<ul style="margin: 0; padding-left: 1.2em; line-height: 1.45; color: {t.text};">
<li><b>Varias cuentas</b> — selector y gestor (añadir, editar, eliminar)</li>
<li><b>OAuth2</b> — Gmail, Outlook, Hotmail, MSN; hosting / cPanel con SSL y STARTTLS</li>
<li><b>Presets</b> — AOL, Yahoo, Hotmail, MSN y detección automática por dominio</li>
<li><b>Bandeja del sistema</b> — minimizar sin cerrar; Salir cierra por completo</li>
<li><b>Sincronización incremental</b> y caché SQLite (apertura rápida)</li>
<li><b>Clasificación</b> — normal, importante, spam (filtro y colores)</li>
<li><b>Visor HTML</b> — WebEngine, imágenes cid y remotas bajo demanda</li>
<li><b>Traducción</b> — bajo demanda al idioma de Preferencias</li>
<li><b>Responder / reenviar / eliminar</b> — barra de herramientas y menú contextual</li>
<li><b>Acuse de recibo</b> — solicitar al enviar o responder cuando te lo pidan</li>
<li><b>Editor enriquecido</b> — negrita, cursiva, listas, enlaces, imágenes</li>
<li><b>Tema claro y oscuro</b> — Preferencias → Apariencia</li>
<li><b>Contraseñas seguras</b> con keyring del sistema</li>
</ul>
"""

# Resuelve el tema desde el padre o las preferencias.
def resolve_theme_from_parent(parent) -> str:
    if parent is not None and hasattr(parent, "_prefs"):
        return normalize_theme(parent._prefs.theme)
    from pyqorreos.core.user_preferences import load_preferences

    return normalize_theme(load_preferences().theme)

# Aplica paleta y hoja de estilos global.
def apply_app_theme(app: QApplication, theme: str) -> str:
    """Aplica paleta y hoja de estilos global. Devuelve el tema normalizado."""
    global _CURRENT_THEME
    theme = normalize_theme(theme)
    _CURRENT_THEME = theme
    t = theme_tokens(theme)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(t.bg_window))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(t.text))
    palette.setColor(QPalette.ColorRole.Base, QColor(t.bg_panel))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(t.bg_muted))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(t.bg_panel))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(t.text))
    palette.setColor(QPalette.ColorRole.Text, QColor(t.text))
    palette.setColor(QPalette.ColorRole.Button, QColor(t.bg_toolbar))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(t.text))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(t.danger_text))
    palette.setColor(QPalette.ColorRole.Link, QColor(t.link))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(t.selection_bg))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(t.selection_text))
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Text,
        QColor(t.text_muted),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor(t.text_muted),
    )
    app.setPalette(palette)
    app.setStyleSheet(app_stylesheet(theme))
    return theme

# Actualiza estilos del visor de mensajes.
def apply_message_viewer_theme(viewer, theme: str | None = None) -> None:
    """Actualiza estilos del visor de mensajes."""
    theme = normalize_theme(theme or _CURRENT_THEME)
    mark_role(viewer._link_warning, "link-warning")
    surface = message_surface_stylesheet(theme)
    if hasattr(viewer, "_web"):
        viewer._web.setStyleSheet(surface)
    if hasattr(viewer, "_fallback"):
        mark_object(viewer._fallback, "pyqMessageSurface")
    if hasattr(viewer, "_text"):
        mark_object(viewer._text, "pyqMessageSurface")

# Actualiza estilos del editor de redacción.
def apply_compose_editor_theme(editor, theme: str | None = None) -> None:
    """Actualiza estilos del editor de redacción."""
    theme = normalize_theme(theme or _CURRENT_THEME)
    t = theme_tokens(theme)
    mark_object(editor.toolbar, "pyqComposeToolbar")
    mark_object(editor.editor, "pyqComposeEditor")
    text_edit = editor.editor
    palette = text_edit.palette()
    palette.setColor(QPalette.ColorRole.Text, QColor(t.text))
    palette.setColor(QPalette.ColorRole.Base, QColor(t.bg_panel))
    text_edit.setPalette(palette)
    text_edit.document().setDefaultStyleSheet(compose_document_stylesheet(theme))
