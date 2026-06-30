# Estructura del proyecto

[← Índice](README.md) · [README](../README.md)

<div align="center">
<img width="451" height="733" alt="about-PyQorreo" src="https://github.com/user-attachments/assets/f2a42a71-0a2f-4c87-9285-e4827177c901" />
</div>

```
PyQorreos/
├── run_app.py              # Lanzador recomendado (venv + deps)
├── main.py                 # Entrada alternativa
├── requirements.txt
├── tests/                  # Pruebas unitarias (pytest)
├── docs/                   # Documentación (esta carpeta)
└── pyqorreos/
    ├── core/
    │   ├── account.py              # Cuentas, presets (Gmail, Microsoft, AOL, Yahoo…)
    │   ├── mail_service.py         # Cliente IMAP/SMTP
    │   ├── mail_cache.py           # Caché SQLite de cabeceras y cuerpos
    │   ├── classifier.py           # Clasificación spam / importante
    │   ├── address_book.py           # Agenda de contactos (JSON local)
    │   ├── retry.py                # Reintentos ante fallos transitorios de red
    │   ├── email_html.py           # Preparación HTML para lectura
    │   ├── email_charset.py        # Charsets MIME (unknown-8bit, etc.)
    │   ├── translate.py            # Traducción de mensajes (deep-translator)
    │   ├── network_errors.py       # Mensajes de error legibles (red/IMAP/SMTP)
    │   ├── list_unsubscribe.py     # Cabecera List-Unsubscribe
    │   ├── link_safety.py          # Detección de enlaces sospechosos
    │   ├── export_mail.py          # Exportación .eml / .mbox
    │   ├── compose_email.py        # HTML, adjuntos y borradores
    │   ├── compose_utils.py        # Utilidades al redactar (p. ej. adjuntos)
    │   ├── reply_utils.py          # Borradores de respuesta / reenvío
    │   ├── settings.py             # Configuración y keyring
    │   ├── user_preferences.py     # Preferencias de la aplicación
    │   ├── folder_utils.py         # Árbol de carpetas y utilidades IMAP
    │   ├── message_attachments.py  # Extracción de adjuntos MIME
    │   ├── oauth.py                # OAuth2 (Gmail / Microsoft: Outlook, Hotmail, MSN)
    │   └── oauth_clients.py        # Client ID/secret OAuth en disco
    ├── img/
    │   ├── logos.png
    │   └── folders/                # Iconos SVG de carpetas
    └── ui/
        ├── main_window.py          # Ventana principal
        ├── message_viewer.py       # Visor HTML (WebEngine)
        ├── attachment_panel.py     # Panel de adjuntos al leer
        ├── compose_dialog.py       # Redactar / responder
        ├── rich_compose_editor.py  # Barra de formato del editor
        ├── account_dialog.py       # Alta/edición de una cuenta
        ├── accounts_manager_dialog.py
        ├── about_dialog.py
        ├── documentation_dialog.py # Visor de documentación integrado (Ayuda → Documentación)
        ├── preferences_dialog.py   # Preferencias (general, plantillas, clasificación, OAuth)
        ├── address_book_dialog.py    # Agenda de contactos
        ├── classification_rules_widget.py  # Editor de reglas importante/spam
        ├── background_sync.py      # IDLE y sync en segundo plano
        ├── notification_utils.py   # Texto de notificaciones de correo nuevo
        ├── folder_tree_widget.py   # Árbol de carpetas
        ├── folder_icons.py         # Iconos por tipo de carpeta
        ├── system_tray.py
        ├── webengine_setup.py
        ├── theme.py                # Tema claro/oscuro y estilos globales
        └── workers.py              # Hilos de red
```

---

**Ver también:** [Configuración y notas](configuration.md) · [Características](features.md)
