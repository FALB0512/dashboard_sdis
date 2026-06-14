# Acceso y roles incorporados

## Primer ingreso

- URL: `http://127.0.0.1:5000/login`
- Usuario inicial: `superadmin`
- Contraseña temporal: `Cambiar123!`

El sistema obliga a cambiarla en el primer acceso.

## Roles

- **Superadministrador:** acceso total y creación de cualquier rol.
- **Administrador:** acceso total, gestión de usuarios y auditoría; no puede crear ni modificar auditores o superadministradores.
- **Auditor:** consulta todos los módulos y la auditoría; no puede modificar información.
- **Usuario:** acceso operativo a los módulos, sin administración de usuarios ni auditoría.
- **Asistente:** Dashboard, Jardines, Matrículas, Comunicaciones y PQRS.

## Puesta en marcha

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Configuración recomendada

Copia `.env.example` como referencia y define las variables en Windows antes de ejecutar. Para producción usa una `SECRET_KEY` larga, configura HTTPS y establece `SESSION_COOKIE_SECURE=1`.

Las credenciales de correo ya no están escritas dentro de `app.py`. Cambia o revoca la contraseña de aplicación que estuvo incluida en la versión anterior del proyecto.
