# logic.py (Versión final que interpreta la estructura completa de la IA)

import os
import re
import json
import google.generativeai as genai
from pdfminer.high_level import extract_text
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

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
    prompt = f"""
    Actúa como una experta en reclutamiento de alta gerencia y coach de carrera.
    Analiza el CV y la oferta de trabajo.
    TAREAS:
    1.  **Optimiza el CV:** Reestructura el contenido del CV en un formato JSON. Re-escribe el "Perfil Profesional". Adapta los logros en la "Experiencia Profesional" usando verbos de acción.
    2.  **Genera Retroalimentación Estratégica:** Crea un análisis para el candidato con 3-4 consejos accionables.
    CV ORIGINAL: --- {texto_cv} ---
    OFERTA DE TRABAJO: --- {texto_oferta} ---
    RESPUESTA: Devuelve tu respuesta únicamente en formato JSON. Asegúrate de que los campos que son listas (como experiencia_profesional, educacion, idiomas, retroalimentacion) sean siempre listas, incluso si están vacías ([]), nunca nulos. La estructura debe ser:
    {{
      "cv_optimizado": {{
        "nombre": "Nombre Completo",
        "contacto": {{ "email": "", "telefono": "", "linkedin": "", "ciudad": "" }},
        "perfil_profesional": "Perfil reescrito.",
        "experiencia_profesional": [ {{ "cargo": "", "empresa": "", "ciudad": "", "periodo": "", "logros": ["Logro 1."] }} ],
        "educacion": [ {{ "titulo": "", "institucion": "", "periodo": "" }} ],
        "habilidades": {{ "tecnicas": ["Habilidad 1"], "competencias": ["Competencia 1"] }},
        "idiomas": [ {{ "idioma": "Idioma", "nivel": "Nivel" }} ]
      }},
      "retroalimentacion": ["Consejo 1."]
    }}
    """
    try:
        response = model.generate_content(prompt)
        if not response.parts:
            raise RuntimeError("La respuesta de la IA fue bloqueada, posiblemente por políticas de seguridad.")
        json_text = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(json_text)
    except Exception as e:
        raise RuntimeError(f"Error al procesar la respuesta de Gemini: {e}")

def crear_docx_optimizado(ruta_completa_salida, data):
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
    # --- LÓGICA CORREGIDA PARA HABILIDADES ---
    for key, title in habilidades.items():
        if title and isinstance(title, list):
            p_hab = doc.add_paragraph()
            # Formateamos el nombre de la categoría, ej: "tecnicas_y_analiticas" -> "Tecnicas y Analiticas"
            p_hab.add_run(key.replace('_', ' ').replace('-', ' ').title() + ': ').bold = True
            p_hab.add_run(", ".join(title))

    doc.add_heading('Idiomas', level=1)
    # --- LÓGICA CORREGIDA PARA IDIOMAS ---
    for idioma_info in cv.get('idiomas') or []:
        if isinstance(idioma_info, dict):
            texto_idioma = f"{idioma_info.get('idioma', '')}: {idioma_info.get('nivel', '')}"
            doc.add_paragraph(texto_idioma)
        else: # Por si acaso devuelve una lista de strings
            doc.add_paragraph(idioma_info)

    doc.save(ruta_completa_salida)
    print("✅ Documento guardado correctamente.")

def procesar_cv_completo(ruta_pdf_cv, texto_oferta, output_folder):
    configurar_gemini()
    texto_cv = extraer_texto_pdf(ruta_pdf_cv)
    datos_optimizados = analizar_y_optimizar_con_gemini(texto_cv, texto_oferta)
    if datos_optimizados:
        nombre_archivo_salida = "cv_optimizado.docx"
        ruta_completa_salida = os.path.join(output_folder, nombre_archivo_salida)
        crear_docx_optimizado(ruta_completa_salida, datos_optimizados)
        retroalimentacion = datos_optimizados.get('retroalimentacion', [])
        return nombre_archivo_salida, retroalimentacion
    else:
        return None, None