# Pilares de calidad de PyQorreos

[← Índice](README.md) · [README](../README.md)

Prioridades del proyecto: **rendimiento**, **robustez** y **calidad visual** por encima de acumular funciones.

## Rendimiento

Objetivo: que una carpeta con decenas de miles de correos siga siendo usable al instante.

| Área | Estado |
|------|--------|
| Caché SQLite con WAL y lectura en segundo plano al abrir carpeta | Implementado |
| Búsqueda en SQLite (asunto/remitente) con debounce | Implementado |
| Sin recargar toda la carpeta en cada lote de sincronización | Implementado |
| Paginación solo en UI (no descarga todo el cuerpo) | Ya existía |
| Índice FTS / búsqueda en cuerpo del mensaje | Pendiente |
| Actualización incremental de caché sin reescribir carpeta entera | Pendiente |

## Robustez

Objetivo: fallos de red o servidor que no bloqueen la interfaz y den mensajes claros.

| Escenario | Estado |
|-----------|--------|
| Operaciones IMAP/SMTP en hilos (UI no se bloquea) | Ya existía |
| Timeouts de socket IMAP/SMTP | Implementado |
| Prueba de cuenta: IMAP **y** SMTP | Implementado |
| Mensajes de error legibles (contraseña, red, timeout…) | Implementado |
| Reconexión IMAP (`ensure_connected`) | Ya existía |
| Límite y aviso de adjuntos grandes al enviar | Implementado |
| Reintentos automáticos en sync/envío | Pendiente |
| Tests automatizados de escenarios de fallo | Pendiente |

## Calidad visual

Objetivo: aspecto coherente y profesional.

| Área | Estado |
|------|--------|
| Iconos y espaciado unificados en todos los diálogos | Implementado (`theme.py`) |
| Tema claro / oscuro (Preferencias → Apariencia) | Implementado |
| Hoja de estilos global (menús, tablas, barras, botones) | Implementado |
| Tema del visor HTML de correos (sigue el del mensaje) | Pendiente |

## Arranque

| Comportamiento | Estado |
|----------------|--------|
| Caché local visible al abrir (sin esperar IMAP) | Implementado |
| Descarga de correo nuevo al conectar (cuenta activa) | Implementado |
| INBOX del resto de cuentas al arrancar (sync en segundo plano) | Implementado |
| UI no bloqueada durante conexión inicial | Implementado |

---

**Ver también:** [Historial de cambios](changelog.md) · [Características](features.md) · [Configuración y notas](configuration.md)
