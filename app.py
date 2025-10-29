# app.py (Versión segura para producción y adaptada a Railway)

import os
import requests
from flask import Flask, render_template, request, send_from_directory, flash, redirect, url_for, session
from werkzeug.utils import secure_filename
from logic import procesar_cv_completo, extraer_texto_pdf, extraer_texto_docx

# --- CONFIGURACIÓN DE RUTAS (ADAPTADA PARA RAILWAY) ---
# Usamos /data, que es la ruta estándar para "Volumes" en Railway.
VOLUME_PATH = "/data"  # <-- MODIFICADO----
UPLOAD_FOLDER = os.path.join(VOLUME_PATH, 'uploads')  # <-- MODIFICADO
OUTPUT_FOLDER = os.path.join(VOLUME_PATH, 'outputs')  # <-- MODIFICADO
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

# --- CONFIGURACIÓN DE CLAVES DESDE VARIABLES DE ENTORNO ---
# Flask usará estas claves cuando esté en la nube. Si no las encuentra, usará un valor por defecto.
app.secret_key = os.getenv('SECRET_KEY', 'una_llave_secreta_por_defecto_para_pruebas')
app.config['RECAPTCHA_SITE_KEY'] = os.getenv('RECAPTCHA_SITE_KEY')
app.config['RECAPTCHA_SECRET_KEY'] = os.getenv('RECAPTCHA_SECRET_KEY')

# (El resto del código no cambia)
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html', site_key=app.config['RECAPTCHA_SITE_KEY'])

@app.route('/procesar', methods=['POST'])
def procesar():
    captcha_response = request.form.get('g-recaptcha-response')
    secret_key = app.config['RECAPTCHA_SECRET_KEY']
    
    # Verificación de que las claves no estén vacías
    if not secret_key or not captcha_response:
        flash('La configuración de reCAPTCHA no es válida. Contacta al administrador.')
        return redirect(url_for('index'))

    verification_url = f'https://www.google.com/recaptcha/api/siteverify?secret={secret_key}&response={captcha_response}'
    response = requests.post(verification_url)
    
    # Manejo de posible error en la llamada a reCAPTCHA
    if not response.ok:
        flash('Error al conectar con el servicio reCAPTCHA.')
        return redirect(url_for('index'))
    
    response_data = response.json()

    if response_data.get('success'):
        if 'habeas_data' not in request.form:
            flash('Debes aceptar la política de tratamiento de datos para continuar.')
            return redirect(url_for('index'))
        if 'cv_file' not in request.files or 'oferta_file' not in request.files:
            flash('No se encontraron los campos de archivo.')
            return redirect(url_for('index'))
        cv_file = request.files['cv_file']
        oferta_file = request.files['oferta_file']
        if cv_file.filename == '' or oferta_file.filename == '':
            flash('Debes subir ambos archivos.')
            return redirect(url_for('index'))
        texto_oferta = ""
        if oferta_file and oferta_file.filename != '':
            if not allowed_file(oferta_file.filename):
                flash('Archivo de oferta no permitido. Sube un .pdf, .docx o .txt.')
                return redirect(url_for('index'))
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            oferta_filename = secure_filename(oferta_file.filename)
            ruta_oferta = os.path.join(app.config['UPLOAD_FOLDER'], oferta_filename)
            oferta_file.save(ruta_oferta)
            if ruta_oferta.lower().endswith('.pdf'):
                texto_oferta = extraer_texto_pdf(ruta_oferta)
            elif ruta_oferta.lower().endswith('.docx'):
                texto_oferta = extraer_texto_docx(ruta_oferta)
            else:
                with open(ruta_oferta, 'r', encoding='utf-8') as f:
                    texto_oferta = f.read()
        else:
            flash('Debes subir un archivo para la oferta laboral.')
            return redirect(url_for('index'))
        if cv_file and cv_file.filename.lower().endswith('.pdf'):
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
            cv_filename = secure_filename(cv_file.filename)
            ruta_cv = os.path.join(app.config['UPLOAD_FOLDER'], cv_filename)
            cv_file.save(ruta_cv)
            try:
                nombre_archivo_resultado, retroalimentacion = procesar_cv_completo(ruta_cv, texto_oferta, app.config['OUTPUT_FOLDER'])
                if nombre_archivo_resultado:
                    session['resultado_cv'] = nombre_archivo_resultado
                    session['retroalimentacion'] = retroalimentacion
                    return redirect(url_for('mostrar_resultado'))
                else:
                    flash('Ocurrió un error durante el procesamiento con la IA.')
                    return redirect(url_for('index'))
            except Exception as e:
                flash(f'Ocurrió un error inesperado: {e}')
                return redirect(url_for('index'))
        else:
            flash('Archivo de CV no permitido. Sube un .pdf.')
            return redirect(url_for('index'))
    else:
        flash('Verificación "No soy un robot" inválida. Por favor, intenta de nuevo.')
        return redirect(url_for('index'))

@app.route('/resultado')
def mostrar_resultado():
    nombre_archivo = session.get('resultado_cv'); retroalimentacion = session.get('retroalimentacion')
    if not nombre_archivo:
        flash('No se encontraron resultados. Por favor, intenta de nuevo.')
        return redirect(url_for('index'))
    return render_template('resultado.html', retro=retroalimentacion, filename=nombre_archivo)

@app.route('/descargar/<path:filename>')
def descargar(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename, as_attachment=True)

@app.route('/donar')
def donar():
    return render_template('donar.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/blog')
def blog():
    return render_template('blog.html')

@app.route('/blog/<article_name>')
def article(article_name):
    # In a real application, you would fetch the article from a database
    # based on the article_name. For now, we just render the sample article.
    return render_template('article.html')

if __name__ == '__main__':
    # Esta línea se ignora en producción cuando usas Gunicorn,
    # pero permite correrlo localmente para pruebas si es necesario.
    app.run(debug=True)