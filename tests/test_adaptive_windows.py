"""Las ventanas restauradas no pintan botones unos encima de otros."""

from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

import pytest
from PySide6.QtCore import QRect
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QCheckBox,
    QComboBox,
    QLineEdit,
    QPushButton,
    QToolButton,
    QWidget,
)

from pyqorreos.core.account import MailAccount
from pyqorreos.core.settings import Settings
from pyqorreos.ui.account_dialog import AccountDialog
from pyqorreos.ui.accounts_manager_dialog import AccountsManagerDialog
from pyqorreos.ui.compose_dialog import ComposeDialog
from pyqorreos.ui.flow_layout import FlowLayout, flow_button


@pytest.fixture(scope="module")
def qapp():
    application = QApplication.instance() or QApplication([])
    yield application


def _window_rect(widget: QWidget, root: QWidget) -> QRect:
    origin = widget.mapTo(root, widget.rect().topLeft())
    return QRect(origin, widget.size())


def _is_ancestor(ancestor: QWidget, widget: QWidget) -> bool:
    parent = widget.parentWidget()
    while parent is not None:
        if parent is ancestor:
            return True
        parent = parent.parentWidget()
    return False


def _visible_controls(root: QWidget) -> list[QWidget]:
    controls: list[QWidget] = []
    for kind in (QPushButton, QToolButton, QComboBox, QCheckBox, QLineEdit):
        for widget in root.findChildren(kind):
            if not widget.isVisible():
                continue
            if widget.width() < 2 or widget.height() < 2:
                continue
            controls.append(widget)
    return controls


def _has_scroll_ancestor(widget: QWidget) -> bool:
    parent = widget.parentWidget()
    while parent is not None:
        if isinstance(parent, QAbstractScrollArea):
            return True
        parent = parent.parentWidget()
    return False


def _painted_rect(widget: QWidget, root: QWidget) -> QRect:
    """Parte del control que queda a la vista, recortada por los scrolls."""
    rect = _window_rect(widget, root)
    parent = widget.parentWidget()
    while parent is not None and parent is not root:
        if isinstance(parent, QAbstractScrollArea):
            rect = rect.intersected(_window_rect(parent.viewport(), root))
        parent = parent.parentWidget()
    return rect


def assert_controls_do_not_overlap(root: QWidget) -> None:
    controls = _visible_controls(root)
    overlaps: list[str] = []
    clipped: list[str] = []
    for index, widget in enumerate(controls):
        parent = widget.parentWidget()
        outside_parent = (
            parent is not None and widget.geometry().bottom() > parent.height() + 2
        )
        if outside_parent and not _has_scroll_ancestor(widget):
            clipped.append(
                f"{widget.text()!r} sobresale de {type(parent).__name__} "
                f"({widget.geometry().bottom()} > {parent.height()})"
            )
        rect = _painted_rect(widget, root)
        if rect.width() <= 2 or rect.height() <= 2:
            continue
        for other in controls[index + 1 :]:
            if _is_ancestor(widget, other) or _is_ancestor(other, widget):
                continue
            shared = rect.intersected(_painted_rect(other, root))
            if shared.width() > 2 and shared.height() > 2:
                overlaps.append(
                    f"{widget.text()!r} y {other.text()!r} comparten {shared.width()}×{shared.height()}"
                )
    assert not overlaps, "; ".join(overlaps)
    assert not clipped, "; ".join(clipped)


def _show_restored(qapp: QApplication, widget: QWidget) -> None:
    widget.show()
    qapp.processEvents()
    widget.resize(800, 500)
    qapp.processEvents()
    layout = widget.layout()
    if layout is not None:
        layout.activate()
    qapp.processEvents()


def test_flow_layout_wraps_instead_of_overlapping(qapp: QApplication) -> None:
    host = QWidget()
    layout = FlowLayout(host, hspacing=8, vspacing=6)
    buttons = [flow_button(QPushButton(f"Acción {index}")) for index in range(4)]
    for button in buttons:
        layout.addWidget(button)
    host.resize(120, 400)
    host.show()
    qapp.processEvents()
    layout.activate()
    qapp.processEvents()
    assert_controls_do_not_overlap(host)
    tops = {button.geometry().top() for button in buttons}
    assert len(tops) > 1
    host.close()


def test_restored_main_window_buttons_do_not_overlap(qapp: QApplication, monkeypatch) -> None:
    monkeypatch.setattr(Settings, "load_accounts", lambda self: [])
    from pyqorreos.ui.main_window import MainWindow

    window = MainWindow()
    try:
        window.message_viewer._btn_load_images.setVisible(True)
        window.message_viewer._btn_view_mode.setVisible(True)
        window.message_viewer._btn_translate.setVisible(True)
        _show_restored(qapp, window)
        assert window.width() <= 860
        assert_controls_do_not_overlap(window)
    finally:
        window._quitting = True
        window.close()
        qapp.processEvents()


def test_accounts_manager_shows_every_button(qapp: QApplication) -> None:
    dialog = AccountsManagerDialog(Settings(), [])
    try:
        dialog.show()
        qapp.processEvents()
        layout = dialog.layout()
        if layout is not None:
            layout.activate()
        qapp.processEvents()
        assert dialog.width() >= 640
        assert dialog.height() >= 460
        labels = {
            button.text()
            for button in dialog.findChildren(QPushButton)
            if button.isVisible()
        }
        assert {"+ Añadir", "Editar", "Eliminar", "Usar esta cuenta", "Cerrar"} <= labels
        for button in dialog.findChildren(QPushButton):
            if not button.isVisible():
                continue
            painted = _painted_rect(button, dialog)
            assert painted.width() >= button.width() - 2, button.text()
            assert painted.height() >= button.height() - 2, button.text()
        assert_controls_do_not_overlap(dialog)
    finally:
        dialog.close()
        qapp.processEvents()


def test_restored_account_and_compose_dialogs_do_not_overlap(qapp: QApplication) -> None:
    account = AccountDialog(Settings(), None)
    compose = ComposeDialog(
        SimpleNamespace(account=MailAccount(email="user@example.com")),
        drafts_folder=None,
    )
    try:
        for dialog in (account, compose):
            _show_restored(qapp, dialog)
            assert dialog.width() <= 860
            assert_controls_do_not_overlap(dialog)
    finally:
        account.close()
        compose.close()
        qapp.processEvents()
