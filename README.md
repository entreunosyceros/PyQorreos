<img width="1408" height="768" alt="PyQorreos" src="https://github.com/user-attachments/assets/19640ae3-ae11-419d-b033-9e1ee7fbcfc2" />

# PyQorreos V.0.1.0

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/UI-PySide6-green?style=flat-square&logo=qt&logoColor=white)
![License](https://img.shields.io/badge/License-GPL--3.0-blue?style=flat-square)

<div align="center">

<img width="451" height="733" alt="about-PyQorreo" src="https://github.com/user-attachments/assets/435c73a7-c688-45ab-ba8e-54084536df76" />

</div>

Gestor de correo electrónico con interfaz gráfica en **Python** y **PySide6**. Cliente ligero, fácil de modificar y orientado al aprendizaje y al uso diario — sin pretender competir con Thunderbird ni Evolution.

## ¿Por qué otro gestor de correo?
<div align="center">

<img width="1917" height="1045" alt="PyQorreos-funcionando" src="https://github.com/user-attachments/assets/a1e2eb19-faf3-4190-8b9b-5f480557edb6" />
</div>

- Aprender IMAP y SMTP en un código legible
- Practicar PySide6 con un proyecto real
- Tener un cliente sencillo, sin dependencias enormes

## En resumen

- **Varias cuentas** IMAP/SMTP (Gmail, Outlook, Hotmail, MSN, AOL, Yahoo, hosting / dominio propio)
- **Bandeja de tres paneles** con sync incremental, caché local y clasificación spam/importante
- **Al arrancar**: caché al instante, **última carpeta** por cuenta y descarga de correo nuevo
- **Estado de conexión** permanente y barra de progreso solo al descargar mensajes nuevos
- **Visor HTML** (WebEngine), imágenes remotas bajo demanda, traducción y anti-phishing
- **Borradores editables** con **autoguardado**, búsqueda multi-carpeta y **en el cuerpo** (FTS5)
- **Destacados** (★, `Ctrl+D`), **archivar** (`Ctrl+E`) y **marcar carpeta como leída**
- **Gestión de carpetas**: crear, eliminar y **renombrar** (doble clic o `F2`); las del sistema protegidas
- **Documentación integrada** en Ayuda → Documentación (`F1`), navegable y con buscador
- **Agenda de contactos** local (direcciones habituales; sin impacto en sync)
- **Corrector ortográfico** al redactar (español / inglés)
- **OAuth2** (Gmail / Microsoft), presets por proveedor y tema claro/oscuro
- **Instalador `.deb`** para Debian/Ubuntu — ver [Instalación](docs/installation.md#paquete-debian-deb)
- **Tests** unitarios en `tests/` (`pytest`)

[Listista completa de características →](docs/features.md)

## Inicio rápido

**Desde el código fuente:**

```bash
cd PyQorreos
python run_app.py
```

**En Debian/Ubuntu** (paquete `.deb` desde [Releases](https://github.com/entreunosyceros/PyQorreos/releases)):

```bash
sudo apt install ./pyqorreos_0.1.0-3_all.deb
pyqorreos
```

Detalles, primer arranque y desinstalación: [Instalación](docs/installation.md#paquete-debian-deb).

`run_app.py` crea el entorno virtual, instala dependencias y arranca la app. Si ya tienes cuentas configuradas, **se conecta y descarga correo nuevo al abrir**; la primera vez: **Cuenta → Gestionar cuentas**.

## Documentación

Para que todo quede claro, en la siguiente tabla se puede consultar toda la documentación del proyecto:

| Guía | Descripción |
|------|-------------|
| [**Índice de documentación**](docs/README.md) | Punto de entrada a toda la documentación |
| [Características](docs/features.md) | Funcionalidades detalladas |
| [Instalación](docs/installation.md) | Requisitos, código fuente y paquete `.deb` |
| [Uso rápido](docs/usage.md) | Primeros pasos en la interfaz |
| [Atajos de teclado](docs/keyboard-shortcuts.md) | Referencia de atajos |
| [Estructura del proyecto](docs/project-structure.md) | Módulos y carpetas del código |
| [Configuración y notas](docs/configuration.md) | Archivos de datos, Gmail, Hotmail, MSN, AOL, privacidad… |
| [Pilares de calidad](docs/quality-pillars.md) | Rendimiento, robustez y aspecto visual |
| [Historial de cambios](docs/changelog.md) | Mejoras recientes |
| [Tests](../tests/) | Pruebas unitarias (`pytest`) |

## Licencia

[GNU General Public License v3.0](LICENSE)

---

**PyQorreos** — Desarrollado con pocas horas de sueño para la comunidad por [entreunosyceros](https://github.com/entreunosyceros), porque Thunderbird me estaba fallando.
