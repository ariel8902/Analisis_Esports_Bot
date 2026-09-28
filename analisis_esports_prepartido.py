import os
import time
from google import genai

# ==========================================
# 1. CONFIGURACIÓN DE VARIABLES DE ENTORNO
# ==========================================
# Importante: Los nombres coinciden exactamente con los Secrets de GitHub
PANDASCORE_TOKEN = os.getenv("PANDASCORE_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN_ESPORTS")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID_ESPORTS")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Validación de credenciales de Telegram
if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    print("Error: Credenciales de Telegram eSports no configuradas.")
else:
    print("Credenciales de Telegram cargadas correctamente.")

# Inicializar cliente de Gemini
client = genai.Client(api_key=GEMINI_API_KEY)


# ==========================================
# 2. FUNCIÓN CON REINTENTOS PARA GEMINI (Evita Error 503)
# ==========================================
def analizar_partido_con_gemini(prompt_partido):
    """
    Envía la solicitud a Gemini con un bucle de reintentos
    para absorber el error 503 UNAVAILABLE cuando los servidores estén saturados.
    """
    max_intentos = 3
    
    for intento in range(max_intentos):
        try:
            # Reemplaza 'gemini-2.5-flash' por el modelo que estés usando
            respuesta = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt_partido
            )
            return respuesta.text

        except Exception as e:
            # Captura el error 503 por alta demanda
            if "503" in str(e) and intento < max_intentos - 1:
                print(f"Gemini ocupado (503). Reintentando en 5 segundos... (Intento {intento + 1}/{max_intentos})")
                time.sleep(5)
            else:
                print(f"Error evaluando partido con Gemini: {e}")
                return None


# ==========================================
# 3. FUNCIÓN PARA ENVIAR MENSAJES A TELEGRAM
# ==========================================
def enviar_mensaje_telegram(mensaje):
    """
    Envía la notificación formateada al chat/canal de Telegram.
    """
    import requests

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Error: Credenciales de Telegram eSports no configuradas.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=payload)
        res_data = response.json()
        if res_data.get("ok"):
            print("Mensaje enviado con éxito a Telegram.")
            return True
        else:
            print(f"Error al enviar a Telegram: {res_data.get('description')}")
            return False
    except Exception as e:
        print(f"Excepción al conectar con Telegram: {e}")
        return False


# ==========================================
# 4. LÓGICA PRINCIPAL DEL SCRIPT
# ==========================================
def main():
    print("Iniciando escaneo de eSports...")
    
    # Aquí va tu lógica para obtener partidos de PandaScore
    # Ejemplo conceptual:
    # partidos = obtener_partidos_pandascore(PANDASCORE_TOKEN)
    
    # Supongamos que recorres cada partido encontrado:
    # for partido in partidos:
    #     prompt = f"Analiza este partido: {partido}"
    #     analisis = analizar_partido_con_gemini(prompt)
    #     if analisis:
    #         enviar_mensaje_telegram(analisis)

if __name__ == "__main__":
    main()
