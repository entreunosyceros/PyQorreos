# Historial de cambios

[← Índice](README.md) · [README](../README.md)

Resumen de las mejoras recientes de PyQorreos (no versionado por release aún).

---

## Alta de Gmail

- Una cuenta Gmail nueva pide el correo y **Identificarse con Google**. El Client ID pegado una vez queda en el cliente incluido del programa.
- Documentado el aviso de Google «esta aplicación no está verificada»: significa que PyQorreos no está certificada por Google y, en modo prueba, se continúa con **Avanzado**.

## Versión 0.1.1

- **Ayuda → Acerca de…** muestra la versión **0.1.1**.

## Ventanas, traducción y Acerca de (reciente)

- Las barras y los formularios se reorganizan al estrechar o restaurar la ventana: los botones pasan a la línea siguiente y, si el panel no da más alto, el contenido se desplaza en lugar de taparse.
- La traducción de un correo junta asunto y cuerpo en una petición cuando caben, espacia los trozos largos y reintenta si el servicio limita las peticiones.
- **Ayuda → Acerca de…** muestra `logo.png` y una lista de funcionalidades al día (cuentas, búsqueda, OpenPGP, agenda, documentación y ventanas adaptables).

## Correo: autenticación, carpetas, envío y cuenta (reciente)

- **OAuth IMAP/SMTP**: la cadena XOAUTH2 se entrega en claro y las bibliotecas la codifican una sola vez. Identificarse con Google o Microsoft vuelve a servir para descargar y enviar.
- El callback local ignora peticiones sin código (por ejemplo el favicon) para no perder la autorización. La ayuda muestra la URI real `http://127.0.0.1:<puerto>/`. El JSON del Client ID queda en modo `0600`.
- **Carpetas con espacio o acentos**: el nombre se lee entre comillas (`[Gmail]/All Mail`, `INBOX.Facturas 2024`) y, si el servidor no acepta UTF-8, se usa UTF-7 modificado.
- **Envío**: el sobre SMTP usa las direcciones reales (nombres con coma y listas con punto y coma). Un adjunto que ya no está en disco detiene el envío. Al redactar se ve «Se enviará a…».
- **Buzón grande**: la primera descarga sin caché trae los 5000 mensajes más recientes, no los más antiguos, y lo dice en la barra de estado. Los mensajes ya en caché actualizan leído y destacado.
- Borrar o mover ya no hace `EXPUNGE` de todos los mensajes marcados como eliminados: con UIDPLUS solo expulsa los elegidos.
- IMAP y SMTP guardan su seguridad por separado. El diálogo de cuenta agrupa identidad, recepción y envío, y resume el modo en una línea.

## OAuth embebido (reciente)

- **Inicio de sesión como Thunderbird**: si el paquete incluye el Client ID de PyQorreos, Gmail y Microsoft se autorizan con «Identificarse con Google/Microsoft» sin configurar Google Cloud ni Azure.
- Orden de resolución: Preferencias del usuario → variables de entorno → cliente embebido (`oauth_clients.builtin.json` / `.local` / `/usr/share/pyqorreos/`).
- Preferencias → OAuth muestra el origen activo y deja los campos como override opcional.
- Herramienta para el empaquetador: `python -m pyqorreos.core.oauth_clients install-builtin`.

## Árbol multicuenta y carpetas por servidor (reciente)

- **Todas las cuentas en el árbol**: cada cuenta configurada es un nodo raíz desplegable con sus carpetas; la activa va en negrita. Pulsar una carpeta de otra cuenta cambia a esa cuenta y la abre.
- Las cuentas inactivas se pintan desde la **caché local** (carpetas y totales), sin abrir una sesión IMAP por cuenta, y el despliegue elegido se conserva entre repintados.
- **Renombrar carpetas de cualquier cuenta**: si la carpeta no es de la cuenta activa, PyQorreos cambia a ella y abre el diálogo al conectarse.
- **Separador IMAP real**: se lee de la respuesta `LIST` y se respeta al construir el árbol y al crear, renombrar o eliminar. Antes todo asumía `/`, así que en servidores Dovecot/cPanel las subcarpetas salían planas y renombrar `INBOX.Trabajo` sacaba la carpeta fuera de `INBOX`.
- Las carpetas del sistema con nombres tipo `INBOX.Drafts` o `INBOX.Trash` quedan protegidas frente a renombrado y borrado.
- El diálogo de renombrado ya no propone el nombre en minúsculas.
- Un nivel intermedio que el servidor no lista como carpeta real solo agrupa visualmente y ya no se puede pulsar (antes daba error al abrirlo).

## Robustez de OpenPGP (reciente)

- Si GnuPG está instalado pero no se puede inicializar (permisos del llavero, `gpg-agent` caído…), los errores dejan de mostrarse **vacíos**: se indica la causa concreta.
- Importar una clave informa del motivo real cuando falla (archivo ilegible, vacío o rechazado por GnuPG) en lugar de un mensaje genérico.
- Listar claves públicas o privadas ya no puede propagar una excepción de `gpg` a la interfaz.

## Modo sin conexión y rendimiento de la lista (reciente)

- **Leer correo sin conexión**: el doble clic (y `Intro`) abre el mensaje desde la caché local aunque la sesión IMAP haya fallado; antes no ocurría nada. Si el cuerpo no está descargado, el panel de lectura lo explica en vez de quedarse en blanco.
- **Navegación entre carpetas sin conexión**: al pulsar una carpeta se carga su contenido guardado sin intentar sincronizar.
- **Actualizar (`F5`) reconecta**: si la sesión IMAP se había perdido, vuelve a conectar y busca correo nuevo en la carpeta activa en cuanto responde el servidor. Pulsarlo durante una conexión en curso ya no reinicia el intento.
- Aviso **no bloqueante** cuando el servidor tarda en responder, indicando el host IMAP afectado; la resolución DNS puede tardar más que el tiempo de espera del socket, así que el aviso no cancela el intento.
- Listado más rápido: la fuente en negrita y los pinceles de color se calculan una sola vez por repintado, los contadores de categoría se obtienen en una sola pasada y cambiar de página ya no recalcula el filtro dos veces.
- Corregida la variable de entorno `QSG_RHI_BACKEND=software` (valor inexistente en Qt) por `QT_QUICK_BACKEND=software`, que sí fuerza el renderizado por software.

## Documentación integrada (reciente)

- Nuevo visor **Ayuda → Documentación** (`F1`): muestra el README y todas las guías de `docs/` dentro de la app, con índice navegable, navegación por enlaces internos, botón **Atrás** y búsqueda en la página. Ventana no modal y botón **Ver en GitHub**. El paquete `.deb` ahora incluye la carpeta `docs/`.

## Búsqueda, destacados, archivar y borradores (reciente)

- **Búsqueda en el cuerpo** con índice **FTS5** (casilla «En el cuerpo»): busca dentro del texto de los mensajes ya descargados, con coincidencia por prefijo y sin acentos; recurre a `LIKE` si el motor SQLite no incluye FTS5.
- **Destacados** (★): destacar/quitar destacado con `Ctrl+D` o el menú contextual; estrella en el listado y filtro **«Solo destacados»**. El destacado (`\Flagged`) es ahora independiente de la categoría «Importante».
- **Archivar** mensajes con `Ctrl+E` o el menú contextual: mueve a la carpeta de archivo (Archive/Archivo/[Gmail]/All Mail) y, si no existe, ofrece crear «Archivo».
- **Marcar toda la carpeta como leída** desde el menú contextual de la carpeta.
- **Autoguardado de borradores**: mientras redactas, el borrador se guarda solo cada 30 s reescribiendo la copia anterior (UIDPLUS) en lugar de acumular copias; al enviar se elimina la copia autoguardada.

## Gestión de carpetas y legibilidad (reciente)

- **Renombrar carpetas** de usuario desde el árbol: menú contextual «Renombrar carpeta…», **doble clic** o tecla **`F2`**; las carpetas del sistema están protegidas y se renombran también las subcarpetas en cascada (servidor y caché local).
- **Color de texto y de fondo** en el editor de redacción.
- **Contraste según el tema**: fuente clara en tema oscuro y oscura en tema claro, tanto al leer correos como al redactarlos.
- El número junto a cada carpeta del árbol muestra el **total de mensajes**, coherente con el contador inferior de la lista; correcto **por cuenta** al cambiar entre cuentas.

## Corrector ortográfico y empaquetado .deb (reciente)

- **Corrector ortográfico** al redactar: subrayado en tiempo real y sugerencias con clic derecho; español, inglés o ambos (`pyspellchecker`).
- **Paquete `.deb`** para Debian/Ubuntu: instalación con `apt`, lanzador `pyqorreos` y acceso directo en el menú; el venv se crea en el primer arranque en `~/.local/share/pyqorreos/.venv`.
- Script `scripts/build-deb.sh` para generar el paquete desde el código fuente.
- Documentación de instalación, actualización y desinstalación del `.deb` en [Instalación](installation.md#paquete-debian-deb).

## Consistencia funcional (reciente)

- **OpenPGP opcional** (GnuPG): cifrar/firmar al enviar, descifrar/verificar al leer; gestión de claves en Herramientas.
- **Agenda de contactos** local: guardar y recuperar direcciones habituales sin penalizar sync ni arranque.
- **Estado de conexión** visible de forma permanente en la barra de estado.
- **Última carpeta** por cuenta recordada entre sesiones.
- Búsqueda unificada con vista de hilos; opción de **buscar en todas las carpetas**.
- **Borradores editables** desde la carpeta Borradores; tras enviar, opción de ver Enviados.
- Pestaña **Clasificación** en Preferencias para gestionar reglas aprendidas.
- **Clic en notificación** de bandeja del sistema para abrir el mensaje o carpeta.
- Atajos `Ctrl+U`, `Ctrl+Shift+U` y `Ctrl+Shift+M` en la lista de mensajes.
- Estados vacíos en la lista cuando no hay correos o no hay coincidencias.
- **Reintentos** ante fallos transitorios de red en conexión, sincronización y envío.
- **Tests** unitarios en `tests/` (retry, caché, carpetas, errores de red, composición).
- **Barra de progreso de sincronización**: solo visible al descargar mensajes nuevos; se oculta al terminar (corrección de barra siempre activa).

## Proveedores, rendimiento y pulido (reciente)

- **Acuse de recibo** opcional al redactar (solicitud MDN al enviar); preferencia por defecto en General → Redacción.
- Aviso y envío de acuse cuando un mensaje recibido lo solicita (`Disposition-Notification-To`, etc.).
- Presets y autodetección para **AOL**, **Hotmail**, **MSN** y **Live** (Microsoft OAuth compartido con Outlook).
- **Eliminación en lote** más rápida (IMAP `UID STORE` por lotes + caché SQLite en una transacción) con feedback visual.
- Caché SQLite: **`busy_timeout`** para evitar errores `database is locked` durante sync y lectura simultánea.
- Limpieza de **adjuntos temporales** al cerrar la aplicación.
- `.gitignore` ampliado: `oauth_clients.json`, `*.eml`, `*.mbox`.

## Hosting, lectura y traducción

- Preset **Hosting / cPanel (Webempresa, etc.)** con IMAP/SMTP **SSL/TLS** y **STARTTLS** configurables.
- Corrección de charsets MIME **`unknown-8bit`** y similares al descargar mensajes (`email_charset.py`).
- **Imágenes remotas**: el botón «Mostrar imágenes remotas» restaura URLs bloqueadas en HTML y CSS aunque el cuerpo esté en caché.
- **Traducción**: extracción de texto mejorada desde HTML; filtrado de ruido de newsletters (`96`, viñetas vacías, CSS suelto); elección inteligente entre parte texto y HTML; traducción fiable al cambiar de mensaje.
- **Varias cuentas**: reconexión IMAP al usar hilos de lectura/sincronización en paralelo.
- Gestor de cuentas: **editar** cuenta existente; **mostrar contraseña** en el diálogo de alta/edición.
- Cierre limpio con **Archivo → Salir** o `Ctrl+C` en terminal; ventana maximizada en el monitor principal al arrancar.

## Arranque y sincronización

- **Al abrir** se muestra de inmediato la caché local y el árbol de carpetas (sin esperar a IMAP).
- Con cuentas ya configuradas, la app **conecta y descarga correo nuevo** al abrir (carpeta activa de la última sesión).
- Si la sincronización en segundo plano está activa (Preferencias → General), el **INBOX del resto de cuentas** también se actualiza al arrancar.
- La ventana **no se bloquea** durante la conexión inicial: puedes ver la caché mientras llega el correo nuevo.

## Rendimiento

- Caché SQLite en modo **WAL** y lectura de carpetas en **hilo secundario** (`LoadFolderWorker`).
- **Búsqueda en SQLite** (asunto/remitente) con espera de 250 ms entre pulsaciones (debounce).
- Durante la sincronización, los lotes nuevos se **fusionan en memoria** sin releer toda la carpeta de la base de datos.
- Método `query_summaries()` en `mail_cache.py` para filtrar y ordenar en SQL.

## Robustez

- **Timeouts** de socket: IMAP 60 s, SMTP 120 s.
- **Prueba de cuenta** valida IMAP **y** SMTP (antes solo IMAP).
- Mensajes de error legibles en `network_errors.py` (contraseña, red, timeout, SSL…).
- **Límites de adjuntos** al enviar: 25 MB por archivo, 50 MB total; aviso si superan 10 MB.
- Errores de workers traducidos con `friendly_mail_error()`.

## Interfaz y tema

- **Tema claro / oscuro** en Archivo → Preferencias → Apariencia.
- Estilos centralizados en `pyqorreos/ui/theme.py` (botones por rol, etiquetas de ayuda, tablas, menús).
- Diálogos unificados: redactar, preferencias, cuentas, acerca de, visor y editor.

## Lectura y traducción

- **Doble clic** (o `Enter`) para abrir un mensaje; un clic solo muestra vista previa.
- **Traducción** bajo demanda con maquetado de lectura (no texto plano suelto).
- **Enlaces clicables** en la vista traducida; clic derecho → «Abrir enlace en el navegador».
- Scroll automático **arriba** al mostrar traducción.
- Normalización de texto de newsletters para evitar huecos y scroll excesivo.

## Carpetas y cuentas

- **Eliminar carpetas** de usuario en el servidor (clic derecho en el árbol); carpetas del sistema protegidas.
- **Aviso Gmail** en el diálogo de cuenta: contraseña de aplicación y enlaces a Google.
- Corrección: clic derecho en barra de menús o marco ya no cierra la aplicación.
- Preferencias en menú **Archivo** (antes en Cuenta).

## Documentación

- README principal acortado con enlaces a `docs/`.
- Guías segmentadas: características, instalación, uso, atajos, estructura, configuración, pilares de calidad.

---

## Archivos nuevos o relevantes

| Archivo | Función |
|---------|---------|
| `tests/` | Pruebas unitarias (`pytest`) |
| `pyqorreos/core/address_book.py` | Agenda de contactos en JSON (carga diferida) |
| `pyqorreos/ui/address_book_dialog.py` | Gestión y selección de contactos |
| `pyqorreos/ui/classification_rules_widget.py` | Editor de reglas importante/spam en Preferencias |
| `pyqorreos/ui/theme.py` | Tema claro/oscuro y estilos globales |
| `pyqorreos/core/network_errors.py` | Mensajes de error legibles |
| `pyqorreos/core/email_charset.py` | Normalización de charsets MIME (`unknown-8bit`, etc.) |
| `pyqorreos/core/mail_cache.py` | Caché SQLite (WAL, `busy_timeout`, `remove_uids` en lote) |
| `pyqorreos/core/account.py` | Presets AOL, Microsoft (Hotmail/MSN), autodetección por dominio |
| `pyqorreos/core/translate.py` | Traducción y HTML de lectura |
| `pyqorreos/core/link_safety.py` | Anti-phishing y URLs sueltas |
| `docs/` | Documentación segmentada |

---

**Ver también:** [Características](features.md) · [Pilares de calidad](quality-pillars.md) · [Uso rápido](usage.md)
