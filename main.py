#!/usr/bin/env python3
"""
Punto de entrada alternativo de PyQorreos.

Requiere tener el entorno virtual activado y las dependencias instaladas.
Para arranque automático del venv, usa run_app.py en su lugar.
"""

from pyqorreos.ui.webengine_setup import configure_webengine_environment

configure_webengine_environment()

from pyqorreos.ui.main_window import run_app

if __name__ == "__main__":
    run_app()
