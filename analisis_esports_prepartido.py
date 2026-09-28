import os
import time
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from google import genai

# ==========================================
# 1. FECHA Y ZONA HORARIA (COLOMBIA)
# ==========================================
tz_colombia = ZoneInfo("America/Bogota")
fecha_hoy_colombia = datetime.now(tz_colombia).strftime('%Y-%m-%d')

print("--- INICIANDO ESCANEO DE ESPORTS ---")
print(f"Fecha local (Colombia): {fecha_hoy_colombia}")

# ==========================================
# 2. CARGA Y VALIDACIÓN DE VARIABLES DE ENTORNO
# ==========================================
PANDASCORE_TOKEN = os.getenv("PANDASCORE_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN_ESPORTS")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID_ESPORTS")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    print("Error: Credenciales de Telegram eSports no configuradas.")
else:
    print("Credenciales de Telegram cargadas correctamente.")

if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY no configurada.")

if not PANDASCORE_TOKEN:
    print("Error: PANDASCORE_TOKEN no configurada.")

# Inicializar cliente Gemini
client = genai.Client(api_key=GEMINI_API_KEY)


# ==========================================
# 3. EVALUACIÓN CON GEMINI (CON FALLBACK DE MODELOS)
# ==========================================
def analizar_con_gemini(prompt):
    """
    Intenta evaluar el prompt probando modelos compatibles.
    Maneja también el error 503 por saturación.
    """
    modelos_a_probar = ["gemini-2.0-flash", "gemini-1.5-flash"]
    
    for modelo in modelos_a_probar:
        max_intentos = 2
        for intento in range(max_intentos):
            try:
                respuesta = client.models.generate_content(
                    model=modelo,
                    contents=prompt
                )
                if respuesta and respuesta.text:
                    return respuesta.text
            except Exception as e:
                error_str = str(e)
                # Si el modelo no existe (404), rompemos el bucle interno e intentamos con el siguiente modelo
                if "404" in error_str or "NOT_FOUND" in error_str:
                    print(f"Modelo {modelo} no disponible. Probando siguiente...")
                    break
                # Si hay sobrecarga (503), esperamos y reintentamos
                elif "503" in error_str and intento < max_intentos - 1:
                    print(f"Gemini ocupado (503) en {modelo}. Reintentando en 5s...")
                    time.sleep(5)
                else:
                    print(f"Error en {modelo}: {e}")
                    break

    return None


# ==========================================
# 4. ENVÍO DE NOTIFICACIONES A TELEGRAM
# ==========================================
def enviar_mensaje_telegram(mensaje):
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
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("Mensaje eSports despachado a Telegram. HTTP: 200")
            return True
        else:
            print(f"Error Telegram HTTP {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"Excepción al conectar con Telegram: {e}")
        return False


# ==========================================
# 5. CONSULTA DE PARTIDOS EN PANDASCORE
# ==========================================
def obtener_partidos_pandascore():
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {PANDASCORE_TOKEN}"
    }
    
    url = "https://api.pandascore.co/matches/upcoming?page[size]=50"
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            partidos = res.json()
            print(f"Partidos obtenidos de PandaScore: {len(partidos)}")
            return partidos
        else:
            print(f"Error al consultar PandaScore. Status: {res.status_code}")
            return []
    except Exception as e:
        print(f"Error de conexión con PandaScore: {e}")
        return []


# ==========================================
# 6. FLUJO PRINCIPAL
# ==========================================
def main():
    partidos = obtener_partidos_pandascore()
    
    if not partidos:
        print("No se encontraron partidos programados para analizar.")
        return

    enviados = 0
    for partido in partidos:
        nombre_partido = partido.get("name", "Partido Sin Nombre")
        liga = partido.get("league", {}).get("name", "Liga Desconocida")
        
        prompt = (
            f"Analiza este partido de eSports y entrega un pronóstico breve para apuestas:\n"
            f"Evento: {nombre_partido}\n"
            f"Torneo/Liga: {liga}\n"
            f"Detalles completos: {partido}"
        )
        
        analisis = analizar_con_gemini(prompt)
        
        if analisis:
            mensaje_final = f"🎮 *ANÁLISIS DE ESPORTS*\n🏆 *{liga}*\n⚔️ {nombre_partido}\n\n{analisis}"
            if enviar_mensaje_telegram(mensaje_final):
                enviados += 1

    print(f"Proceso eSports completado. Enviados: {enviados}")


if __name__ == "__main__":
    main()
