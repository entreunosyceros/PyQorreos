# Guía de contribución

¡Gracias por interesarte en **[PyQorreos](https://github.com/entreunosyceros/PyQorreos)**! Este proyecto es un gestor de correo con **Python** y **PySide6**, publicado bajo [GPL-3.0](LICENSE). Cualquier mejora bien planteada es bienvenida.

## Antes de empezar

- Lee el [README](README.md) y el [índice de documentación](docs/README.md) para entender el alcance del proyecto.
- Revisa [issues abiertas](https://github.com/entreunosyceros/PyQorreos/issues) por si alguien ya trabaja en lo mismo.
- Para dudas de comportamiento en la comunidad, consulta el [Código de conducta](CODE_OF_CONDUCT.md).

## Cómo puedes ayudar

- **Reportar errores** con pasos claros para reproducirlos (proveedor de correo, versión de Python, salida de terminal).
- **Proponer mejoras** explicando el problema que resuelven.
- **Enviar pull requests** con cambios acotados y probados.
- **Mejorar documentación** (README, `docs/`, comentarios en el código).
- **Probar OAuth, sync o el visor** en distintos proveedores (Gmail, Outlook, IMAP propio).

## Entorno de desarrollo

Requisitos: **Python 3.10+**, entorno gráfico con soporte para Qt y, para el visor HTML, las dependencias de **Qt WebEngine**.

```bash
git clone https://github.com/entreunosyceros/PyQorreos.git
cd PyQorreos
python run_app.py
```

`run_app.py` crea el entorno virtual (`.venv`), instala dependencias desde `requirements.txt` y arranca la aplicación.

### Arranque manual (opcional)

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run_app.py
```

### OAuth (Gmail / Outlook)

Si pruebas autenticación OAuth, configura las credenciales en **Archivo → Preferencias → OAuth** (o edita `~/.config/pyqorreos/oauth_clients.json`). Consulta [docs/configuration.md](docs/configuration.md).

## Estructura del código

| Ruta | Contenido |
|------|-----------|
| `pyqorreos/core/` | Cuentas, IMAP/SMTP, caché SQLite, OAuth, clasificación |
| `pyqorreos/ui/` | Ventana principal, diálogos, workers Qt |
| `docs/` | Documentación de usuario y del proyecto |
| `run_app.py` | Lanzador recomendado |

Más detalle en [docs/project-structure.md](docs/project-structure.md).

## Estilo de código

- Sigue el estilo del código existente (nombres, imports, nivel de comentarios).
- Cambios **mínimos y enfocados**: no mezcles varias funcionalidades en un mismo PR.
- Los textos visibles para el usuario van en **español**.
- No incluyas secretos, `oauth_clients.json`, rutas personales ni correos reales en los commits.
- Las operaciones de red (IMAP/SMTP) deben ejecutarse en **workers** (`QThread`), no en el hilo de la interfaz.

## Pull requests

1. Crea una rama descriptiva desde `main` (por ejemplo `fix/oauth-refresh` o `feat/export-mbox`).
2. Describe **qué** cambias y **por qué**.
3. Indica cómo lo has probado (pasos manuales, proveedor de correo usado, capturas si aplica).
4. Si tocas sincronización, caché o cuentas, menciona el impacto en datos en `~/.config/pyqorreos/`.
5. Actualiza `docs/` o el README solo si el cambio lo requiere.

Usa la [plantilla de pull request](.github/pull_request_template.md) al abrir el PR.

## Reportar problemas de seguridad

No abras issues públicas para vulnerabilidades. Sigue la [política de seguridad](SECURITY.md).

## Licencia

Al contribuir, aceptas que tu aportación se publique bajo la misma licencia del proyecto: [GPL-3.0](LICENSE).
