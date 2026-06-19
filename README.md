<img width="1408" height="768" alt="PyQorreos" src="https://github.com/user-attachments/assets/19640ae3-ae11-419d-b033-9e1ee7fbcfc2" />

# PyQorreos

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/UI-PySide6-green?style=flat-square&logo=qt&logoColor=white)
![License](https://img.shields.io/badge/License-GPL--3.0-blue?style=flat-square)

<img width="1408" height="768" alt="PyQorreos" src="https://github.com/user-attachments/assets/19640ae3-ae11-419d-b033-9e1ee7fbcfc2" />

Gestor de correo electrónico con interfaz gráfica en **Python** y **PySide6**. Cliente ligero, fácil de modificar y orientado al aprendizaje y al uso diario — sin pretender competir con Thunderbird ni Evolution.

## ¿Por qué otro gestor de correo?

- Aprender IMAP y SMTP en un código legible
- Practicar PySide6 con un proyecto real
- Tener un cliente sencillo, sin dependencias enormes

## En resumen

- **Varias cuentas** IMAP/SMTP (Gmail, Outlook, Yahoo, servidor propio)
- **Bandeja de tres paneles** con sync incremental, caché local y clasificación spam/importante
- **Al arrancar**: caché al instante + descarga de correo nuevo del servidor
- **Visor HTML** (WebEngine), traducción, anti-phishing y List-Unsubscribe
- **Tema claro/oscuro** y estilos unificados

[Listista completa de características →](docs/features.md)

## Inicio rápido

```bash
cd PyQorreos
python run_app.py
```

`run_app.py` crea el entorno virtual, instala dependencias y arranca la app. Si ya tienes cuentas configuradas, **se conecta y descarga correo nuevo al abrir**; la primera vez: **Cuenta → Gestionar cuentas**.

## Documentación

Para que todo quede claro, en la siguiente tabla se puede consultar toda la documentación del proyecto:

| Guía | Descripción |
|------|-------------|
| [**Índice de documentación**](docs/README.md) | Punto de entrada a toda la documentación |
| [Características](docs/features.md) | Funcionalidades detalladas |
| [Instalación](docs/installation.md) | Requisitos e instalación manual |
| [Uso rápido](docs/usage.md) | Primeros pasos en la interfaz |
| [Atajos de teclado](docs/keyboard-shortcuts.md) | Referencia de atajos |
| [Estructura del proyecto](docs/project-structure.md) | Módulos y carpetas del código |
| [Configuración y notas](docs/configuration.md) | Archivos de datos, Gmail, privacidad… |
| [Pilares de calidad](docs/quality-pillars.md) | Rendimiento, robustez y aspecto visual |
| [Historial de cambios](docs/changelog.md) | Mejoras recientes |

## Licencia

[GNU General Public License v3.0](LICENSE)

---

**PyQorreos** — Desarrollado con pocas horas de sueño para la comunidad por [entreunosyceros](https://github.com/entreunosyceros), porque Thunderbird me estaba fallando.
