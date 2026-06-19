# Historial de cambios

[← Índice](README.md) · [README](../README.md)

Resumen de las mejoras recientes de PyQorreos (no versionado por release aún).

---

## Arranque y sincronización

- **Al abrir la aplicación** se muestra de inmediato la caché local de INBOX (sin esperar a IMAP).
- En paralelo se **conecta al servidor** y se **descargan cabeceras nuevas** de la carpeta activa.
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
| `pyqorreos/ui/theme.py` | Tema claro/oscuro y estilos globales |
| `pyqorreos/core/network_errors.py` | Mensajes de error legibles |
| `pyqorreos/core/translate.py` | Traducción y HTML de lectura |
| `pyqorreos/core/link_safety.py` | Anti-phishing y URLs sueltas |
| `docs/` | Documentación segmentada |

---

**Ver también:** [Características](features.md) · [Pilares de calidad](quality-pillars.md) · [Uso rápido](usage.md)
