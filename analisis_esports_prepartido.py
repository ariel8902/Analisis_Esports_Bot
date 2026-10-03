import os
import json
import time
import requests
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from google import genai

# ---------------------------------------------------------
# 1. CONFIGURACIÓN Y CREDENCIALES (ESPORTS)
# ---------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PANDASCORE_API_KEY = os.getenv("PANDASCORE_TOKEN")

UMBRAL_MINIMO_FILTRO = 70.0
ZONA_HORARIA_COLOMBIA = timezone(timedelta(hours=-5))

client_gemini = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
MODELO_GEMINI = 'gemini-3.8-flash'

JUEGOS_ESPORTS = [
    {"nombre": "🎮 Counter-Strike 2", "slug": "csgo"},
    {"nombre": "⚔️ League of Legends", "slug": "league-of-legends"},
    {"nombre": "🛡️ Dota 2", "slug": "dota-2"}
]

class AnalisisEsportsSchema(BaseModel):
    prob_pick_principal: float = Field(description="Probabilidad estimada opción principal (0 a 100)")
    pick_principal: str = Field(description="Mercado principal recomendado (ej. Gana Equipo A, Map Handicap -1.5, Over 2.5 Mapas)")
    stake_principal: str = Field(description="Stake sugerido (ej. 3/5 o 4/5)")
    prob_cobertura: float = Field(description="Probabilidad estimada cobertura (0 a 100)")
    pick_cobertura: str = Field(description="Opción de cobertura (ej. Hándicap Mapas +1.5)")
    analisis_tactico: str = Field(description="Justificación táctica en máx 2 oraciones basada en estado de forma y map pool.")

def enviar_mensaje_telegram(texto):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Error: Credenciales de Telegram no configuradas.")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "HTML"}
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.status_code == 200
    except Exception as e:
        print("Error enviando mensaje a Telegram:", e)
        return False

# ---------------------------------------------------------
# 2. INGESTA DE PARTIDOS ESPORTS (PANDASCORE)
# ---------------------------------------------------------
def obtener_partidos_esports():
    if not PANDASCORE_API_KEY:
        print("Error: PANDASCORE_API_KEY no está configurada.")
        return []

    lista_partidos = []
    ahora_utc = datetime.now(timezone.utc)
    limite_jornada = ahora_utc + timedelta(hours=36)

    headers = {"Authorization": f"Bearer {PANDASCORE_API_KEY}"}

    for juego in JUEGOS_ESPORTS:
        url = f"https://api.pandascore.co/{juego['slug']}/matches/upcoming"
        params = {"page[size]": 10, "sort": "begin_at"}
        try:
            res = requests.get(url, headers=headers, params=params, timeout=10)
            if res.status_code != 200:
                print(f"Error {res.status_code} en PandaScore para {juego['nombre']}")
                continue
            matches = res.json()
            for match in matches:
                begin_raw = match.get("begin_at")
                if not begin_raw:
                    continue
                dt_utc = datetime.fromisoformat(begin_raw.replace("Z", "+00:00"))
                if not (ahora_utc <= dt_utc <= limite_jornada):
                    continue
                dt_colombia = dt_utc.astimezone(ZONA_HORARIA_COLOMBIA)

                opponents = match.get("opponents", [])
                if len(opponents) < 2:
                    continue

                team_a = opponents[0].get("opponent", {}).get("name", "Equipo A")
                team_b = opponents[1].get("opponent", {}).get("name", "Equipo B")
                league_name = match.get("league", {}).get("name", "Torneo eSports")
                match_type = match.get("number_of_games", 3)  # Ej. Best of 3 (Bo3)

                lista_partidos.append({
                    "juego": juego["nombre"],
                    "torneo": league_name,
                    "equipo_a": team_a,
                    "equipo_b": team_b,
                    "formato": f"Bo{match_type}",
                    "fecha": dt_colombia.strftime("%Y-%m-%d"),
                    "hora": dt_colombia.strftime("%H:%M")
                })
            time.sleep(0.3)
        except Exception as e:
            print(f"Error consultando {juego['nombre']}:", e)

    return lista_partidos

# ---------------------------------------------------------
# 3. EVALUACIÓN Y VALIDACIÓN CON IA (GEMINI 3.8)
# ---------------------------------------------------------
def analizar_partido_esports_ia(partido):
    if not client_gemini:
        return None, "IA no configurada"

    prompt = (
        f"Analiza el partido de eSports: {partido['equipo_a']} vs {partido['equipo_b']} ({partido['juego']} - {partido['torneo']}).\n"
        f"Formato de serie: {partido['formato']}.\n"
        f"Considera factores competitivos de eSports (estado de forma reciente, sinergia del roster, map pool habitual y jerarquía en el torneo).\n"
        f"Establece en 'pick_principal' la mejor alternativa de valor (Ganador de Serie, Hándicap de Mapas o Total Mapas) con certeza >= 70%."
    )

    try:
        res = client_gemini.models.generate_content(
            model=MODELO_GEMINI,
            contents=prompt,
            config={"response_mime_type": "application/json", "response_schema": AnalisisEsportsSchema}
        )
        if res and res.text:
            return json.loads(res.text), "OK"
    except Exception as e:
        print(f"Error evaluando {partido['equipo_a']} vs {partido['equipo_b']}: {e}")
        return None, str(e)

    return None, "ERROR_GENERAL"

# ---------------------------------------------------------
# 4. ORQUESTADOR PRINCIPAL
# ---------------------------------------------------------
def ejecutar_escaneo():
    fecha_colombia = datetime.now(ZONA_HORARIA_COLOMBIA).strftime("%Y-%m-%d")
    print(f"Iniciando escaneo de eSports Prepartido: {fecha_colombia}")
    partidos = obtener_partidos_esports()

    if not partidos:
        msg = f"🎮 <b>REPORTE ESPORTS - {fecha_colombia}</b>\n\n<i>Sin partidas programadas en la ventana de las próximas 36 horas.</i>"
        enviar_mensaje_telegram(msg)
        print("Finalizado: Sin partidas eSports en la ventana actual.")
        return

    enviar_mensaje_telegram(f"🎮 <b>PRONÓSTICOS ESPORTS VIP</b> | Escaneo: <b>{fecha_colombia}</b>")
    
    partidos_enviados = 0
    descartados_certeza = 0

    for p in partidos:
        time.sleep(2)
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
            f"📅 <b>Fecha:</b> <code>{p['fecha']}</code> | ⏰ <b>Hora:</b> <code>{p['hora']}</code>\n\n"
            f"🎯 <b>APUESTA PRINCIPAL: {analisis['pick_principal']}</b>\n"
            f"📊 <b>Probabilidad:</b> <code>{analisis['prob_pick_principal']}%</code> | <b>Stake:</b> <code>{analisis['stake_principal']}</code>\n"
            f"💡 <i>[Gemini] {analisis['analisis_tactico']}</i>\n\n"
            f"🛡 <b>COBERTURA ALTERNATIVA:</b> {analisis['pick_cobertura']} (<code>{analisis['prob_cobertura']}%</code>)"
        )
        
        exito_envio = enviar_mensaje_telegram(msg)
        if exito_envio:
            partidos_enviados += 1
            print(f"✅ Enviado a Telegram: {p['equipo_a']} vs {p['equipo_b']}")

    msg_resumen = f"<b>Escaneo eSports completado.</b> Pronósticos enviados: {partidos_enviados}"
    if partidos_enviados == 0 and descartados_certeza > 0:
        msg_resumen += f"\n\n<b>Detalle:</b> {descartados_certeza} partida(s) analizadas no alcanzaron el {UMBRAL_MINIMO_FILTRO}% de certeza."

    enviar_mensaje_telegram(msg_resumen)
    print(f"Proceso eSports completado. Enviados: {partidos_enviados}")

if __name__ == "__main__":
    ejecutar_escaneo()
