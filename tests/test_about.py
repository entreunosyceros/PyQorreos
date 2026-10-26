"""La ventana Acerca de usa el logo actual y resume las funciones vigentes."""

from pyqorreos.ui.about_dialog import LOGO_PATH
from pyqorreos.ui.theme import about_features_html


def test_about_logo_is_logo_png() -> None:
    assert LOGO_PATH.name == "logo.png"
    assert LOGO_PATH.is_file()
    assert LOGO_PATH.stat().st_size > 0


def test_about_features_cover_current_capabilities() -> None:
    html = about_features_html("light")
    for token in (
        "OAuth2",
        "sin conexión",
        "OpenPGP",
        "Documentación",
        "Ventanas adaptables",
        "Traducción",
    ):
        assert token in html
