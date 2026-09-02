import os
import re
import sqlite3
import resend
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_cors import CORS
from dotenv import load_dotenv
import mercadopago

load_dotenv()
resend.api_key = os.getenv("RESEND_API_KEY")

app = Flask(__name__, template_folder='.')
CORS(app)

# --- SEGURIDAD Y CONTRASEÑA ---
app.secret_key = "clave_secreta_super_segura_dra_furlan"
PASSWORD_DOCTORA = "Furlan2026"

# --- CONFIGURACIÓN DE BASE DE DATOS SQLITE ---
DB_NAME = "consultorio.db"

def init_db():
    """Crea la tabla 'pacientes' si no existe."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pacientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_apellido TEXT NOT NULL,
                edad INTEGER NOT NULL,
                dni TEXT NOT NULL,
                celular TEXT NOT NULL,
                email TEXT,
                link_meet TEXT,
                fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
    print(" BASE DE DATOS SQLITE INICIALIZADA CORRECTAMENTE.")

init_db()

# --- CARGAR MERCADO PAGO ---
token = os.getenv("MP_ACCESS_TOKEN")
print(f"--- TOKEN CARGADO: {token} ---")
sdk = mercadopago.SDK(token)


# ==========================================
# FUNCIONES AUXILIARES DE FORMATEO Y NOTIFICACIÓN
# ==========================================

def enviar_email_confirmacion(email_paciente, nombre_paciente, fecha_turno="Registrada en Calendly", hora_turno="Registrada en Calendly", link_meet="https://meet.google.com/abc-defg-hij"):
    try:
        remitente = os.getenv("SENDER_EMAIL", "onboarding@resend.dev")
        
        # 1. Email al Paciente
        resend.Emails.send({
            "from": f"Dra. Furlan <{remitente}>",
            "to": [email_paciente],
            "subject": "¡Turno confirmado! - Dra. Furlan",
            "html": f"""
                <h2>¡Hola {nombre_paciente}!</h2>
                <p>Tu turno médico ha sido confirmado con éxito.</p>
                <p><b>Fecha y Hora:</b> {fecha_turno} - {hora_turno}</p>
                <p><b>Acceso a la videollamada:</b> <a href="{link_meet}">{link_meet}</a></p>
            """
        })
        
        # 2. Email de notificación a la Doctora
        doctor_email = os.getenv("DOCTOR_EMAIL")
        if doctor_email:
            resend.Emails.send({
                "from": f"Sistema Consultorio <{remitente}>",
                "to": [doctor_email],
                "subject": f"Nuevo turno reservado - {nombre_paciente}",
                "html": f"""
                    <h2>Nuevo turno agendado</h2>
                    <p><b>Paciente:</b> {nombre_paciente}</p>
                    <p><b>Email:</b> {email_paciente}</p>
                    <p><b>Enlace a Google Meet:</b> <a href="{link_meet}">{link_meet}</a></p>
                """
            })
        return True
    except Exception as e:
        print(f"Error al enviar email con Resend: {e}")
        return False

# ==========================================
# RUTAS PÚBLICAS (WEB Y FORMULARIO)
# ==========================================

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/crear-preferencia', methods=['POST'])
def crear_preferencia():
    try:
        preference_data = {
            "items": [
                {
                    "title": "Consulta Médica - Dra. Furlan",
                    "quantity": 1,
                    "unit_price": 15000.0,
                    "currency_id": "ARS"
                }
            ],
            "back_urls": {
                "success": "http://127.0.0.1:5000/pago-exitoso",
                "pending": "http://127.0.0.1:5000/pago-pendiente",
                "failure": "http://127.0.0.1:5000/pago-fallido"
            },
            "auto_return": "approved"
        }

        preference_response = sdk.preference().create(preference_data)
        response_data = preference_response.get("response", {})

        if "init_point" in response_data:
            return jsonify({"init_point": response_data["init_point"]})
        else:
            return jsonify({"error": "No se obtuvo init_point", "detalle": preference_response}), 400

    except Exception as e:
        print(f"Error en el servidor: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/guardar-paciente', methods=['POST'])
def guardar_paciente():
    try:
        data = request.get_json()
        nombre = data.get('nombre')
        edad = data.get('edad')
        dni = data.get('dni')
        celular = data.get('celular')
        email = data.get('email')
        link_meet = "https://meet.google.com/abc-defg-hij"

    # 1. Guardar en SQLite
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO pacientes (nombre_apellido, edad, dni, celular, email, link_meet)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (nombre, edad, dni, celular, email, link_meet))
            conn.commit()
            paciente_id = cursor.lastrowid

        print(f"\n--- PACIENTE GUARDADO EN BASE DE DATOS (ID: {paciente_id}) | Email: {email} ---")
        
        # 2. Envío de emails con Resend
        if email:
            enviar_email_confirmacion(
                email_paciente=email,
                nombre_paciente=nombre,
                fecha_turno="Registrada en Calendly",
                hora_turno="Registrada en Calendly",
                link_meet=link_meet
    )

        return jsonify({
            'success': True,
            'message': 'Paciente guardado en BD y notificación lista.',
            'paciente_id': paciente_id
        })
    except Exception as e:
        print(f"Error en /guardar-paciente: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==========================================
# RUTAS PRIVADAS (PANEL DE LA DOCTORA)
# ==========================================

@app.route('/panel', methods=['GET', 'POST'])
def panel_pacientes():
    """Panel visual protegido con contraseña para la doctora."""
    
    if request.method == 'POST':
        clave_ingresada = request.form.get('password')
        if clave_ingresada == PASSWORD_DOCTORA:
            session['doctora_logueada'] = True
        else:
            return """
            <div style="font-family: Arial, sans-serif; text-align: center; margin-top: 50px;">
                <h3 style="color: red;">Contraseña incorrecta</h3>
                <a href="/panel">Intentar de nuevo</a>
            </div>
            """

    if not session.get('doctora_logueada'):
        return """
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <title>Acceso Restringido - Dra. Furlan</title>
            <style>
                body { font-family: Arial, sans-serif; background-color: #f1f5f9; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
                .login-card { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 100%; max-width: 320px; text-align: center; }
                input[type="password"] { width: 100%; padding: 10px; margin: 15px 0; border: 1px solid #ccc; border-radius: 5px; box-sizing: border-box; }
                button { width: 100%; background-color: #0d6efd; color: white; padding: 10px; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; }
            </style>
        </head>
        <body>
            <div class="login-card">
                <h2>🔐 Acceso Médico</h2>
                <p style="color: #666; font-size: 0.9rem;">Ingresá la contraseña para ver el listado de pacientes:</p>
                <form method="POST" action="/panel">
                    <input type="password" name="password" placeholder="Contraseña" required>
                    <button type="submit">Ingresar al Panel</button>
                </form>
            </div>
        </body>
        </html>
        """

    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nombre_apellido, edad, dni, celular, email, link_meet FROM pacientes ORDER BY id DESC")
            pacientes = cursor.fetchall()

        html = """
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <title>Panel de Pacientes - Dra. Furlan</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; background-color: #f8fafc; color: #334155; }
                .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
                h2 { color: #0f172a; margin: 0; }
                .btn-logout { background-color: #dc3545; color: white; padding: 8px 15px; text-decoration: none; border-radius: 5px; font-size: 0.9rem; }
                table { width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
                th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #e2e8f0; }
                th { background-color: #0d6efd; color: white; font-weight: 600; }
                tr:hover { background-color: #f1f5f9; }
                .wa-link { color: #25D366; font-weight: bold; text-decoration: none; }
            </style>
        </head>
        <body>
            <div class="header">
                <h2>📋 Pacientes Registrados</h2>
                <div>
                    <a href="/" style="margin-right: 15px; text-decoration: none; color: #0d6efd;">Ver Web</a>
                    <a href="/logout" class="btn-logout">Cerrar Sesión</a>
                </div>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Nombre y Apellido</th>
                        <th>Edad</th>
                        <th>DNI</th>
                        <th>Celular / WhatsApp</th>
                        <th>Email</th>
                        <th>Link Meet</th>
                        <th>Fecha de Registro</th>
                    </tr>
                </thead>
                <tbody>
        """
        for p in pacientes:
            num_clean = p[4].replace('+', '').replace(' ', '').replace('-', '')
            html += f"""
                <tr>
                    <td>{p[0]}</td>
                    <td>{p[1]}</td>
                    <td>{p[2]}</td>
                    <td>{p[3]}</td>
                    <td>{p[4]}</td>
                    <td>{p[5]}</td>
                    <td><a href="{p[6]}" target="_blank" style="color: #007bff; font-weight: bold;">Unirse a Meet</a></td>
                </tr>
            """

        html += """
                </tbody>
            </table>
        </body>
        </html>
        """
        return html

    except Exception as e:
        return f"Error al cargar los pacientes: {e}"

@app.route('/logout')
def logout():
    session.pop('doctora_logueada', None)
    return redirect(url_for('panel_pacientes'))

@app.route('/pago-exitoso')
def pago_exitoso():
    # Mercado Pago suele enviar parámetros por URL (payment_id, status, etc.)
    return render_template('pago_exitoso.html')

@app.route('/pago-pendiente')
def pago_pendiente():
    return render_template('pago_pendiente.html')

@app.route('/pago-fallido')
def pago_fallido():
    return render_template('pago_fallido.html')


if __name__ == '__main__':
    app.run(debug=True, port=5000)