from extensions import db
from flask_login import UserMixin # type: ignore
from datetime import datetime
from sqlalchemy.schema import UniqueConstraint # Para asegurar la unicidad del Curso

# Clase para modelar las Carreras
class Carrera(db.Model):
    __tablename__ = "carreras"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    campus = db.Column(db.String(50), nullable=False) 

# Clase para modelar a los Docentes (Usuarios)
class Docente(UserMixin, db.Model):
    __tablename__ = "docentes"
    id = db.Column(db.Integer, primary_key=True)
    numero_nomina = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(120), nullable=False)
    campus = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    
    # Relación con la tabla Carrera
    carrera_id = db.Column(db.Integer, db.ForeignKey("carreras.id"), nullable=False)
    carrera = db.relationship("Carrera", backref=db.backref("docentes", lazy=True))

    # 🚨 CAMBIO CLAVE (se elimina la relación directa Docente.materias)
    cursos_impartidos = db.relationship("Curso", backref="docente", lazy=True)
    reportes = db.relationship("Reporte", backref="docente", lazy=True)
    
    # NUEVA RELACIÓN: Para ver todos los archivos subidos por este docente
    archivos_subidos = db.relationship("Archivo", backref="docente", lazy=True)

# Clase para modelar las Materias (Concepto global: No necesita FK a Docente)
class Materia(db.Model):
    __tablename__ = "materias"
    id = db.Column(db.Integer, primary_key=True)
    # Hacemos que la materia sea única por nombre
    nombre = db.Column(db.String(120), unique=True, nullable=False) 
    
    cursos = db.relationship("Curso", backref="materia", lazy=True)

# Clase para modelar a los Alumnos
class Alumno(db.Model):
    __tablename__ = "alumnos"
    id = db.Column(db.Integer, primary_key=True)
    numero_control = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)

    # Relaciones
    cursos = db.relationship("Curso", secondary="curso_alumno", back_populates="alumnos")
    reportes = db.relationship("Reporte", backref="alumno", lazy=True)

# Tabla de relación para la asociación de Alumno y Curso (muchos a muchos)
curso_alumno = db.Table("curso_alumno",
    db.Column("curso_id", db.Integer, db.ForeignKey("cursos.id"), primary_key=True),
    db.Column("alumno_id", db.Integer, db.ForeignKey("alumnos.id"), primary_key=True)
)

# Clase para modelar los Cursos (la instancia de Materia + Periodo + Docente)
class Curso(db.Model):
    __tablename__ = "cursos"
    id = db.Column(db.Integer, primary_key=True)
    docente_id = db.Column(db.Integer, db.ForeignKey("docentes.id"), nullable=False)
    materia_id = db.Column(db.Integer, db.ForeignKey("materias.id"), nullable=False)
    
    # NUEVO: Campo para el Periodo (ej. 2024-2025A)
    periodo = db.Column(db.String(50), nullable=False) 

    # Restricción: Un Docente no puede tener la misma Materia en el mismo Periodo dos veces
    __table_args__ = (db.UniqueConstraint('docente_id', 'materia_id', 'periodo', name='_docente_materia_periodo_uc'),)

    # Relaciones
    alumnos = db.relationship("Alumno", secondary=curso_alumno, back_populates="cursos")
    reportes = db.relationship("Reporte", backref="curso", lazy=True)
    
    # NUEVA RELACIÓN INVERSA: Para que un Curso pueda ver sus archivos
    archivos_adjuntos = db.relationship("Archivo", backref="curso", lazy=True)

# Clase para modelar los Reportes
class Reporte(db.Model):
    __tablename__ = "reportes"
    id = db.Column(db.Integer, primary_key=True)
    docente_id = db.Column(db.Integer, db.ForeignKey("docentes.id"), nullable=False)
    curso_id = db.Column(db.Integer, db.ForeignKey("cursos.id"), nullable=False)
    alumno_id = db.Column(db.Integer, db.ForeignKey("alumnos.id"), nullable=False)
    
    observaciones = db.Column(db.Text, nullable=False)
    fecha_reporte = db.Column(db.DateTime, default=datetime.utcnow)

# CLAVE: Modelo Archivo con referencias a Docente y Curso
class Archivo(db.Model):
    __tablename__ = "archivos"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(255), unique=True, nullable=False)
    fecha_subida = db.Column(db.DateTime, default=datetime.utcnow)

    # Referencia al Docente que subió el archivo
    docente_id = db.Column(db.Integer, db.ForeignKey("docentes.id"), nullable=False)
    # Referencia al Curso (Materia + Periodo)
    curso_id = db.Column(db.Integer, db.ForeignKey("cursos.id"), nullable=False)