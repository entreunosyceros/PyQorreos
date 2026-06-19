# Configuración y notas

[← Índice](README.md) · [README](../README.md)

## Datos y configuración

| Ubicación | Contenido |
|-----------|-----------|
| `~/.config/pyqorreos/accounts.json` | Cuentas configuradas |
| `~/.config/pyqorreos/classification.json` | Reglas de clasificación |
| `~/.config/pyqorreos/preferences.json` | Preferencias (sync, imágenes, hilos, idioma de traducción, **tema**, plantillas…) |
| `~/.config/pyqorreos/mail_cache.db` | Caché local de correos |
| `~/.config/pyqorreos/oauth_clients.json` | Client ID y secret OAuth (Gmail / Outlook) |
| Llavero del sistema | Contraseñas y tokens OAuth (vía `keyring`) |

## Notas importantes

### Gmail y cuentas

- Para **Gmail** puedes usar **OAuth2** (recomendado) o una [contraseña de aplicación](https://support.google.com/accounts/answer/185833).
- Para **Outlook / Hotmail** también puedes usar **OAuth2** o contraseña de aplicación si tu cuenta lo permite.
- En Linux, el llavero usa Secret Service (GNOME Keyring, KWallet, etc.).

### OAuth2 (Gmail y Outlook)

1. En PyQorreos: **Archivo → Preferencias → OAuth** y rellena el **Client ID** y el **Client secret** de cada proveedor que uses. También puedes abrir esa pestaña desde **Cuenta → Añadir / Editar** con el botón «Configurar OAuth en Preferencias…».
2. Registra una aplicación de **escritorio** en el proveedor (las instrucciones paso a paso están en la misma pestaña OAuth):
   - **Google:** [Google Cloud Console](https://console.cloud.google.com/) → APIs → Gmail API activada → Credenciales → ID de cliente OAuth → Aplicación de escritorio. URI de redirección: `http://127.0.0.1`.
   - **Microsoft:** [Entra / Azure Portal](https://portal.azure.com/) → Registros de aplicaciones → Nueva → Aplicaciones móviles y de escritorio → URI `http://127.0.0.1`. Permisos delegados: `IMAP.AccessAsUser.All`, `SMTP.Send`, `offline_access`.
3. Pulsa **Aceptar** en Preferencias para guardar en `~/.config/pyqorreos/oauth_clients.json`.
4. En **Cuenta → Añadir / Editar** → Autenticación **OAuth2** → **Identificarse con Google/Microsoft**.

El `refresh_token` se guarda en el llavero de forma permanente; el `access_token` se usa para conectar y se renueva automáticamente al caducar.

### Privacidad y visor

- Por defecto las **imágenes remotas** están bloqueadas; puedes mostrarlas con el botón del visor o desactivar el bloqueo en Preferencias.
- Los avisos de Chromium/WebEngine en terminal están filtrados cuando es posible; no afectan al uso normal.

### Sincronización al arrancar

- Con cuentas ya configuradas, la app **conecta y descarga correo nuevo** al abrir (INBOX de la cuenta activa).
- Las demás cuentas se actualizan al inicio si **Sincronizar cuentas en segundo plano** está activo en Preferencias.
- La caché local permite ver la bandeja **antes** de que termine la conexión.

### Traducción

- La **traducción** solo se ejecuta al pulsar «Traducir»; el texto se envía a un servicio en línea gratuito ([deep-translator](https://github.com/nidhaloff/deep-translator)).
- Configura el idioma destino en **Archivo → Preferencias → General**.

### Carpetas IMAP

- Si en Gmail aparece una carpeta **Mailspring** (u otra de un cliente antiguo), puedes eliminarla con clic derecho en el árbol → **Eliminar carpeta…** (las carpetas del sistema como INBOX o `[Gmail]/…` están protegidas).

### Bandeja del sistema

- La bandeja del sistema incluye acceso directo a **Bandeja de entrada** de la cuenta seleccionada.

---

**Ver también:** [Uso rápido](usage.md) · [Instalación](installation.md) · [Características](features.md)
