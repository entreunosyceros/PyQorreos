# PyQorreos

Gestor de correo electrónico con interfaz gráfica en **Python** y **PySide6**. PyQorreos nace porque quería un cliente de correo sencillo, rápido y completamente en Python. No pretende competir con Thunderbird ni Evolution, sino ofrecer una alternativa ligera, fácil de modificar y orientada al aprendizaje y al uso diario.

## ¿Por qué otro gestor de correo?

- aprender IMAP
- aprender SMTP
- practicar PySide
- tener un cliente sencillo
- evitar dependencias enormes

## Características

### Cuentas y conexión
- Varias cuentas de correo (Gmail, Outlook, Yahoo o servidor personalizado)
- Selector rápido de cuenta activa y gestor de cuentas (añadir, editar, eliminar)
- Conexión IMAP/SMTP con contraseñas en el llavero del sistema (`keyring`)
- Firma de correo configurable por cuenta
- Base preparada para OAuth2 (Gmail / Outlook); de momento se usa contraseña de aplicación
- Bandeja del sistema: la app sigue activa al cerrar la ventana

### Bandeja y sincronización
- Vista de tres paneles: carpetas | lista de mensajes | lectura
- Árbol de carpetas con iconos SVG y contador de no leídos
- Sincronización incremental (solo descarga mensajes nuevos)
- Sincronización en segundo plano (IMAP IDLE + polling) configurable en preferencias (por defecto cada 15 minutos)
- Caché local SQLite para abrir la bandeja al instante
- Paginación configurable y barra de progreso de sincronización
- Clasificación automática: normal, importante, spam (con filtro y colores)
- Búsqueda por asunto o remitente, filtro «Solo no leídos» y ordenación
- Vista de conversaciones (agrupación por hilos, opcional en preferencias)
- Notificaciones de correo nuevo en la bandeja del sistema

### Lectura de mensajes
- Visor HTML con Qt WebEngine (maquetado fiel al correo original)
- Imágenes embebidas (cid); imágenes remotas bloqueables por privacidad
- Botón «Mostrar imágenes remotas» bajo demanda
- Adjuntos: listar, abrir y guardar desde el panel del lector
- Caché de cuerpos: los mensajes ya abiertos se muestran sin volver a descargar
- Precarga del siguiente mensaje de la lista

### Acciones sobre el correo
- Responder, responder a todos, reenviar y eliminar
- Selección múltiple: marcar, eliminar o mover varios mensajes a la vez
- Mover mensajes entre carpetas (menú contextual)
- Vaciar papelera desde el menú contextual de la carpeta
- Marcar como leído / no leído
- Marcar categoría (importante, spam, normal) desde barra, menú o clic derecho
- Menú contextual en el listado (copiar remitente, actualizar carpeta…)
- Atajos: `Ctrl+R`, `Ctrl+Shift+R`, `Ctrl+L`, `Supr`, `F5`

### Redacción
- Editor enriquecido: negrita, cursiva, subrayado, listas, color, enlaces e imágenes
- Adjuntar archivos al enviar
- Envío HTML + texto plano por SMTP
- Borradores precargados al responder o reenviar (cita HTML del mensaje original)
- Guardar borrador en la carpeta Drafts del servidor
- Firma insertada automáticamente al redactar

### Rendimiento y estabilidad
- Operaciones de red en hilos secundarios (la interfaz no se bloquea)
- Conexión IMAP dedicada por mensaje y reintentos ante errores de protocolo
- Cabeceras limitadas en carpetas muy grandes (>5000 mensajes) en la primera sync

## Requisitos

- Python 3.10+
- PySide6 (incluye Qt WebEngine para el visor HTML)
- keyring

## Instalación

```bash
cd PyQorreos
python run_app.py
```

El script `run_app.py` crea el entorno virtual (`.venv`) si no existe, instala las dependencias y arranca la aplicación.

Instalación manual:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Uso rápido

1. **Cuenta → Gestionar cuentas** (o **Gestionar…** en la barra superior) para añadir una o más cuentas.
2. Usa **Probar conexión** en el diálogo de cuenta antes de guardar.
3. Opcional: define una **firma** en el diálogo de cuenta.
4. Cambia de cuenta con el desplegable **Cuenta:**.
5. Navega por el **árbol de carpetas**; clic izquierdo en un mensaje para abrirlo.
6. Usa la **barra de búsqueda** y los filtros sobre la lista de mensajes.
7. **Redactar** (`Ctrl+N`) o **Responder** (`Ctrl+R`) con el editor enriquecido.
8. Clic derecho en el listado o en una carpeta para más acciones.
9. Ajusta el comportamiento en **Cuenta → Preferencias…** (`Ctrl+,`).

## Atajos de teclado

| Atajo | Acción |
|-------|--------|
| `Ctrl+N` | Redactar |
| `Ctrl+R` | Responder |
| `Ctrl+Shift+R` | Responder a todos |
| `Ctrl+L` | Reenviar |
| `Ctrl+B` / `I` / `U` | Negrita / cursiva / subrayado (en el editor) |
| `Delete` | Eliminar mensaje(s) seleccionado(s) |
| `F5` | Actualizar carpeta |
| `Ctrl+,` | Preferencias |
| `Ctrl+Q` | Salir |

En la lista de mensajes puedes usar **selección múltiple** (`Ctrl+clic`, `Shift+clic`) para eliminar o mover varios correos.

## Estructura del proyecto

```
PyQorreos/
├── run_app.py              # Lanzador recomendado (venv + deps)
├── main.py                 # Entrada alternativa
├── requirements.txt
└── pyqorreos/
    ├── core/
    │   ├── account.py              # Cuentas y presets de proveedores
    │   ├── mail_service.py         # Cliente IMAP/SMTP
    │   ├── mail_cache.py           # Caché SQLite de cabeceras y cuerpos
    │   ├── classifier.py           # Clasificación spam / importante
    │   ├── email_html.py           # Preparación HTML para lectura
    │   ├── compose_email.py        # HTML, adjuntos y borradores
    │   ├── reply_utils.py          # Borradores de respuesta / reenvío
    │   ├── settings.py             # Configuración y keyring
    │   ├── user_preferences.py     # Preferencias de la aplicación
    │   ├── folder_utils.py         # Árbol de carpetas y utilidades IMAP
    │   ├── message_attachments.py  # Extracción de adjuntos MIME
    │   └── oauth.py                # Base OAuth2 (Gmail / Outlook)
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
        ├── preferences_dialog.py   # Preferencias de la aplicación
        ├── background_sync.py      # IDLE y sync en segundo plano
        ├── folder_tree_widget.py   # Árbol de carpetas
        ├── folder_icons.py         # Iconos por tipo de carpeta
        ├── system_tray.py
        ├── webengine_setup.py
        └── workers.py              # Hilos de red
```

## Datos y configuración

| Ubicación | Contenido |
|-----------|-----------|
| `~/.config/pyqorreos/accounts.json` | Cuentas configuradas |
| `~/.config/pyqorreos/classification.json` | Reglas de clasificación |
| `~/.config/pyqorreos/preferences.json` | Preferencias (sync, imágenes, hilos…) |
| `~/.config/pyqorreos/mail_cache.db` | Caché local de correos |
| Llavero del sistema | Contraseñas y tokens OAuth (vía `keyring`) |

## Notas

- Para **Gmail** necesitas una [contraseña de aplicación](https://support.google.com/accounts/answer/185833), no tu contraseña habitual.
- **OAuth2** está preparado a nivel de configuración; el flujo completo con navegador aún no está integrado.
- En Linux, el llavero usa Secret Service (GNOME Keyring, KWallet, etc.).
- Los avisos de Chromium/WebEngine en terminal están filtrados cuando es posible; no afectan al uso normal.
- Por defecto las **imágenes remotas** están bloqueadas; puedes mostrarlas con el botón del visor o desactivar el bloqueo en Preferencias.

## Licencia

MIT
