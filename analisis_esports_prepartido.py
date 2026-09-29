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
fecha_hoy_colombia = datetime.now(tz_colombia).strftime('%Y-%m-%d %H:%M:%S')

print("--- INICIANDO ESCANEO DE ESPORTS ---")
print(f"Fecha local (Colombia): {fecha_hoy_colombia}")

# ==========================================
# 2. CARGA DE VARIABLES DE ENTORNO
# ==========================================
PANDASCORE_TOKEN = os.getenv("PANDASCORE_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN_ESPORTS")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID_ESPORTS")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    print("Error: Credenciales de Telegram eSports no configuradas.")
else:
    print("Credenciales de Telegram cargadas correctamente.")

# Inicializar cliente de Gemini con la SDK google-genai
client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Error inicializando cliente Gemini: {e}")


# ==========================================
# 3. EVALUACIÓN CON GEMINI
# ==========================================
def analizar_con_gemini(prompt):
    if not client:
        print("Cliente de Gemini no configurado.")
        return None
    
    modelo = "gemini-3.8-flash"
    max_intentos = 3
    
    for intento in range(max_intentos):
        try:
            respuesta = client.models.generate_content(
                model=modelo,
                contents=prompt
            )
            if respuesta and hasattr(respuesta, 'text') and respuesta.text:
                return respuesta.text
        except Exception as e:
            print(f"Intento {intento + 1}/{max_intentos} falló con {modelo}: {e}")
            if intento < max_intentos - 1:
                time.sleep(6)

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
    # Procesamos los primeros 5 partidos
    for partido in partidos[:5]:
        nombre_partido = partido.get("name", "Partido Sin Nombre")
        liga = partido.get("league", {}).get("name", "Liga Desconocida")
        
        prompt = (
            f"Analiza este partido de eSports: {nombre_partido} de la liga {liga}.\n"
            f"Responde ESTRICTAMENTE con esta plantilla exacta, sin introducciones, saludos ni explicaciones adicionales, y sin usar guiones bajos:\n\n"
            f"📊 **Probabilidades:**\n"
            f"• [Equipo 1]: [X]% | [Equipo 2]: [X]%\n"
            f"🎯 **Pronóstico Principal:** [Selección de apuesta] ([X]% probabilidad de acierto)\n"
            f"💡 **Mercado Alternativo:** [Selección de mercado alternativo u over/under]\n"
            f"📈 **Confianza:** [Alta/Media/Baja] ([X]/5)"
        )
        
        analisis = analizar_con_gemini(prompt)
        
        if analisis:
            mensaje_final = f"🎮 **ESPORTS** | {liga}\n⚔️ **{nombre_partido}**\n\n{analisis}"
        else:
            mensaje_final = f"🎮 **PRÓXIMO PARTIDO ESPORTS**\n🏆 *{liga}*\n⚔️ {nombre_partido}\n\n_(Análisis de IA no disponible temporalmente)_"
        
        if enviar_mensaje_telegram(mensaje_final):
            enviados += 1
            time.sleep(4)

    print(f"Proceso eSports completado. Enviados: {enviados}")


if __name__ == "__main__":
    main()
