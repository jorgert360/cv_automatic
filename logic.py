# logic.py (Versión con manejo de error de Límite de Tarifa)

import os
import re
import json
import google.generativeai as genai
from pdfminer.high_level import extract_text
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from google.api_core import exceptions as google_exceptions # <-- 1. IMPORTAR EXCEPCIONES DE GOOGLE

# --- INICIO DE LA MODIFICACIÓN (Error Personalizado) ---
# 2. Creamos un error personalizado que nuestra app pueda entender
class RateLimitError(Exception):
    pass
# --- FIN DE LA MODIFICACIÓN ---

def limpiar_texto_para_xml(texto):
    if texto is None: return ""
    return re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', texto)

def configurar_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("No se encontró la variable de entorno GEMINI_API_KEY.")
    genai.configure(api_key=api_key)

def extraer_texto_pdf(ruta_pdf):
    try:
        texto_extraido = extract_text(ruta_pdf)
        return limpiar_texto_para_xml(texto_extraido)
    except Exception as e:
        raise RuntimeError(f"Error al leer el PDF: {e}")

def extraer_texto_docx(ruta_docx):
    try:
        doc = Document(ruta_docx)
        full_text = [para.text for para in doc.paragraphs]
        return limpiar_texto_para_xml('\n'.join(full_text))
    except Exception as e:
        raise RuntimeError(f"Error al leer el DOCX: {e}")

def analizar_y_optimizar_con_gemini(texto_cv, texto_oferta):
    print("🤖 Analizando y optimizando el CV con IA...")
    
    model = genai.GenerativeModel("models/gemini-2.5-pro")
    print(f"DEBUG: Intentando usar el modelo: {model.model_name}")

    prompt = f"""
    Actúa como una coach de carrera de élite y experta en reclutamiento C-Suite, alineada con las 
    filosofías de expertos como Andrew LaCivita y EdnaJobs. Tu objetivo es transformar un CV 
    para que no solo supere el ATS, sino que impresione al reclutador humano. Tu enfoque es la 
    "contratación basada en habilidades" y la "cuantificación del impacto".

    CV ORIGINAL: --- {texto_cv} ---
    OFERTA DE TRABAJO: --- {texto_oferta} ---

    TAREAS:

    1.  **Optimiza el CV (Formato JSON):** (Esta tarea no cambia) Reestructura el contenido del CV en el formato 
        JSON de salida.
        a.  **Perfil Profesional:** Re-escribe un "Perfil Profesional" de alto impacto (3-4 líneas) 
            que actúe como un "gancho" y sea un "espejo" de la OFERTA ESPECÍFICA.
        b.  **Experiencia Profesional:** Adapta los logros. Reemplaza el lenguaje pasivo 
            (ej: "responsable de") por **verbos de acción potentes**. Donde sea posible, 
            **CUANTIFICA** el impacto usando el método de las "8 Grandes".
        c.  **Coherencia ATS:** Asegúrate de que las palabras clave críticas de la OFERTA DE TRABAJO 
            se reflejen en el perfil y la experiencia.

    2.  **Genera Retroalimentación Estratégica (Lista de strings):** Crea un análisis en 
        dos partes para el candidato.
        a.  **Paso 1: Fortalezas Clave (El primer ítem de la lista):** Comienza la retroalimentación 
            con un párrafo positivo y alentador. Identifica las 2-3 **fortalezas y habilidades** principales del candidato que SÍ se alinean perfectamente con la oferta de trabajo.
        b.  **Paso 2: Consejos Accionables (Los siguientes ítems):** Después del inicio positivo, 
            continúa con 3-4 consejos accionables (Análisis de Brecha Crítica, 
            Oportunidad de Impacto, Movimiento Estratégico).

    RESPUESTA: Devuelve tu respuesta únicamente en formato JSON. Asegúrate de que los campos que 
    son listas (como experiencia_profesional, educacion, idiomas, retroalimentacion) sean siempre 
    listas, incluso si están vacías ([]), nunca nulos. La estructura debe ser:
    {{
      "cv_optimizado": {{
        "nombre": "Nombre Completo",
        "contacto": {{ "email": "", "telefono": "", "linkedin": "", "ciudad": "" }},
        "perfil_profesional": "Perfil reescrito.",
        "experiencia_profesional": [ {{ "cargo": "", "empresa": "", "ciudad": "", "periodo": "", "logros": ["Logro 1.", "Logro 2."] }} ],
        "educacion": [ {{ "titulo": "", "institucion": "", "periodo": "" }} ],
        "habilidades": {{ "tecnicas": ["Habilidad 1"], "competencias": ["Competencia 1"] }},
        "idiomas": [ {{ "idioma": "Idioma", "nivel": "Nivel" }} ]
      }},
      "retroalimentacion": [
        "**Tus Fortalezas Clave:** Eres un candidato fuerte para este rol gracias a tu experiencia en [Habilidad 1] y [Habilidad 2].",
        "**Análisis de Brecha Crítica:** Consejo 1.",
        "**Oportunidad de Impacto:** Consejo 2.",
        "**Movimiento Estratégico:** Consejo 3."
      ]
    }}
    """
    
    # --- INICIO DE LA MODIFICACIÓN (Atrapar Error 429) ---
    # 3. Añadimos un try/except más específico
    try:
        response = model.generate_content(prompt)
        if not response.parts:
            raise RuntimeError("La respuesta de la IA fue bloqueada, posiblemente por políticas de seguridad.")
        json_text = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(json_text)
    
    except google_exceptions.ResourceExhausted as e:
        # ¡Este es el error de "demasiadas solicitudes" (429)!
        print(f"⚠️ Error de Límite de Tasa de API de Gemini (429): {e}")
        # Lanzamos nuestro error personalizado para que app.py lo atrape
        raise RateLimitError("API de Gemini sobrecargada. Por favor, inténtelo de nuevo en un minuto.")
    
    except Exception as e:
        # Errores generales (bloqueo de seguridad, etc.)
        raise RuntimeError(f"Error al procesar la respuesta de Gemini: {e}")
    # --- FIN DE LA MODIFICACIÓN ---

def crear_docx_optimizado(ruta_completa_salida, data):
    # ... (Esta función permanece exactamente igual) ...
    print(f"🎨 Creando documento Word en: {ruta_completa_salida}")
    if not data or 'cv_optimizado' not in data:
        raise ValueError("No se recibieron datos válidos para crear el documento.")
    
    cv = data.get('cv_optimizado') or {}
    retro = data.get('retroalimentacion') or []
    
    doc = Document()
    style = doc.styles['Normal']; font = style.font; font.name = 'Calibri'; font.size = Pt(11)
    
    doc.add_paragraph(cv.get('nombre', '')).alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.paragraphs[-1].runs[0].font.size = Pt(20); doc.paragraphs[-1].runs[0].font.bold = True
    
    contacto = cv.get('contacto') or {}
    contact_items = [contacto.get('email'), contacto.get('telefono'), contacto.get('linkedin'), contacto.get('ciudad')]
    contact_line = " | ".join(filter(None, contact_items))
    doc.add_paragraph(contact_line).alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.paragraphs[-1].runs[0].font.size = Pt(10)
    
    doc.add_heading('Perfil Profesional', level=1); doc.add_paragraph(cv.get('perfil_profesional', ''))
    
    doc.add_heading('Experiencia Profesional', level=1)
    for exp in cv.get('experiencia_profesional') or []:
        p_cargo = doc.add_paragraph(); p_cargo.add_run(exp.get('cargo', '')).bold = True
        empresa_line = f"{exp.get('empresa', '')} | {exp.get('ciudad', '')} | {exp.get('periodo', '')}"
        p_empresa = doc.add_paragraph(); p_empresa.add_run(empresa_line).italic = True
        p_empresa.paragraph_format.space_before = Pt(0); p_empresa.paragraph_format.space_after = Pt(4)
        for logro in exp.get('logros') or []:
            doc.add_paragraph(logro, style='List Bullet')
        doc.add_paragraph()
        
    doc.add_heading('Educación', level=1)
    for edu in cv.get('educacion') or []:
        p_edu = doc.add_paragraph(); p_edu.add_run(edu.get('titulo', '')).bold = True
        p_edu.add_run(f"\n{edu.get('institucion', '')} | {edu.get('periodo', '')}")
    
    doc.add_heading('Habilidades', level=1)
    habilidades = cv.get('habilidades') or {}
    for key, title in habilidades.items():
        if title and isinstance(title, list):
            p_hab = doc.add_paragraph()
            p_hab.add_run(key.replace('_', ' ').replace('-', ' ').title() + ': ').bold = True
            p_hab.add_run(", ".join(title))

    doc.add_heading('Idiomas', level=1)
    for idioma_info in cv.get('idiomas') or []:
        if isinstance(idioma_info, dict):
            texto_idioma = f"{idioma_info.get('idioma', '')}: {idioma_info.get('nivel', '')}"
            doc.add_paragraph(texto_idioma)
        else:
            doc.add_paragraph(idioma_info)

    doc.save(ruta_completa_salida)
    print("✅ Documento guardado correctamente.")

def procesar_cv_completo(ruta_pdf_cv, texto_oferta, output_folder):
    configurar_gemini()
    texto_cv = extraer_texto_pdf(ruta_pdf_cv)

    MAX_CARACTERES_CV = 15000 
    
    if len(texto_cv) > MAX_CARACTERES_CV:
        print(f"⚠️ Alerta: El CV era muy largo ({len(texto_cv)} caracteres). Se ha truncado a {MAX_CARACTERES_CV}.")
        texto_cv = texto_cv[:MAX_CARACTERES_CV]

    datos_optimizados = analizar_y_optimizar_con_gemini(texto_cv, texto_oferta)
    
    if datos_optimizados:
        nombre_archivo_salida = "cv_optimizado.docx"
        ruta_completa_salida = os.path.join(output_folder, nombre_archivo_salida)
        crear_docx_optimizado(ruta_completa_salida, datos_optimizados)
        
        retroalimentacion = datos_optimizados.get('retroalimentacion', [])
        nombre_candidato = datos_optimizados.get('cv_optimizado', {}).get('nombre', 'Candidato')
        
        return nombre_archivo_salida, retroalimentacion, nombre_candidato
    else:
        return None, None, None