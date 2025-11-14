# dashboard.py

from flask import Blueprint, render_template, redirect, url_for # type: ignore
from flask_login import login_required, current_user # type: ignore

# Definición del Blueprint para las rutas del dashboard
dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

@dashboard_bp.route("/")
@login_required
def home():
    """Muestra la página principal del docente (dashboard)."""
    # 'current_user' es inyectado por Flask-Login
    return render_template("dashboard.html", docente=current_user)

@dashboard_bp.route("/reports")
@login_required
def reports():
    """
    Ruta para mostrar la página de reportes.
    El endpoint es 'dashboard.reports'
    """
    # Se necesita crear la plantilla 'reports.html'
    return render_template("reports.html")