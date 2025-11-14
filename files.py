from flask import Blueprint, request, send_from_directory, jsonify, render_template, abort # type: ignore
from flask_login import login_required, current_user  # type: ignore
from werkzeug.utils import secure_filename 
import os
# Eliminamos la importación de sqlite3
from datetime import datetime
# Importamos SQLAlchemy y los modelos
from extensions import db
from models import Archivo, Materia, Curso, Docente 
from sqlalchemy.exc import IntegrityError, OperationalError 

# Definición del Blueprint para las rutas de archivos
files_bp = Blueprint("files", __name__, url_prefix="/files")

# --- Configuración ---
UPLOAD_FOLDER = 'uploads'
# Eliminamos DB_PATH = 'Documentos.db'

# Crear la carpeta de subida si no existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Rutas de Vistas y Gestión ---

@files_bp.route("/")
@login_required
def manage_files():
    """Ruta para mostrar la página de gestión de archivos (files.html)."""
    return render_template("files.html")

@files_bp.route("/data_for_upload")
@login_required
def data_for_upload():
    """Ruta (API) para obtener la lista de materias y periodos existentes para autocompletar."""
    try:
        # Obtener todas las materias existentes
        materias = Materia.query.all()
        materias_list = [{"id": m.id, "nombre": m.nombre} for m in materias]

        # Obtener todos los periodos únicos de los cursos del docente actual
        periodos_unicos = db.session.query(Curso.periodo)\
                                   .filter(Curso.docente_id == current_user.id)\
                                   .distinct()\
                                   .all()
        periodos_list = [p[0] for p in periodos_unicos]

        return jsonify({
            "materias": materias_list,
            "periodos": periodos_list
        })
    except OperationalError:
        # Esto puede ocurrir si las tablas aún no se han creado
        return jsonify({"error": "Las tablas de la base de datos no están inicializadas.", "materias": [], "periodos": []}), 500
    except Exception as e:
        return jsonify({"error": f"Error al obtener datos: {str(e)}", "materias": [], "periodos": []}), 500


@files_bp.route('/upload', methods=['POST'])
@login_required
def upload():
    """Ruta (API) para subir archivos con metadatos."""
    
    # 1. Obtener datos del formulario
    file = request.files.get('file')
    nombre_materia_raw = request.form.get('materia')
    periodo_raw = request.form.get('periodo')
    
    if not file or file.filename == '':
        return 'No se encontró el archivo o el nombre está vacío.', 400
    if not nombre_materia_raw or not periodo_raw:
        return 'Faltan datos de Materia o Periodo.', 400

    nombre_materia = nombre_materia_raw.strip()
    periodo = periodo_raw.strip()

    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    try:
        # 3.1. Buscar/Crear la Materia (concepto)
        materia = Materia.query.filter_by(nombre=nombre_materia).first()
        if not materia:
            materia = Materia(nombre=nombre_materia)
            db.session.add(materia)
            db.session.flush() # Obtiene el ID antes del commit

        # 3.2. Buscar/Crear el Curso (instancia: Docente + Materia + Periodo)
        curso = Curso.query.filter_by(
            docente_id=current_user.id,
            materia_id=materia.id,
            periodo=periodo
        ).first()

        if not curso:
            curso = Curso(
                docente_id=current_user.id,
                materia_id=materia.id,
                periodo=periodo
            )
            db.session.add(curso)
            db.session.flush()

        # 4. Guardar archivo físico
        file.save(filepath)

        # 5. Registrar/Actualizar en la DB (Modelo Archivo)
        archivo_existente = Archivo.query.filter_by(nombre=filename).first()
        
        if archivo_existente:
            archivo_existente.fecha_subida = datetime.utcnow()
            archivo_existente.docente_id = current_user.id
            archivo_existente.curso_id = curso.id
            mensaje = f'Archivo actualizado y asignado a {materia.nombre} - {periodo}.'
        else:
            nuevo_archivo = Archivo(
                nombre=filename,
                fecha_subida=datetime.utcnow(),
                docente_id=current_user.id,
                curso_id=curso.id          
            )
            db.session.add(nuevo_archivo)
            mensaje = f'Archivo subido y asignado a {materia.nombre} - {periodo}.'
            
        db.session.commit()
        return mensaje
        
    except IntegrityError:
        db.session.rollback()
        if os.path.exists(filepath): os.remove(filepath)
        return "Error: Ya existe un archivo con ese nombre.", 500
    except Exception as e:
        db.session.rollback()
        if os.path.exists(filepath): os.remove(filepath)
        return f"Error al registrar en DB: {str(e)}. Archivo eliminado del disco.", 500


@files_bp.route('/list', methods=['GET'])
@login_required
def list_files():
    """Ruta para listar archivos subidos con metadatos."""
    search_query = request.args.get('search', '').lower()
    
    # Consulta avanzada usando JOINs de SQLAlchemy para obtener todos los metadatos
    query = db.session.query(
        Archivo.nombre,
        Archivo.fecha_subida,
        Docente.nombre.label('docente_nombre'),
        Materia.nombre.label('materia_nombre'),
        Curso.periodo
    ).join(Docente, Archivo.docente_id == Docente.id)\
     .join(Curso, Archivo.curso_id == Curso.id)\
     .join(Materia, Curso.materia_id == Materia.id)\
     .order_by(Archivo.fecha_subida.desc())

    if search_query:
        # Filtro de búsqueda por nombre de archivo, materia o periodo
        query = query.filter(
            (Archivo.nombre.ilike(f"%{search_query}%")) | 
            (Materia.nombre.ilike(f"%{search_query}%")) |
            (Curso.periodo.ilike(f"%{search_query}%"))
        )
        
    files_list = []
    for row in query.all():
        # 4. (IMPORTANTE) Verificar que el archivo físico también exista
        if os.path.exists(os.path.join(UPLOAD_FOLDER, row.nombre)):
            files_list.append({
                "nombre": row.nombre,
                "fecha_subida": row.fecha_subida.strftime("%d/%m/%Y %H:%M"),
                "docente": row.docente_nombre,
                "materia": row.materia_nombre,
                "periodo": row.periodo,
                "etiqueta_curso": f"{row.materia_nombre} ({row.periodo})"
            })
            
    return jsonify(files_list)

@files_bp.route('/view/<filename>')
@login_required
def view_file(filename):
    """Ruta para mostrar el archivo PDF directamente en el navegador."""
    try:
        return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=False)
    except FileNotFoundError:
        abort(404)

@files_bp.route('/downloads/<filename>')
@login_required
def download_file(filename):
    """Ruta para descargar el archivo (fuerza la descarga)."""
    try:
        return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)
    except FileNotFoundError:
        abort(404)
        
@files_bp.route('/delete/<filename>', methods=['DELETE'])
@login_required
def delete_file(filename):
    """Ruta para eliminar un archivo (físico y lógico)."""
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    # 1. Eliminar de la DB primero
    archivo_db = Archivo.query.filter_by(nombre=filename).first()
    
    if archivo_db:
        db.session.delete(archivo_db)
        db.session.commit()
    
    # 2. Eliminar del sistema de archivos
    if os.path.exists(filepath):
        os.remove(filepath)
        return 'Archivo eliminado correctamente.', 200
        
    return 'Registro eliminado, pero el archivo físico no fue encontrado.', 202

@files_bp.route('/rename', methods=['PUT'])
@login_required
def rename_file():
    """Ruta para renombrar un archivo (físico y lógico)."""
    data = request.get_json(force=True)
    if not data:
        return "No se recibió información JSON.", 400

    old_name = data.get("old_name")
    new_name_raw = data.get("new_name")
    
    if not old_name or not new_name_raw:
        return "Se requiere el nombre antiguo y el nuevo nombre", 400
        
    clean_new_name = secure_filename(new_name_raw)

    if not clean_new_name.lower().endswith('.pdf'):
        final_new_name = clean_new_name + ".pdf"
    else:
        final_new_name = clean_new_name

    old_path = os.path.join(UPLOAD_FOLDER, old_name)
    new_path = os.path.join(UPLOAD_FOLDER, final_new_name)

    if not os.path.exists(old_path):
        return "El archivo original no existe.", 404
    if os.path.exists(new_path):
        return "Ya existe un archivo físico con ese nuevo nombre.", 400

    # 1. Buscar y validar en la DB
    archivo_db = Archivo.query.filter_by(nombre=old_name).first()
    if not archivo_db:
        return "Error: El archivo no se encontró en la base de datos.", 404
        
    if Archivo.query.filter_by(nombre=final_new_name).first():
        return "Ya existe un registro en la DB con ese nuevo nombre.", 400

    # 2. Renombrar en el sistema de archivos (Físico)
    try:
        os.rename(old_path, new_path)
    except Exception as e:
        return f"Error en el sistema de archivos: {str(e)}", 500
    
    # 3. Actualizar en la base de datos (Lógico)
    try:
        archivo_db.nombre = final_new_name 
        db.session.commit()
        return f"Archivo renombrado a {final_new_name}."
    except Exception as e:
        db.session.rollback()
        # ¡Reversión! Si falla la DB, deshace el renombrado físico
        os.rename(new_path, old_path) 
        return f"Error al actualizar la DB: {str(e)}. Se revirtió el cambio en el disco.", 500