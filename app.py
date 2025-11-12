# app.py (Versión con manejo de error de Límite de Tarifa)

import os
import requests
from flask import Flask, render_template, request, send_from_directory, flash, redirect, url_for, session
from werkzeug.utils import secure_filename
# --- INICIO DE LA MODIFICACIÓN ---
from logic import (
    procesar_cv_completo, extraer_texto_pdf, 
    extraer_texto_docx, RateLimitError  # <-- 1. Importar el nuevo error
)
# --- FIN DE LA MODIFICACIÓN ---

# --- Carga las variables de entorno desde el archivo .env ---
from dotenv import load_dotenv
load_dotenv()
# -----------------------------------------------------------


# --- CONFIGURACIÓN DE RUTAS (ADAPTADA PARA RENDER) ---
VOLUME_PATH = "/tmp"  # <-- Usando la carpeta de Render
UPLOAD_FOLDER = os.path.join(VOLUME_PATH, 'uploads')
OUTPUT_FOLDER = os.path.join(VOLUME_PATH, 'outputs')
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

# --- CONFIGURACIÓN DE CLAVES DESDE VARIABLES DE ENTORNO ---
app.secret_key = os.getenv('SECRET_KEY', 'una_llave_secreta_por_defecto_para_pruebas')
app.config['RECAPTCHA_SITE_KEY'] = os.getenv('RECAPTCHA_SITE_KEY')
app.config['RECAPTCHA_SECRET_KEY'] = os.getenv('RECAPTCHA_SECRET_KEY')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html', site_key=app.config['RECAPTCHA_SITE_KEY'])

@app.route('/procesar', methods=['POST'])
def procesar():
    captcha_response = request.form.get('g-recaptcha-response')
    secret_key = app.config['RECAPTCHA_SECRET_KEY']
    
    if not secret_key or not captcha_response:
        flash('La configuración de reCAPTCHA no es válida. Contacta al administrador.')
        return redirect(url_for('index'))

    verification_url = f'https://www.google.com/recaptcha/api/siteverify?secret={secret_key}&response={captcha_response}'
    response = requests.post(verification_url)
    
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
        MAX_CARACTERES_OFERTA = 10000 

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
            
            if len(texto_oferta) > MAX_CARACTERES_OFERTA:
                print(f"⚠️ Alerta: La oferta laboral era muy larga ({len(texto_oferta)} caracteres). Se ha truncado a {MAX_CARACTERES_OFERTA}.")
                texto_oferta = texto_oferta[:MAX_CARACTERES_OFERTA]

        else:
            flash('Debes subir un archivo para la oferta laboral.')
            return redirect(url_for('index'))
        
        if cv_file and cv_file.filename.lower().endswith('.pdf'):
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
            cv_filename = secure_filename(cv_file.filename)
            ruta_cv = os.path.join(app.config['UPLOAD_FOLDER'], cv_filename)
            cv_file.save(ruta_cv)
            
            # --- INICIO DE LA MODIFICACIÓN (Atrapar Error) ---
            # 2. Envolvemos la llamada a proceso en un try/except
            try:
                (
                    nombre_archivo_resultado, 
                    retroalimentacion, 
                    nombre_candidato
                ) = procesar_cv_completo(ruta_cv, texto_oferta, app.config['OUTPUT_FOLDER'])

                if nombre_archivo_resultado:
                    session['resultado_cv'] = nombre_archivo_resultado
                    session['retroalimentacion'] = retroalimentacion
                    session['nombre_candidato'] = nombre_candidato 
                    return redirect(url_for('mostrar_resultado'))
                else:
                    flash('Ocurrió un error durante el procesamiento con la IA.')
                    return redirect(url_for('index'))
            
            except RateLimitError:
                # 3. ¡Atrapamos el error de límite de tarifa!
                flash('Nuestro servicio de IA está experimentando un alto tráfico en este momento. Por favor, inténtelo de nuevo en uno o dos minutos.')
                return redirect(url_for('index'))
            
            except Exception as e:
                # Atrapamos todos los demás errores (como el 500 que vimos antes)
                flash(f'Ocurrió un error inesperado: {e}')
                return redirect(url_for('index'))
            # --- FIN DE LA MODIFICACIÓN ---
        else:
            flash('Archivo de CV no permitido. Sube un .pdf.')
            return redirect(url_for('index'))
    else:
        flash('Verificación "No soy un robot" inválida. Por favor, intenta de nuevo.')
        return redirect(url_for('index'))

@app.route('/resultado')
def mostrar_resultado():
    nombre_archivo = session.get('resultado_cv')
    retroalimentacion = session.get('retroalimentacion')
    nombre_candidato = session.get('nombre_candidato', 'Candidato') 
    
    if not nombre_archivo:
        flash('No se encontraron resultados. Por favor, intenta de nuevo.')
        return redirect(url_for('index'))
    
    return render_template('resultado.html', retro=retroalimentacion, filename=nombre_archivo, nombre_candidato=nombre_candidato)

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

# --- Rutas del Blog ---

@app.route('/blog/como-escribir-un-cv-perfecto')
def blog_cv_perfecto():
    return render_template('blog-cv-perfecto.html')

@app.route('/blog/5-errores-comunes-ats')
def blog_errores_ats():
    return render_template('blog-errores-ats.html')

@app.route('/blog/formato-cv-ganador-2025')
def blog_formato_cv():
    return render_template('blog-formato-cv.html')

@app.route('/blog/las-8-grandes-de-andrew-lacivita')
def blog_8_grandes():
    return render_template('blog-8-grandes.html')

@app.route('/blog/errores-descarte-vivian-montoya')
def blog_errores_descarte_vivian_montoya():
    return render_template('blog-errores-descarte.html')

@app.route('/blog/consejos-ats-ednajobs')
def blog_consejos_ednajobs():
    return render_template('blog-consejos-ednajobs.html')

@app.route('/blog/contratacion-basada-en-habilidades')
def blog_habilidades():
    return render_template('blog-habilidades.html')

@app.route('/blog/cv-hibrido-sin-experiencia')
def blog_cv_hibrido():
    return render_template('blog-cv-hibrido.html')

@app.route('/blog/como-manejar-huecos-laborales')
def blog_huecos_laborales():
    return render_template('blog-huecos-laborales.html')

@app.route('/blog/mito-una-pagina')
def blog_mito_una_pagina():
    return render_template('blog-mito-una-pagina.html')

@app.route('/robots.txt')
def static_from_root_robots():
    return send_from_directory(app.static_folder, request.path[1:])

@app.route('/sitemap.xml')
def static_from_root_sitemap():
    return send_from_directory(app.static_folder, request.path[1:])

if __name__ == '__main__':
    app.run(debug=True)