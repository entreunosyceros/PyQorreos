# Política de seguridad

## Versiones con soporte

| Versión | Soportada |
| ------- | --------- |
| 0.1.x   | ✅        |
| < 0.1   | ❌        |

## Alcance

**PyQorreos** es un cliente de correo de **escritorio** (Python + PySide6) que se conecta a servidores IMAP/SMTP y guarda datos en local. En el ámbito de seguridad nos interesa especialmente:

- **Credenciales**: contraseñas en el llavero del sistema (`keyring`), tokens OAuth y el archivo `~/.config/pyqorreos/oauth_clients.json`.
- **Contenido de correo**: ejecución de HTML/JavaScript no prevista en el visor (Qt WebEngine), enlaces maliciosos y fugas de datos al abrir URLs externas.
- **Red**: conexiones IMAP/SMTP/TLS, validación de certificados y manejo de errores de protocolo.
- **Almacenamiento local**: caché SQLite (`mail_cache.db`), archivos de configuración en `~/.config/pyqorreos/` y permisos de lectura/escritura.
- **OAuth**: flujo de autorización con callback en `127.0.0.1`, almacenamiento de `refresh_token` y renovación de `access_token`.
- **Dependencias**: vulnerabilidades conocidas en PySide6, `keyring` u otras librerías del proyecto.

**Fuera de alcance habitual:**

- Seguridad de los servidores de correo de terceros (Gmail, Outlook, etc.).
- Contenido malicioso dentro de correos que el usuario abre voluntariamente (aunque sí nos interesan fallos del visor que amplíen el impacto).
- Recomendaciones sobre qué proveedor de correo usar.

## Cómo reportar una vulnerabilidad

1. **No** abras un issue público con detalles del fallo ni pegues correos, tokens o contraseñas.
2. Usa [GitHub Security Advisories](https://github.com/entreunosyceros/PyQorreos/security/advisories/new) (**Report a vulnerability**) si tienes acceso.
3. Si no puedes usar Advisories, abre un issue con título `SECURITY (sin detalles)` y pide un canal privado; no incluyas pasos de explotación en público.

Incluye, en la medida de lo posible:

- Descripción del problema y componente afectado (`core/`, `ui/`, OAuth, visor, etc.).
- Pasos para reproducirlo.
- Impacto estimado (credenciales, datos locales, ejecución de código, red).
- Versión o commit afectado.
- Proveedor de correo y sistema operativo, si aplica.
- Sugerencia de mitigación, si la tienes.

## Qué esperar

- **Acuse de recibo** en un plazo razonable (habitualmente en pocos días).
- Evaluación del informe y, si procede, parche o mitigación en una versión posterior.
- Crédito al informante en las notas de la corrección, salvo que prefiera anonimato.

## Buenas prácticas para usuarios

- No compartas `~/.config/pyqorreos/oauth_clients.json`, el llavero del sistema ni capturas con tokens visibles.
- Usa **contraseñas de aplicación** o **OAuth2** en Gmail; no guardes la contraseña principal de tu cuenta Google.
- Mantén Python y las dependencias actualizadas (`pip install -r requirements.txt --upgrade` dentro de `.venv`).
- Clona y descarga el código solo desde el repositorio oficial: [github.com/entreunosyceros/PyQorreos](https://github.com/entreunosyceros/PyQorreos).
- En equipos compartidos, protege el directorio `~/.config/pyqorreos/` con permisos adecuados.
