from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, session, abort
from flask_mail import Mail, Message  # <-- NUEVA IMPORTACIÓN
from database import get_db, init_db
import sqlite3
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from auth import init_security_db, install_security, log_audit, ROLE_LABELS, current_user, role_is

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'CAMBIA-ESTA-CLAVE-EN-PRODUCCION')

# Configuración de archivos
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ========== CONFIGURACIÓN DE CORREO ==========
# Para pruebas con Gmail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', app.config['MAIL_USERNAME'])

mail = Mail(app)

# Configuración de archivos (lo que ya tenías)
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def enviar_correo_matricula(destinatario, nombre_nino, nombre_jardin, fecha_matricula, acudiente_nombre):
    """Envía un correo de confirmación de matrícula al acudiente"""
    try:
        asunto = f"✅ Confirmación de Matrícula - Jardín Infantil {nombre_jardin}"
        
        cuerpo = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f8f9fa; padding: 20px; border-radius: 0 0 10px 10px; }}
                .info {{ margin: 15px 0; padding: 10px; background: white; border-radius: 8px; }}
                .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>🎉 ¡Matrícula Confirmada! 🎉</h2>
                </div>
                <div class="content">
                    <p>Estimado/a <strong>{acudiente_nombre}</strong>,</p>
                    
                    <p>Nos complace informarle que la matrícula de <strong>{nombre_nino}</strong> ha sido <strong>registrada exitosamente</strong>.</p>
                    
                    <div class="info">
                        <h3>📋 Detalles de la Matrícula:</h3>
                        <p><strong>🏫 Jardín Infantil:</strong> {nombre_jardin}</p>
                        <p><strong>📅 Fecha de Matrícula:</strong> {fecha_matricula}</p>
                        <p><strong>👶 Nombre del Niño(a):</strong> {nombre_nino}</p>
                    </div>
                    
                    <div class="info">
                        <h3>📌 Próximos Pasos:</h3>
                        <ul>
                            <li>✅ Documentos requeridos: Registro Civil, Carnet de Vacunación</li>
                            <li>✅ Revisar el correo para información adicional</li>
                            <li>✅ Asistir a la reunión de padres</li>
                        </ul>
                    </div>
                    
                    <p>¡Bienvenido/a a nuestra comunidad educativa! 🌟</p>
                    
                    <p>Saludos cordiales,<br>
                    <strong>Jardines Infantiles<br>
                    Ciudad Bolívar</strong></p>
                </div>
                <div class="footer">
                    <p>Este es un mensaje automático, por favor no responder a este correo.</p>
                    <p>&copy; 2026 NubiDoc</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg = Message(asunto, recipients=[destinatario])
        msg.html = cuerpo
        mail.send(msg)
        print(f"✅ Correo enviado a {destinatario}")
        return True
        
    except Exception as e:
        print(f"❌ Error al enviar correo: {str(e)}")
        return False


# ==================== AUTENTICACIÓN Y SEGURIDAD ====================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user():
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        db = get_db()
        user = db.execute('SELECT * FROM usuarios WHERE username = ? COLLATE NOCASE', (username,)).fetchone()
        now = datetime.now()
        if user and user['bloqueado_hasta']:
            try:
                if datetime.fromisoformat(user['bloqueado_hasta']) > now:
                    db.close(); flash('Cuenta bloqueada temporalmente. Intenta más tarde.', 'error')
                    log_audit(get_db, 'Inicio de sesión', f'Cuenta bloqueada: {username}', 'Fallido', {'username': username})
                    return render_template('auth/login.html')
            except ValueError: pass
        if not user or not user['activo'] or not check_password_hash(user['password_hash'], password):
            if user:
                intentos = user['intentos_fallidos'] + 1
                bloqueado = (now + __import__('datetime').timedelta(minutes=15)).isoformat(timespec='seconds') if intentos >= 5 else None
                db.execute('UPDATE usuarios SET intentos_fallidos=?, bloqueado_hasta=? WHERE id=?', (0 if bloqueado else intentos, bloqueado, user['id']))
                db.commit()
            db.close(); flash('Usuario o contraseña incorrectos.', 'error')
            log_audit(get_db, 'Inicio de sesión', f'Intento fallido: {username}', 'Fallido', {'username': username})
            return render_template('auth/login.html')
        db.execute('UPDATE usuarios SET intentos_fallidos=0, bloqueado_hasta=NULL, ultimo_acceso=? WHERE id=?', (now.isoformat(timespec='seconds'), user['id']))
        db.commit(); db.close()
        session.clear(); session.permanent = True
        session['user'] = {'id': user['id'], 'nombre_completo': user['nombre_completo'], 'username': user['username'], 'rol': user['rol'], 'debe_cambiar_password': bool(user['debe_cambiar_password'])}
        log_audit(get_db, 'Inicio de sesión', 'Acceso concedido', 'Exitoso')
        return redirect(request.args.get('next') or url_for('dashboard'))
    return render_template('auth/login.html')

@app.route('/logout')
def logout():
    log_audit(get_db, 'Cierre de sesión', 'Sesión finalizada', 'Exitoso')
    session.clear(); flash('Sesión cerrada correctamente.', 'success')
    return redirect(url_for('login'))

@app.route('/cambiar-password', methods=['GET', 'POST'])
def cambiar_password():
    if not current_user(): return redirect(url_for('login'))
    if request.method == 'POST':
        actual=request.form.get('actual',''); nueva=request.form.get('nueva',''); confirmar=request.form.get('confirmar','')
        db=get_db(); user=db.execute('SELECT * FROM usuarios WHERE id=?',(current_user()['id'],)).fetchone()
        if not check_password_hash(user['password_hash'], actual):
            db.close(); flash('La contraseña actual no es correcta.', 'error')
        elif len(nueva) < 8 or not any(c.isupper() for c in nueva) or not any(c.isdigit() for c in nueva):
            db.close(); flash('La nueva contraseña debe tener mínimo 8 caracteres, una mayúscula y un número.', 'warning')
        elif nueva != confirmar:
            db.close(); flash('Las contraseñas nuevas no coinciden.', 'error')
        else:
            db.execute('UPDATE usuarios SET password_hash=?, debe_cambiar_password=0, actualizado_en=? WHERE id=?', (generate_password_hash(nueva), datetime.now().isoformat(timespec='seconds'), user['id']))
            db.commit(); db.close(); session['user']['debe_cambiar_password']=False; session.modified=True
            log_audit(get_db,'Cambio de contraseña','Contraseña actualizada','Exitoso'); flash('Contraseña actualizada.', 'success')
            return redirect(url_for('dashboard'))
    return render_template('auth/cambiar_password.html')

@app.route('/usuarios')
def usuarios():
    if not role_is('superadmin','admin'): abort(403)
    db=get_db(); rows=db.execute('SELECT * FROM usuarios ORDER BY nombre_completo').fetchall(); db.close()
    return render_template('usuarios/listar.html', usuarios=rows)

@app.route('/usuarios/crear', methods=['GET','POST'])
def crear_usuario():
    if not role_is('superadmin','admin'): abort(403)
    roles = ['admin','usuario','asistente'] if role_is('admin') else list(ROLE_LABELS.keys())
    if request.method == 'POST':
        rol=request.form.get('rol')
        if rol not in roles: abort(403)
        nombre=request.form.get('nombre_completo','').strip(); username=request.form.get('username','').strip(); email=request.form.get('email','').strip() or None; password=request.form.get('password','')
        if not nombre or not username or len(password)<8:
            flash('Completa los campos obligatorios. La contraseña debe tener mínimo 8 caracteres.', 'warning')
        else:
            db=get_db()
            try:
                db.execute('INSERT INTO usuarios (nombre_completo,username,email,password_hash,rol,creado_por) VALUES (?,?,?,?,?,?)', (nombre,username,email,generate_password_hash(password),rol,current_user()['id']))
                db.commit(); db.close(); log_audit(get_db,'Crear usuario',f'Usuario {username}, rol {rol}','Exitoso'); flash('Usuario creado correctamente.','success'); return redirect(url_for('usuarios'))
            except sqlite3.IntegrityError:
                db.close(); flash('El usuario o correo ya existe.','error')
    return render_template('usuarios/form.html', usuario=None, roles=roles)

@app.route('/usuarios/editar/<int:id>', methods=['GET','POST'])
def editar_usuario(id):
    if not role_is('superadmin','admin'): abort(403)
    db=get_db(); usuario=db.execute('SELECT * FROM usuarios WHERE id=?',(id,)).fetchone()
    if not usuario: db.close(); abort(404)
    if role_is('admin') and usuario['rol'] in ('auditor','superadmin'): db.close(); abort(403)
    roles=['admin','usuario','asistente'] if role_is('admin') else list(ROLE_LABELS.keys())
    if request.method=='POST':
        rol=request.form.get('rol')
        if rol not in roles: db.close(); abort(403)
        if id==current_user()['id'] and (request.form.get('activo')!='1' or rol!=usuario['rol']): db.close(); flash('No puedes desactivar tu cuenta ni cambiar tu propio rol.','warning'); return redirect(url_for('editar_usuario',id=id))
        password=request.form.get('password','')
        params=[request.form.get('nombre_completo','').strip(),request.form.get('email','').strip() or None,rol,1 if request.form.get('activo')=='1' else 0,datetime.now().isoformat(timespec='seconds')]
        sql='UPDATE usuarios SET nombre_completo=?,email=?,rol=?,activo=?,actualizado_en=?'
        if password:
            sql+=',password_hash=?,debe_cambiar_password=1'; params.append(generate_password_hash(password))
        sql+=' WHERE id=?'; params.append(id)
        try:
            db.execute(sql,params); db.commit(); db.close(); log_audit(get_db,'Editar usuario',f'Usuario ID {id}','Exitoso'); flash('Usuario actualizado.','success'); return redirect(url_for('usuarios'))
        except sqlite3.IntegrityError: db.close(); flash('El correo ya está registrado.','error')
    else: db.close()
    return render_template('usuarios/form.html', usuario=usuario, roles=roles)

@app.route('/auditoria')
def auditoria():
    if not role_is('superadmin','admin','auditor'): abort(403)
    filtros=[]; params=[]
    for campo in ('username','modulo','accion','resultado'):
        val=request.args.get(campo,'').strip()
        if val: filtros.append(f'{campo} LIKE ?'); params.append(f'%{val}%')
    desde=request.args.get('desde',''); hasta=request.args.get('hasta','')
    if desde: filtros.append('date(fecha_hora)>=date(?)'); params.append(desde)
    if hasta: filtros.append('date(fecha_hora)<=date(?)'); params.append(hasta)
    where=' WHERE '+' AND '.join(filtros) if filtros else ''
    db=get_db(); rows=db.execute('SELECT * FROM auditoria'+where+' ORDER BY id DESC LIMIT 1000',params).fetchall(); db.close()
    return render_template('auditoria/listar.html', registros=rows)

# ==================== COMUNICACIONES / GESTIÓN DOCUMENTAL ====================
COM_TIPOS = ['Interna','Recibida','Enviada','Respuesta']
COM_PRIORIDADES = ['Baja','Media','Alta','Urgente']
COM_ESTADOS = ['Borrador','Radicado','Asignado','En trámite','Devuelto','Reasignado','Respondido','Archivado','Anulado']

def generar_radicado_comunicacion(db, tipo):
    prefijo = {'Interna':'INT','Recibida':'REC','Enviada':'ENV','Respuesta':'ENV'}.get(tipo,'COM')
    anio = datetime.now().year
    fila = db.execute("SELECT COUNT(*) total FROM comunicaciones WHERE tipo=? AND strftime('%Y', fecha_creacion)=?", (tipo,str(anio))).fetchone()
    return f"{prefijo}-{anio}-{fila['total'] + 1:06d}"

def puede_ver_comunicacion(db, doc):
    u=current_user()
    if not u: return False
    if u['rol'] in ('superadmin','admin','auditor'): return True
    if doc['creado_por']==u['id'] or doc['responsable_id']==u['id']: return True
    return bool(db.execute('SELECT 1 FROM comunicacion_destinatarios WHERE comunicacion_id=? AND usuario_id=?',(doc['id'],u['id'])).fetchone())

def registrar_movimiento(db, comunicacion_id, accion, detalle='', estado_anterior=None, estado_nuevo=None):
    u=current_user(); ahora=datetime.now().isoformat(timespec='seconds')
    db.execute("""INSERT INTO comunicacion_movimientos
        (comunicacion_id,usuario_id,fecha_hora,accion,detalle,estado_anterior,estado_nuevo)
        VALUES (?,?,?,?,?,?,?)""",(comunicacion_id,u['id'] if u else None,ahora,accion,detalle,estado_anterior,estado_nuevo))

@app.route('/comunicaciones')
def comunicaciones():
    db=get_db(); u=current_user(); filtro=request.args.get('bandeja','entrada'); q=request.args.get('q','').strip(); estado=request.args.get('estado','')
    base="""SELECT c.*, uc.nombre_completo creador_nombre, ur.nombre_completo responsable_nombre,
      (SELECT group_concat(u2.nombre_completo, ', ') FROM comunicacion_destinatarios cd JOIN usuarios u2 ON u2.id=cd.usuario_id WHERE cd.comunicacion_id=c.id) destinatarios
      FROM comunicaciones c LEFT JOIN usuarios uc ON uc.id=c.creado_por LEFT JOIN usuarios ur ON ur.id=c.responsable_id"""
    filtros=[]; params=[]
    if u['rol'] not in ('superadmin','admin','auditor'):
        if filtro=='enviados': filtros.append('c.creado_por=?'); params.append(u['id'])
        elif filtro=='archivados': filtros.append("c.estado='Archivado' AND (c.creado_por=? OR c.responsable_id=? OR EXISTS(SELECT 1 FROM comunicacion_destinatarios x WHERE x.comunicacion_id=c.id AND x.usuario_id=?))"); params += [u['id']]*3
        elif filtro=='devueltos': filtros.append("c.estado='Devuelto' AND (c.creado_por=? OR c.responsable_id=? OR EXISTS(SELECT 1 FROM comunicacion_destinatarios x WHERE x.comunicacion_id=c.id AND x.usuario_id=?))"); params += [u['id']]*3
        elif filtro=='borradores': filtros.append("c.estado='Borrador' AND c.creado_por=?"); params.append(u['id'])
        else: filtros.append('(c.responsable_id=? OR EXISTS(SELECT 1 FROM comunicacion_destinatarios x WHERE x.comunicacion_id=c.id AND x.usuario_id=?))'); params += [u['id'],u['id']]
    else:
        if filtro=='archivados': filtros.append("c.estado='Archivado'")
        elif filtro=='devueltos': filtros.append("c.estado='Devuelto'")
        elif filtro=='borradores': filtros.append("c.estado='Borrador'")
        elif filtro=='enviados': filtros.append('c.creado_por=?'); params.append(u['id'])
    if q: filtros.append('(c.radicado LIKE ? OR c.asunto LIKE ? OR c.remitente_externo LIKE ?)'); params += [f'%{q}%']*3
    if estado: filtros.append('c.estado=?'); params.append(estado)
    where=' WHERE '+' AND '.join(filtros) if filtros else ''
    docs=db.execute(base+where+' ORDER BY c.id DESC',params).fetchall()
    resumen=db.execute('SELECT estado,COUNT(*) total FROM comunicaciones GROUP BY estado').fetchall(); db.close()
    return render_template('comunicaciones/listar.html',documentos=docs,resumen=resumen,estados=COM_ESTADOS,bandeja=filtro)

@app.route('/comunicaciones/crear', methods=['GET','POST'])
def crear_comunicacion():
    db=get_db(); usuarios=db.execute("SELECT id,nombre_completo FROM usuarios WHERE activo=1 AND id<>? ORDER BY nombre_completo",(current_user()['id'],)).fetchall()
    if request.method=='POST':
        tipo=request.form.get('tipo'); asunto=request.form.get('asunto','').strip(); descripcion=request.form.get('descripcion','').strip(); accion=request.form.get('accion','borrador')
        if tipo not in COM_TIPOS or not asunto or not descripcion:
            db.close(); flash('Completa tipo, asunto y descripción.','warning'); return render_template('comunicaciones/form.html',usuarios=usuarios,tipos=COM_TIPOS,prioridades=COM_PRIORIDADES)
        estado='Borrador' if accion=='borrador' else 'Radicado'; radicado=None if estado=='Borrador' else generar_radicado_comunicacion(db,tipo); ahora=datetime.now().isoformat(timespec='seconds')
        cur=db.execute("""INSERT INTO comunicaciones (radicado,tipo,asunto,descripcion,remitente_externo,radicado_externo,prioridad,confidencial,requiere_respuesta,fecha_limite,estado,creado_por,responsable_id,fecha_creacion,fecha_radicacion,numero_folios,medio,observaciones)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(radicado,tipo,asunto,descripcion,request.form.get('remitente_externo','').strip() or None,request.form.get('radicado_externo','').strip() or None,request.form.get('prioridad','Media'),1 if request.form.get('confidencial') else 0,1 if request.form.get('requiere_respuesta') else 0,request.form.get('fecha_limite') or None,estado,current_user()['id'],request.form.get('responsable_id') or None,ahora,ahora if radicado else None,request.form.get('numero_folios') or 0,request.form.get('medio','Sistema'),request.form.get('observaciones','').strip() or None))
        cid=cur.lastrowid
        for uid in request.form.getlist('destinatarios'):
            db.execute('INSERT OR IGNORE INTO comunicacion_destinatarios (comunicacion_id,usuario_id,tipo_destinatario) VALUES (?,?,?)',(cid,uid,'Principal'))
        archivo=request.files.get('archivo')
        if archivo and archivo.filename:
            if not allowed_file(archivo.filename): db.rollback(); db.close(); flash('Formato de archivo no permitido.','error'); return redirect(url_for('crear_comunicacion'))
            carpeta=os.path.join(app.config['UPLOAD_FOLDER'],'comunicaciones'); os.makedirs(carpeta,exist_ok=True); nombre=f"{cid}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(archivo.filename)}"; ruta=os.path.join(carpeta,nombre); archivo.save(ruta)
            db.execute('INSERT INTO comunicacion_adjuntos (comunicacion_id,nombre_original,nombre_archivo,ruta_archivo,fecha_subida,subido_por) VALUES (?,?,?,?,?,?)',(cid,archivo.filename,nombre,ruta,ahora,current_user()['id']))
        registrar_movimiento(db,cid,'Creación',f'Documento creado como {estado}',None,estado); db.commit(); db.close(); log_audit(get_db,'Crear comunicación',radicado or f'Borrador {cid}','Exitoso',modulo='Comunicaciones'); flash('Comunicación guardada correctamente.','success'); return redirect(url_for('ver_comunicacion',comunicacion_id=cid))
    db.close(); return render_template('comunicaciones/form.html',usuarios=usuarios,tipos=COM_TIPOS,prioridades=COM_PRIORIDADES)

@app.route('/comunicaciones/<int:comunicacion_id>')
def ver_comunicacion(comunicacion_id):
    db=get_db(); doc=db.execute("""SELECT c.*,uc.nombre_completo creador_nombre,ur.nombre_completo responsable_nombre FROM comunicaciones c LEFT JOIN usuarios uc ON uc.id=c.creado_por LEFT JOIN usuarios ur ON ur.id=c.responsable_id WHERE c.id=?""",(comunicacion_id,)).fetchone()
    if not doc: db.close(); abort(404)
    if not puede_ver_comunicacion(db,doc): db.close(); abort(403)
    destinatarios=db.execute('SELECT u.id,u.nombre_completo,cd.tipo_destinatario FROM comunicacion_destinatarios cd JOIN usuarios u ON u.id=cd.usuario_id WHERE cd.comunicacion_id=?',(comunicacion_id,)).fetchall(); movimientos=db.execute('SELECT m.*,u.nombre_completo usuario_nombre FROM comunicacion_movimientos m LEFT JOIN usuarios u ON u.id=m.usuario_id WHERE m.comunicacion_id=? ORDER BY m.id DESC',(comunicacion_id,)).fetchall(); adjuntos=db.execute('SELECT * FROM comunicacion_adjuntos WHERE comunicacion_id=? ORDER BY id DESC',(comunicacion_id,)).fetchall(); usuarios=db.execute("SELECT id,nombre_completo FROM usuarios WHERE activo=1 ORDER BY nombre_completo").fetchall(); respuestas=db.execute('SELECT * FROM comunicaciones WHERE documento_origen_id=? ORDER BY id DESC',(comunicacion_id,)).fetchall(); db.close()
    return render_template('comunicaciones/ver.html',doc=doc,destinatarios=destinatarios,movimientos=movimientos,adjuntos=adjuntos,usuarios=usuarios,respuestas=respuestas,estados=COM_ESTADOS)

@app.route('/comunicaciones/<int:comunicacion_id>/radicar',methods=['POST'])
def radicar_comunicacion(comunicacion_id):
    db=get_db(); doc=db.execute('SELECT * FROM comunicaciones WHERE id=?',(comunicacion_id,)).fetchone()
    if not doc or doc['creado_por']!=current_user()['id'] or doc['estado']!='Borrador': db.close(); abort(403)
    rad=generar_radicado_comunicacion(db,doc['tipo']); ahora=datetime.now().isoformat(timespec='seconds'); db.execute("UPDATE comunicaciones SET radicado=?,estado='Radicado',fecha_radicacion=?,fecha_actualizacion=? WHERE id=?",(rad,ahora,ahora,comunicacion_id)); registrar_movimiento(db,comunicacion_id,'Radicación',f'Radicado {rad}','Borrador','Radicado'); db.commit(); db.close(); flash('Documento radicado correctamente.','success'); return redirect(url_for('ver_comunicacion',comunicacion_id=comunicacion_id))

@app.route('/comunicaciones/<int:comunicacion_id>/devolver',methods=['POST'])
def devolver_comunicacion(comunicacion_id):
    motivo=request.form.get('motivo','').strip(); just=request.form.get('justificacion','').strip()
    if not motivo or not just: flash('El motivo y la justificación son obligatorios.','warning'); return redirect(url_for('ver_comunicacion',comunicacion_id=comunicacion_id))
    db=get_db(); doc=db.execute('SELECT * FROM comunicaciones WHERE id=?',(comunicacion_id,)).fetchone()
    if not doc or not puede_ver_comunicacion(db,doc) or doc['estado'] in ('Archivado','Anulado'): db.close(); abort(403)
    anterior=doc['estado']; ahora=datetime.now().isoformat(timespec='seconds'); db.execute("UPDATE comunicaciones SET estado='Devuelto',responsable_id=?,fecha_actualizacion=? WHERE id=?",(doc['creado_por'],ahora,comunicacion_id)); registrar_movimiento(db,comunicacion_id,'Devolución',f'{motivo}: {just}',anterior,'Devuelto'); db.commit(); db.close(); log_audit(get_db,'Devolver comunicación',f"{doc['radicado']}: {just}",'Exitoso',modulo='Comunicaciones'); flash('Comunicación devuelta al remitente.','success'); return redirect(url_for('ver_comunicacion',comunicacion_id=comunicacion_id))

@app.route('/comunicaciones/<int:comunicacion_id>/reasignar',methods=['POST'])
def reasignar_comunicacion(comunicacion_id):
    nuevo=request.form.get('responsable_id'); just=request.form.get('justificacion','').strip()
    if not nuevo or not just: flash('Selecciona responsable y escribe la justificación.','warning'); return redirect(url_for('ver_comunicacion',comunicacion_id=comunicacion_id))
    db=get_db(); doc=db.execute('SELECT * FROM comunicaciones WHERE id=?',(comunicacion_id,)).fetchone()
    if not doc or not puede_ver_comunicacion(db,doc) or doc['estado'] in ('Archivado','Anulado'): db.close(); abort(403)
    anterior=doc['estado']; db.execute("UPDATE comunicaciones SET responsable_id=?,estado='Reasignado',fecha_actualizacion=? WHERE id=?",(nuevo,datetime.now().isoformat(timespec='seconds'),comunicacion_id)); registrar_movimiento(db,comunicacion_id,'Reasignación',just,anterior,'Reasignado'); db.commit(); db.close(); flash('Comunicación reasignada.','success'); return redirect(url_for('ver_comunicacion',comunicacion_id=comunicacion_id))

@app.route('/comunicaciones/<int:comunicacion_id>/archivar',methods=['POST'])
def archivar_comunicacion(comunicacion_id):
    just=request.form.get('justificacion','').strip(); resultado=request.form.get('resultado','').strip(); expediente=request.form.get('expediente','').strip()
    if not just or not resultado: flash('La justificación y el resultado del trámite son obligatorios.','warning'); return redirect(url_for('ver_comunicacion',comunicacion_id=comunicacion_id))
    db=get_db(); doc=db.execute('SELECT * FROM comunicaciones WHERE id=?',(comunicacion_id,)).fetchone()
    if not doc or not puede_ver_comunicacion(db,doc) or doc['estado'] in ('Archivado','Anulado','Borrador'): db.close(); abort(403)
    anterior=doc['estado']; ahora=datetime.now().isoformat(timespec='seconds'); db.execute("UPDATE comunicaciones SET estado='Archivado',justificacion_archivo=?,resultado_tramite=?,expediente=?,fecha_archivo=?,archivado_por=?,fecha_actualizacion=? WHERE id=?",(just,resultado,expediente or None,ahora,current_user()['id'],ahora,comunicacion_id)); registrar_movimiento(db,comunicacion_id,'Archivo',f'{resultado}. Justificación: {just}. Expediente: {expediente}',anterior,'Archivado'); db.commit(); db.close(); log_audit(get_db,'Archivar comunicación',doc['radicado'] or str(doc['id']),'Exitoso',modulo='Comunicaciones'); flash('Documento archivado y bloqueado para edición.','success'); return redirect(url_for('ver_comunicacion',comunicacion_id=comunicacion_id))

@app.route('/comunicaciones/<int:comunicacion_id>/reabrir',methods=['POST'])
def reabrir_comunicacion(comunicacion_id):
    if not role_is('superadmin','admin'): abort(403)
    just=request.form.get('justificacion','').strip()
    if not just: flash('La justificación es obligatoria.','warning'); return redirect(url_for('ver_comunicacion',comunicacion_id=comunicacion_id))
    db=get_db(); doc=db.execute('SELECT * FROM comunicaciones WHERE id=?',(comunicacion_id,)).fetchone()
    if not doc or doc['estado']!='Archivado': db.close(); abort(400)
    db.execute("UPDATE comunicaciones SET estado='En trámite',fecha_actualizacion=? WHERE id=?",(datetime.now().isoformat(timespec='seconds'),comunicacion_id)); registrar_movimiento(db,comunicacion_id,'Reapertura',just,'Archivado','En trámite'); db.commit(); db.close(); flash('Documento reabierto.','success'); return redirect(url_for('ver_comunicacion',comunicacion_id=comunicacion_id))

@app.route('/comunicaciones/<int:comunicacion_id>/responder',methods=['POST'])
def responder_comunicacion(comunicacion_id):
    texto=request.form.get('respuesta','').strip()
    if not texto: flash('Escribe el contenido de la respuesta.','warning'); return redirect(url_for('ver_comunicacion',comunicacion_id=comunicacion_id))
    db=get_db(); origen=db.execute('SELECT * FROM comunicaciones WHERE id=?',(comunicacion_id,)).fetchone()
    if not origen or not puede_ver_comunicacion(db,origen) or origen['estado'] in ('Archivado','Anulado'): db.close(); abort(403)
    ahora=datetime.now().isoformat(timespec='seconds'); rad=generar_radicado_comunicacion(db,'Respuesta'); cur=db.execute("""INSERT INTO comunicaciones (radicado,tipo,asunto,descripcion,prioridad,estado,creado_por,responsable_id,fecha_creacion,fecha_radicacion,documento_origen_id,medio) VALUES (?,'Respuesta',?,?,?,?,?,?,?,?,?,'Sistema')""",(rad,'Respuesta a '+origen['asunto'],texto,origen['prioridad'],'Radicado',current_user()['id'],origen['creado_por'],ahora,ahora,comunicacion_id)); rid=cur.lastrowid; db.execute("UPDATE comunicaciones SET estado='Respondido',fecha_actualizacion=? WHERE id=?",(ahora,comunicacion_id)); registrar_movimiento(db,comunicacion_id,'Respuesta',f'Respuesta asociada {rad}',origen['estado'],'Respondido'); registrar_movimiento(db,rid,'Creación de respuesta',f"Respuesta a {origen['radicado']}",None,'Radicado'); db.commit(); db.close(); flash(f'Respuesta creada con radicado {rad}.','success'); return redirect(url_for('ver_comunicacion',comunicacion_id=comunicacion_id))

@app.route('/comunicaciones/adjunto/<int:adjunto_id>')
def descargar_adjunto_comunicacion(adjunto_id):
    db=get_db(); adj=db.execute('SELECT * FROM comunicacion_adjuntos WHERE id=?',(adjunto_id,)).fetchone()
    if not adj: db.close(); abort(404)
    doc=db.execute('SELECT * FROM comunicaciones WHERE id=?',(adj['comunicacion_id'],)).fetchone()
    if not puede_ver_comunicacion(db,doc): db.close(); abort(403)
    db.close(); return send_from_directory(os.path.dirname(adj['ruta_archivo']),os.path.basename(adj['ruta_archivo']),as_attachment=True,download_name=adj['nombre_original'])

# ==================== PQRS ====================
PQRS_ESTADOS = ['Recibida', 'En revisión', 'Asignada', 'En trámite', 'Pendiente de información', 'Respondida', 'Cerrada', 'Reabierta', 'Anulada']
PQRS_TIPOS = ['Petición', 'Queja', 'Reclamo', 'Sugerencia', 'Denuncia', 'Felicitación']
PQRS_PRIORIDADES = ['Baja', 'Media', 'Alta', 'Urgente']

def generar_radicado_pqrs(db):
    anio = datetime.now().year
    fila = db.execute("SELECT COUNT(*) AS total FROM pqrs WHERE strftime('%Y', fecha_radicacion)=?", (str(anio),)).fetchone()
    return f"PQRS-{anio}-{fila['total'] + 1:06d}"

@app.route('/pqrs/radicar', methods=['GET', 'POST'])
def pqrs_publica():
    if request.method == 'POST':
        tipo=request.form.get('tipo','').strip(); asunto=request.form.get('asunto','').strip(); descripcion=request.form.get('descripcion','').strip()
        anonima=1 if request.form.get('anonima')=='1' else 0
        nombre=request.form.get('nombre_solicitante','').strip(); documento=request.form.get('documento','').strip(); correo=request.form.get('correo','').strip(); telefono=request.form.get('telefono','').strip()
        if tipo not in PQRS_TIPOS or not asunto or not descripcion or request.form.get('autorizacion_datos')!='1':
            flash('Completa los campos obligatorios y acepta el tratamiento de datos.','warning'); return render_template('pqrs/publica.html',tipos=PQRS_TIPOS)
        if not anonima and (not nombre or not correo):
            flash('Para una solicitud identificada debes indicar nombre y correo.','warning'); return render_template('pqrs/publica.html',tipos=PQRS_TIPOS)
        db=get_db(); radicado=generar_radicado_pqrs(db); codigo=__import__('secrets').token_hex(4).upper(); ahora=datetime.now().isoformat(timespec='seconds')
        cur=db.execute("""INSERT INTO pqrs (radicado,codigo_consulta,tipo,nombre_solicitante,documento,correo,telefono,asunto,descripcion,estado,prioridad,anonima,fecha_radicacion,fecha_limite)
            VALUES (?,?,?,?,?,?,?,?,?,'Recibida','Media',?,?,date(?,'+15 days'))""",(radicado,codigo,tipo,None if anonima else nombre,None if anonima else documento,None if anonima else correo,None if anonima else telefono,asunto,descripcion,anonima,ahora,ahora))
        pqrs_id=cur.lastrowid
        db.execute("""INSERT INTO pqrs_historial (pqrs_id,fecha_hora,accion,estado_nuevo,detalle,actor) VALUES (?,?,'Radicación','Recibida','PQRS registrada desde el formulario público','Ciudadano')""",(pqrs_id,ahora))
        archivo=request.files.get('archivo')
        if archivo and archivo.filename:
            if not allowed_file(archivo.filename):
                db.rollback(); db.close(); flash('Formato de archivo no permitido.','error'); return render_template('pqrs/publica.html',tipos=PQRS_TIPOS)
            carpeta=os.path.join(app.config['UPLOAD_FOLDER'],'pqrs'); os.makedirs(carpeta,exist_ok=True)
            guardado=f"{pqrs_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secure_filename(archivo.filename)}"; ruta=os.path.join(carpeta,guardado); archivo.save(ruta)
            db.execute('INSERT INTO pqrs_adjuntos (pqrs_id,nombre_original,nombre_archivo,ruta_archivo,fecha_subida,publico) VALUES (?,?,?,?,?,1)',(pqrs_id,archivo.filename,guardado,ruta,ahora))
        db.commit(); db.close(); return render_template('pqrs/confirmacion.html',radicado=radicado,codigo=codigo)
    return render_template('pqrs/publica.html',tipos=PQRS_TIPOS)

@app.route('/pqrs/consultar', methods=['GET','POST'])
def consultar_pqrs_publica():
    caso=None; historial=[]
    if request.method=='POST':
        db=get_db(); caso=db.execute('SELECT * FROM pqrs WHERE upper(radicado)=? AND upper(codigo_consulta)=?',(request.form.get('radicado','').strip().upper(),request.form.get('codigo','').strip().upper())).fetchone()
        if caso: historial=db.execute('SELECT * FROM pqrs_historial WHERE pqrs_id=? AND visible_ciudadano=1 ORDER BY id',(caso['id'],)).fetchall()
        else: flash('No encontramos una PQRS con esos datos.','error')
        db.close()
    return render_template('pqrs/consultar.html',caso=caso,historial=historial)

@app.route('/pqrs')
def pqrs():
    filtros=[]; params=[]
    for campo in ('estado','tipo','prioridad'):
        valor=request.args.get(campo,'').strip()
        if valor: filtros.append(f'p.{campo}=?'); params.append(valor)
    buscar=request.args.get('buscar','').strip()
    if buscar: filtros.append('(p.radicado LIKE ? OR p.asunto LIKE ? OR p.nombre_solicitante LIKE ?)'); params.extend([f'%{buscar}%']*3)
    if request.args.get('responsable')=='mias': filtros.append('p.responsable_id=?'); params.append(current_user()['id'])
    where=' WHERE '+' AND '.join(filtros) if filtros else ''
    db=get_db(); casos=db.execute("""SELECT p.*,u.nombre_completo responsable_nombre,CAST(julianday(p.fecha_limite)-julianday('now') AS INTEGER) dias_restantes FROM pqrs p LEFT JOIN usuarios u ON u.id=p.responsable_id"""+where+' ORDER BY p.id DESC',params).fetchall(); resumen=db.execute('SELECT estado,COUNT(*) total FROM pqrs GROUP BY estado').fetchall(); db.close()
    return render_template('pqrs/listar.html',casos=casos,resumen=resumen,estados=PQRS_ESTADOS,tipos=PQRS_TIPOS,prioridades=PQRS_PRIORIDADES)

@app.route('/pqrs/<int:pqrs_id>')
def ver_pqrs(pqrs_id):
    db=get_db(); caso=db.execute('SELECT p.*,u.nombre_completo responsable_nombre FROM pqrs p LEFT JOIN usuarios u ON u.id=p.responsable_id WHERE p.id=?',(pqrs_id,)).fetchone()
    if not caso: db.close(); abort(404)
    historial=db.execute('SELECT * FROM pqrs_historial WHERE pqrs_id=? ORDER BY id DESC',(pqrs_id,)).fetchall(); adjuntos=db.execute('SELECT * FROM pqrs_adjuntos WHERE pqrs_id=? ORDER BY id DESC',(pqrs_id,)).fetchall(); usuarios=db.execute("SELECT id,nombre_completo FROM usuarios WHERE activo=1 AND rol IN ('superadmin','admin','usuario','asistente') ORDER BY nombre_completo").fetchall(); db.close()
    return render_template('pqrs/ver.html',caso=caso,historial=historial,adjuntos=adjuntos,usuarios=usuarios,estados=PQRS_ESTADOS,prioridades=PQRS_PRIORIDADES)

@app.route('/pqrs/<int:pqrs_id>/gestionar',methods=['POST'])
def gestionar_pqrs(pqrs_id):
    db=get_db(); caso=db.execute('SELECT * FROM pqrs WHERE id=?',(pqrs_id,)).fetchone()
    if not caso: db.close(); abort(404)
    estado=request.form.get('estado',caso['estado']); prioridad=request.form.get('prioridad',caso['prioridad']); responsable=request.form.get('responsable_id') or None; nota=request.form.get('nota','').strip()
    if estado not in PQRS_ESTADOS or prioridad not in PQRS_PRIORIDADES: db.close(); abort(400)
    ahora=datetime.now().isoformat(timespec='seconds'); db.execute('UPDATE pqrs SET estado=?,prioridad=?,responsable_id=?,fecha_actualizacion=? WHERE id=?',(estado,prioridad,responsable,ahora,pqrs_id)); detalle=nota or f"Estado: {caso['estado']} → {estado}. Prioridad: {prioridad}."
    db.execute("""INSERT INTO pqrs_historial (pqrs_id,usuario_id,fecha_hora,accion,estado_anterior,estado_nuevo,detalle,actor,visible_ciudadano) VALUES (?,?,?,'Gestión interna',?,?,?,?,0)""",(pqrs_id,current_user()['id'],ahora,caso['estado'],estado,detalle,current_user()['nombre_completo']))
    db.commit(); db.close(); log_audit(get_db,'Gestionar PQRS',f"{caso['radicado']}: {detalle}",'Exitoso',modulo='PQRS'); flash('PQRS actualizada correctamente.','success'); return redirect(url_for('ver_pqrs',pqrs_id=pqrs_id))

@app.route('/pqrs/<int:pqrs_id>/responder',methods=['POST'])
def responder_pqrs(pqrs_id):
    respuesta=request.form.get('respuesta','').strip()
    if not respuesta: flash('Escribe la respuesta antes de enviarla.','warning'); return redirect(url_for('ver_pqrs',pqrs_id=pqrs_id))
    db=get_db(); caso=db.execute('SELECT * FROM pqrs WHERE id=?',(pqrs_id,)).fetchone()
    if not caso: db.close(); abort(404)
    ahora=datetime.now().isoformat(timespec='seconds'); db.execute("UPDATE pqrs SET respuesta=?,estado='Respondida',fecha_respuesta=?,fecha_actualizacion=? WHERE id=?",(respuesta,ahora,ahora,pqrs_id)); db.execute("""INSERT INTO pqrs_historial (pqrs_id,usuario_id,fecha_hora,accion,estado_anterior,estado_nuevo,detalle,actor,visible_ciudadano) VALUES (?,?,?,'Respuesta emitida',?,'Respondida',?,?,1)""",(pqrs_id,current_user()['id'],ahora,caso['estado'],respuesta,current_user()['nombre_completo'])); db.commit(); db.close(); log_audit(get_db,'Responder PQRS',caso['radicado'],'Exitoso',modulo='PQRS'); flash('Respuesta registrada y disponible para consulta ciudadana.','success'); return redirect(url_for('ver_pqrs',pqrs_id=pqrs_id))

@app.route('/pqrs/adjunto/<int:adjunto_id>')
def descargar_adjunto_pqrs(adjunto_id):
    db=get_db(); adj=db.execute('SELECT * FROM pqrs_adjuntos WHERE id=?',(adjunto_id,)).fetchone(); db.close()
    if not adj or not os.path.exists(adj['ruta_archivo']): abort(404)
    return send_from_directory(os.path.dirname(adj['ruta_archivo']),os.path.basename(adj['ruta_archivo']),as_attachment=True,download_name=adj['nombre_original'])


# ==================== DASHBOARD ====================
# 🔴 ESTA ES LA PARTE QUE DEBES REEMPLAZAR 🔴
@app.route('/')
def dashboard():
    db = get_db()
    
    # ========== DATOS DE JARDINES ==========
    jardines_rows = db.execute('SELECT * FROM jardines ORDER BY nombre').fetchall()
    
    jardines = []
    total_matriculados = 0
    capacidad_total = 0
    
    for row in jardines_rows:
        jardin = dict(row)
        matriculados = db.execute(
            'SELECT COUNT(*) as count FROM ninos WHERE jardin_id = ? AND estado_matricula = "Activo"',
            (jardin['id'],)
        ).fetchone()['count']
        jardin['matriculados'] = matriculados
        jardin['ocupacion'] = round((matriculados / jardin['capacidad']) * 100, 1) if jardin['capacidad'] > 0 else 0
        jardines.append(jardin)
        total_matriculados += matriculados
        capacidad_total += jardin['capacidad']
    
    cupos_disponibles = capacidad_total - total_matriculados
    ocupacion_total = round((total_matriculados / capacidad_total) * 100, 1) if capacidad_total > 0 else 0
    
    # ========== DATOS DE PERSONAL (DINÁMICOS) ==========
    # Total personal activo
    personal_activo = db.execute('SELECT COUNT(*) as count FROM personal WHERE estado = "Activo"').fetchone()['count']
    
    # Personal contratado esta semana (últimos 7 días)
    personal_nuevo_semana = db.execute('''
        SELECT COUNT(*) as count FROM personal 
        WHERE fecha_contratacion >= date('now', '-7 days')
    ''').fetchone()['count']
    
    # ========== DATOS DE ASISTENCIA (SIMULADOS por ahora) ==========
    asistencia_dia = 92.4
    ninos_presentes = int(total_matriculados * asistencia_dia / 100) if total_matriculados > 0 else 0
    
    # ========== DATOS DE ALERTAS ==========
    # Documentos por vencer en los próximos 30 días
    documentos_por_vencer = db.execute('''
        SELECT COUNT(*) as count FROM documentos 
        WHERE fecha_vencimiento IS NOT NULL 
        AND fecha_vencimiento BETWEEN date('now') AND date('now', '+30 days')
    ''').fetchone()['count']
    
    vacunas_pendientes = 12  # Simulado por ahora
    total_alertas = documentos_por_vencer + vacunas_pendientes
    
    # ========== ACTIVIDADES PRÓXIMAS ==========
    actividades = [
        {'titulo': 'Reunión de equipo pedagógico', 'lugar': 'Sede Paraíso', 'fecha': 'Hoy'},
        {'titulo': 'Visita de nutricionista', 'lugar': 'Jardín La Estrella', 'fecha': 'Mañana'},
        {'titulo': 'Taller de familia: Crianza positiva', 'lugar': 'Sede Minuto de María', 'fecha': 'Miércoles'},
        {'titulo': 'Comité de convivencia', 'lugar': 'Sede Arborizadora Alta', 'fecha': 'Jueves'},
    ]
    
    # ========== ALERTAS RECIENTES ==========
    alertas_recientes = [
        {'mensaje': 'Nueva matrícula registrada', 'lugar': 'Jardín Paraíso', 'tiempo': 'Hace 15 min'},
        {'mensaje': 'Documento por vencer', 'lugar': 'Jardín La Estrella', 'tiempo': 'Hace 45 min'},
        {'mensaje': 'Vacuna pendiente', 'lugar': 'Jardín Dejando Huella', 'tiempo': 'Hace 2h'},
        {'mensaje': 'Mensaje enviado a familias', 'lugar': 'Jardín Minuto de María', 'tiempo': 'Hace 3h'},
    ]
    
    return render_template('dashboard.html',
                         jardines=jardines,
                         total_jardines=len(jardines),
                         total_matriculados=total_matriculados,
                         cupos_disponibles=cupos_disponibles,
                         capacidad_total=capacidad_total,
                         ocupacion_total=ocupacion_total,
                         personal_activo=personal_activo,
                         personal_nuevo_semana=personal_nuevo_semana,
                         asistencia_dia=asistencia_dia,
                         ninos_presentes=ninos_presentes,
                         total_alertas=total_alertas,
                         documentos_por_vencer=documentos_por_vencer,
                         vacunas_pendientes=vacunas_pendientes,
                         actividades=actividades,
                         alertas_recientes=alertas_recientes)


# ==================== JARDINES ====================
@app.route('/jardines')
def listar_jardines():
    db = get_db()
    jardines_rows = db.execute('SELECT * FROM jardines ORDER BY nombre').fetchall()
    
    jardines = []
    for row in jardines_rows:
        jardin = dict(row)
        matriculados = db.execute(
            'SELECT COUNT(*) as count FROM ninos WHERE jardin_id = ? AND estado_matricula = "Activo"',
            (jardin['id'],)
        ).fetchone()['count']
        jardin['matriculados'] = matriculados
        jardin['ocupacion'] = round((matriculados / jardin['capacidad']) * 100, 1) if jardin['capacidad'] > 0 else 0
        jardines.append(jardin)
    
    return render_template('jardines/listar.html', jardines=jardines)

@app.route('/jardines/crear', methods=['GET', 'POST'])
def crear_jardin():
    if request.method == 'POST':
        db = get_db()
        try:
            db.execute('''
                INSERT INTO jardines (nombre, direccion, localidad, capacidad, estado)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                request.form['nombre'],
                request.form['direccion'],
                request.form['localidad'],
                int(request.form['capacidad']),
                request.form.get('estado', 'Activo')
            ))
            db.commit()
            flash('Jardín creado exitosamente', 'success')
            return redirect(url_for('listar_jardines'))
        except sqlite3.IntegrityError:
            flash('Ya existe un jardín con ese nombre', 'error')
    
    return render_template('jardines/crear.html')

@app.route('/jardines/editar/<int:id>', methods=['GET', 'POST'])
def editar_jardin(id):
    db = get_db()
    jardin = db.execute('SELECT * FROM jardines WHERE id = ?', (id,)).fetchone()
    
    if request.method == 'POST':
        try:
            db.execute('''
                UPDATE jardines 
                SET nombre=?, direccion=?, localidad=?, capacidad=?, estado=?
                WHERE id=?
            ''', (
                request.form['nombre'],
                request.form['direccion'],
                request.form['localidad'],
                int(request.form['capacidad']),
                request.form.get('estado', 'Activo'),
                id
            ))
            db.commit()
            flash('Jardín actualizado exitosamente', 'success')
            return redirect(url_for('listar_jardines'))
        except sqlite3.IntegrityError:
            flash('Ya existe un jardín con ese nombre', 'error')
    
    return render_template('jardines/editar.html', jardin=jardin)

# ==================== DOCUMENTOS DEL PERSONAL ====================
@app.route('/personal/documentos/<int:personal_id>')
def listar_documentos_personal(personal_id):
    db = get_db()
    
    # Obtener información del empleado
    persona = db.execute('SELECT * FROM personal WHERE id = ?', (personal_id,)).fetchone()
    if not persona:
        flash('Empleado no encontrado', 'error')
        return redirect(url_for('listar_personal'))
    
    # Obtener documentos del empleado
    documentos = db.execute('''
        SELECT * FROM documentos_personal 
        WHERE personal_id = ? 
        ORDER BY fecha_subida DESC
    ''', (personal_id,)).fetchall()
    
    # Agregar la fecha actual para el template
    from datetime import datetime
    today = datetime.now().strftime('%Y-%m-%d')
    
    return render_template('personal/documentos/listar.html', 
                         persona=dict(persona), 
                         documentos=[dict(d) for d in documentos],
                         today=today)  # ← Agregar today aquí

@app.route('/personal/documentos/subir/<int:personal_id>', methods=['GET', 'POST'])
def subir_documento_personal(personal_id):
    db = get_db()
    persona = db.execute('SELECT * FROM personal WHERE id = ?', (personal_id,)).fetchone()
    
    if not persona:
        flash('Empleado no encontrado', 'error')
        return redirect(url_for('listar_personal'))
    
    # Tipos de documentos para personal
    tipos_documento_personal = [
        'Cédula de Ciudadanía',
        'Tarjeta Profesional',
        'Diploma / Acta de Grado',
        'Certificado de Estudios',
        'Certificado de Experiencia Laboral',
        'Certificado de Competencias',
        'Antecedentes Disciplinarios',
        'Antecedentes Judiciales',
        'Certificado Médico',
        'Carnet de Vacunación',
        'Exámenes de Ingreso',
        'Contrato Laboral',
        'Certificado EPS',
        'Certificado ARL',
        'Certificado Fondo de Pensiones',
        'Certificado de Afiliación a Caja de Compensación',
        'Curso de Seguridad y Salud en el Trabajo',
        'Certificado de Altura (si aplica)',
        'Licencia de Conducción',
        'Otros'
    ]
    
    if request.method == 'POST':
        tipo_documento = request.form['tipo_documento']
        fecha_vencimiento = request.form.get('fecha_vencimiento') or None
        observaciones = request.form.get('observaciones', '')
        
        if 'archivo' not in request.files:
            flash('No se seleccionó ningún archivo', 'error')
            return redirect(request.url)
        
        archivo = request.files['archivo']
        
        if archivo.filename == '':
            flash('No se seleccionó ningún archivo', 'error')
            return redirect(request.url)
        
        if archivo and allowed_file(archivo.filename):
            filename = secure_filename(archivo.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"personal_{personal_id}_{timestamp}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            archivo.save(filepath)
            
            db.execute('''
                INSERT INTO documentos_personal (personal_id, tipo_documento, nombre_archivo, ruta_archivo, fecha_subida, fecha_vencimiento, observaciones)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (personal_id, tipo_documento, filename, filepath, datetime.now().strftime('%Y-%m-%d'), fecha_vencimiento, observaciones))
            db.commit()
            
            flash(f'📄 Documento "{tipo_documento}" subido exitosamente', 'success')
            return redirect(url_for('listar_documentos_personal', personal_id=personal_id))
        else:
            flash('Tipo de archivo no permitido. Use: PDF, JPG, PNG, DOC', 'error')
    
    return render_template('personal/documentos/subir.html', persona=dict(persona), tipos_documento=tipos_documento_personal)

@app.route('/personal/documentos/ver/<int:doc_id>')
def ver_documento_personal(doc_id):
    db = get_db()
    doc = db.execute('SELECT * FROM documentos_personal WHERE id = ?', (doc_id,)).fetchone()
    
    if not doc:
        flash('Documento no encontrado', 'error')
        return redirect(url_for('listar_personal'))
    
    if os.path.exists(doc['ruta_archivo']):
        return send_from_directory(
            os.path.dirname(doc['ruta_archivo']), 
            os.path.basename(doc['ruta_archivo'])
        )
    else:
        flash('El archivo no existe en el servidor', 'error')
        return redirect(url_for('listar_documentos_personal', personal_id=doc['personal_id']))

@app.route('/personal/documentos/eliminar/<int:doc_id>')
def eliminar_documento_personal(doc_id):
    db = get_db()
    doc = db.execute('SELECT * FROM documentos_personal WHERE id = ?', (doc_id,)).fetchone()
    
    if doc:
        if os.path.exists(doc['ruta_archivo']):
            os.remove(doc['ruta_archivo'])
        
        db.execute('DELETE FROM documentos_personal WHERE id = ?', (doc_id,))
        db.commit()
        
        flash('🗑️ Documento eliminado exitosamente', 'success')
        return redirect(url_for('listar_documentos_personal', personal_id=doc['personal_id']))
    
    flash('Documento no encontrado', 'error')
    return redirect(url_for('listar_personal'))

@app.route('/jardines/eliminar/<int:id>')
def eliminar_jardin(id):
    db = get_db()
    ninos = db.execute('SELECT COUNT(*) as count FROM ninos WHERE jardin_id = ?', (id,)).fetchone()
    if ninos['count'] > 0:
        flash('No se puede eliminar el jardín porque tiene niños matriculados', 'error')
    else:
        db.execute('DELETE FROM jardines WHERE id = ?', (id,))
        db.commit()
        flash('Jardín eliminado exitosamente', 'success')
    
    return redirect(url_for('listar_jardines'))

# ==================== MATRÍCULAS ====================
@app.route('/matriculas')
def listar_matriculas():
    db = get_db()
    page = request.args.get('page', 1, type=int)
    per_page = 20  # Registros por página
    query = request.args.get('q', '')
    
    offset = (page - 1) * per_page
    
    # Contar total
    if query:
        total = db.execute('''
            SELECT COUNT(*) as count FROM ninos n 
            JOIN jardines j ON n.jardin_id = j.id 
            WHERE n.nombre_completo LIKE ? OR n.documento_identidad LIKE ? OR j.nombre LIKE ?
        ''', (f'%{query}%', f'%{query}%', f'%{query}%')).fetchone()['count']
        
        matriculas_rows = db.execute('''
            SELECT n.*, j.nombre as jardin_nombre 
            FROM ninos n 
            JOIN jardines j ON n.jardin_id = j.id 
            WHERE n.nombre_completo LIKE ? OR n.documento_identidad LIKE ? OR j.nombre LIKE ?
            ORDER BY n.fecha_matricula DESC
            LIMIT ? OFFSET ?
        ''', (f'%{query}%', f'%{query}%', f'%{query}%', per_page, offset)).fetchall()
    else:
        total = db.execute('SELECT COUNT(*) as count FROM ninos').fetchone()['count']
        matriculas_rows = db.execute('''
            SELECT n.*, j.nombre as jardin_nombre 
            FROM ninos n 
            JOIN jardines j ON n.jardin_id = j.id 
            ORDER BY n.fecha_matricula DESC
            LIMIT ? OFFSET ?
        ''', (per_page, offset)).fetchall()
    
    matriculas = [dict(row) for row in matriculas_rows]
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('matriculas/listar.html', 
                         matriculas=matriculas,
                         page=page,
                         total_pages=total_pages,
                         total=total,
                         query=query,
                         per_page=per_page)

@app.route('/matriculas/crear', methods=['GET', 'POST'])
def crear_matricula():
    db = get_db()
    jardines = db.execute('SELECT id, nombre, capacidad FROM jardines WHERE estado = "Activo" ORDER BY nombre').fetchall()
    
    fecha_actual = datetime.now().strftime('%Y-%m-%d')
    
    if request.method == 'POST':
        # Datos del niño
        nombre_completo = request.form['nombre_completo']
        fecha_nacimiento = request.form['fecha_nacimiento']
        documento_identidad = request.form['documento_identidad']
        genero = request.form.get('genero', '')
        direccion = request.form.get('direccion', '')
        eps = request.form.get('eps', '')
        tipo_sangre = request.form.get('tipo_sangre', '')
        tiene_alergias = request.form.get('tiene_alergias', 'No')
        alergias_descripcion = request.form.get('alergias_descripcion', '') if tiene_alergias == 'Si' else ''
        jardin_id = int(request.form['jardin_id'])
        fecha_matricula = request.form['fecha_matricula']
        estrato = int(request.form.get('estrato', 3))
        apoyo_academico = request.form.get('apoyo_academico', 'No')
        autorizacion_foto = request.form.get('autorizacion_foto', 'No')
        observaciones = request.form.get('observaciones', '')
        
        # Datos del acudiente
        acudiente_nombre = request.form['acudiente_nombre']
        acudiente_documento = request.form['acudiente_documento']
        acudiente_telefono = request.form.get('acudiente_telefono', '')
        acudiente_email = request.form.get('acudiente_email', '')
        acudiente_direccion = request.form.get('acudiente_direccion', '')
        parentesco = request.form.get('parentesco', '')
        
        # Verificar capacidad
        jardin = db.execute('SELECT capacidad FROM jardines WHERE id = ?', (jardin_id,)).fetchone()
        matriculados = db.execute('SELECT COUNT(*) as count FROM ninos WHERE jardin_id = ? AND estado_matricula = "Activo"', (jardin_id,)).fetchone()
        
        if matriculados['count'] >= jardin['capacidad']:
            flash('❌ El jardín ha alcanzado su capacidad máxima', 'error')
            return render_template('matriculas/crear.html', jardines=jardines, fecha_actual=fecha_actual)
        
        try:
            cursor = db.execute('''
                INSERT INTO ninos (
                    nombre_completo, fecha_nacimiento, documento_identidad, genero, 
                    direccion, eps, tipo_sangre, tiene_alergias, alergias_descripcion,
                    jardin_id, fecha_matricula, estrato, apoyo_academico, autorizacion_foto, observaciones
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                nombre_completo, fecha_nacimiento, documento_identidad, genero, 
                direccion, eps, tipo_sangre, tiene_alergias, alergias_descripcion,
                jardin_id, fecha_matricula, estrato, apoyo_academico, autorizacion_foto, observaciones
            ))
            
            nino_id = cursor.lastrowid
            
            db.execute('''
                INSERT INTO acudientes (nombre_completo, documento_identidad, telefono, email, direccion, parentesco, nino_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (acudiente_nombre, acudiente_documento, acudiente_telefono, acudiente_email, 
                  acudiente_direccion, parentesco, nino_id))
            
            
            jardin_info = db.execute('SELECT nombre FROM jardines WHERE id = ?', (jardin_id,)).fetchone()
            nombre_jardin = jardin_info['nombre'] if jardin_info else "Jardín asignado"
            
            # ========== ENVIAR CORREO DE CONFIRMACIÓN ==========
            if acudiente_email and acudiente_email.strip():
                enviar_correo_matricula(
                    destinatario=acudiente_email,
                    nombre_nino=nombre_completo,
                    nombre_jardin=nombre_jardin,
                    fecha_matricula=fecha_matricula,
                    acudiente_nombre=acudiente_nombre
                )
                flash('✅ Matrícula creada exitosamente. Se ha enviado un correo de confirmación al acudiente.', 'success')
            else:
                flash('✅ Matrícula creada exitosamente. (No se envió correo porque no hay email registrado)', 'success')
            
            db.commit()
            return redirect(url_for('listar_matriculas'))
            
        except sqlite3.IntegrityError:
            flash('❌ Ya existe un niño con ese documento de identidad', 'error')
    
    return render_template('matriculas/crear.html', jardines=jardines, fecha_actual=fecha_actual)


@app.route('/matriculas/ver/<int:id>')
def ver_matricula(id):
    db = get_db()
    
    # Obtener datos del niño y su jardín
    matricula = db.execute('''
        SELECT n.*, j.nombre as jardin_nombre, j.direccion as jardin_direccion
        FROM ninos n 
        JOIN jardines j ON n.jardin_id = j.id 
        WHERE n.id = ?
    ''', (id,)).fetchone()
    
    # Validar si existe
    if matricula is None:
        flash('❌ Matrícula no encontrada', 'error')
        return redirect(url_for('listar_matriculas'))
    
    # Obtener acudiente
    acudiente = db.execute('SELECT * FROM acudientes WHERE nino_id = ?', (id,)).fetchone()
    
    # Contar documentos
    try:
        count = db.execute('SELECT COUNT(*) as count FROM documentos WHERE nino_id = ?', (id,)).fetchone()
        documentos_count = count['count'] if count else 0
    except:
        documentos_count = 0
    
    return render_template('matriculas/ver.html', 
                         matricula=dict(matricula), 
                         acudiente=dict(acudiente) if acudiente else None,
                         documentos_count=documentos_count)

@app.route('/matriculas/eliminar/<int:id>')
def eliminar_matricula(id):
    db = get_db()
    # Eliminar acudiente primero
    db.execute('DELETE FROM acudientes WHERE nino_id = ?', (id,))
    # Eliminar documentos (los archivos)
    docs = db.execute('SELECT ruta_archivo FROM documentos WHERE nino_id = ?', (id,)).fetchall()
    for doc in docs:
        if os.path.exists(doc['ruta_archivo']):
            os.remove(doc['ruta_archivo'])
    db.execute('DELETE FROM documentos WHERE nino_id = ?', (id,))
    # Eliminar niño
    db.execute('DELETE FROM ninos WHERE id = ?', (id,))
    db.commit()
    flash('🗑️ Matrícula eliminada exitosamente', 'success')
    return redirect(url_for('listar_matriculas'))

# ==================== PERSONAL ====================
@app.route('/personal')
def listar_personal():
    db = get_db()
    page = request.args.get('page', 1, type=int)
    per_page = 20
    query = request.args.get('q', '')
    
    offset = (page - 1) * per_page
    
    if query:
        total = db.execute('''
            SELECT COUNT(*) as count FROM personal p
            JOIN jardines j ON p.jardin_id = j.id
            WHERE p.nombre_completo LIKE ? 
               OR p.documento_identidad LIKE ? 
               OR p.cargo LIKE ?
               OR j.nombre LIKE ?
        ''', (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%')).fetchone()['count']
        
        personal_rows = db.execute('''
            SELECT p.*, j.nombre as jardin_nombre 
            FROM personal p
            JOIN jardines j ON p.jardin_id = j.id
            WHERE p.nombre_completo LIKE ? 
               OR p.documento_identidad LIKE ? 
               OR p.cargo LIKE ?
               OR j.nombre LIKE ?
            ORDER BY p.id DESC
            LIMIT ? OFFSET ?
        ''', (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%', per_page, offset)).fetchall()
    else:
        total = db.execute('SELECT COUNT(*) as count FROM personal').fetchone()['count']
        
        personal_rows = db.execute('''
            SELECT p.*, j.nombre as jardin_nombre 
            FROM personal p
            JOIN jardines j ON p.jardin_id = j.id
            ORDER BY p.id DESC
            LIMIT ? OFFSET ?
        ''', (per_page, offset)).fetchall()
    
    personal = [dict(row) for row in personal_rows]
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('personal/listar.html', 
                         personal=personal,
                         page=page,
                         total_pages=total_pages,
                         total=total,
                         query=query)

@app.route('/personal/crear', methods=['GET', 'POST'])
def crear_personal():
    db = get_db()
    jardines = db.execute('SELECT id, nombre FROM jardines WHERE estado = "Activo" ORDER BY nombre').fetchall()
    
    cargos = [
        'Directora(e)',
        'Coordinadora(e) Académica',
        'Psicóloga(o)',
        'Trabajadora(e) Social',
        'Profesora(e) de Preescolar',
        'Auxiliar de Aula',
        'Nutricionista',
        'Enfermera(o)',
        'Terapeuta Ocupacional',
        'Fonoaudióloga(o)',
        'Psicopedagoga(o)',
        'Coordinadora(e) de Convivencia',
        'Administrativa(o)',
        'Secretaria(o)',
        'Contadora(e)',
        'Mantenimiento',
        'Vigilante',
        'Conductora(e)',
        'Aseo y Cafetería',
        'Otro'
    ]
    
    if request.method == 'POST':
        nombre_completo = request.form['nombre_completo']
        documento_identidad = request.form['documento_identidad']
        tipo_documento = request.form.get('tipo_documento', 'CC')
        fecha_nacimiento = request.form.get('fecha_nacimiento') or None
        genero = request.form.get('genero', '')
        telefono = request.form.get('telefono', '')
        email = request.form.get('email', '')
        direccion = request.form.get('direccion', '')
        cargo = request.form['cargo']
        especialidad = request.form.get('especialidad', '')
        jardin_id = int(request.form['jardin_id'])
        fecha_contratacion = request.form['fecha_contratacion']
        salario = request.form.get('salario', '').replace(',', '') or None
        horario = request.form.get('horario', '')
        eps = request.form.get('eps', '')
        arl = request.form.get('arl', '')
        fondo_pension = request.form.get('fondo_pension', '')
        observaciones = request.form.get('observaciones', '')
        
        try:
            db.execute('''
                INSERT INTO personal (
                    nombre_completo, documento_identidad, tipo_documento, fecha_nacimiento,
                    genero, telefono, email, direccion, cargo, especialidad, jardin_id,
                    fecha_contratacion, salario, horario, eps, arl, fondo_pension, observaciones
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (nombre_completo, documento_identidad, tipo_documento, fecha_nacimiento,
                  genero, telefono, email, direccion, cargo, especialidad, jardin_id,
                  fecha_contratacion, salario, horario, eps, arl, fondo_pension, observaciones))
            db.commit()
            flash('✅ Personal creado exitosamente', 'success')
            return redirect(url_for('listar_personal'))
        except sqlite3.IntegrityError:
            flash('❌ Ya existe una persona con ese documento de identidad', 'error')
    
    return render_template('personal/crear.html', jardines=jardines, cargos=cargos)

@app.route('/personal/ver/<int:id>')
def ver_personal(id):
    db = get_db()
    persona = db.execute('''
        SELECT p.*, j.nombre as jardin_nombre 
        FROM personal p
        JOIN jardines j ON p.jardin_id = j.id
        WHERE p.id = ?
    ''', (id,)).fetchone()
    
    if not persona:
        flash('Personal no encontrado', 'error')
        return redirect(url_for('listar_personal'))
    
    # Contar documentos del empleado
    documentos_count = db.execute('SELECT COUNT(*) as count FROM documentos_personal WHERE personal_id = ?', (id,)).fetchone()['count']
    
    return render_template('personal/ver.html', persona=dict(persona), documentos_count=documentos_count)

@app.route('/personal/editar/<int:id>', methods=['GET', 'POST'])
def editar_personal(id):
    db = get_db()
    persona = db.execute('SELECT * FROM personal WHERE id = ?', (id,)).fetchone()
    jardines = db.execute('SELECT id, nombre FROM jardines WHERE estado = "Activo" ORDER BY nombre').fetchall()
    
    cargos = [
        'Directora(e)', 'Coordinadora(e) Académica', 'Psicóloga(o)', 'Trabajadora(e) Social',
        'Profesora(e) de Preescolar', 'Auxiliar de Aula', 'Nutricionista', 'Enfermera(o)',
        'Terapeuta Ocupacional', 'Fonoaudióloga(o)', 'Psicopedagoga(o)', 'Coordinadora(e) de Convivencia',
        'Administrativa(o)', 'Secretaria(o)', 'Contadora(e)', 'Mantenimiento', 'Vigilante',
        'Conductora(e)', 'Aseo y Cafetería', 'Otro'
    ]
    
    if request.method == 'POST':
        try:
            db.execute('''
                UPDATE personal SET
                    nombre_completo=?, documento_identidad=?, tipo_documento=?, fecha_nacimiento=?,
                    genero=?, telefono=?, email=?, direccion=?, cargo=?, especialidad=?,
                    jardin_id=?, fecha_contratacion=?, salario=?, horario=?, eps=?, arl=?,
                    fondo_pension=?, observaciones=?
                WHERE id=?
            ''', (
                request.form['nombre_completo'], request.form['documento_identidad'],
                request.form.get('tipo_documento', 'CC'), request.form.get('fecha_nacimiento') or None,
                request.form.get('genero', ''), request.form.get('telefono', ''),
                request.form.get('email', ''), request.form.get('direccion', ''),
                request.form['cargo'], request.form.get('especialidad', ''),
                int(request.form['jardin_id']), request.form['fecha_contratacion'],
                request.form.get('salario', '').replace(',', '') or None, request.form.get('horario', ''),
                request.form.get('eps', ''), request.form.get('arl', ''),
                request.form.get('fondo_pension', ''), request.form.get('observaciones', ''),
                id
            ))
            db.commit()
            flash('✅ Personal actualizado exitosamente', 'success')
            return redirect(url_for('listar_personal'))
        except sqlite3.IntegrityError:
            flash('❌ Ya existe una persona con ese documento de identidad', 'error')
    
    return render_template('personal/editar.html', persona=dict(persona), jardines=jardines, cargos=cargos)

@app.route('/personal/eliminar/<int:id>')
def eliminar_personal(id):
    db = get_db()
    db.execute('DELETE FROM personal WHERE id = ?', (id,))
    db.commit()
    flash('🗑️ Personal eliminado exitosamente', 'success')
    return redirect(url_for('listar_personal'))


# ==================== DOCUMENTOS ====================
@app.route('/documentos/<int:nino_id>')
def listar_documentos(nino_id):
    db = get_db()
    
    nino = db.execute('SELECT * FROM ninos WHERE id = ?', (nino_id,)).fetchone()
    if not nino:
        flash('Niño no encontrado', 'error')
        return redirect(url_for('listar_matriculas'))
    
    documentos = db.execute('''
        SELECT * FROM documentos 
        WHERE nino_id = ? 
        ORDER BY fecha_subida DESC
    ''', (nino_id,)).fetchall()
    
    return render_template('documentos/listar.html', 
                         nino=dict(nino), 
                         documentos=[dict(d) for d in documentos])

@app.route('/documentos/subir/<int:nino_id>', methods=['GET', 'POST'])
def subir_documento(nino_id):
    db = get_db()
    nino = db.execute('SELECT * FROM ninos WHERE id = ?', (nino_id,)).fetchone()
    
    if not nino:
        flash('Niño no encontrado', 'error')
        return redirect(url_for('listar_matriculas'))
    
    tipos_documento = [
        'Registro Civil de Nacimiento',
        'Tarjeta de Identidad',
        'Certificado de Vacunación',
        'Carnet EPS',
        'Autorización Médica',
        'Certificado de Afiliación EPS',
        'SISBEN',
        'Certificado de Discapacidad',
        'Autorización Fotográfica',
        'Historia Clínica',
        'Otros'
    ]
    
    if request.method == 'POST':
        tipo_documento = request.form['tipo_documento']
        fecha_vencimiento = request.form.get('fecha_vencimiento') or None
        observaciones = request.form.get('observaciones', '')
        
        if 'archivo' not in request.files:
            flash('No se seleccionó ningún archivo', 'error')
            return redirect(request.url)
        
        archivo = request.files['archivo']
        
        if archivo.filename == '':
            flash('No se seleccionó ningún archivo', 'error')
            return redirect(request.url)
        
        if archivo and allowed_file(archivo.filename):
            filename = secure_filename(archivo.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{nino_id}_{timestamp}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            archivo.save(filepath)
            
            db.execute('''
                INSERT INTO documentos (nino_id, tipo_documento, nombre_archivo, ruta_archivo, fecha_subida, fecha_vencimiento, observaciones)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (nino_id, tipo_documento, filename, filepath, datetime.now().strftime('%Y-%m-%d'), fecha_vencimiento, observaciones))
            db.commit()
            
            flash(f'📄 Documento "{tipo_documento}" subido exitosamente', 'success')
            return redirect(url_for('listar_documentos', nino_id=nino_id))
        else:
            flash('Tipo de archivo no permitido', 'error')
    
    return render_template('documentos/subir.html', nino=dict(nino), tipos_documento=tipos_documento)

@app.route('/documentos/ver/<int:doc_id>')
def ver_documento(doc_id):
    db = get_db()
    doc = db.execute('SELECT * FROM documentos WHERE id = ?', (doc_id,)).fetchone()
    
    if not doc:
        flash('Documento no encontrado', 'error')
        return redirect(url_for('listar_matriculas'))
    
    if os.path.exists(doc['ruta_archivo']):
        return send_from_directory(
            os.path.dirname(doc['ruta_archivo']), 
            os.path.basename(doc['ruta_archivo'])
        )
    else:
        flash('El archivo no existe en el servidor', 'error')
        return redirect(url_for('listar_documentos', nino_id=doc['nino_id']))

@app.route('/documentos/eliminar/<int:doc_id>')
def eliminar_documento(doc_id):
    db = get_db()
    doc = db.execute('SELECT * FROM documentos WHERE id = ?', (doc_id,)).fetchone()
    
    if doc:
        if os.path.exists(doc['ruta_archivo']):
            os.remove(doc['ruta_archivo'])
        
        db.execute('DELETE FROM documentos WHERE id = ?', (doc_id,))
        db.commit()
        
        flash('🗑️ Documento eliminado exitosamente', 'success')
        return redirect(url_for('listar_documentos', nino_id=doc['nino_id']))
    
    flash('Documento no encontrado', 'error')
    return redirect(url_for('listar_matriculas'))

init_db()
init_security_db(get_db)
install_security(app, get_db)

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Iniciando servidor SDIS Dashboard")
    print("📱 Accede en: http://127.0.0.1:5000")
    print("🏡 Jardines: http://127.0.0.1:5000/jardines")
    print("📝 Matrículas: http://127.0.0.1:5000/matriculas")
    print("🛑 Presiona CTRL+C para detener")
    print("=" * 50)
    app.run(debug=True, host='127.0.0.1', port=5000)