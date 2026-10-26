from pyqorreos.ui.theme import (
    THEME_DARK,
    THEME_LIGHT,
    app_stylesheet,
    compose_document_stylesheet,
    normalize_theme,
    theme_tokens,
)


def test_theme_tokens_are_complete_and_distinct() -> None:
    light = theme_tokens(THEME_LIGHT)
    dark = theme_tokens(THEME_DARK)

    assert light.bg_window != dark.bg_window
    assert light.text != dark.text
    assert light.focus
    assert dark.focus
    assert light.status_online
    assert dark.status_error


def test_stylesheet_contains_modern_and_accessible_states() -> None:
    for theme in (THEME_LIGHT, THEME_DARK):
        stylesheet = app_stylesheet(theme)
        assert 'QLabel[pyqRole="section-title"]' in stylesheet
        assert 'QLabel[pyqRole="status-online"]' in stylesheet
        assert "QPushButton:focus" in stylesheet
        assert "QLineEdit:focus" in stylesheet
        assert "QScrollBar:vertical" in stylesheet
        assert "QSplitter::handle:hover" in stylesheet


def test_compose_document_uses_selected_theme() -> None:
    light_css = compose_document_stylesheet(THEME_LIGHT)
    dark_css = compose_document_stylesheet(THEME_DARK)

    assert theme_tokens(THEME_LIGHT).text in light_css
    assert theme_tokens(THEME_DARK).text in dark_css
    assert light_css != dark_css


def test_invalid_theme_falls_back_to_light() -> None:
    assert normalize_theme("unknown") == THEME_LIGHT
