# Configuración y notas

[← Índice](README.md) · [README](../README.md)

## Datos y configuración

| Ubicación | Contenido |
|-----------|-----------|
| `~/.config/pyqorreos/accounts.json` | Cuentas configuradas |
| `~/.config/pyqorreos/classification.json` | Reglas de clasificación |
| `~/.config/pyqorreos/preferences.json` | Preferencias (sync, imágenes, hilos, idioma de traducción, plantillas…) |
| `~/.config/pyqorreos/mail_cache.db` | Caché local de correos |
| Llavero del sistema | Contraseñas y tokens OAuth (vía `keyring`) |

## Notas importantes

### Gmail y cuentas

- Para **Gmail** necesitas una [contraseña de aplicación](https://support.google.com/accounts/answer/185833), no tu contraseña habitual.
- **OAuth2** está preparado a nivel de configuración; el flujo completo con navegador aún no está integrado.
- En Linux, el llavero usa Secret Service (GNOME Keyring, KWallet, etc.).

### Privacidad y visor

- Por defecto las **imágenes remotas** están bloqueadas; puedes mostrarlas con el botón del visor o desactivar el bloqueo en Preferencias.
- Los avisos de Chromium/WebEngine en terminal están filtrados cuando es posible; no afectan al uso normal.

### Traducción

- La **traducción** solo se ejecuta al pulsar «Traducir»; el texto se envía a un servicio en línea gratuito ([deep-translator](https://github.com/nidhaloff/deep-translator)).
- Configura el idioma destino en **Archivo → Preferencias → General**.

### Carpetas IMAP

- Si en Gmail aparece una carpeta **Mailspring** (u otra de un cliente antiguo), puedes eliminarla con clic derecho en el árbol → **Eliminar carpeta…** (las carpetas del sistema como INBOX o `[Gmail]/…` están protegidas).

### Bandeja del sistema

- La bandeja del sistema incluye acceso directo a **Bandeja de entrada** de la cuenta seleccionada.

---

**Ver también:** [Uso rápido](usage.md) · [Instalación](installation.md) · [Características](features.md)
