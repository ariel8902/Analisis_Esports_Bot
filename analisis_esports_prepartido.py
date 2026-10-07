import os
import json
import time
import requests
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# ---------------------------------------------------------
# 1. CONFIGURACIÓN Y CREDENCIALES (ESPORTS - PISO 1.40)
# ---------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_ESPORTS") or os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID_ESPORTS") or os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PANDASCORE_API_KEY = os.getenv("PANDASCORE_TOKEN")

UMBRAL_MINIMO_FILTRO = 75.0
PISO_MINIMO_CUOTA = 1.40  # CANDADO DE RENTABILIDAD
MAX_PARTIDOS_ENVIAR = 10
ZONA_HORARIA_COLOMBIA = timezone(timedelta(hours=-5))

client_gemini = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
MODELO_GEMINI = 'gemini-3.8-flash'

JUEGOS_ESPORTS = [
    {"nombre": "🎮 Counter-Strike 2", "slug": "csgo"},
    {"nombre": "⚔️ League of Legends", "slug": "lol"},
    {"nombre": "🛡️ Dota 2", "slug": "dota2"}
]

class AnalisisEsportsSchema(BaseModel):
    prob_pick_principal: float = Field(description="Probabilidad estimada opción principal (0 a 100)")
    pick_principal: str = Field(description="Mercado comercial en BetPlay (ej. Ganador de Serie ML, Hándicap de Mapas +1.5, Total de Mapas Over 2.5)")
    cuota_piso_permitida: float = Field(description="Cuota mínima exacta permitida en BetPlay para esta opción (DEBE SER >= 1.40).")
    rango_cuota_permitido: str = Field(description="Instrucción de cuota en BetPlay (ej. 'Entrar solo si la cuota en BetPlay está entre 1.45 y 1.75. ABSTENERSE si paga menos de 1.40 o más de 2.10').")
    stake_principal: str = Field(description="Stake sugerido según certeza (ej. 3/5 o 4/5)")
    prob_cobertura: float = Field(description="Probabilidad estimada cobertura (0 a 100)")
    pick_cobertura: str = Field(description="Opción de cobertura comercial (ej. Ganador de Mapa 1)")
    analisis_tactico: str = Field(description="Justificación táctica en máx 2 oraciones.")

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
            time.sleep(2)
            res_retry = requests.post(url, json=payload, timeout=5)
            return res_retry.status_code == 200
    except Exception as e:
        print("Error enviando mensaje a Telegram:", e)
        return False

def obtener_partidos_esports():
    if not PANDASCORE_API_KEY:
        print("Error: PANDASCORE_TOKEN no está configurado.")
        return []

    lista_partidos = []
    ahora_utc = datetime.now(timezone.utc)
    fin_ventana_utc = ahora_utc + timedelta(hours=12)

    headers = {"Authorization": f"Bearer {PANDASCORE_API_KEY}"}

    for juego in JUEGOS_ESPORTS:
        url = f"https://api.pandascore.co/{juego['slug']}/matches/upcoming"
        params = {"page[size]": 20, "sort": "begin_at"}
        try:
            res = requests.get(url, headers=headers, params=params, timeout=5)
            if res.status_code != 200:
                continue
            
            coincidencias = res.json()
            for match in coincidencias:
                begin_raw = match.get("begin_at")
                if not begin_raw:
                    continue
                
                dt_utc = datetime.fromisoformat(begin_raw.replace("Z", "+00:00"))
                
                if not (ahora_utc <= dt_utc <= fin_ventana_utc):
                    continue

                dt_colombia = dt_utc.astimezone(ZONA_HORARIA_COLOMBIA)
                opponents = match.get("opponents", [])
                if len(opponents) < 2:
                    continue
                
                equipo_a = opponents[0].get("opponent", {}).get("name", "Equipo A")
                equipo_b = opponents[1].get("opponent", {}).get("name", "Equipo B")
                nombre_liga = match.get("league", {}).get("name", "Torneo eSports")
                match_type = match.get("number_of_games", 3)

                lista_partidos.append({
                    "juego": juego["nombre"],
                    "torneo": nombre_liga,
                    "equipo_a": equipo_a,
                    "equipo_b": equipo_b,
                    "formato": f"Bo{match_type}",
                    "fecha": dt_colombia.strftime("%Y-%m-%d"),
                    "hora": dt_colombia.strftime("%I:%M %p")
                })
            time.sleep(0.3)
        except Exception as e:
            print(f"Error consultando {juego['nombre']}:", e)
    return lista_partidos

def analizar_partido_esports_ia(partido):
    if not client_gemini:
        return None, "IA no configurada"

    prompt = (
        f"Analiza el partido de eSports para las PRÓXIMAS 12 HORAS: {partido['equipo_a']} vs {partido['equipo_b']} ({partido['juego']} - {partido['torneo']}).\n"
        f"Formato de serie: {partido['formato']}.\n\n"
        f"REGLA DE RENTABILIDAD Y AUDITORÍA DE CUOTA BETPLAY:\n"
        f"1. Tu 'pick_principal' DEBE SER OBLIGATORIAMENTE un mercado disponible en BetPlay (Ganador de Serie, Hándicap +1.5 Mapas o Total de Mapas Over 2.5).\n"
        f"2. CANDADO PISO DE CUOTA: La opción recomendada DEBE PAGAR OBLIGATORIAMENTE >= {PISO_MINIMO_CUOTA}. Queda estrictamente PROHIBIDO sugerir o dar como buena una cuota menor a 1.40 (ej. 1.15, 1.20, 1.30).\n"
        f"3. En 'cuota_piso_permitida' asigna el valor flotante de la cuota mínima permitida (mínimo 1.40).\n"
        f"4. En 'rango_cuota_permitido' da la orden explícita de ABSTENERSE si en BetPlay la cuota paga menos de 1.40 o si supera 2.10 por riesgo de suplentes."
    )

    try:
        res = client_gemini.models.generate_content(
            model=MODELO_GEMINI,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AnalisisEsportsSchema,
                temperature=0.10
            )
        )
        if res and res.text:
            return json.loads(res.text), "OK"
    except Exception as e:
        print(f"Error evaluando {partido['equipo_a']} vs {partido['equipo_b']}: {e}")
        return None, str(e)

    return None, "ERROR_GENERAL"

def ejecutar_escaneo():
    ahora_colombia = datetime.now(ZONA_HORARIA_COLOMBIA)
    fecha_hora_col = ahora_colombia.strftime("%Y-%m-%d %I:%M %p")
    print(f"Iniciando escaneo de eSports (Piso Cuota 1.40 - Filtro 75%): {fecha_hora_col}")
    partidos = obtener_partidos_esports()

    if not partidos:
        msg = f"🎮 <b>REPORTE ESPORTS</b>\n<i>Escaneo: {fecha_hora_col}</i>\n\n<i>Sin partidas programadas para las próximas 12 horas.</i>"
        enviar_mensaje_telegram(msg)
        return

    enviar_mensaje_telegram(f"🎮 <b>PRONÓSTICOS ESPORTS VIP (PISO CUOTA 1.40)</b>\n<i>Escaneo: {fecha_hora_col}</i>")
    
    partidos_enviados = 0
    descartados_certeza = 0

    for p in partidos:
        if partidos_enviados >= MAX_PARTIDOS_ENVIAR:
            break

        time.sleep(1.5)
        analisis, estado = analizar_partido_esports_ia(p)

        if not analisis:
            continue

        prob_max = max(analisis.get("prob_pick_principal", 0), analisis.get("prob_cobertura", 0))
        cuota_piso = analisis.get("cuota_piso_permitida", 0.0)

        # CANDADO DE RENTABILIDAD: Si la certeza es < 75% O la cuota es < 1.40, SE BLOQUEA EL ENVÍO
        if prob_max < UMBRAL_MINIMO_FILTRO or cuota_piso < PISO_MINIMO_CUOTA:
            descartados_certeza += 1
            print(f"⛔ Bloqueado {p['equipo_a']} vs {p['equipo_b']} (Prob: {prob_max}%, Cuota Piso: {cuota_piso})")
            continue

        msg = (
            f"{p['juego']} | <b>{p['torneo']}</b>\n"
            f"⚔️ <b>{p['equipo_a']} vs {p['equipo_b']}</b> (<code>{p['formato']}</code>)\n"
            f"📅 <b>Fecha:</b> <code>{p['fecha']}</code> | ⏰ <b>Hora Col:</b> <code>{p['hora']}</code>\n\n"
            f"🎯 <b>APUESTA PRINCIPAL: {analisis['pick_principal']}</b>\n"
            f"🔎 <b>Rango de Cuota BetPlay:</b> <i>{analisis['rango_cuota_permitido']}</i>\n"
            f"📊 <b>Probabilidad:</b> <code>{analisis['prob_pick_principal']}%</code> | <b>Stake:</b> <code>{analisis['stake_principal']}</code>\n"
            f"💡 <i>[Gemini] {analisis['analisis_tactico']}</i>\n\n"
            f"🛡 <b>COBERTURA ALTERNATIVA:</b> {analisis['pick_cobertura']} (<code>{analisis['prob_cobertura']}%</code>)"
        )
        
        exito_envio = enviar_mensaje_telegram(msg)
        if exito_envio:
            partidos_enviados += 1
            print(f"✅ Confirmado Telegram ({partidos_enviados}/{MAX_PARTIDOS_ENVIAR}): {p['equipo_a']} vs {p['equipo_b']}")

    msg_resumen = f"<b>Escaneo eSports completado.</b> Pronósticos rentables enviados: {partidos_enviados}"
    if partidos_enviados == 0 and descartados_certeza > 0:
        msg_resumen += f"\n\n<b>Detalle:</b> {descartados_certeza} partida(s) descartadas por cuota no rentable (< 1.40) o baja certeza."

    enviar_mensaje_telegram(msg_resumen)
    print(f"Proceso eSports completado. Enviados: {partidos_enviados}")

if __name__ == "__main__":
    ejecutar_escaneo()
