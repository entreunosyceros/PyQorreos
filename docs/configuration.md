# Configuración y notas

[← Índice](README.md) · [README](../README.md)

## Datos y configuración

| Ubicación | Contenido |
|-----------|-----------|
| `~/.config/pyqorreos/accounts.json` | Cuentas configuradas |
| `~/.config/pyqorreos/classification.json` | Reglas de clasificación |
| `~/.config/pyqorreos/preferences.json` | Preferencias (sync, imágenes, hilos, idioma de traducción, **tema**, plantillas…) |
| `~/.config/pyqorreos/mail_cache.db` | Caché local de correos |
| `~/.config/pyqorreos/oauth_clients.json` | Client ID y secret OAuth (Gmail / Microsoft) |
| Llavero del sistema | Contraseñas y tokens OAuth (vía `keyring`) |

Los archivos sensibles (`oauth_clients.json`, `accounts.json`, `mail_cache.db`, exportaciones `.eml`/`.mbox`) están en `.gitignore` si se copian al directorio del proyecto; la configuración real vive en `~/.config/pyqorreos/`.

## Notas importantes

### Gmail y cuentas

- Para **Gmail** puedes usar **OAuth2** (recomendado) o una [contraseña de aplicación](https://support.google.com/accounts/answer/185833).
- Para **Outlook / Hotmail / MSN / Live** (`@outlook.*`, `@hotmail.*`, `@live.*`, `@msn.com`): elige el preset **Outlook / Hotmail / MSN** o escribe el correo y se autoconfigura. **OAuth2** (Microsoft) es lo recomendado; con contraseña, puede hacer falta una contraseña de aplicación si tienes verificación en dos pasos.
- Para **AOL** (`@aol.*`): preset **AOL** (`imap.aol.com` / `smtp.aol.com`); suele requerir [contraseña de aplicación](https://login.aol.com/account/security).
- Para **Yahoo**: preset Yahoo; contraseña de aplicación habitual en cuentas con 2FA.
- Para **hosting / cPanel** (Webempresa, Raiola, etc.): preset **Hosting / cPanel**. Suele ser `mail.tudominio.com`, usuario = correo completo, IMAP **993 SSL/TLS**, SMTP **465 SSL** o **587 STARTTLS**. Usa **Probar conexión** antes de guardar.
- En Linux, el llavero usa Secret Service (GNOME Keyring, KWallet, etc.).

### OAuth2 (Gmail y Microsoft)

<div align="center">

<img width="457" height="707" alt="OAuth-PyQorreos" src="https://github.com/user-attachments/assets/c38b997a-d175-4073-912b-fb2c319d6d47" />

</div>

1. En PyQorreos: **Archivo → Preferencias → OAuth** y rellena el **Client ID** y el **Client secret** de cada proveedor que uses. También puedes abrir esa pestaña desde **Cuenta → Añadir / Editar** con el botón «Configurar OAuth en Preferencias…».
2. Registra una aplicación de **escritorio** en el proveedor (las instrucciones paso a paso están en la misma pestaña OAuth):
   - **Google:** [Google Cloud Console](https://console.cloud.google.com/) → APIs → Gmail API activada → Credenciales → ID de cliente OAuth → Aplicación de escritorio. URI de redirección: `http://127.0.0.1`.
   - **Microsoft:** [Entra / Azure Portal](https://portal.azure.com/) → Registros de aplicaciones → Nueva → Aplicaciones móviles y de escritorio → URI `http://127.0.0.1`. Permisos delegados: `IMAP.AccessAsUser.All`, `SMTP.Send`, `offline_access`.
3. Pulsa **Aceptar** en Preferencias para guardar en `~/.config/pyqorreos/oauth_clients.json`.
4. En **Cuenta → Añadir / Editar** → Autenticación **OAuth2** → **Identificarse con Google/Microsoft** (válido para Outlook, Hotmail y MSN).

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
- El texto se extrae del mensaje (HTML o parte de texto plano) y se limpia de restos de maquetación antes de traducir; el resultado se muestra en modo lectura con enlaces activos.
- Las traducciones se **cachean por mensaje**; «Ver original» restaura el correo sin volver a descargarlo.

### Carpetas IMAP

- Si en Gmail aparece una carpeta **Mailspring** (u otra de un cliente antiguo), puedes eliminarla con clic derecho en el árbol → **Eliminar carpeta…** (las carpetas del sistema como INBOX o `[Gmail]/…` están protegidas).

### Bandeja del sistema

- La bandeja del sistema incluye acceso directo a **Bandeja de entrada** de la cuenta seleccionada.

---

**Ver también:** [Uso rápido](usage.md) · [Instalación](installation.md) · [Características](features.md)
