import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from flask import session, request, redirect, url_for, flash, abort, g, render_template
from werkzeug.security import generate_password_hash, check_password_hash

ROLE_LABELS = {
    'superadmin': 'Superadministrador',
    'admin': 'Administrador',
    'auditor': 'Auditor',
    'usuario': 'Usuario',
    'asistente': 'Asistente',
}

BASIC_ENDPOINTS = {
    'dashboard', 'listar_jardines', 'crear_jardin', 'editar_jardin', 'eliminar_jardin',
    'listar_matriculas', 'crear_matricula', 'ver_matricula', 'eliminar_matricula',
    'listar_documentos', 'subir_documento', 'ver_documento', 'eliminar_documento',
    'comunicaciones', 'ver_poster_comunicacion', 'crear_comunicacion', 'ver_comunicacion', 'radicar_comunicacion', 'devolver_comunicacion', 'reasignar_comunicacion', 'archivar_comunicacion', 'responder_comunicacion', 'descargar_adjunto_comunicacion', 'pqrs', 'ver_pqrs', 'gestionar_pqrs', 'responder_pqrs', 'descargar_adjunto_pqrs'
}
PUBLIC_ENDPOINTS = {'login', 'static', 'pqrs_publica', 'consultar_pqrs_publica'}
AUDIT_SKIP = {'static'}


def init_security_db(get_db):
    db = get_db()
    db.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre_completo TEXT NOT NULL,
        username TEXT NOT NULL UNIQUE COLLATE NOCASE,
        email TEXT UNIQUE COLLATE NOCASE,
        password_hash TEXT NOT NULL,
        rol TEXT NOT NULL CHECK (rol IN ('superadmin','admin','auditor','usuario','asistente')),
        activo INTEGER NOT NULL DEFAULT 1,
        debe_cambiar_password INTEGER NOT NULL DEFAULT 1,
        intentos_fallidos INTEGER NOT NULL DEFAULT 0,
        bloqueado_hasta TEXT,
        ultimo_acceso TEXT,
        creado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        actualizado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        creado_por INTEGER,
        FOREIGN KEY (creado_por) REFERENCES usuarios(id)
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS auditoria (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        username TEXT,
        rol TEXT,
        fecha_hora TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        ip TEXT,
        metodo TEXT,
        endpoint TEXT,
        ruta TEXT,
        modulo TEXT,
        accion TEXT,
        detalle TEXT,
        resultado TEXT,
        user_agent TEXT,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
    )''')
    db.execute('CREATE INDEX IF NOT EXISTS idx_auditoria_fecha ON auditoria(fecha_hora)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_auditoria_usuario ON auditoria(usuario_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_auditoria_modulo ON auditoria(modulo)')
    count = db.execute("SELECT COUNT(*) AS n FROM usuarios WHERE rol='superadmin'").fetchone()['n']
    if count == 0:
        username = os.getenv('INITIAL_ADMIN_USER', 'superadmin')
        password = os.getenv('INITIAL_ADMIN_PASSWORD', 'Cambiar123!')
        db.execute('''INSERT INTO usuarios
            (nombre_completo, username, email, password_hash, rol, activo, debe_cambiar_password)
            VALUES (?, ?, ?, ?, 'superadmin', 1, 1)''',
            ('Superadministrador del sistema', username, 'admin@nubi.local', generate_password_hash(password)))
    db.commit(); db.close()


def current_user():
    return session.get('user')


def role_is(*roles):
    user = current_user()
    return bool(user and user.get('rol') in roles)


def log_audit(get_db, accion, detalle='', resultado='Exitoso', user=None, endpoint=None, modulo=None):
    user = user or current_user() or {}
    try:
        db = get_db()
        db.execute('''INSERT INTO auditoria
            (usuario_id, username, rol, fecha_hora, ip, metodo, endpoint, ruta, modulo, accion, detalle, resultado, user_agent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
            user.get('id'), user.get('username'), user.get('rol'), datetime.now().isoformat(timespec='seconds'),
            request.headers.get('X-Forwarded-For', request.remote_addr), request.method,
            endpoint or request.endpoint, request.path, modulo or module_from_endpoint(endpoint or request.endpoint),
            accion, detalle[:1000], resultado, request.user_agent.string[:500]
        ))
        db.commit(); db.close()
    except Exception:
        pass


def module_from_endpoint(endpoint):
    endpoint = endpoint or ''
    if 'jardin' in endpoint: return 'Jardines'
    if 'matricula' in endpoint: return 'Matrículas'
    if 'personal' in endpoint: return 'Personal'
    if 'documento' in endpoint: return 'Documentos'
    if 'usuario' in endpoint: return 'Usuarios'
    if 'auditoria' in endpoint: return 'Auditoría'
    if endpoint == 'dashboard': return 'Dashboard'
    if endpoint == 'login' or endpoint == 'logout': return 'Autenticación'
    if endpoint and 'comunicacion' in endpoint: return 'Comunicaciones'
    if endpoint and 'pqrs' in endpoint: return 'PQRS'
    return 'Sistema'


def action_from_request():
    if request.endpoint == 'login': return 'Inicio de sesión'
    if request.endpoint == 'logout': return 'Cierre de sesión'
    if request.method == 'GET': return 'Consulta'
    if request.method == 'POST': return 'Creación/actualización'
    if request.method == 'DELETE': return 'Eliminación'
    return request.method


def install_security(app, get_db):
    app.permanent_session_lifetime = timedelta(minutes=int(os.getenv('SESSION_MINUTES', '60')))
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.getenv('SESSION_COOKIE_SECURE', '0') == '1'
    )

    @app.context_processor
    def security_context():
        return {'current_user': current_user(), 'role_is': role_is, 'ROLE_LABELS': ROLE_LABELS}

    @app.before_request
    def enforce_access():
        endpoint = request.endpoint
        if endpoint is None or endpoint in PUBLIC_ENDPOINTS:
            return None
        user = current_user()
        if not user:
            flash('Debes iniciar sesión para continuar.', 'warning')
            return redirect(url_for('login', next=request.full_path))
        session.permanent = True
        if user.get('debe_cambiar_password') and endpoint not in {'cambiar_password', 'logout'}:
            return redirect(url_for('cambiar_password'))
        role = user.get('rol')
        if role == 'asistente' and endpoint not in BASIC_ENDPOINTS and endpoint not in {'cambiar_password','logout'}:
            abort(403)
        if role == 'usuario' and endpoint in {'usuarios', 'crear_usuario', 'editar_usuario', 'auditoria', 'ver_auditoria'}:
            abort(403)
        if role == 'auditor' and request.method not in {'GET', 'HEAD', 'OPTIONS'} and endpoint not in {'logout','cambiar_password'}:
            abort(403)
        if role == 'admin' and endpoint in {'crear_usuario','editar_usuario'}:
            target_role = request.form.get('rol')
            if target_role in {'auditor','superadmin'}:
                abort(403)
        return None

    @app.after_request
    def audit_response(response):
        if request.endpoint not in AUDIT_SKIP and request.endpoint not in {'login'} and current_user():
            log_audit(get_db, action_from_request(), f'HTTP {response.status_code}',
                      'Exitoso' if response.status_code < 400 else 'Fallido')
        return response

    @app.errorhandler(403)
    def forbidden(error):
        log_audit(get_db, 'Acceso denegado', 'Intento de acceso sin permisos', 'Fallido')
        return render_template('auth/403.html'), 403
