"""Legibilidad del HTML de correo con el tema de la aplicación."""

from __future__ import annotations

from pyqorreos.core.email_html import apply_viewer_theme_styles
from pyqorreos.ui.theme import THEME_DARK, THEME_LIGHT, theme_tokens, viewer_email_base_css


def test_viewer_css_neutralizes_nested_white_panels() -> None:
    css = viewer_email_base_css(THEME_DARK)
    assert "background-color: transparent !important" in css
    assert "background-image: none !important" in css
    assert theme_tokens(THEME_DARK).text in css
    assert theme_tokens(THEME_DARK).link in css
    assert theme_tokens(THEME_DARK).bg_panel in css


def test_theme_styles_injected_at_end_of_body() -> None:
    """Debe ir al final para ganar a <style> del propio newsletter."""
    html = """
    <html><head><style>td{color:#fff!important;background:#fff!important}</style></head>
    <body><table bgcolor="#ffffff"><tr><td style="color:#ffffff">Hola</td></tr></table>
    </body></html>
    """
    out = apply_viewer_theme_styles(html, THEME_DARK)
    assert out.lower().rfind("pyqorreos-viewer-theme") < out.lower().rfind("</body>")
    assert out.lower().rfind("pyqorreos-viewer-theme") > out.lower().rfind(
        "color:#fff!important"
    )


def test_white_on_white_newsletter_gets_dark_theme_contrast() -> None:
    html = (
        '<html><body><table bgcolor="#ffffff" width="100%">'
        '<tr><td style="color:#ffffff;background-color:#ffffff">'
        'Oferta <a href="https://example.com" style="color:#ffffff">aquí</a>'
        "</td></tr></table></body></html>"
    )
    out = apply_viewer_theme_styles(html, THEME_DARK)
    dark = theme_tokens(THEME_DARK)
    assert dark.text in out
    assert dark.link in out
    assert dark.bg_panel in out
    assert "background-color: transparent !important" in out


def test_light_theme_keeps_dark_text() -> None:
    html = "<html><body><p>Hola</p></body></html>"
    out = apply_viewer_theme_styles(html, THEME_LIGHT)
    light = theme_tokens(THEME_LIGHT)
    assert light.text in out
    assert light.bg_panel in out


def test_reapply_does_not_duplicate_theme_style() -> None:
    html = "<html><body><p>Hola</p></body></html>"
    once = apply_viewer_theme_styles(html, THEME_DARK)
    twice = apply_viewer_theme_styles(once, THEME_LIGHT)
    assert twice.count("id='pyqorreos-viewer-theme'") == 1
    assert theme_tokens(THEME_LIGHT).text in twice
