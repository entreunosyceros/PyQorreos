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
| `~/.config/pyqorreos/mail_cache.db` | Caché local de correos (incluye índice **FTS5** para la búsqueda en el cuerpo) |
| `~/.config/pyqorreos/oauth_clients.json` | Override opcional de Client ID/secret OAuth (si no, se usa el cliente embebido) |
| Llavero del sistema | Contraseñas y tokens OAuth (vía `keyring`) |

Los archivos sensibles (`oauth_clients.json`, `accounts.json`, `mail_cache.db`, exportaciones `.eml`/`.mbox`) están en `.gitignore` si se copian al directorio del proyecto; la configuración real vive en `~/.config/pyqorreos/`.

## Notas importantes

### Gmail y cuentas

- Para **Gmail** el alta muestra el correo y **Identificarse con Google**. Google no deja usar el Client ID de Thunderbird: la primera vez hay que pegar el de una aplicación de escritorio creada para PyQorreos; se guarda en el equipo y, a partir de ahí, el botón abre el navegador. En el navegador Google avisa de que la aplicación **no está verificada** (el aviso de que no está certificada): es lo previsto y se puede continuar; el detalle está en [Aviso de Google](#aviso-google-no-ha-verificado-esta-aplicación). **Configuración avanzada** muestra puertos, cifrado y la contraseña de aplicación. Mientras la pantalla de consentimiento esté en modo prueba, solo entran los Gmail añadidos como usuarios de prueba.
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
- Para **GMX** (`@gmx.com`, `@gmx.net`, `@gmx.de`, `@gmx.es`…): preset **GMX** (`imap.gmx.com:993` SSL / `mail.gmx.com:587` STARTTLS). **Importante:** GMX trae **IMAP/POP3 desactivado por defecto**; debes activarlo en el webmail (**Ajustes → POP3 & IMAP → «Habilitar el acceso a esta cuenta mediante POP3 e IMAP» → Guardar**) o el inicio de sesión fallará aunque la contraseña sea correcta. GMX puede volver a desactivarlo tras un periodo largo sin usarlo. [Guía oficial](https://support.gmx.com/pop-imap/toggle.html).
- Para **Yahoo**: preset Yahoo; contraseña de aplicación habitual en cuentas con 2FA.
- Para **hosting / cPanel** (Webempresa, Raiola, etc.): preset **Hosting / cPanel**. Suele ser `mail.tudominio.com`, usuario = correo completo, IMAP **993 SSL/TLS**, SMTP **465 SSL** o **587 STARTTLS**. Usa **Probar conexión** antes de guardar.
- La seguridad de **IMAP y SMTP se elige por separado** (SSL, STARTTLS o sin cifrar). El diálogo muestra una línea con el modo real, por ejemplo «IMAP SSL en el puerto 993 · SMTP STARTTLS en el puerto 587». Una cuenta antigua se migra por el puerto: 993 es IMAP SSL, 143 con STARTTLS sigue en STARTTLS, 465 es SMTP SSL y 587 es SMTP STARTTLS.
- En Linux, el llavero usa Secret Service (GNOME Keyring, KWallet, etc.).

### OAuth2 (Gmail y Microsoft)

<div align="center">

<img width="457" height="707" alt="OAuth-PyQorreos" src="https://github.com/user-attachments/assets/c38b997a-d175-4073-912b-fb2c319d6d47" />

</div>

#### Uso normal (recomendado)

1. **Cuenta → Añadir**. Con Gmail basta el correo y **Identificarse con Google** (o Microsoft).
2. Autoriza en el navegador. Los tokens se guardan en el llavero y se renuevan solos.
3. **Configuración avanzada** deja ver servidores, puertos y la alternativa de contraseña.

Thunderbird trae el cliente de Mozilla y Google no permite reutilizarlo. PyQorreos abre el navegador cuando este equipo ya tiene el Client ID de su propia aplicación de escritorio (la primera pulsación de **Identificarse con Google** lo pide y lo guarda en `~/.config/pyqorreos/oauth_clients.json`).

#### Aviso «Google no ha verificado esta aplicación»

Al autorizar el correo, Google muestra una pantalla que dice que la aplicación **no está verificada**. Es el aviso de que PyQorreos **no está certificada por Google**. Aparece porque el Client ID pide el permiso de Gmail (`https://mail.google.com/`) y Google no ha revisado ese proyecto de Cloud. El cliente de Thunderbird no lo muestra porque Mozilla completó esa revisión.

Mientras la pantalla de consentimiento siga en **modo prueba**, el aviso es el comportamiento normal. Para continuar:

1. Pulsa **Avanzado**.
2. Pulsa **Ir a PyQorreos (no seguro)**. El nombre es el que pusiste a la aplicación en Google Cloud.
3. Acepta el acceso al correo.

Eso autoriza la cuenta con la que has entrado. En modo prueba, esa cuenta tiene que figurar también en **Usuarios de prueba** de la pantalla de consentimiento (hasta 100). El aviso no tiene que ver con el cifrado del correo: IMAP y SMTP siguen conectando con los servidores de Google por TLS.

Hacer que cualquier Gmail entre sin este aviso exige la verificación de Google del proyecto. El ámbito de Gmail es restringido y esa revisión queda fuera del uso personal.

#### Override opcional (desarrolladores / tu propia app)

Si quieres usar **tu** Client ID en lugar del incluido:

1. **Archivo → Preferencias → OAuth** y rellena Client ID / secret.
2. Registra una aplicación de escritorio. En la consola la URI es `http://127.0.0.1`. PyQorreos pide la autorización en `http://127.0.0.1:<puerto>/`: el puerto cambia en cada identificación.
3. Se guarda en `~/.config/pyqorreos/oauth_clients.json` y **sustituye** al cliente embebido.

#### Empaquetar el cliente incluido (quien genera el .deb)

Una sola vez, con Preferencias → OAuth ya rellenado en tu máquina de build:

```bash
python -m pyqorreos.core.oauth_clients install-builtin
```

Eso escribe `pyqorreos/resources/oauth_clients.builtin.local.json` (gitignored). Al generar el `.deb`, copia ese fichero a `oauth_clients.builtin.json` dentro del paquete (o a `/usr/share/pyqorreos/`). También puedes definir `PYQORREOS_OAUTH_GMAIL_CLIENT_ID` / `_CLIENT_SECRET` (y lo mismo para `OUTLOOK`) en el entorno de build.

El `refresh_token` se guarda en el llavero de forma permanente; el `access_token` se usa para conectar y se renueva automáticamente al caducar.

### Privacidad y visor

- Por defecto las **imágenes remotas** están bloqueadas; puedes mostrarlas con el botón del visor o desactivar el bloqueo en Preferencias.
- Los avisos de Chromium/WebEngine en terminal están filtrados cuando es posible; no afectan al uso normal.

### Sincronización al arrancar

- Con cuentas ya configuradas, la app **conecta y descarga correo nuevo** al abrir (carpeta activa de la última sesión, no siempre INBOX).
- Las demás cuentas se actualizan al inicio si **Sincronizar cuentas en segundo plano** está activo en Preferencias.
- La caché local permite ver la bandeja **antes** de que termine la conexión.
- La **barra de progreso** bajo la lista solo aparece cuando hay mensajes nuevos que descargar; el estado de red (conectado, sincronizando…) se muestra de forma permanente a la derecha de la barra de estado.
- La **primera** sincronización de una carpeta con más de 5000 mensajes, si aún no hay caché, descarga solo los **5000 más recientes**. La barra de estado lo indica («Mostrando los 5000 más recientes de N»). Las siguientes sincronizaciones traen el correo nuevo y actualizan leído y destacado de lo ya guardado.

### Cuando el servidor no responde

Un fallo de DNS o de red **no bloquea** la aplicación:

- Aparece un aviso en la parte superior del panel de lectura con el **host IMAP** que ha fallado y botones **Reintentar** y **Editar cuenta**.
- La lista de mensajes sigue mostrando la caché local y puedes **cambiar de carpeta** y **abrir mensajes con doble clic** si su cuerpo ya estaba descargado.
- Si el cuerpo no está en caché, el panel de lectura lo indica en lugar de quedarse en blanco.
- **Actualizar** (`F5`) reconecta y, en cuanto el servidor responde, busca correo nuevo en la carpeta que estabas viendo.
- Como la resolución DNS puede tardar mucho más que el tiempo de espera del socket IMAP, el aviso también aparece si la conexión se alarga, sin cancelar el intento en curso.

Si el problema persiste, comprueba la resolución del host desde la terminal:

```bash
getent hosts imap.tuservidor.com
```

### Traducción

- La **traducción** solo se ejecuta al pulsar «Traducir»; el texto se envía a un servicio en línea gratuito ([deep-translator](https://github.com/nidhaloff/deep-translator)).
- Configura el idioma destino en **Archivo → Preferencias → General**.
- El texto se extrae del mensaje (HTML o parte de texto plano) y se limpia de restos de maquetación antes de traducir; el resultado se muestra en modo lectura con enlaces activos.
- Asunto y cuerpo se envían juntos cuando caben en una petición. Si el mensaje es largo, las peticiones van espaciadas y, si el servicio responde que hay demasiadas, se reintenta con esperas crecientes.
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

- El árbol de la izquierda muestra **todas las cuentas configuradas**. Cada cuenta es un nodo desplegable con sus propias carpetas; la cuenta activa aparece en **negrita**.
- Al pulsar una carpeta de otra cuenta, PyQorreos **cambia a esa cuenta** y abre la carpeta. El estado de despliegue se conserva mientras trabajas.
- Las cuentas que no están activas muestran las carpetas y los totales **guardados en la caché local**, así que el árbol está completo aunque solo haya una sesión IMAP abierta.
- Si en Gmail aparece una carpeta **Mailspring** (u otra de un cliente antiguo), puedes eliminarla con clic derecho en el árbol → **Eliminar carpeta…** (las carpetas del sistema como INBOX o `[Gmail]/…` están protegidas).
- **Renombrar una carpeta** de usuario: clic derecho en el árbol → **Renombrar carpeta…**, **doble clic** sobre ella o tecla **`F2`**. Se renombra en el servidor y se actualiza la caché local (incluidas las subcarpetas). Las carpetas del sistema no se pueden renombrar.
- Puedes renombrar carpetas de **cualquier cuenta**: si la carpeta pertenece a una cuenta que no está activa, PyQorreos cambia primero a esa cuenta y abre el diálogo al conectarse.

#### Separador de carpetas del servidor

No todos los servidores anidan las carpetas igual: Gmail y Exchange usan `/` (`INBOX/Trabajo`) y Dovecot o cPanel usan `.` (`INBOX.Trabajo`). PyQorreos lee el separador de la respuesta `LIST` del servidor y lo respeta al crear, renombrar y eliminar. Por eso:

- Renombrar `INBOX.Trabajo` como «Proyectos» produce `INBOX.Proyectos`, sin sacar la carpeta de INBOX.
- El nombre nuevo no puede contener el separador del servidor; PyQorreos avisa indicando cuál es.
- En el árbol, un nivel intermedio que el servidor no lista como carpeta real solo agrupa visualmente y no se puede abrir.

### Búsqueda, destacados y borradores

- La casilla **«En el cuerpo»** activa la búsqueda dentro del texto de los mensajes usando un índice **FTS5** en `mail_cache.db`. Solo cubre los mensajes cuyo cuerpo ya está en caché (los que has abierto/descargado); el resto se puede buscar por asunto y remitente como siempre.
- Si tu instalación de SQLite no incluye FTS5, la búsqueda en el cuerpo recurre automáticamente a `LIKE` (más lenta pero equivalente).
- El filtro **«Solo destacados»** muestra los mensajes con la estrella (★). Destacar/quitar destacado: `Ctrl+D` o el menú contextual. El destacado usa el flag IMAP `\Flagged` y es independiente de la categoría «Importante».
- **Archivar** (`Ctrl+E`): mueve los mensajes a la carpeta de archivo (Archive/Archivo o `[Gmail]/All Mail`). Si no se detecta ninguna, PyQorreos ofrece crear «Archivo».
- **Autoguardado de borradores**: al redactar, el borrador se guarda cada 30 s en la carpeta Borradores reescribiendo la copia anterior (mediante UIDPLUS/APPENDUID cuando el servidor lo soporta). Al enviar el correo se elimina la copia autoguardada para no dejar borradores huérfanos.

### Bandeja del sistema

- La bandeja del sistema incluye acceso directo a **Bandeja de entrada** de la cuenta seleccionada.

---

**Ver también:** [Uso rápido](usage.md) · [Instalación](installation.md) · [Características](features.md)
