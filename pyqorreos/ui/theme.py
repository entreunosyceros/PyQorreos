"""
Tema visual unificado de PyQorreos (claro / oscuro).

Todos los estilos de la interfaz deben definirse aquí. Los widgets marcan su rol
con mark_role() o un objectName reconocido por app_stylesheet().
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget

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

# Normaliza el nombre de un tema.
def normalize_theme(value: str) -> str:
    value = (value or "").strip().lower()
    return value if value in THEME_CHOICES else THEME_LIGHT


def theme_tokens(theme: str | None = None) -> ThemeTokens:
    theme = normalize_theme(theme or _CURRENT_THEME)
    if theme == THEME_DARK:
        return ThemeTokens(
            bg_window="#2b2b2b",
            bg_panel="#333333",
            bg_input="#383838",
            bg_muted="#3a3a3a",
            bg_toolbar="#404040",
            text="#e8e8e8",
            text_muted="#aaaaaa",
            border="#555555",
            border_light="#484848",
            accent="#5ba3e8",
            accent_hover="#6eb3f2",
            accent_pressed="#3d8ad4",
            accent_border="#4a8fd4",
            danger_bg="#6b2d2d",
            danger_hover="#7d3535",
            danger_pressed="#5a2424",
            danger_border="#8b3a3a",
            danger_text="#ffe8e8",
            warning_bg="#4a4020",
            warning_text="#f0e0a8",
            warning_border="#8a7530",
            btn_bg="#454545",
            btn_hover="#505050",
            btn_pressed="#3a3a3a",
            btn_border="#666666",
            selection_bg="#5ba3e8",
            selection_text="#ffffff",
            tree_hover="#404040",
            link="#7eb8f0",
        )
    # Tokens de colores para el tema claro.
    return ThemeTokens(
        bg_window="#f8f8f8",
        bg_panel="#ffffff",
        bg_input="#ffffff",
        bg_muted="#f4f4f4",
        bg_toolbar="#f0f4f8",
        text="#1a1a1a",
        text_muted="#666666",
        border="#cccccc",
        border_light="#dddddd",
        accent="#2d7dd2",
        accent_hover="#3a8de0",
        accent_pressed="#1f5fa8",
        accent_border="#1f5fa8",
        danger_bg="#fff5f5",
        danger_hover="#ffe8e6",
        danger_pressed="#ffd5d2",
        danger_border="#f0a8a0",
        danger_text="#b42318",
        warning_bg="#fff3cd",
        warning_text="#664d03",
        warning_border="#ffc107",
        btn_bg="#e3ebf3",
        btn_hover="#d5e3f0",
        btn_pressed="#c5d8eb",
        btn_border="#b8c4d0",
        selection_bg="#2d7dd2",
        selection_text="#ffffff",
        tree_hover="#e8e8e8",
        link="#1a5fb4",
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
            border-radius: 5px;
            padding: 7px 14px;
            font-size: 10pt;
            font-weight: 600;
            min-height: 32px;
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
            border-radius: 5px;
            padding: 7px 14px;
            font-size: 10pt;
            font-weight: 600;
            min-height: 32px;
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
            border-radius: 5px;
            padding: 7px 12px;
            font-size: 10pt;
            font-weight: 600;
            min-height: 32px;
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
            border-radius: 5px;
            padding: 7px 12px;
            font-size: 10pt;
            font-weight: 600;
            min-height: 32px;
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
        border-radius: 5px;
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
    """

# Genera la hoja de estilos para la aplicación.
def app_stylesheet(theme: str) -> str:
    t = theme_tokens(theme)
    buttons = "".join(_button_block(t, role) for role in ("default", "primary", "secondary", "danger", "category"))
    return f"""
    QWidget {{
        background-color: {t.bg_window};
        color: {t.text};
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
    QLabel[pyqRole="link-warning"] {{
        background: {t.warning_bg};
        color: {t.warning_text};
        border: 1px solid {t.warning_border};
        border-radius: 4px;
        padding: 6px 10px;
        font-size: 10pt;
    }}
    QLineEdit, QComboBox, QSpinBox, QTextEdit, QPlainTextEdit, QListWidget {{
        background-color: {t.bg_input};
        color: {t.text};
        border: 1px solid {t.border};
        border-radius: 4px;
        padding: 4px 6px;
        selection-background-color: {t.selection_bg};
        selection-color: {t.selection_text};
    }}
    QTreeWidget, QTableWidget {{
        background-color: {t.bg_panel};
        color: {t.text};
        border: 1px solid {t.border_light};
        gridline-color: {t.border_light};
        alternate-background-color: {t.bg_muted};
    }}
    QTreeWidget#pyqFolderTree {{
        background-color: {t.bg_muted};
        border-radius: 4px;
    }}
    QWidget#pyqFolderPanel, QWidget#pyqMailPanel, QWidget#pyqReaderPanel {{
        background-color: {t.bg_window};
    }}
    QTreeWidget#pyqFolderTree::item {{
        padding: 6px 8px;
    }}
    QTreeWidget#pyqFolderTree::item:selected {{
        background-color: {t.accent};
        color: {t.selection_text};
    }}
    QTreeWidget#pyqFolderTree::item:hover:!selected {{
        background-color: {t.tree_hover};
    }}
    QTableWidget#pyqMessageTable::item {{
        padding: 2px 4px;
    }}
    QTableWidget#pyqMessageTable {{
        selection-background-color: {t.selection_bg};
        selection-color: {t.selection_text};
    }}
    QHeaderView::section {{
        background-color: {t.bg_muted};
        color: {t.text};
        padding: 6px 8px;
        border: none;
        border-bottom: 1px solid {t.border_light};
    }}
    QToolBar {{
        background: {t.bg_panel};
        border-bottom: 1px solid {t.border_light};
        spacing: 6px;
        padding: 4px;
    }}
    QToolBar#pyqComposeToolbar {{
        background-color: {t.bg_toolbar};
        border: 1px solid {t.btn_border};
        border-radius: 5px;
        padding: 4px 6px;
    }}
    QToolButton {{
        background-color: {t.btn_bg};
        color: {t.text};
        border: 1px solid {t.btn_border};
        border-radius: 4px;
        padding: 5px 11px;
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
    QStatusBar {{
        background: {t.bg_muted};
        color: {t.text_muted};
        border-top: 1px solid {t.border_light};
    }}
    QMenu {{
        background-color: {t.bg_input};
        color: {t.text};
        border: 1px solid {t.border};
        padding: 4px;
    }}
    QMenu::item {{
        padding: 6px 28px 6px 16px;
    }}
    QMenu::item:selected {{
        background-color: {t.accent};
        color: {t.selection_text};
    }}
    QGroupBox {{
        font-weight: 600;
        border: 1px solid {t.border_light};
        border-radius: 6px;
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
        border-radius: 4px;
        background: {t.bg_panel};
    }}
    QTabBar::tab {{
        background: {t.bg_muted};
        color: {t.text_muted};
        padding: 8px 16px;
        border: 1px solid {t.border_light};
        border-bottom: none;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }}
    QTabBar::tab:selected {{
        background: {t.bg_panel};
        color: {t.text};
        border-bottom: 1px solid {t.bg_panel};
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
        background: {t.border};
        width: 2px;
    }}
    QTextBrowser#pyqMessageSurface, QTextEdit#pyqComposeEditor {{
        background-color: {t.bg_panel};
        color: {t.text};
        border: 1px solid {t.border};
        border-radius: 4px;
        padding: 6px;
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
    t = theme_tokens(theme)
    return f"""
body, div, p, td, th, li, span {{
    color: {t.text} !important;
    font-family: sans-serif;
}}
body {{
    background: {t.bg_panel} !important;
    margin: 8px;
    line-height: 1.45;
}}
img {{
    max-width: 100% !important;
    height: auto !important;
}}
table {{ max-width: 100% !important; }}
a {{ color: {t.link} !important; }}
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
}}
img, video, iframe {{ display: none !important; }}
table {{ width: 100% !important; border-collapse: collapse !important; }}
td, th {{ padding: 0.25rem 0 !important; }}
a {{ color: {t.link} !important; text-decoration: underline !important; }}
blockquote {{
    border-left: 3px solid {t.border} !important;
    margin-left: 0 !important;
    padding-left: 1rem !important;
    color: {t.text_muted} !important;
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
    if theme == THEME_DARK:
        palette.setColor(QPalette.ColorRole.Window, QColor(t.bg_window))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(t.text))
        palette.setColor(QPalette.ColorRole.Base, QColor(t.bg_panel))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(t.bg_muted))
        palette.setColor(QPalette.ColorRole.Text, QColor(t.text))
        palette.setColor(QPalette.ColorRole.Button, QColor(t.bg_toolbar))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(t.text))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(t.accent))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(t.selection_text))
    else:
        palette = app.style().standardPalette()
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
