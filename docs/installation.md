# Instalación

[← Índice](README.md) · [README](../README.md)

## Requisitos

- Python 3.10+
- PySide6 (incluye Qt WebEngine para el visor HTML)
- keyring
- deep-translator (traducción de mensajes bajo demanda)
- pyspellchecker (corrector ortográfico al redactar)
- pytest (opcional, para ejecutar las pruebas en `tests/`)

## Instalación recomendada (código fuente)

```bash
cd PyQorreos
python run_app.py
```

El script `run_app.py` crea el entorno virtual (`.venv`) si no existe, instala las dependencias y arranca la aplicación.

## Instalación manual (código fuente)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Paquete Debian (.deb)

Instalador para **Debian / Ubuntu** y derivados. El paquete incluye el código de la aplicación (~1,4 MB); **no** incluye PySide6 ni un entorno virtual preinstalado.

### Instalar desde una release de GitHub

1. Descarga `pyqorreos_0.1.0-3_all.deb` desde [Releases](https://github.com/entreunosyceros/PyQorreos/releases).
2. Instala el paquete:

```bash
sudo apt install ./pyqorreos_0.1.0-3_all.deb
```

También puedes hacer doble clic en el archivo `.deb` desde el gestor de archivos.

**Arrancar la aplicación:**

- Menú de aplicaciones → **PyQorreos**
- O en terminal: `pyqorreos`

### Primer arranque tras instalar el .deb

1. Necesitas **conexión a internet** (se descargan PySide6 y el resto de dependencias con `pip`).
2. `run_app.py` crea el entorno virtual en:  
   `~/.local/share/pyqorreos/.venv`
3. El código de la aplicación queda en:  
   `/usr/share/pyqorreos`
4. Los datos de usuario (cuentas, caché, preferencias) en:  
   `~/.config/pyqorreos/`

Los siguientes arranques serán mucho más rápidos.

### Requisitos del paquete .deb

- Python 3.10+, `python3-venv` y `python3-pip` (instalados como dependencias del paquete)
- Recomendado: `gnupg` (OpenPGP), `libsecret-1-0` (llavero del sistema)

Arquitectura del `.deb`: **all** (código Python). En el primer arranque, `pip` instala los binarios de PySide6 adecuados para tu CPU.

### Actualizar el paquete

Descarga el `.deb` de la nueva versión e instálalo de nuevo:

```bash
sudo apt install ./pyqorreos_0.1.0-3_all.deb
```

Tu configuración en `~/.config/pyqorreos/` y el venv en `~/.local/share/pyqorreos/.venv` se conservan. Si tras una actualización hay problemas con dependencias Python, borra el venv y deja que se recree al arrancar (ver desinstalación completa).

### Desinstalar

Solo el paquete del sistema (conserva datos y entorno virtual del usuario):

```bash
sudo apt remove pyqorreos
```

Desinstalación completa (paquete + entorno virtual + datos locales):

```bash
sudo apt remove pyqorreos
rm -rf ~/.local/share/pyqorreos ~/.config/pyqorreos
```

> **Nota:** `~/.config/pyqorreos/` contiene cuentas (contraseñas en el llavero del sistema), caché de correo y preferencias. Solo bórralo si quieres eliminar todo rastro de la aplicación.

### Construir el .deb desde el código fuente

Para desarrolladores o empaquetadores:

```bash
# Dependencias de empaquetado
sudo apt install debhelper devscripts python3

# Construir (genera el .deb en el directorio padre del proyecto)
./scripts/build-deb.sh
```

El script deja el archivo en `../pyqorreos_0.1.0-3_all.deb` (ruta relativa a la raíz del repositorio).

## Ejecutar tests (opcional)

```bash
pip install -r requirements.txt
python -m pytest tests/ -q
```

---

**Siguiente paso:** [Uso rápido](usage.md) · **Ver también:** [Configuración y notas](configuration.md) (Gmail, llavero…)
