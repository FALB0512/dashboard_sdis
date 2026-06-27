import sqlite3
import os

DATABASE = 'sdis_dashboard.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Crea las tablas necesarias"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Tabla de jardines
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jardines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            direccion TEXT NOT NULL,
            localidad TEXT NOT NULL,
            estado TEXT DEFAULT 'Activo',
            capacidad INTEGER NOT NULL,
            telefono TEXT,
            encargado TEXT,
            email TEXT
        )
    ''')
    
    # Tabla de niños
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ninos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_completo TEXT NOT NULL,
            fecha_nacimiento DATE NOT NULL,
            documento_identidad TEXT UNIQUE NOT NULL,
            genero TEXT,
            direccion TEXT,
            eps TEXT,
            tipo_sangre TEXT,
            tiene_alergias TEXT DEFAULT 'No',
            alergias_descripcion TEXT,
            jardin_id INTEGER,
            fecha_matricula DATE NOT NULL,
            estado_matricula TEXT DEFAULT 'Activo',
            estrato INTEGER DEFAULT 3,
            apoyo_academico TEXT DEFAULT 'No',
            autorizacion_foto TEXT DEFAULT 'No',
            observaciones TEXT,
            FOREIGN KEY (jardin_id) REFERENCES jardines (id)
        )
    ''')
    
    # Tabla de acudientes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS acudientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_completo TEXT NOT NULL,
            documento_identidad TEXT UNIQUE NOT NULL,
            telefono TEXT,
            email TEXT,
            direccion TEXT,
            parentesco TEXT,
            nino_id INTEGER,
            FOREIGN KEY (nino_id) REFERENCES ninos (id)
        )
    ''')

# Agrega esta tabla después de la tabla de acudientes

# Tabla de personal
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS personal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre_completo TEXT NOT NULL,
        documento_identidad TEXT UNIQUE NOT NULL,
        tipo_documento TEXT DEFAULT 'CC',
        fecha_nacimiento DATE,
        genero TEXT,
        telefono TEXT,
        email TEXT,
        direccion TEXT,
        cargo TEXT NOT NULL,
        especialidad TEXT,
        jardin_id INTEGER NOT NULL,
        fecha_contratacion DATE NOT NULL,
        salario DECIMAL(10,2),
        horario TEXT,
        estado TEXT DEFAULT 'Activo',
        eps TEXT,
        arl TEXT,
        fondo_pension TEXT,
        observaciones TEXT,
        FOREIGN KEY (jardin_id) REFERENCES jardines (id)
    )
''')
        
    # NUEVA TABLA: Documentos del niño
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nino_id INTEGER NOT NULL,
            tipo_documento TEXT NOT NULL,
            nombre_archivo TEXT NOT NULL,
            ruta_archivo TEXT NOT NULL,
            fecha_subida DATE NOT NULL,
            fecha_vencimiento DATE,
            estado TEXT DEFAULT 'Activo',
            observaciones TEXT,
            FOREIGN KEY (nino_id) REFERENCES ninos (id) ON DELETE CASCADE
        )
    ''')

    # Agrega esta tabla después de la tabla de documentos

# Tabla de documentos del personal
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS documentos_personal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        personal_id INTEGER NOT NULL,
        tipo_documento TEXT NOT NULL,
        nombre_archivo TEXT NOT NULL,
        ruta_archivo TEXT NOT NULL,
        fecha_subida DATE NOT NULL,
        fecha_vencimiento DATE,
        estado TEXT DEFAULT 'Activo',
        observaciones TEXT,
        FOREIGN KEY (personal_id) REFERENCES personal (id) ON DELETE CASCADE
    )
''')
    
    # Insertar datos de ejemplo si la tabla está vacía
    cursor.execute("SELECT COUNT(*) FROM jardines")
    if cursor.fetchone()[0] == 0:
        jardines_ejemplo = [
            ("Jardín Infantil Paraiso", "Carrera 27L, No. 71G - 14 Sur", "Ciudad Bolívar", "Activo", 140),
            ("Jardín Infantil Minuto de María", "Carrera 18A Bis B No. 80A - 21 Sur", "Ciudad Bolívar", "Activo", 140),
            ("Jardín Infantil Arborizadora Alta", "Transversal 35 No. 69M - 85 Sur", "Ciudad Bolívar", "Activo", 140),
            ("Jardín Infantil Cartagena de Indias", "Diagonal 70 Sur No. 56 - 12", "Ciudad Bolívar", "Activo", 140),
            ("Jardín Infantil Anául Verbenal Quiba", "Verbenal Quiba", "Ciudad Bolívar", "Activo", 140),
            ("Jardín Infantil La Estrella", "Carrera 18G No. 74A - 75 Sur", "Ciudad Bolívar", "Activo", 140),
            ("Jardín Infantil Luna Lunea Nocturno", "Carrera 74G No. 59A - 87 Sur", "Ciudad Bolívar", "Activo", 140),
            ("Jardín Infantil Dejando Huella", "Calle 91C Sur No. 18H - 14", "Ciudad Bolívar", "Activo", 140),
            ("Jardín Infantil Noches de Cartagena", "Calle 70 Sur No. 56 - 04", "Ciudad Bolívar", "Activo", 140),
            ("Jardín Infantil Montaña de Colores", "Pasquilla, Finca La Floresta", "Ciudad Bolívar", "Activo", 140),
        ]
        cursor.executemany('''
            INSERT INTO jardines (nombre, direccion, localidad, estado, capacidad)
            VALUES (?, ?, ?, ?, ?)
        ''', jardines_ejemplo)
    
    # Módulo PQRS
    cursor.execute("""CREATE TABLE IF NOT EXISTS pqrs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, radicado TEXT NOT NULL UNIQUE, codigo_consulta TEXT NOT NULL,
        tipo TEXT NOT NULL, nombre_solicitante TEXT, documento TEXT, correo TEXT, telefono TEXT,
        asunto TEXT NOT NULL, descripcion TEXT NOT NULL, estado TEXT NOT NULL DEFAULT 'Recibida',
        prioridad TEXT NOT NULL DEFAULT 'Media', anonima INTEGER NOT NULL DEFAULT 0, responsable_id INTEGER,
        respuesta TEXT, fecha_radicacion TEXT NOT NULL, fecha_limite TEXT, fecha_respuesta TEXT,
        fecha_cierre TEXT, fecha_actualizacion TEXT, FOREIGN KEY (responsable_id) REFERENCES usuarios(id)
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS pqrs_historial (
        id INTEGER PRIMARY KEY AUTOINCREMENT, pqrs_id INTEGER NOT NULL, usuario_id INTEGER, fecha_hora TEXT NOT NULL,
        accion TEXT NOT NULL, estado_anterior TEXT, estado_nuevo TEXT, detalle TEXT, actor TEXT,
        visible_ciudadano INTEGER NOT NULL DEFAULT 1, FOREIGN KEY (pqrs_id) REFERENCES pqrs(id) ON DELETE CASCADE
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS pqrs_adjuntos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, pqrs_id INTEGER NOT NULL, nombre_original TEXT NOT NULL,
        nombre_archivo TEXT NOT NULL, ruta_archivo TEXT NOT NULL, fecha_subida TEXT NOT NULL, publico INTEGER DEFAULT 0,
        FOREIGN KEY (pqrs_id) REFERENCES pqrs(id) ON DELETE CASCADE
    )""")
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pqrs_radicado ON pqrs(radicado)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pqrs_estado ON pqrs(estado)')

    # Módulo de Comunicaciones / Gestión Documental
    cursor.execute("""CREATE TABLE IF NOT EXISTS comunicaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT, radicado TEXT UNIQUE, tipo TEXT NOT NULL, asunto TEXT NOT NULL,
        descripcion TEXT NOT NULL, remitente_externo TEXT, radicado_externo TEXT, prioridad TEXT DEFAULT 'Media',
        confidencial INTEGER DEFAULT 0, requiere_respuesta INTEGER DEFAULT 0, fecha_limite TEXT, estado TEXT DEFAULT 'Borrador',
        creado_por INTEGER NOT NULL, responsable_id INTEGER, fecha_creacion TEXT NOT NULL, fecha_radicacion TEXT,
        fecha_actualizacion TEXT, numero_folios INTEGER DEFAULT 0, medio TEXT, observaciones TEXT, documento_origen_id INTEGER,
        justificacion_archivo TEXT, resultado_tramite TEXT, expediente TEXT, fecha_archivo TEXT, archivado_por INTEGER,
        FOREIGN KEY(creado_por) REFERENCES usuarios(id), FOREIGN KEY(responsable_id) REFERENCES usuarios(id),
        FOREIGN KEY(documento_origen_id) REFERENCES comunicaciones(id), FOREIGN KEY(archivado_por) REFERENCES usuarios(id)
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS comunicacion_destinatarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT, comunicacion_id INTEGER NOT NULL, usuario_id INTEGER NOT NULL,
        tipo_destinatario TEXT DEFAULT 'Principal', leido_en TEXT,
        UNIQUE(comunicacion_id,usuario_id), FOREIGN KEY(comunicacion_id) REFERENCES comunicaciones(id) ON DELETE CASCADE,
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS comunicacion_movimientos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, comunicacion_id INTEGER NOT NULL, usuario_id INTEGER,
        fecha_hora TEXT NOT NULL, accion TEXT NOT NULL, detalle TEXT, estado_anterior TEXT, estado_nuevo TEXT,
        FOREIGN KEY(comunicacion_id) REFERENCES comunicaciones(id) ON DELETE CASCADE, FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS comunicacion_adjuntos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, comunicacion_id INTEGER NOT NULL, nombre_original TEXT NOT NULL,
        nombre_archivo TEXT NOT NULL, ruta_archivo TEXT NOT NULL, fecha_subida TEXT NOT NULL, subido_por INTEGER,
        version INTEGER DEFAULT 1, vigente INTEGER DEFAULT 1,
        FOREIGN KEY(comunicacion_id) REFERENCES comunicaciones(id) ON DELETE CASCADE, FOREIGN KEY(subido_por) REFERENCES usuarios(id)
    )""")
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_com_radicado ON comunicaciones(radicado)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_com_estado ON comunicaciones(estado)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_com_responsable ON comunicaciones(responsable_id)')

    conn.commit()
    conn.close()
    print("Base de datos inicializada correctamente")

if not os.path.exists(DATABASE):
    init_db()