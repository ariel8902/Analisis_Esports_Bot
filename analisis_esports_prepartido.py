import os
import json
import time
import requests
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# ---------------------------------------------------------
# 1. CONFIGURACIÓN Y CREDENCIALES (ESPORTS - REFORZADO 80%)
# ---------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_ESPORTS") or os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID_ESPORTS") or os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PANDASCORE_API_KEY = os.getenv("PANDASCORE_TOKEN")

UMBRAL_MINIMO_FILTRO = 80.0  # <-- EXIGENCIA ELEVADA AL 80% PARA FILTRAR VARIANZA
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
    pick_principal: str = Field(description="Mercado principal recomendado (ej. Gana Equipo A Moneyline, Map Handicap +1.5, Over 2.5 Mapas)")
    regla_valor_betplay: str = Field(description="Instrucción de adaptación para BetPlay si no está la línea exacta o si la cuota movió puntos.")
    stake_principal: str = Field(description="Stake sugerido (ej. 3/5 o 4/5)")
    prob_cobertura: float = Field(description="Probabilidad estimada cobertura (0 a 100)")
    pick_cobertura: str = Field(description="Opción de cobertura accesible en BetPlay (ej. Ganador de Mapa 1)")
    analisis_tactico: str = Field(description="Justificación táctica basada en rendimiento de los últimos 10 días, adaptación al parche y explicación de cuota.")

def enviar_mensaje_telegram(texto):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Error: Credenciales de Telegram no configuradas.")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "HTML"}
    try:
        res = requests.post(url, json=payload, timeout=5)
        return res.status_code == 200
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
        f"Formato de serie: {partido['formato']}.\n"
        f"REGLA DE EXIGENCIA ELEVADA: Sé muy estricto con la racha reciente (últimos 10 días). Prioriza Hándicaps de Mapas (+1.5) si el favorito muestra la menor duda.\n"
        f"REGLA BETPLAY: En 'regla_valor_betplay' explica cómo adaptar el pick si BetPlay no ofrece la línea exacta.\n"
        f"Establece en 'pick_principal' la mejor opción con certeza SOLO SI es >= {UMBRAL_MINIMO_FILTRO}%."
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
    print(f"Iniciando escaneo de eSports (Filtro 80%): {fecha_hora_col}")
    partidos = obtener_partidos_esports()

    if not partidos:
        msg = f"🎮 <b>REPORTE ESPORTS</b>\n<i>Escaneo: {fecha_hora_col}</i>\n\n<i>Sin partidas programadas para las próximas 12 horas.</i>"
        enviar_mensaje_telegram(msg)
        return

    enviar_mensaje_telegram(f"🎮 <b>PRONÓSTICOS ESPORTS VIP (FILTRO REFORZADO 80%)</b>\n<i>Escaneo: {fecha_hora_col}</i>")
    
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
        if prob_max < UMBRAL_MINIMO_FILTRO:
            descartados_certeza += 1
            continue

        msg = (
            f"{p['juego']} | <b>{p['torneo']}</b>\n"
            f"⚔️ <b>{p['equipo_a']} vs {p['equipo_b']}</b> (<code>{p['formato']}</code>)\n"
            f"📅 <b>Fecha:</b> <code>{p['fecha']}</code> | ⏰ <b>Hora Col:</b> <code>{p['hora']}</code>\n\n"
            f"🎯 <b>APUESTA PRINCIPAL: {analisis['pick_principal']}</b>\n"
            f"📲 <b>Regla de Valor BetPlay:</b> <i>{analisis['regla_valor_betplay']}</i>\n"
            f"📊 <b>Probabilidad:</b> <code>{analisis['prob_pick_principal']}%</code> | <b>Stake:</b> <code>{analisis['stake_principal']}</code>\n"
            f"💡 <i>[Gemini] {analisis['analisis_tactico']}</i>\n\n"
            f"🛡 <b>COBERTURA ALTERNATIVA:</b> {analisis['pick_cobertura']} (<code>{analisis['prob_cobertura']}%</code>)"
        )
        
        exito_envio = enviar_mensaje_telegram(msg)
        if exito_envio:
            partidos_enviados += 1
            print(f"✅ Enviado a Telegram ({partidos_enviados}/{MAX_PARTIDOS_ENVIAR}): {p['equipo_a']} vs {p['equipo_b']}")

    msg_resumen = f"<b>Escaneo eSports completado.</b> Pronósticos enviados: {partidos_enviados}"
    if partidos_enviados == 0 and descartados_certeza > 0:
        msg_resumen += f"\n\n<b>Detalle:</b> {descartados_certeza} partida(s) analizadas descartadas por no alcanzar el {UMBRAL_MINIMO_FILTRO}% de certeza."

    enviar_mensaje_telegram(msg_resumen)

if __name__ == "__main__":
    ejecutar_escaneo()
