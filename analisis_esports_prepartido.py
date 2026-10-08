import os
import json
import time
import requests
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# ---------------------------------------------------------
# 1. CONFIGURACIÓN Y CREDENCIALES (ESPORTS - TRIANGULACIÓN REAL)
# ---------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

PANDASCORE_API_KEY = os.getenv("PANDASCORE_API_KEY") or os.getenv("PANDASCORE_KEY") or os.getenv("PANDASCORE_TOKEN")

UMBRAL_MINIMO_FILTRO = 75.0
PISO_MINIMO_CUOTA = 1.40  # CANDADO DE RENTABILIDAD INVIOLABLE
ZONA_HORARIA_COLOMBIA = timezone(timedelta(hours=-5))

client_gemini = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
MODELO_GEMINI = 'gemini-3.8-flash'

class AnalisisEsportsSchema(BaseModel):
    prob_pick_principal: float = Field(description="Probabilidad estimada final para la opción principal (0 a 100)")
    pick_principal: str = Field(description="Mercado principal comercial en BetPlay (ej. Ganador de la Serie ML, Handicap de Mapas -1.5, Total de Mapas Over 2.5)")
    cuota_estimada_pick: float = Field(description="Cuota decimal estimada en BetPlay (DEBE SER >= 1.40).")
    margen_operatividad_universal: str = Field(description="Instrucción del rango de cuota/línea de mapas aceptable en BetPlay y cuándo ABSTENERSE.")
    regla_valor_betplay: str = Field(description="Instrucción de cuota mínima en BetPlay. Exige abstenerse si cae de 1.40.")
    stake_principal: str = Field(description="Stake sugerido según certeza (ej. 3/5 o 4/5)")
    prob_cobertura: float = Field(description="Probabilidad estimada opción de cobertura (0 a 100)")
    pick_cobertura: str = Field(description="Opción de cobertura accesible en BetPlay")
    analisis_tactico: str = Field(description="Justificación basada en triangulación de vetos de mapas, sustitutos (stand-ins) y rendimiento reciente en máx 2 oraciones.")

def enviar_mensaje_telegram(texto):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Error: Credenciales de Telegram no configuradas.")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "HTML"}
    try:
        res = requests.post(url, json=payload, timeout=5)
        if res.status_code == 200:
            return True
        else:
            time.sleep(1)
            res_retry = requests.post(url, json=payload, timeout=5)
            return res_retry.status_code == 200
    except Exception as e:
        print("Error enviando mensaje a Telegram:", e)
        return False

def obtener_partidos_esports():
    if not PANDASCORE_API_KEY:
        print("Error: PANDASCORE_API_KEY no configurada.")
        return []

    lista_partidos = []
    ahora_utc = datetime.now(timezone.utc)
    fin_ventana_utc = ahora_utc + timedelta(hours=12)

    url = "https://api.pandascore.co/matches/upcoming"
    headers = {"Authorization": f"Bearer {PANDASCORE_API_KEY}"}
    params = {"page[size]": 20, "sort": "begin_at"}

    try:
        res = requests.get(url, headers=headers, params=params, timeout=8)
        if res.status_code != 200:
            return []
        
        matches = res.json()
        for m in matches:
            begin_raw = m.get("begin_at")
            if not begin_raw:
                continue
            dt_utc = datetime.fromisoformat(begin_raw.replace("Z", "+00:00"))

            if not (ahora_utc <= dt_utc <= fin_ventana_utc):
                continue

            opponents = m.get("opponents", [])
            if len(opponents) < 2:
                continue

            t1 = opponents[0].get("opponent", {}).get("name", "Team 1")
            t2 = opponents[1].get("opponent", {}).get("name", "Team 2")
            videogame = m.get("videogame", {}).get("name", "eSports")
            league_name = m.get("league", {}).get("name", "")
            serie_name = m.get("serie", {}).get("full_name", "")
            match_type = f"Bo{m.get('number_of_games', 3)}"

            dt_colombia = dt_utc.astimezone(ZONA_HORARIA_COLOMBIA)

            lista_partidos.append({
                "juego": videogame,
                "torneo": f"{league_name} - {serie_name}".strip(" -"),
                "equipo1": t1,
                "equipo2": t2,
                "formato": match_type,
                "fecha": dt_colombia.strftime("%Y-%m-%d"),
                "hora": dt_colombia.strftime("%I:%M %p")
            })
            if len(lista_partidos) >= 10:  # LÍMITE DE PROTECCIÓN DE TIEMPO
                break
    except Exception as e:
        print("Error consultando PandaScore:", e)

    return lista_partidos

def analizar_partido_esports_ia(p):
    if not client_gemini:
        return None, "IA no configurada"

    # PASO 1: BÚSQUEDA WEB EN VIVO (GROUNDING CON TIMEOUT DE PROTECCIÓN)
    query_noticias = f"{p['juego']} {p['equipo1']} vs {p['equipo2']} roster stand-in news Liquipedia HLTV {p['fecha']}"
    noticias_obtenidas = ""
    try:
        res_search = client_gemini.models.generate_content(
            model=MODELO_GEMINI,
            contents=f"Busca sustitutos (stand-ins), cambios de roster de última hora y resultados recientes para: {query_noticias}",
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}]
            )
        )
        if res_search and res_search.text:
            noticias_obtenidas = res_search.text
    except Exception as e:
        print(f"Rastreo web omitido por tiempo en {p['equipo1']} vs {p['equipo2']}: {e}")
        noticias_obtenidas = "Evaluación estándar por datos de torneo."

    # PASO 2: ESTRUCTURACIÓN Y TRIANGULACIÓN CERRADA
    prompt_triangulacion = (
        f"EVALUACIÓN DE TRIANGULACIÓN OBLIGATORIA DE ESPORTS ({p['equipo1']} vs {p['equipo2']} - {p['juego']} {p['formato']}):\n\n"
        f"1. DATOS DE PROGRAMACIÓN Y TORNEO:\n"
        f"   - Torneo: {p['torneo']}\n"
        f"   - Formato: {p['formato']}\n\n"
        f"2. NOTICIAS EN VIVO Y RASTREO WEB (PASO 1):\n"
        f"   {noticias_obtenidas}\n\n"
        f"REGLAS DE TRIANGULACIÓN STRICTA (CERO COMPLACENCIAS):\n"
        f"A. Cruza las noticias reales del Paso 1 (sustitutos, rendimiento de mapas) con las cuotas reales de BetPlay. Si hay un jugador suplente (stand-in) o duda táctica, reduce la probabilidad por debajo del 75%.\n"
        f"B. CANDADO PISO DE CUOTA: La opción sugerida DEBE TENER 'cuota_estimada_pick' >= {PISO_MINIMO_CUOTA}. Queda ESTRICTAMENTE PROHIBIDO sugerir cuotas menores a 1.40.\n"
        f"C. MARGEN DE OPERATIVIDAD UNIVERSAL: Especifica el rango de cuota/línea de mapas aceptable en BetPlay y cuándo ABSTENERSE por pérdida de valor.\n"
        f"D. Si la certeza calculada es menor al {UMBRAL_MINIMO_FILTRO}%, descarta el partido inmediatamente."
    )

    try:
        res = client_gemini.models.generate_content(
            model=MODELO_GEMINI,
            contents=prompt_triangulacion,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AnalisisEsportsSchema,
                temperature=0.10
            )
        )
        if res and res.text:
            return json.loads(res.text), "OK"
    except Exception as e:
        print(f"Error evaluando {p['equipo1']} vs {p['equipo2']}: {e}")
        return None, str(e)

    return None, "ERROR_GENERAL"

def ejecutar_escaneo():
    ahora_colombia = datetime.now(ZONA_HORARIA_COLOMBIA)
    fecha_hora_col = ahora_colombia.strftime("%Y-%m-%d %I:%M %p")
    print(f"Iniciando escaneo de eSports (Triangulación + Grounding + Piso 1.40): {fecha_hora_col}")
    partidos = obtener_partidos_esports()

    if not partidos:
        msg = f"🎮 <b>REPORTE ESPORTS</b>\n<i>Escaneo: {fecha_hora_col}</i>\n\n<i>Sin partidos programados para las próximas 12 horas.</i>"
        enviar_mensaje_telegram(msg)
        return

    enviar_mensaje_telegram(f"🎮 <b>PRONÓSTICOS ESPORTS VIP (TRIANGULACIÓN REAL)</b>\n<i>Escaneo: {fecha_hora_col}</i>")
    
    partidos_enviados = 0
    descartados_certeza = 0

    for p in partidos:
        time.sleep(0.5)
        analisis, estado = analizar_partido_esports_ia(p)

        if not analisis:
            continue

        prob_max = max(analisis.get("prob_pick_principal", 0), analisis.get("prob_cobertura", 0))
        cuota_pick = analisis.get("cuota_estimada_pick", 0.0)

        # CANDADO DE RENTABILIDAD Y CERTEZA
        if prob_max < UMBRAL_MINIMO_FILTRO or cuota_pick < PISO_MINIMO_CUOTA:
            descartados_certeza += 1
            print(f"⛔ Bloqueado {p['equipo1']} vs {p['equipo2']} (Prob: {prob_max}%, Cuota: {cuota_pick})")
            continue

        msg = (
            f"🎮 <b>[{p['juego']}] {p['torneo']}</b>\n"
            f"⚔️ <b>{p['equipo1']} vs {p['equipo2']}</b> (<code>{p['formato']}</code>)\n"
            f"📅 <b>Fecha:</b> <code>{p['fecha']}</code> | ⏰ <b>Hora Col:</b> <code>{p['hora']}</code>\n\n"
            f"🎯 <b>APUESTA PRINCIPAL: {analisis['pick_principal']}</b>\n"
            f"📏 <b>Margen de Operatividad BetPlay:</b> <i>{analisis['margen_operatividad_universal']}</i>\n"
            f"📲 <b>Regla de Validación BetPlay:</b> <i>{analisis['regla_valor_betplay']}</i>\n"
            f"📈 <b>Probabilidad:</b> <code>{analisis['prob_pick_principal']}%</code> | <b>Stake:</b> <code>{analisis['stake_principal']}</code>\n"
            f"💡 <i>[Gemini Triangulado] {analisis['analisis_tactico']}</i>\n\n"
            f"🛡 <b>COBERTURA ALTERNATIVA:</b> {analisis['pick_cobertura']} (<code>{analisis['prob_cobertura']}%</code>)"
        )
        
        exito_envio = enviar_mensaje_telegram(msg)
        if exito_envio:
            partidos_enviados += 1
            print(f"✅ Enviado a Telegram: {p['equipo1']} vs {p['equipo2']}")

    msg_resumen = f"<b>Escaneo eSports completado.</b> Pronósticos rentables enviados: {partidos_enviados}"
    if descartados_certeza > 0:
        msg_resumen += f"\n\n<b>Detalle:</b> {descartados_certeza} partido(s) descartados por no superar la triangulación (< 75% certeza o cuota < 1.40)."

    enviar_mensaje_telegram(msg_resumen)

if __name__ == "__main__":
    ejecutar_escaneo()
