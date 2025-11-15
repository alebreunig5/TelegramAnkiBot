# anki_functions.py
import os
import requests
import json
import google.generativeai as genai
from dotenv import load_dotenv
import re

# --- Configuración de la API y AnkiConnect ---
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("Error: La clave de API no está configurada. Asegúrate de crear un archivo .env con GOOGLE_API_KEY.")

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

def obtener_info_completa_ia(palabra_en_ingles):
    """
    Obtiene la información completa sobre una palabra usando la IA de Gemini.
    """
    prompt = f""". Estoy aprendiendo ingles. Proporciona información completa y detallada sobre la palabra en inglés "{palabra_en_ingles}". Responde únicamente con el objeto JSON y no incluyas texto adicional.

    JSON {{
        "Palabra": "{palabra_en_ingles}",
        "Significado": "[Lista con los significados en español]. Solo palabra clave o frase corta sin oraciones completas",
        "Pronunciacion": "La pronunciación fonética simplificada en español. No la pronunciación oficial, sino en español, por ejemplo Hello = /jelou/ o Help=/jelp/",
        "Gramatica": "Incluye el infinitivo, los tiempos verbales y las conjugaciones más comunes (si aplica)",
        "Etimologia": "Explica el origen y la historia de la palabra, algo para ayudar a memorizarla",
        "Oracion_Comun": "Una oracion en ingles, de ejemplo en contexto general",
        "Oracion_medica": "Una oracion en ingles, de ejemplo en contexto médico",
    }}"""

    try:
        response = model.generate_content(prompt)
        json_limpio = response.text.strip().replace("```json", "").replace("```", "")
        datos_json = json.loads(json_limpio)
        return datos_json
    except Exception as e:
        print(f"Error al obtener información de IA: {e}")
        return None

def crear_tarjeta_anki(datos_json, modelName, deck_name):
    """
    Crea una tarjeta en Anki con los datos extraídos del JSON.
    FORMATO ACTUALIZADO:
    - Front: Palabra (Pronunciacion)
    - Back: Significados + Oraciones
    """
    print(f"=== DEBUG crear_tarjeta_anki ===")
    print(f"modelName recibido: {modelName}")
    print(f"deck_name recibido: {deck_name}")
    
    # Verificar conexión con AnkiConnect primero
    try:
        test_response = requests.post("http://localhost:8765", 
                                    json={"action": "version", "version": 6}, 
                                    timeout=5)
        if test_response.status_code != 200:
            return {"error": "No se puede conectar con Anki. ¿Está Anki ejecutándose?"}
    except Exception as e:
        return {"error": f"No se puede conectar con AnkiConnect: {str(e)}"}

    # Mapear nombres a los que realmente existen en Anki
    model_map = {
        "basic_card": "Basic",
        "reversed_card": "Basic (and reversed card)",
        "Basic": "Basic", 
        "Basic (and reversed card)": "Basic (and reversed card)"
    }
    
    deck_map = {
        "deck_step1": "0 USA::STEP 1",
        "deck_self_learning": "0 USA::Self-Learning", 
        "0 USA::STEP 1": "0 USA::STEP 1",
        "0 USA::Self-Learning": "0 USA::Self-Learning"
    }
    
    # Usar nombres mapeados o los originales
    final_model = model_map.get(modelName, "Basic")
    final_deck = deck_map.get(deck_name, deck_name)
    
    print(f"modelName final: {final_model}")
    print(f"deck_name final: {final_deck}")
    
    try:
        if not datos_json:
            return {"error": "No se proporcionaron datos para crear la tarjeta"}
        
        palabra = datos_json.get('Palabra', '')
        if not palabra:
            return {"error": "No se encontró la palabra en los datos"}
        
        # CREAR CONTENIDO FRONT (SIMPLIFICADO)
        contenido_front = f"{palabra}"
        if datos_json.get('Pronunciacion'):
            contenido_front += f" ({datos_json.get('Pronunciacion')})"
        
        # CREAR CONTENIDO BACK (SIGNIFICADOS + ORACIONES)
        contenido_back = ""
        if isinstance(datos_json.get('Significado'), list):
            for significado in datos_json.get('Significado'):
                contenido_back += f"• {significado}<br>"
        else:
            contenido_back = f"{datos_json.get('Significado', '')}<br>"
        
        # Agregar oraciones al BACK
        if datos_json.get('Oracion_Comun'):
            contenido_back += f"<br>💬 <i>{datos_json.get('Oracion_Comun')}</i>"
        
        if datos_json.get('Oracion_medica'):
            contenido_back += f"<br>🏥 <i>{datos_json.get('Oracion_medica')}</i>"
        
        print(f"Contenido Front: {contenido_front}")
        print(f"Contenido Back: {contenido_back}")
        
        anki_payload = {
            "action": "addNote",
            "version": 6,
            "params": {
                "note": {
                    "deckName": final_deck,
                    "modelName": final_model,
                    "fields": {
                        "Front": contenido_front,
                        "Back": contenido_back
                    },
                    "tags": ["telegram-bot"],
                    "options": {
                        "allowDuplicate": False
                    }
                }
            }
        }
        
        print(f"Enviando payload a AnkiConnect...")
        response = requests.post("http://localhost:8765", json=anki_payload, timeout=10)
        print(f"Status code: {response.status_code}")
        
        result = response.json()
        print(f"Respuesta completa de AnkiConnect: {result}")
        
        # MEJOR MANEJO DE LA RESPUESTA
        if result.get('error') is not None:
            return {"error": f"AnkiConnect error: {result.get('error')}"}
        
        if result.get('result') is None:
            return {"error": "La tarjeta no se pudo crear (posible duplicado)"}
        
        # ÉXITO - la tarjeta fue creada
        return {
            "success": True,
            "note_id": result.get('result'),
            "message": f"Tarjeta creada exitosamente con ID: {result.get('result')}"
        }
        
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(f"EXCEPCIÓN: {error_msg}")
        return {"error": error_msg}  

def editar_tarjeta_existente(note_id, campos_a_editar):
    """
    Edita una tarjeta de Anki existente.
    """
    url = "http://localhost:8765"
    payload = {
        "action": "updateNoteFields",
        "version": 6,
        "params": {
            "note": {
                "id": note_id,
                "fields": campos_a_editar
            }
        }
    }
    
    try:
        response = requests.post(url, data=json.dumps(payload))
        response.raise_for_status()
        result = response.json()
        return result
    except requests.exceptions.RequestException as e:
        return {"error": f"Error de conexión con AnkiConnect: {e}"}

def buscar_palabra_en_deck(deck_name, palabra_a_buscar):
    """
    Busca una palabra específica en un deck de Anki utilizando AnkiConnect.
    """
    url = "http://localhost:8765"
    query_str = f'deck:"{deck_name}" "{palabra_a_buscar}"'
    
    payload = {
        "action": "findNotes",
        "version": 6,
        "params": {
            "query": query_str
        }
    }
    
    try:
        response = requests.post(url, data=json.dumps(payload))
        response.raise_for_status()
        result = response.json()
        
        if result['error'] is not None:
            return []
            
        return result['result']
        
    except requests.exceptions.RequestException as e:
        print(f"Error de conexión con AnkiConnect: {e}")
        return []

def obtener_info_notas(note_ids):
    """
    Obtiene el contenido completo de las notas a partir de sus IDs.
    """
    url = "http://localhost:8765"
    payload = {
        "action": "notesInfo",
        "version": 6,
        "params": {
            "notes": note_ids
        }
    }
    
    try:
        response = requests.post(url, data=json.dumps(payload))
        response.raise_for_status()
        result = response.json()

        if result['error'] is not None:
            return []

        return result['result']
    except requests.exceptions.RequestException as e:
        print(f"Error de conexión con AnkiConnect: {e}")
        return []

def limpiar_html(texto):
    """
    Elimina las etiquetas HTML de un texto y formatea las listas.
    """
    limpio = re.sub('<br>', '\n', texto)
    limpio = re.sub('</?ul>', '', limpio)
    limpio = re.sub('<li>', '- ', limpio)
    limpio = re.sub('</?li>', '', limpio)
    return limpio.strip()

def formatear_json_para_telegram(datos_json):
    """Formatea el JSON para mostrarlo en Telegram"""
    mensaje = f"📚 *Información de la palabra:* {datos_json.get('Palabra', 'N/A')}\n\n"
    
    # Significado
    significado = datos_json.get('Significado', [])
    if isinstance(significado, list):
        mensaje += f"📖 *Significado:*\n"
        for i, sig in enumerate(significado, 1):
            mensaje += f"  {i}. {sig}\n"
    else:
        mensaje += f"📖 *Significado:* {significado}\n"
    
    # Pronunciación
    mensaje += f"🔊 *Pronunciación:* {datos_json.get('Pronunciacion', 'N/A')}\n\n"
    
    # Oración común
    mensaje += f"💬 *Oración común:*\n{datos_json.get('Oracion_Comun', 'N/A')}\n\n"
    
    # Oración médica
    mensaje += f"🏥 *Oración médica:*\n{datos_json.get('Oracion_medica', 'N/A')}\n\n"
    
    # Gramática
    gramatica = datos_json.get('Gramatica', 'N/A')
    if len(gramatica) > 200:  # Acortar si es muy largo
        gramatica = gramatica[:200] + "..."
    mensaje += f"📝 *Gramática:*\n{gramatica}\n\n"
    
    # Etimología
    etimologia = datos_json.get('Etimologia', 'N/A')
    if len(etimologia) > 200:  # Acortar si es muy largo
        etimologia = etimologia[:200] + "..."
    mensaje += f"📜 *Etimología:*\n{etimologia}\n"
    
    return mensaje

def formatear_notas_existentes(notas):
    """
    Formatea las notas existentes para mostrar en Telegram.
    """
    if not notas:
        return "No se encontraron notas."
    
    mensaje = "📋 *Tarjetas existentes encontradas:*\n\n"
    
    for i, nota in enumerate(notas, 1):
        anverso = limpiar_html(nota['fields']['Front']['value'])
        reverso = limpiar_html(nota['fields']['Back']['value'])
        
        mensaje += f"*Tarjeta #{i}:*\n"
        mensaje += f"*ID:* `{nota['noteId']}`\n"
        mensaje += f"*Anverso:* {anverso}\n"
        mensaje += f"*Reverso:* {reverso}\n\n"
    
    return mensaje

def convertir_nota_a_datos_anki(nota, palabra_original):
    """
    Convierte una nota existente de Anki al formato de datos_anki para edición - VERSIÓN SIMPLIFICADA
    """
    try:
        # Extraer información de los campos de la nota
        front = nota['fields']['Front']['value']
        back = nota['fields']['Back']['value']
        
        # Intentar extraer pronunciación si está entre paréntesis en el Front
        pronunciacion = ""
        if '(' in front and ')' in front:
            import re
            match = re.search(r'\((.*?)\)', front)
            if match:
                pronunciacion = match.group(1)
        
        # Extraer la palabra principal (sin pronunciación)
        palabra = palabra_original
        
        # Intentar extraer significados del Back (suponiendo que están en líneas con viñetas)
        significados = []
        lineas = back.split('<br>')
        for linea in lineas:
            linea_limpia = limpiar_html(linea).strip()
            if linea_limpia.startswith('•'):
                significado = linea_limpia[1:].strip()
                if significado:
                    significados.append(significado)
        
        # Si no se encontraron viñetas, usar todo el back como significado
        if not significados:
            significados = [limpiar_html(back)]
        
        # Extraer oraciones (buscando emojis característicos)
        oracion_comun = ""
        oracion_medica = ""
        
        for linea in lineas:
            linea_limpia = limpiar_html(linea).strip()
            if '💬' in linea:
                oracion_comun = linea_limpia.replace('💬', '').strip()
            elif '🏥' in linea:
                oracion_medica = linea_limpia.replace('🏥', '').strip()
        
        # SOLO CAMPOS QUE VAN A ANKI - Sin Gramática ni Etimología
        datos_anki = {
            'Palabra': palabra,
            'Significado': significados,
            'Pronunciacion': pronunciacion,
            'Oracion_Comun': oracion_comun,
            'Oracion_medica': oracion_medica
        }
        
        return datos_anki
        
    except Exception as e:
        print(f"Error al convertir nota a datos_anki: {e}")
        # Devolver estructura básica en caso de error
        return {
            'Palabra': palabra_original,
            'Significado': ['Significado no disponible'],
            'Pronunciacion': '',
            'Oracion_Comun': '',
            'Oracion_medica': ''
        }

def editar_tarjeta_existente_completa(note_id, datos_json, modelName, deck_name):
    """
    Edita una tarjeta existente en Anki con nuevos datos.
    """
    print(f"=== DEBUG editar_tarjeta_existente_completa ===")
    print(f"note_id: {note_id}")
    print(f"modelName: {modelName}")
    print(f"deck_name: {deck_name}")
    
    try:
        if not datos_json:
            return {"error": "No se proporcionaron datos para actualizar la tarjeta"}
        
        palabra = datos_json.get('Palabra', '')
        if not palabra:
            return {"error": "No se encontró la palabra en los datos"}
        
        # Crear contenido actualizado (igual que en crear_tarjeta_anki)
        contenido_front = f"{palabra}"
        if datos_json.get('Pronunciacion'):
            contenido_front += f" ({datos_json.get('Pronunciacion')})"
        
        contenido_back = ""
        if isinstance(datos_json.get('Significado'), list):
            for significado in datos_json.get('Significado'):
                contenido_back += f"• {significado}<br>"
        else:
            contenido_back = f"{datos_json.get('Significado', '')}<br>"
        
        if datos_json.get('Oracion_Comun'):
            contenido_back += f"<br>💬 <i>{datos_json.get('Oracion_Comun')}</i>"
        
        if datos_json.get('Oracion_medica'):
            contenido_back += f"<br>🏥 <i>{datos_json.get('Oracion_medica')}</i>"
        
        print(f"Contenido Front actualizado: {contenido_front}")
        print(f"Contenido Back actualizado: {contenido_back}")
        
        # Actualizar los campos de la nota existente
        anki_payload = {
            "action": "updateNoteFields",
            "version": 6,
            "params": {
                "note": {
                    "id": note_id,
                    "fields": {
                        "Front": contenido_front,
                        "Back": contenido_back
                    }
                }
            }
        }
        
        print(f"Enviando payload de actualización a AnkiConnect...")
        response = requests.post("http://localhost:8765", json=anki_payload, timeout=10)
        print(f"Status code: {response.status_code}")
        
        result = response.json()
        print(f"Respuesta completa de AnkiConnect: {result}")
        
        if result.get('error') is not None:
            return {"error": f"AnkiConnect error: {result.get('error')}"}
        
        if result.get('result') is None:
            return {"error": "La tarjeta no se pudo actualizar"}
        
        # ÉXITO - la tarjeta fue actualizada
        return {
            "success": True,
            "message": f"Tarjeta actualizada exitosamente"
        }
        
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(f"EXCEPCIÓN: {error_msg}")
        return {"error": error_msg}