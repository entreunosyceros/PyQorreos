#!/usr/bin/env python3
"""
Lanzador de PyQorreos.

Este script es el punto de entrada recomendado. Se encarga de:
  1. Crear el entorno virtual (.venv) si no existe.
  2. Instalar las dependencias listadas en requirements.txt.
  3. Relanzar la aplicación con el intérprete del venv.
  4. Abrir la interfaz gráfica del gestor de correo.

Uso:
    python run_app.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Rutas base del proyecto (siempre relativas a este archivo).
PROJECT_DIR = Path(__file__).resolve().parent
VENV_DIR = PROJECT_DIR / ".venv"
REQUIREMENTS_FILE = PROJECT_DIR / "requirements.txt"
REQUIRED_PACKAGES = ("PySide6", "keyring")


def get_venv_python() -> Path:
    """Devuelve la ruta al ejecutable Python dentro de .venv."""
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def is_running_in_venv() -> bool:
    """
    Comprueba si el intérprete actual pertenece al venv del proyecto.

    Se usa sys.prefix (directorio del entorno activo), NO sys.executable.resolve(),
    porque en Linux el binario del venv suele ser un enlace simbólico al Python
    del sistema y ambos resolverían a la misma ruta, provocando falsos positivos.
    """
    if not VENV_DIR.exists():
        return False
    return Path(sys.prefix).resolve() == VENV_DIR.resolve()


def create_venv() -> None:
    """Crea un entorno virtual nuevo en la carpeta .venv del proyecto."""
    print("Creando entorno virtual en .venv …")
    subprocess.run(
        [sys.executable, "-m", "venv", str(VENV_DIR)],
        check=True,
        cwd=PROJECT_DIR,
    )
    print("Entorno virtual creado.")


def ensure_venv() -> Path:
    """
    Garantiza que existe .venv y devuelve la ruta a su ejecutable Python.

    Si el entorno no existe, lo crea antes de devolver la ruta.
    """
    venv_python = get_venv_python()
    if not venv_python.exists():
        create_venv()
        venv_python = get_venv_python()
    if not venv_python.exists():
        raise RuntimeError("No se pudo crear el entorno virtual.")
    return venv_python


def install_dependencies(venv_python: Path) -> None:
    """
    Instala (o actualiza) las dependencias dentro del entorno virtual.

    Usa requirements.txt si existe; en caso contrario instala los paquetes
    mínimos definidos en REQUIRED_PACKAGES.
    """
    print("Instalando dependencias en el entorno virtual …")

    # Actualizar pip de forma silenciosa.
    subprocess.run(
        [str(venv_python), "-m", "pip", "install", "-q", "--upgrade", "pip"],
        check=True,
        cwd=PROJECT_DIR,
    )

    if REQUIREMENTS_FILE.exists():
        cmd = [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "-q",
            "-r",
            str(REQUIREMENTS_FILE),
        ]
    else:
        cmd = [str(venv_python), "-m", "pip", "install", "-q", *REQUIRED_PACKAGES]

    subprocess.run(cmd, check=True, cwd=PROJECT_DIR)
    print("Dependencias instaladas correctamente.")


def launch_app() -> int:
    """
    Importa y arranca la interfaz gráfica.

    Solo debe llamarse cuando ya estamos ejecutando con el Python del venv,
    de modo que PySide6 y el resto de paquetes estén disponibles.
    """
    from pyqorreos.ui.webengine_setup import configure_webengine_environment

    configure_webengine_environment()
    from pyqorreos.ui.main_window import run_app

    try:
        run_app()
    except KeyboardInterrupt:
        print("\nAplicación cerrada por el usuario.")
        os._exit(0)
    return 0


def main() -> int:
    """Orquesta la preparación del entorno y el arranque de la aplicación."""
    os.chdir(PROJECT_DIR)
    if str(PROJECT_DIR) not in sys.path:
        sys.path.insert(0, str(PROJECT_DIR))

    if is_running_in_venv():
        try:
            return launch_app()
        except Exception as exc:
            import traceback

            print(f"Error al iniciar PyQorreos: {exc}", file=sys.stderr)
            traceback.print_exc()
            return 1

    from pyqorreos.ui.webengine_setup import configure_webengine_environment

    configure_webengine_environment()

    try:
        venv_python = ensure_venv()
        install_dependencies(venv_python)

        print("Iniciando PyQorreos …")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT_DIR)
        os.environ.update(env)
        argv = [str(venv_python), str(__file__), *sys.argv[1:]]
        # Reemplaza este proceso por el Python del venv (sin proceso padre bloqueando
        # la terminal en subprocess.run tras cerrar la aplicación).
        os.execv(str(venv_python), argv)
        return 1

    except subprocess.CalledProcessError as exc:
        print(f"Error al preparar el entorno: {exc}", file=sys.stderr)
        print(
            "\nSugerencias:\n"
            "- Comprueba tu conexión a internet.\n"
            "- Instala manualmente: .venv/bin/pip install -r requirements.txt\n"
            "- Recrea el entorno: rm -rf .venv && python run_app.py",
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        print("\nAplicación cerrada por el usuario.")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
