#!/usr/bin/env bash
# Genera el paquete .deb de PyQorreos (requiere debhelper, python3-venv).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

need() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Falta $1. Instala con:" >&2
        echo "  sudo apt install debhelper devscripts python3 python3-venv python3-pip" >&2
        exit 1
    fi
}

need dpkg-buildpackage
need dh
need python3

echo "==> Construyendo paquete Debian de PyQorreos…"
echo "    (solo código fuente; run_app.py crea .venv al primer arranque)"
echo

# Limpiar artefactos previos en el directorio padre.
rm -f ../pyqorreos_*.deb ../pyqorreos_*.changes ../pyqorreos_*.buildinfo 2>/dev/null || true
rm -rf debian/pyqorreos debian/.debhelper debian/files debian/debhelper-build-stamp 2>/dev/null || true

export DEB_BUILD_OPTIONS="nocheck"
dpkg-buildpackage -b -us -uc

DEB="$(ls -1t ../pyqorreos_*.deb 2>/dev/null | head -1)"
if [ -n "${DEB:-}" ] && [ -f "$DEB" ]; then
    echo
    echo "Paquete generado:"
    echo "  $DEB"
    echo
    echo "Instalar:"
    echo "  sudo apt install ./$(basename "$DEB")"
    if command -v lintian >/dev/null 2>&1; then
        echo
        echo "==> Comprobación Lintian:"
        lintian "$DEB" 2>&1 | head -30 || true
    fi
else
    echo "No se encontró el archivo .deb generado." >&2
    exit 1
fi
