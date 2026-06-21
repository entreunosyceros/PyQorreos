# Configuración y notas

[← Índice](README.md) · [README](../README.md)

## Datos y configuración

| Ubicación | Contenido |
|-----------|-----------|
| `~/.config/pyqorreos/accounts.json` | Cuentas configuradas (`last_account_id`, `last_folders` por cuenta) |
| `~/.config/pyqorreos/classification.json` | Reglas de clasificación (también editables en Preferencias → Clasificación) |
| `~/.config/pyqorreos/contacts.json` | Agenda de contactos (correo, nombre, notas) |
| `~/.config/pyqorreos/preferences.json` | Preferencias (sync, imágenes, hilos, búsqueda multi-carpeta, idioma de traducción, **tema**, plantillas, **OpenPGP**…) |
| `~/.config/pyqorreos/gnupg/` | Llavero GnuPG de PyQorreos (si no usas `~/.gnupg` del sistema) |
| `~/.config/pyqorreos/mail_cache.db` | Caché local de correos |
| `~/.config/pyqorreos/oauth_clients.json` | Client ID y secret OAuth (Gmail / Microsoft) |
| Llavero del sistema | Contraseñas y tokens OAuth (vía `keyring`) |

Los archivos sensibles (`oauth_clients.json`, `accounts.json`, `mail_cache.db`, exportaciones `.eml`/`.mbox`) están en `.gitignore` si se copian al directorio del proyecto; la configuración real vive en `~/.config/pyqorreos/`.

## Notas importantes

### Gmail y cuentas

- Para **Gmail** puedes usar **OAuth2** (recomendado) o una [contraseña de aplicación](https://support.google.com/accounts/answer/185833).
- Para **Outlook / Hotmail / MSN / Live** (`@outlook.*`, `@hotmail.*`, `@live.*`, `@msn.com`): elige el preset **Outlook / Hotmail / MSN** o escribe el correo y se autoconfigura. **OAuth2** (Microsoft) es lo recomendado; con contraseña, puede hacer falta una contraseña de aplicación si tienes verificación en dos pasos.
- **Envío bloqueado por Microsoft** (`550 country not allowed`): el SMTP de Microsoft puede rechazar conexiones desde ciertas redes (VPN, IP de servidor/VPS, país distinto al habitual). No depende del acuse de recibo ni de los adjuntos. Prueba otra red, sin VPN, o envía desde [Outlook en la web](https://outlook.live.com/).

#### Si usas VPN (Outlook / Hotmail / MSN)

Microsoft suele **bloquear el envío SMTP** cuando la VPN saca el tráfico por un país distinto al de tu cuenta. La **lectura** (IMAP) a veces sigue funcionando; el fallo aparece al **enviar**.

Opciones habituales:

1. **Desconectar la VPN** solo al enviar correo (puedes volver a conectarla después).
2. **Split tunneling** en tu cliente VPN: excluir `smtp.office365.com` y `outlook.office365.com` para que el correo salga por tu IP real.
3. Elegir un **servidor VPN en tu país** (menos fiable que las dos anteriores).
4. Cuentas **Gmail, AOL o hosting propio** suelen ser menos estrictas con VPN; MSN/Outlook es el caso más habitual.
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

- Con cuentas ya configuradas, la app **conecta y descarga correo nuevo** al abrir (carpeta activa de la última sesión, no siempre INBOX).
- Las demás cuentas se actualizan al inicio si **Sincronizar cuentas en segundo plano** está activo en Preferencias.
- La caché local permite ver la bandeja **antes** de que termine la conexión.
- La **barra de progreso** bajo la lista solo aparece cuando hay mensajes nuevos que descargar; el estado de red (conectado, sincronizando…) se muestra de forma permanente a la derecha de la barra de estado.

### Traducción

- La **traducción** solo se ejecuta al pulsar «Traducir»; el texto se envía a un servicio en línea gratuito ([deep-translator](https://github.com/nidhaloff/deep-translator)).
- Configura el idioma destino en **Archivo → Preferencias → General**.
- El texto se extrae del mensaje (HTML o parte de texto plano) y se limpia de restos de maquetación antes de traducir; el resultado se muestra en modo lectura con enlaces activos.
- Las traducciones se **cachean por mensaje**; «Ver original» restaura el correo sin volver a descargarlo.

### Acuse de recibo

- Al **enviar**: marca «Solicitar acuse de recibo» en el editor, o activa **Solicitar acuse de recibo al enviar por defecto** en **Archivo → Preferencias → General → Redacción**.
- Al **recibir**: si el remitente lo pidió, el visor muestra un aviso con **Enviar acuse** o **Descartar**. El acuse se envía por SMTP como notificación MDN estándar.
- Gmail y otros clientes pueden ignorar la solicitud o preguntar al usuario antes de enviar el acuse.

### OpenPGP

- Instala **GnuPG** en el sistema (`gpg`) y el paquete Python `python-gnupg` (`pip install -r requirements.txt`).
- Activa OpenPGP en **Archivo → Preferencias → General → OpenPGP**. La sincronización de bandeja **no** se ve afectada.
- Importa claves en **Herramientas → Claves OpenPGP…** (públicas de destinatarios y tu clave privada para firmar/descifrar).
- Por defecto las claves viven en `~/.config/pyqorreos/gnupg`. Marca **Usar el llavero GnuPG del sistema** para compartir con `~/.gnupg`.
- La frase de paso la pide **gpg-agent** al firmar o descifrar; PyQorreos no la almacena.
- Si desactivas **Guardar cuerpos descifrados en caché**, los mensajes cifrados no guardan el texto plano en SQLite (se vuelven a descifrar al abrir).

### Carpetas IMAP

- Si en Gmail aparece una carpeta **Mailspring** (u otra de un cliente antiguo), puedes eliminarla con clic derecho en el árbol → **Eliminar carpeta…** (las carpetas del sistema como INBOX o `[Gmail]/…` están protegidas).

### Bandeja del sistema

- La bandeja del sistema incluye acceso directo a **Bandeja de entrada** de la cuenta seleccionada.

---

**Ver también:** [Uso rápido](usage.md) · [Instalación](installation.md) · [Características](features.md)
