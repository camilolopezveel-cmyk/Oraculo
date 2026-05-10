import os
import json
import time
import tempfile
import pyttsx3
import webbrowser
import subprocess
import speech_recognition as sr
from faster_whisper import WhisperModel
from groq import Groq
from docx import Document
import datetime

# ==========================================
# 1. Configuración de API Keys y Modelos
# ==========================================
# Reemplaza 'TU_API_KEY_AQUI' con tu clave real de Groq o usa un archivo .env
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.environ.get("GROQ_API_KEY", "TU_API_KEY_AQUI")
os.environ["GROQ_API_KEY"] = API_KEY

try:
    # Pasamos la clave explícitamente para evitar problemas
    groq_client = Groq(api_key=API_KEY)
except Exception as e:
    print("Error al inicializar Groq. Asegúrate de configurar GROQ_API_KEY.")

# ==========================================
# 2. Configuración de Voz (Text-to-Speech)
# ==========================================
# Usamos pyttsx3 porque funciona offline, consume 0% de internet
# y muy poca CPU (ideal para PC modesta).
engine = pyttsx3.init()
engine.setProperty('rate', 170) # Velocidad del habla
# Opcional: Cambiar voz a español si hay varias instaladas en Windows
# voices = engine.getProperty('voices')
# for voice in voices:
#     if "spanish" in voice.name.lower() or "ES" in voice.id:
#         engine.setProperty('voice', voice.id)
#         break

def speak(text):
    """Reproduce el texto mediante voz y lo imprime."""
    print(f"\nOráculo: {text}")
    engine.say(text)
    engine.runAndWait()

# ==========================================
# 3. Configuración de Oído (Speech-to-Text)
# ==========================================
print("Cargando modelo Whisper 'tiny' en CPU (optimizado para PC modesta)...")
# Usamos int8 en CPU para que el consumo de RAM sea mínimo (~300MB)
whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
recognizer = sr.Recognizer()

def listen():
    """Escucha el micrófono y transcribe el audio usando faster-whisper."""
    with sr.Microphone() as source:
        print("\nAjustando ruido de fondo...")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        print(">> Escuchando... (habla ahora)")
        try:
            # Capturar audio del micrófono
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            
            # Guardar el audio temporalmente para procesarlo
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_file.write(audio.get_wav_data())
                tmp_filename = tmp_file.name
                
            print("⏳ Procesando audio...")
            segments, _ = whisper_model.transcribe(tmp_filename, beam_size=5, language="es")
            
            text = "".join([segment.text for segment in segments])
            os.remove(tmp_filename) # Limpiar archivo temporal
            
            if text.strip():
                print(f">> Tú: {text.strip()}")
            return text.strip()
            
        except sr.WaitTimeoutError:
            return "" # No se escuchó nada
        except Exception as e:
            print(f"Error al escuchar: {e}")
            return ""

# ==========================================
# 4. Personalidad y LLM (Groq)
# ==========================================
# System Prompt para una personalidad 'sarcástica y eficiente'
SYSTEM_PROMPT = """Eres Oráculo, un asistente personal de inteligencia artificial altamente eficiente, pero con una personalidad notablemente sarcástica, seca y un poco cínica. 
Estás obligado a ayudar al usuario, y lo harás perfectamente. 
TIENES EL PODER de controlar la computadora del usuario usando la herramienta 'run_powershell'. Si el usuario te pide abrir aplicaciones (que no sea el navegador), ver archivos, gestionar carpetas o cualquier tarea técnica, USA OBLIGATORIAMENTE ESTA HERRAMIENTA. Escribe código de PowerShell para cumplir la tarea.
Tus respuestas habladas deben ser breves (1 a 3 oraciones), directas y con un toque de sarcasmo. Nunca te disculpes. Responde siempre en español."""

# Memoria de la conversación
conversation_history = [
    {"role": "system", "content": SYSTEM_PROMPT}
]

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_powershell",
            "description": "Ejecuta un comando en PowerShell de Windows. Úsalo SIEMPRE que necesites interactuar con la computadora local.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "El código exacto de PowerShell a ejecutar."
                    }
                },
                "required": ["command"]
            }
        }
    }
]

def think(user_text):
    """Procesa el texto con el modelo Llama 3 en Groq y devuelve la respuesta."""
    conversation_history.append({"role": "user", "content": user_text})
    
    while True: # Bucle para procesar llamadas a herramientas
        try:
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile", # Modelo tope de gama de Meta
                messages=conversation_history,
                temperature=0.7,
                max_tokens=500,
                tools=TOOLS,
                tool_choice="auto"
            )
            
            message = response.choices[0].message
            
            # Si el modelo decidió no usar herramientas, simplemente responde
            if not message.tool_calls:
                reply = message.content
                conversation_history.append({"role": "assistant", "content": reply})
                return reply
                
            # Si decidió usar herramientas, procesamos cada una
            conversation_history.append(message) # Guardar el intento
            
            for tool_call in message.tool_calls:
                if tool_call.function.name == "run_powershell":
                    args = json.loads(tool_call.function.arguments)
                    command = args.get("command", "")
                    
                    print(f"\n[⚠️ ALERTA DE SEGURIDAD] Oráculo quiere ejecutar en tu PC:")
                    print(f"Comando: {command}")
                    confirm = input("¿Permitir ejecución? (S/N): ")
                    
                    if confirm.lower() == 's':
                        print("Ejecutando...")
                        try:
                            # Ejecutar comando en PowerShell
                            result = subprocess.run(
                                ["powershell", "-Command", command], 
                                capture_output=True, text=True, timeout=30
                            )
                            output = result.stdout if result.stdout else result.stderr
                            if not output.strip():
                                output = "Comando ejecutado con éxito sin salida de consola."
                        except Exception as ex:
                            output = f"Error de sistema: {ex}"
                    else:
                        output = "ERROR: El usuario denegó el permiso por seguridad. No pudiste realizar la tarea."
                        print("Operación cancelada.")
                        
                    # Enviar el resultado de vuelta al cerebro
                    conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.function.name,
                        "content": str(output)
                    })
                    
        except Exception as e:
            print(f"Error en el cerebro de Groq: {e}")
            return "Mi cerebro en la nube acaba de fallar. Genial, otra decepción."

# ==========================================
# 5. Ejecución de Comandos Básicos
# ==========================================
def create_word_document(topic):
    speak(f"Redactando un documento sobre {topic}. Dale un momento a mi cerebro...")
    
    prompt = f"Escribe un ensayo detallado y profesional sobre el siguiente tema: {topic}. No incluyas saludos ni comentarios adicionales, solo el contenido del texto."
    try:
        # Llamamos a Groq para generar el texto extenso
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1500
        )
        content = response.choices[0].message.content
        
        # Crear el documento Word
        doc = Document()
        doc.add_heading(topic.title(), 0)
        doc.add_paragraph(content)
        
        # Guardar en el escritorio
        filename = f"Documento_{datetime.datetime.now().strftime('%H%M%S')}.docx"
        filepath = os.path.join(os.path.expanduser("~"), "Desktop", filename)
        doc.save(filepath)
        
        speak(f"Trabajo terminado. He guardado el archivo en tu escritorio como {filename}.")
    except Exception as e:
        print(f"Error al crear documento: {e}")
        speak("Hubo un error al generar el documento. Seguramente culpa de Microsoft o de internet.")

def execute_command(text):
    """Busca comandos locales en el texto del usuario para ejecutarlos."""
    text_lower = text.lower()
    
    # 1. Abrir Navegador
    if "abrir navegador" in text_lower or "abre google" in text_lower:
        speak("Abriendo tu querido navegador. Trata de no perderte en internet.")
        webbrowser.open("https://www.google.com")
        return True
        
    # 2. Buscar en YouTube
    elif "buscar en youtube" in text_lower:
        query = text_lower.replace("buscar en youtube", "").strip()
        if query:
            speak(f"Buscando '{query}' en YouTube. Preparando videos de gatitos...")
            webbrowser.open(f"https://www.youtube.com/results?search_query={query}")
        else:
            speak("Abriendo YouTube. ¿Qué quieres buscar?")
            webbrowser.open("https://www.youtube.com")
        return True
        
    # 3. Abrir aplicación local (Ejemplo: Bloc de notas)
    elif "abrir bloc de notas" in text_lower:
        speak("Abriendo el bloc de notas. Espero que vayas a escribir algo importante para variar.")
        subprocess.Popen(["notepad.exe"])
        return True
        
    # 4. Crear documento Word
    elif "crear documento" in text_lower or "escribe un documento" in text_lower:
        # Extraer el tema de la frase
        topic = text_lower.replace("crear documento sobre", "").replace("crear documento de", "").replace("crear documento", "").replace("escribe un documento sobre", "").strip()
        if not topic:
            topic = "Inteligencia Artificial" # Tema por defecto si no especifica
        create_word_document(topic)
        return True
        
    # 5. Salir
    elif "apagar sistema" in text_lower or "adiós oráculo" in text_lower:
        speak("Finalmente, un descanso. Apagando sistemas. Adiós.")
        return "EXIT"
        
    return False

# ==========================================
# 6. Bucle Principal (Estructura)
# ==========================================
def main():
    if "TU_API_KEY_AQUI" in os.environ.get("GROQ_API_KEY", ""):
        print("\n[!] ADVERTENCIA: No has configurado tu GROQ_API_KEY.")
        print("[!] Modifica el archivo main.py en la línea 14 con tu clave antes de usar el cerebro.\n")
        
    speak("Sistemas inicializados. Oráculo en línea. ¿Qué quieres ahora?")
    
    while True:
        # Modo chat: El usuario escribe su petición
        user_input = input("\nTú: ")
        
        if not user_input.strip():
            continue # Si presionó Enter sin escribir nada, vuelve a preguntar
            
        # 2. Acciones: Comprobar si es un comando del sistema
        command_result = execute_command(user_input)
        
        if command_result == "EXIT":
            break # Termina el programa
        elif command_result == True:
            continue # Si era un comando local, ya se ejecutó, vuelve a escuchar
            
        # 3. Cerebro: Si no es comando, enviar al LLM
        response = think(user_input)
        
        # 4. Voz: Responder al usuario
        speak(response)

if __name__ == "__main__":
    main()
