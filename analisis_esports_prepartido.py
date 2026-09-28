import os
import time
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from google import genai

# 1. Configuración de zona horaria e impresión de diagnóstico
tz_colombia = ZoneInfo("America/Bogota")
fecha_hora_actual = datetime.now(tz_colombia).strftime('%Y-%m-%d %H:%M:%S')

print("=== PRUEBA DE DIAGNÓSTICO DE BOT ESPORTS ===")
print(f"Fecha y Hora actual (Colombia): {fecha_hora_actual}")

# 2. Carga de Variables de Entorno
PANDASCORE_TOKEN = os.getenv("PANDASCORE_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN_ESPORTS")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID_ESPORTS")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

print(f"Token Telegram detectado: {'SI' if TELEGRAM_TOKEN else 'NO'}")
print(f"Chat ID Telegram detectado: {'SI' if TELEGRAM_CHAT_ID else 'NO'}")
print(f"Gemini API Key detectada: {'SI' if GEMINI_API_KEY else 'NO'}")

# 3. Función de prueba para enviar a Telegram
def enviar_prueba_telegram(mensaje):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("ERROR: No se pueden enviar mensajes porque faltan las credenciales de Telegram.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown"
    }

    try:
        res = requests.post(url, json=payload, timeout=10)
        print(f"Respuesta de Telegram API Status: {res.status_code}")
        print(f"Respuesta de Telegram Body: {res.text}")
        return res.status_code == 200
    except Exception as e:
        print(f"Excepción al conectar con Telegram: {e}")
        return False

# 4. Probar generación con Gemini
def probar_gemini():
    if not GEMINI_API_KEY:
        print("ERROR: No hay GEMINI_API_KEY configurada.")
        return None

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Intentar llamada directa
        prompt = "Escribe un mensaje de saludo muy corto notificando que el Bot de eSports está en línea."
        respuesta = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return respuesta.text
    except Exception as e:
        print(f"Error generando con Gemini: {e}")
        return None

def main():
    print("\n--- PASO 1: Generando respuesta de prueba con Gemini ---")
    texto_gemini = probar_gemini()

    if texto_gemini:
        print(f"Respuesta de Gemini generada con éxito:\n{texto_gemini}\n")
        mensaje_final = f"🧪 *MENSAJE DE PRUEBA DEL BOT DE ESPORTS*\n📅 {fecha_hora_actual}\n\n🤖 *Respuesta de Gemini:*\n{texto_gemini}"
    else:
        print("Fallo la generación con Gemini. Se enviará un mensaje simple de plantilla.")
        mensaje_final = f"🧪 *MENSAJE DE PRUEBA DE CONEXIÓN*\n📅 {fecha_hora_actual}\n\nEl bot de eSports se ha ejecutado correctamente desde GitHub Actions."

    print("--- PASO 2: Enviando mensaje a Telegram ---")
    exito = enviar_prueba_telegram(mensaje_final)

    if exito:
        print("\n✅ PRUEBA COMPLETADA: El mensaje debió llegar a tu Telegram.")
    else:
        print("\n❌ PRUEBA FALLIDA: Ocurrió un problema al entregar el mensaje a Telegram.")

if __name__ == "__main__":
    main()
