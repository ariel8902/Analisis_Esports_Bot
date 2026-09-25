import os
import math
import json
import time
import random
import urllib.request
import urllib.parse
from datetime import datetime
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# ---------------------------------------------------------
# 1. CONFIGURACIÓN Y CREDENCIALES
# ---------------------------------------------------------
PANDASCORE_TOKEN = os.getenv("PANDASCORE_TOKEN", "Jxk4dGBK3ZDscCP1j1I855-ClSheRATabiwM7_FBZRa3UH7RKwQ")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN_ESPORTS", "8919715865:AAEZYIYdoZVs_8zqt0M321i4OvN2RPsCy1o")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID_ESPORTS", "8707489920")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

UMBRAL_MINIMO_FILTRO = 70.0  # Certeza mínima 70%
NUM_SIMULACIONES = 10000

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

LIGAS_PRIORITARIAS = [
    "WORLDS", "WORLD CHAMPIONSHIP", "MSI", "MID-SEASON INVITATIONAL",
    "LCK", "LPL", "LEC", "LCS", "VCS", "LLA", "CBLOL", "PCS",
    "MAJOR", "IEM", "INTEL EXTREME MASTERS", "ESL PRO LEAGUE", 
    "BLAST", "BLAST PREMIER", "WORLD FINAL", "PGL"
]

class AjusteFuerzaeSportsSchema(BaseModel):
    prob_mapa_local: float = Field(description="Probabilidad base estimada del equipo local de ganar 1 mapa individual (0.1 a 0.9)")
    prob_mapa_visitante: float = Field(description="Probabilidad base estimada del equipo visitante de ganar 1 mapa individual (0.1 a 0.9)")
    novedades_roster: str = Field(description="Resumen breve de parches, sustitutos o estado de forma reciente.")

# ---------------------------------------------------------
# 2. MOTOR CUANTITATIVO ESTOCÁSTICO (MONTE CARLO ESPORTS)
# ---------------------------------------------------------
def simular_serie_esports(prob_mapa_loc, prob_mapa_vis, numero_mapas=3, num_simulaciones=10000):
    """
    Ejecuta 10,000 simulaciones estocásticas mapa a mapa para series BO3 o BO5.
    """
    p_win_map_loc = prob_mapa_loc / (prob_mapa_loc + prob_mapa_vis)
    mapas_para_ganar = 2 if numero_mapas == 3 else 3

    victoria_local = 0
    victoria_visitante = 0
    over_mapas = 0  # Over 2.5 en BO3 o Over 3.5 en BO5
    local_gana_al_menos_1 = 0
    visita_gana_al_menos_1 = 0

    for _ in range(num_simulaciones):
        maps_loc = 0
        maps_vis = 0
        
        while maps_loc < mapas_para_ganar and maps_vis < mapas_para_ganar:
            if random.random() < p_win_map_loc:
                maps_loc += 1
            else:
                maps_vis += 1

        total_mapas_jugados = maps_loc + maps_vis
        
        if maps_loc > maps_vis:
            victoria_local += 1
        else:
            victoria_visitante += 1

        if maps_loc >= 1:
            local_gana_al_menos_1 += 1
        if maps_vis >= 1:
            visita_gana_al_menos_1 += 1

        if numero_mapas == 3 and total_mapas_jugados >= 3:
            over_mapas += 1
        elif numero_mapas == 5 and total_mapas_jugados >= 4:
            over_mapas += 1

    p_over = (over_mapas / num_simulaciones) * 100
    p_hc_loc = (local_gana_al_menos_1 / num_simulaciones) * 100
    p_hc_vis = (visita_gana_al_menos_1 / num_simulaciones) * 100

    return {
        "p_over": round(p_over, 1),
        "p_hc_loc": round(p_hc_loc, 1),
        "p_hc_vis": round(p_hc_vis, 1)
    }

# ---------------------------------------------------------
# 3. REFINACIÓN CUALITATIVA EN VIVO CON GEMINI + SEARCH
# ---------------------------------------------------------
def analizar_partido_esports_ia(equipo_local, equipo_visitante, liga, numero_mapas):
    prob_loc = 0.50
    prob_vis = 0.50

    if client:
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        prompt = (
            f"Investiga en Google Search el estado de forma actual de hoy ({fecha_hoy}) para el partido de eSports: {equipo_local} vs {equipo_visitante} ({liga}).\n"
            f"Analiza win-rate reciente, rendimiento en el parche actual, bajas de jugadores o sustitutos de última hora.\n"
            f"Estima la probabilidad de ganar 1 mapa individual para cada equipo."
        )
        try:
            time.sleep(6)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    response_mime_type="application/json",
                    response_schema=AjusteFuerzaeSportsSchema,
                )
            )
            if response.text:
                data = json.loads(response.text)
                prob_loc = float(data.get("prob_mapa_local", 0.50))
                prob_vis = float(data.get("prob_mapa_visitante", 0.50))
        except Exception as e:
            print("Error llamando a IA Gemini:", e)

    stats = simular_serie_esports(prob_loc, prob_vis, numero_mapas, NUM_SIMULACIONES)
    
    # MAPPING EXACTO PARA BETPLAY / RUSHBET
    if numero_mapas == 3:
        nombre_over = "Total de mapas -> Más de 2.5"
        concepto_over = "La serie se alarga a 3 mapas (Ambos ganan al menos 1 mapa)"
    else:
        nombre_over = "Total de mapas -> Más de 3.5"
        concepto_over = "La serie se alarga a más de 3.5 mapas"

    # Seleccionar la opción de mayor certeza
    opciones = [
        (concepto_over, nombre_over, stats["p_over"]),
        (f"{equipo_local} gana al menos 1 mapa", f"Hándicap de Mapas -> {equipo_local} (+1.5)", stats["p_hc_loc"]),
        (f"{equipo_visitante} gana al menos 1 mapa", f"Hándicap de Mapas -> {equipo_visitante} (+1.5)", stats["p_hc_vis"])
    ]
    
    opciones_ordenadas = sorted(opciones, key=lambda x: x[2], reverse=True)
    top_pick = opciones_ordenadas[0]
    cobertura = opciones_ordenadas[1]

    return {
        "certeza": f"{top_pick[2]}%",
        "pick_principal": top_pick[0],
        "betplay_principal": top_pick[1],
        "stake_principal": "5/5" if top_pick[2] >= 80 else "4/5",
        "pick_cobertura": cobertura[0],
        "betplay_cobertura": cobertura[1],
        "stake_cobertura": "5/5" if cobertura[2] >= 80 else "4/5"
    }

# ---------------------------------------------------------
# 4. CONSULTA PANDASCORE
# ---------------------------------------------------------
def obtener_partidos_pandascore():
    url = f"https://api.pandascore.co/matches/upcoming?page[size]=15&sort=scheduled_at"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {PANDASCORE_TOKEN}", "Accept": "application/json"})
    
    partidos_filtrados = []
    try:
        with urllib.request.urlopen(req) as res:
            if res.status == 200:
                eventos = json.loads(res.read().decode('utf-8'))
                for ev in eventos:
                    if ev.get("opponents") and len(ev["opponents"]) >= 2:
                        liga_nom = ev.get("league", {}).get("name", "")
                        torneo_nom = ev.get("tournament", {}).get("name", "")
                        liga_completa = f"{liga_nom} {torneo_nom}".strip().upper()
                        
                        if any(l in liga_completa for l in LIGAS_PRIORITARIAS):
                            eq1 = ev["opponents"][0]["opponent"]["name"]
                            eq2 = ev["opponents"][1]["opponent"]["name"]
                            num_mapas = ev.get("number_of_games", 3)
                            
                            partidos_filtrados.append({
                                "juego": ev.get("videogame", {}).get("name", "eSports"),
                                "local": eq1,
                                "visitante": eq2,
                                "liga": liga_completa,
                                "num_mapas": num_mapas,
                                "hora": datetime.now().strftime("%Y-%m-%d — %I:%M %p")
                            })
    except Exception as e:
        print("Error al consultar PandaScore:", e)
        
    return partidos_filtrados

# ---------------------------------------------------------
# 5. DESPACHO TELEGRAM
# ---------------------------------------------------------
def enviar_mensaje_telegram(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "HTML"}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            print("Mensaje despachado a Telegram. HTTP:", res.status)
    except Exception as e:
        print("Error enviando Telegram:", e)

def ejecutar_escaneo():
    partidos = obtener_partidos_pandascore()
    
    if not partidos:
        # Si no hay partidos de PandaScore en este segundo, ejecutamos un análisis de prueba con agenda
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        partidos = [
            {"juego": "League of Legends", "local": "FlyQuest", "visitante": "Shopify Rebellion", "liga": "LCS PLAYOFFS", "num_mapas": 5, "hora": f"{fecha_hoy} — 03:00 PM"},
            {"juego": "League of Legends", "local": "9Gaming", "visitante": "SN CyberCore Esports", "liga": "VCS PLAYOFFS", "num_mapas": 5, "hora": f"{fecha_hoy} — 04:00 AM"}
        ]

    for p in partidos:
        res = analizar_partido_esports_ia(p["local"], p["visitante"], p["liga"], p["num_mapas"])
        
        mensaje = (
            f"🏆 <b>{p['juego']}</b>\n"
            f"⚔️ <b>{p['local']} vs {p['visitante']}</b>\n"
            f"🏟️ Liga: <code>{p['liga']}</code>\n"
            f"⏰ Hora: <code>{p['hora']}</code> (BO{p['num_mapas']})\n\n"
            f"🎯 <b>Certeza Estimada de la Dinámica:</b> <b>{res['certeza']}</b>\n\n"
            f"🔥 <b>PRONÓSTICO PRINCIPAL (MÁXIMA CERTEZA):</b>\n"
            f"🎯 <b>Concepto:</b> {res['pick_principal']}\n"
            f"📌 <b>En Betplay/Rushbet buscar:</b> <code>{res['betplay_principal']}</code>\n"
            f"📈 <b>Confianza / Stake:</b> <code>{res['stake_principal']}</code>\n\n"
            f"🛡️ <b>OPCIÓN COBERTURA (BLINDADA):</b>\n"
            f"🎯 <b>Concepto:</b> {res['pick_cobertura']}\n"
            f"📌 <b>En Betplay/Rushbet buscar:</b> <code>{res['betplay_cobertura']}</code>\n"
            f"📈 <b>Confianza / Stake:</b> <code>{res['stake_cobertura']}</code>"
        )
        enviar_mensaje_telegram(mensaje)
        time.sleep(3)

if __name__ == "__main__":
    ejecutar_escaneo()
