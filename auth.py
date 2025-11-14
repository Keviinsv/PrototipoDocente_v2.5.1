from flask import Blueprint, render_template, redirect, url_for, request, flash # type: ignore
from flask_login import login_user, logout_user, login_required, current_user  # type: ignore
from extensions import db, bcrypt, login_manager
from models import Docente, Carrera
from datetime import datetime
from sqlalchemy.exc import IntegrityError # 🚨 IMPORTACIÓN CLAVE PARA ROBUSTEZ EN DB

# Definición del Blueprint para las rutas de autenticación
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# Función de carga de usuario para Flask-Login
@login_manager.user_loader
def load_user(user_id):
    """Carga un usuario dado su ID para Flask-Login."""
    return Docente.query.get(int(user_id))

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Maneja el inicio de sesión del docente."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))
        
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = Docente.query.filter_by(email=email).first()
        # Verifica usuario y contraseña (hash)
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            flash(f"Bienvenido, {user.nombre.split()[0]}.", "success")
            # Redirige a la página principal del dashboard
            return redirect(url_for("dashboard.home")) 
        else:
            flash("Credenciales inválidas. Verifica tu correo y contraseña.", "danger")
    # Si es GET o fallo de POST, muestra el formulario de login
    return render_template("login.html")

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Maneja el registro de nuevos docentes."""
    carreras = Carrera.query.all()
    
    if request.method == "POST":
        # Recolección de datos
        numero_nomina = request.form.get("numero_nomina", "").strip() # 🚨 Limpieza
        nombre = request.form.get("nombre", "").strip() # 🚨 Limpieza
        campus = request.form.get("campus")
        carrera_id = request.form.get("carrera_id")
        email = request.form.get("email", "").strip() # 🚨 Limpieza
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # 🚨 ROBUSTEZ 1: Validar datos requeridos en el servidor
        if not all([numero_nomina, nombre, campus, carrera_id, email, password, confirm_password]):
            flash("Todos los campos marcados son obligatorios.", "danger")
            # Devolver el template con los datos del formulario (request.form)
            return render_template("register.html", all_carreras=carreras)

        # 🚨 ROBUSTEZ 2: Validar contraseñas
        if password != confirm_password:
            flash("Las contraseñas no coinciden. Por favor, revísalas.", "danger")
            return render_template("register.html", all_carreras=carreras)
            
        # 🚨 ROBUSTEZ 3: Validar que la carrera exista y sea un ID válido
        try:
            carrera_id_int = int(carrera_id)
            if not Carrera.query.get(carrera_id_int):
                raise ValueError("Carrera no encontrada o ID inválido.")
        except (ValueError, TypeError):
            flash("Selección de carrera inválida. Inténtalo de nuevo.", "danger")
            return render_template("register.html", all_carreras=carreras)


        # Creación del nuevo docente
        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
        
        nuevo_docente = Docente(
            numero_nomina=numero_nomina,
            nombre=nombre,
            campus=campus, 
            carrera_id=carrera_id_int, # Usar el ID entero validado
            email=email,
            password=hashed_password
        )

        try:
            db.session.add(nuevo_docente)
            db.session.commit()
            flash("Registro exitoso. ¡Ahora puedes iniciar sesión!", "success")
            return redirect(url_for("auth.login"))
        except IntegrityError:
            db.session.rollback()
            # 🚨 Mensaje más útil en caso de duplicidad
            if Docente.query.filter_by(numero_nomina=numero_nomina).first():
                flash("Error: El número de nómina ya está registrado.", "danger")
            elif Docente.query.filter_by(email=email).first():
                flash("Error: El correo electrónico ya está registrado.", "danger")
            else:
                 flash("Ocurrió un error de integridad de datos desconocido.", "danger")

            return render_template("register.html", all_carreras=carreras)
        except Exception as e:
            db.session.rollback()
            flash(f"Ocurrió un error inesperado al registrar: {str(e)}", "danger")

    return render_template("register.html", all_carreras=carreras)

@auth_bp.route("/logout")
@login_required
def logout():
    """Cierra la sesión del docente."""
    logout_user()
    flash("Has cerrado sesión exitosamente.", "info")
    return redirect(url_for("auth.login"))

@auth_bp.route("/edit_profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    """Maneja la edición del perfil del docente."""
    docente = current_user
    carreras = Carrera.query.all()

    if request.method == "POST":
        # Recolección y limpieza de datos
        numero_nomina = request.form.get("numero_nomina", "").strip()
        nombre = request.form.get("nombre", "").strip()
        campus = request.form.get("campus")
        carrera_id_str = request.form.get("carrera_id")
        email = request.form.get("email", "").strip()
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # 🚨 ROBUSTEZ 1: Validar datos requeridos
        if not all([numero_nomina, nombre, campus, carrera_id_str, email]):
            flash("Todos los campos marcados son obligatorios.", "danger")
            return render_template("edit_profile.html", docente=docente, all_carreras=carreras)


        # 🚨 ROBUSTEZ 2: Validar contraseñas
        if password or confirm_password:
            if password != confirm_password:
                flash("Las contraseñas no coinciden. La contraseña no ha sido cambiada.", "danger")
                return render_template("edit_profile.html", docente=docente, all_carreras=carreras)
            
        # 🚨 ROBUSTEZ 3: Validar Carrera ID
        try:
            carrera_id_int = int(carrera_id_str)
            if not Carrera.query.get(carrera_id_int):
                raise ValueError("Carrera no encontrada o ID inválido.")
        except (ValueError, TypeError):
            flash("Selección de carrera inválida. Inténtalo de nuevo.", "danger")
            return render_template("edit_profile.html", docente=docente, all_carreras=carreras)


        # 🚨 Aplicar Actualización de campos
        docente.numero_nomina = numero_nomina
        docente.nombre = nombre
        docente.campus = campus
        docente.carrera_id = carrera_id_int # Usar el ID entero validado
        docente.email = email

        # La contraseña solo se actualiza si se proporciona una nueva y válida
        if password and password == confirm_password:
            docente.password = bcrypt.generate_password_hash(password).decode("utf-8")
        
        try:
            db.session.commit()
            flash("Perfil actualizado exitosamente.", "success")
            return redirect(url_for("dashboard.home"))
        except IntegrityError:
            db.session.rollback()
            # 🚨 Manejo de duplicidad de campos (Nómina/Email)
            q_nomina = Docente.query.filter_by(numero_nomina=numero_nomina).first()
            q_email = Docente.query.filter_by(email=email).first()
            
            if q_nomina and q_nomina.id != docente.id:
                 flash("Error: El número de nómina ya está registrado por otro usuario.", "danger")
            elif q_email and q_email.id != docente.id:
                 flash("Error: El correo electrónico ya está registrado por otro usuario.", "danger")
            else:
                 flash("Ocurrió un error de integridad de datos desconocido.", "danger")
                 
            return render_template("edit_profile.html", docente=docente, all_carreras=carreras)
        except Exception as e:
            db.session.rollback()
            flash(f"Ocurrió un error inesperado al actualizar el perfil: {str(e)}", "danger")
            return render_template("edit_profile.html", docente=docente, all_carreras=carreras)

    return render_template("edit_profile.html", docente=docente, all_carreras=carreras)

@auth_bp.route("/delete_account", methods=["POST"])
@login_required
def delete_account():
    """Maneja la eliminación de la cuenta del docente."""
    docente = current_user
    # Primero cerrar la sesión
    logout_user() 
    
    try:
        # 🚨 ROBUSTEZ: Asegurar la eliminación en cascada si es necesario, 
        # o manejar las relaciones antes de la eliminación del docente.
        # Por ahora, confiamos en que SQLAlchemy maneja las dependencias o no existen
        # reportes, cursos o materias que impidan el borrado por restricciones de FK.
        db.session.delete(docente)
        db.session.commit()
        flash("Tu cuenta ha sido eliminada permanentemente.", "info")
        return redirect(url_for("auth.login"))
    except Exception as e:
        db.session.rollback()
        flash(f"Ocurrió un error al intentar eliminar tu cuenta: {str(e)}. Por favor, contacta a soporte.", "danger")
        # Si la eliminación falla, redirige al login, ya que el logout ya se hizo.
        return redirect(url_for("auth.login"))