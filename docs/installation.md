# Instalación

[← Índice](README.md) · [README](../README.md)

## Requisitos

- Python 3.10+
- PySide6 (incluye Qt WebEngine para el visor HTML)
- keyring
- deep-translator (traducción de mensajes bajo demanda)

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

---

**Siguiente paso:** [Uso rápido](usage.md) · **Ver también:** [Configuración y notas](configuration.md) (Gmail, llavero…)
