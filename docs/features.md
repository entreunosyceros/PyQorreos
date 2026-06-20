# Características

[← Índice](README.md) · [README](../README.md)

Resumen detallado de lo que ofrece PyQorreos. Para empezar a usarlo, consulta [Uso rápido](usage.md).

<div align="center">
<img width="640" height="797" alt="preferencias-pyqcorreos" src="https://github.com/user-attachments/assets/38dec139-a4c5-49ab-94d5-da9f6372878e" />
</div>

## Cuentas y conexión

- Varias cuentas de correo (Gmail, Outlook, Hotmail, MSN, Live, AOL, Yahoo, **hosting / cPanel** o servidor personalizado)
- **Presets de proveedor** con servidores IMAP/SMTP preconfigurados; al escribir el correo en una cuenta nueva, se **detecta el preset** según el dominio (`@hotmail.*`, `@msn.com`, `@aol.*`, etc.)
- Selector rápido de cuenta activa y gestor de cuentas (**añadir, editar, eliminar**)
- Conexión IMAP/SMTP con **SSL/TLS** o **STARTTLS** configurable por cuenta (puertos 993/143, 465/587)
- Preset **Hosting / cPanel (Webempresa, etc.)** para correo en dominio propio (`mail.tudominio.com`)
- Contraseñas en el llavero del sistema (`keyring`); opción **mostrar contraseña** al configurar la cuenta
- Avisos contextuales al configurar **Gmail**, **AOL** y **Microsoft** (contraseña de aplicación u OAuth)
- Firma de correo configurable por cuenta
- OAuth2 integrado para **Gmail** y **Microsoft** (Outlook, Hotmail, MSN, Live) — inicio de sesión en navegador + renovación automática de tokens
- Alternativa: contraseña de aplicación según el proveedor
- Bandeja del sistema: la app sigue activa al cerrar la ventana; **Archivo → Salir** cierra por completo

### Presets incluidos

| Proveedor | Dominios típicos | IMAP | SMTP |
|-----------|------------------|------|------|
| Gmail | `@gmail.com`, `@googlemail.com` | `imap.gmail.com:993` | `smtp.gmail.com:587` |
| Outlook / Hotmail / MSN | `@outlook.*`, `@hotmail.*`, `@live.*`, `@msn.com` | `outlook.office365.com:993` | `smtp.office365.com:587` |
| Yahoo | `@yahoo.*`, `@ymail.com` | `imap.mail.yahoo.com:993` | `smtp.mail.yahoo.com:587` |
| AOL | `@aol.*` | `imap.aol.com:993` | `smtp.aol.com:587` |
| Hosting / cPanel | dominio propio | `mail.tudominio.com:993` | `mail.tudominio.com:465/587` |

## Bandeja y sincronización

- Vista de tres paneles: carpetas | lista de mensajes | lectura
- **Al iniciar la aplicación**: muestra la caché local de INBOX al instante y descarga cabeceras nuevas del servidor en segundo plano
- Árbol de carpetas con iconos SVG y contador de no leídos
- Crear carpetas y subcarpetas en el servidor IMAP; eliminar carpetas de usuario (p. ej. restos de otros clientes como `Mailspring`)
- Sincronización incremental (solo descarga mensajes nuevos)
- Sincronización en segundo plano (IMAP IDLE + polling) configurable en preferencias (por defecto cada 15 minutos)
- Caché local SQLite para abrir la bandeja al instante
- Paginación configurable y barra de progreso de sincronización
- Indicador de cuota de almacenamiento IMAP bajo el árbol de carpetas
- Clasificación automática: normal, importante, spam (con filtro y colores)
- Reglas de remitente al marcar spam o importante (aprendizaje persistente)
- Búsqueda por asunto o remitente, filtro «Solo no leídos» y ordenación
- Vista de conversaciones (agrupación por hilos, opcional en preferencias)
- Notificaciones de correo nuevo en la bandeja del sistema (remitente y asunto)

## Lectura de mensajes

- **Doble clic** (o `Enter`) en un mensaje para abrirlo; un solo clic solo muestra vista previa (asunto y remitente)
- Visor HTML con Qt WebEngine (maquetado fiel al correo original)
- Modos de vista: HTML original, modo lectura y texto plano
- Imágenes embebidas (cid); imágenes remotas bloqueables por privacidad
- Botón **«Mostrar imágenes remotas»** bajo demanda (descarga en segundo plano, incluso si el HTML en caché estaba bloqueado)
- **Traducción** bajo demanda al idioma configurado en Preferencias (botón «Traducir» / «Ver original»); caché por mensaje; enlaces clicables y menú «Abrir en el navegador»
- Extracción de texto para traducir desde HTML o texto plano, filtrando ruido típico de newsletters (CSS suelto, viñetas vacías)
- Decodificación de charsets MIME habituales en hosting (`unknown-8bit`, `x-unknown`, etc.)
- Advertencia anti-phishing al pasar el ratón sobre enlaces sospechosos; la URL se muestra en la barra de estado
- List-Unsubscribe: botón y menú contextual para darse de baja de listas de correo
- Adjuntos: listar, abrir y guardar desde el panel del lector
- Caché de cuerpos: los mensajes ya abiertos se muestran sin volver a descargar
- Precarga del siguiente mensaje de la lista

## Acciones sobre el correo

- Responder, responder a todos, reenviar y eliminar
- **Eliminación en lote** optimizada (IMAP y caché SQLite por lotes) con aviso en barra de estado y barra de progreso al borrar varios mensajes
- Selección múltiple: marcar, eliminar o mover varios correos a la vez
- Mover mensajes entre carpetas (menú contextual o botón «Mover a…»)
- Vaciar papelera desde el menú contextual de la carpeta
- Exportar mensaje a `.eml` o carpeta completa a `.mbox`
- Marcar como leído / no leído
- Marcar categoría (importante, spam, normal) desde barra, menú o clic derecho
- Menú contextual en el listado (abrir, copiar remitente, actualizar carpeta…)
- Atajos: `Ctrl+R`, `Ctrl+Shift+R`, `Ctrl+L`, `Supr`, `F5`, `Enter` (abrir mensaje) — [tabla completa](keyboard-shortcuts.md)

## Redacción
<div align="center">
<img width="818" height="655" alt="redactar-correo" src="https://github.com/user-attachments/assets/133d2766-2950-4b74-9cac-378c5135b511" />
</div>


- Editor enriquecido: negrita, cursiva, subrayado, listas, color, enlaces e imágenes
- **Plantillas** de texto rápido (pestaña «Plantillas» en Preferencias; menú en el editor al redactar)
- Aviso si el cuerpo menciona adjuntos pero no hay ninguno seleccionado
- Adjuntar archivos al enviar
- Envío HTML + texto plano por SMTP
- Borradores precargados al responder o reenviar (cita HTML del mensaje original)
- Guardar borrador en la carpeta Drafts del servidor
- Firma insertada automáticamente al redactar

## Rendimiento y estabilidad

- Operaciones de red en hilos secundarios (la interfaz no se bloquea)
- Caché SQLite en modo **WAL** con `busy_timeout` para lecturas concurrentes durante la sincronización
- Búsqueda en base de datos con debounce
- Conexión IMAP dedicada por mensaje y reintentos ante errores de protocolo
- Reconexión IMAP segura al usar varias cuentas o hilos de lectura en paralelo
- Limpieza de adjuntos temporales al cerrar la aplicación
- Cabeceras limitadas en carpetas muy grandes (>5000 mensajes) en la primera sync
- Timeouts IMAP/SMTP y mensajes de error claros — ver [Pilares de calidad](quality-pillars.md)

## Apariencia

- **Tema claro u oscuro** (Archivo → Preferencias → Apariencia)
- Ventana principal maximizada en el **monitor principal** al arrancar
- Estilos unificados en tablas, botones, menús y diálogos (`pyqorreos/ui/theme.py`)

---

**Ver también:** [Instalación](installation.md) · [Uso rápido](usage.md) · [Configuración y notas](configuration.md)
