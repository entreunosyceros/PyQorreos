<img width="1408" height="768" alt="PyQorreos" src="https://github.com/user-attachments/assets/19640ae3-ae11-419d-b033-9e1ee7fbcfc2" />

# PyQorreos

Gestor de correo electrónico con interfaz gráfica en **Python** y **PySide6**. Cliente ligero, fácil de modificar y orientado al aprendizaje y al uso diario — sin pretender competir con Thunderbird ni Evolution.

## ¿Por qué otro gestor de correo?

- Aprender IMAP y SMTP en un código legible
- Practicar PySide6 con un proyecto real
- Tener un cliente sencillo, sin dependencias enormes

## En resumen

- **Varias cuentas** IMAP/SMTP (Gmail, Outlook, Yahoo, servidor propio)
- **Bandeja de tres paneles** con sync incremental, caché local y clasificación spam/importante
- **Visor HTML** (WebEngine), traducción bajo demanda, anti-phishing y List-Unsubscribe
- **Editor enriquecido** con plantillas, adjuntos y borradores en el servidor

[Listista completa de características →](docs/features.md)

## Inicio rápido

```bash
cd PyQorreos
python run_app.py
```

`run_app.py` crea el entorno virtual, instala dependencias y arranca la app. Luego: **Cuenta → Gestionar cuentas**, prueba la conexión y empieza a leer correo.

## Documentación

| Guía | Descripción |
|------|-------------|
| [**Índice de documentación**](docs/README.md) | Punto de entrada a toda la documentación |
| [Características](docs/features.md) | Funcionalidades detalladas |
| [Instalación](docs/installation.md) | Requisitos e instalación manual |
| [Uso rápido](docs/usage.md) | Primeros pasos en la interfaz |
| [Atajos de teclado](docs/keyboard-shortcuts.md) | Referencia de atajos |
| [Estructura del proyecto](docs/project-structure.md) | Módulos y carpetas del código |
| [Configuración y notas](docs/configuration.md) | Archivos de datos, Gmail, privacidad… |

## Licencia

MIT

---

**PyQorreos** — Desarrollado con pocas horas de sueño para la comunidad por [entreunosyceros](https://github.com/entreunosyceros/pyqorreos), porque Thunderbird me estaba fallando.
