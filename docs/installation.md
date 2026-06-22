# Instalación

[← Índice](README.md) · [README](../README.md)

## Requisitos

- Python 3.10+
- PySide6 (incluye Qt WebEngine para el visor HTML)
- keyring
- deep-translator (traducción de mensajes bajo demanda)
- pytest (opcional, para ejecutar las pruebas en `tests/`)

## Instalación recomendada

```bash
cd PyQorreos
python run_app.py
```

El script `run_app.py` crea el entorno virtual (`.venv`) si no existe, instala las dependencias y arranca la aplicación.

## Instalación manual

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Paquete Debian (.deb)

Para generar e instalar un paquete `.deb` en Debian/Ubuntu:

```bash
# Dependencias de empaquetado
sudo apt install debhelper devscripts python3 python3-venv python3-pip

# Construir (descarga PySide6 en el venv del paquete; ~2–5 min)
./scripts/build-deb.sh

# Instalar el .deb generado en el directorio padre
sudo apt install ../pyqorreos_0.1.0-2_amd64.deb
```

Tras instalar, ejecuta **PyQorreos** desde el menú de aplicaciones o con `pyqorreos`.
La aplicación queda en `/usr/lib/pyqorreos` con su propio entorno virtual.

## Ejecutar tests (opcional)

```bash
pip install -r requirements.txt
python -m pytest tests/ -q
```

---

**Siguiente paso:** [Uso rápido](usage.md) · **Ver también:** [Configuración y notas](configuration.md) (Gmail, llavero…)
