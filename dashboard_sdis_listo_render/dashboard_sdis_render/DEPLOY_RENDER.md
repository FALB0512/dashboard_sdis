# Despliegue en Render

## Configuración
- Root Directory: dejar vacío si esta carpeta es la raíz del repositorio.
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app --workers 1 --threads 4 --timeout 120`

## Variables obligatorias
- `SECRET_KEY`: clave aleatoria larga.
- `INITIAL_ADMIN_USER`: usuario administrador inicial.
- `INITIAL_ADMIN_PASSWORD`: contraseña segura inicial.
- `SESSION_COOKIE_SECURE`: `1`.

## Variables de correo (opcionales)
- `MAIL_USERNAME`
- `MAIL_PASSWORD`
- `MAIL_DEFAULT_SENDER`

## Advertencia
Este proyecto usa SQLite (`sdis_dashboard.db`) y guarda archivos en `uploads/`.
En una instancia gratuita de Render, los cambios locales pueden perderse al reiniciar o redesplegar.
Usar este despliegue para demostración. Para operación real, migrar la base de datos a PostgreSQL y los adjuntos a almacenamiento externo.
