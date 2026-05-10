from groq import Groq
import os

from dotenv import load_dotenv
load_dotenv()

API_KEY = os.environ.get("GROQ_API_KEY", "TU_API_KEY_AQUI")
print("Iniciando prueba de Groq...")
try:
    client = Groq(api_key=API_KEY)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": "hola"}],
    )
    print("Éxito! Respuesta:", response.choices[0].message.content)
except Exception as e:
    print(f"\nERROR DETALLADO:\n{type(e).__name__}: {e}")
