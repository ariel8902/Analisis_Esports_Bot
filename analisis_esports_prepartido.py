importar sistema operativo
importar json
hora de importación
solicitudes de importación
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
Importar genai desde Google

# ---------------------------------------------------------
# 1. CONFIGURACIÓN Y CREDENCIALES (ESPORTS)
# ---------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PANDASCORE_API_KEY = os.getenv("PANDASCORE_TOKEN")

UMBRAL_MINIMO_FILTRO = 75.0 # Elevado al 75% para mayor rentabilidad y precisión
MAX_PARTIDOS_ENVIAR = 10 # Máximo de pronósticos por ejecución
ZONA_HORARIA_COLOMBIA = zona horaria(timedelta(horas=-5))

client_gemini = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
MODELO_GEMINI = 'géminis-3.8-flash'

# Slugs de PandaScore corregidos
JUEGOS_ESPORTS = [
    {"nombre": "🎮 Counter-Strike 2", "slug": "csgo"},
    {"nombre": "⚔️ League of Legends", "slug": "lol"},
    {"nombre": "🛡️ Dota 2", "slug": "dota2"}
]

clase AnalisisEsportsSchema(BaseModel):
    prob_pick_principal: float = Field(description="Probabilidad estimada opción principal (0 a 100)")
    pick_principal: str = Field(description="Mercado principal recomendado (ej. Gana Equipo A, Map Handicap -1.5, Over 2.5 Mapas)")
    stake_principal: str = Campo(descripción="Stake sugerido (ej. 3/5 o 4/5)")
    prob_cobertura: float = Field(description="Probabilidad estimada cobertura (0 a 100)")
    pick_cobertura: str = Field(description="Opción de cobertura (ej. Hándicap Mapas +1.5)")
    analisis_tactico: str = Field(description="Justificación táctica en máx 2 oraciones basada en rendimiento de los últimos 10 días y map pool.")

def enviar_mensaje_telegram(texto):
    si no es TELEGRAM_BOT_TOKEN o no es TELEGRAM_CHAT_ID:
        print("Error: Credenciales de Telegram no configuradas.")
        devolver Falso
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "HTML"}
    intentar:
        res = requests.post(url, json=payload, timeout=10)
        devolver res.status_code == 200
    excepto Excepción como e:
        print("Error enviando mensaje a Telegram:", e)
        devolver Falso

# ---------------------------------------------------------
# 2. INGESTA DE PARTIDOS ESPORTS (PANDASCORE)
# ---------------------------------------------------------
def obtener_partidos_esports():
    Si no existe PANDASCORE_API_KEY:
        print("Error: PANDASCORE_API_KEY no está configurado.")
        devolver []

    lista_partidos = []
    ahora_utc = datetime.now(timezone.utc)
    limite_jornada = ahora_utc + timedelta(horas=36)

    encabezados = {"Autorización": f"Portador {PANDASCORE_API_KEY}"}

    para juego en JUEGOS_ESPORTS:
        url = f"https://api.pandascore.co/{juego['slug']}/matches/upcoming"
        parámetros = {"página[tamaño]": 10, "ordenar": "inicio_en"}
        intentar:
            res = requests.get(url, headers=headers, params=params, timeout=10)
            Si res.status_code != 200:
                print(f"Error {res.status_code} en PandaScore para {juego['nombre']}")
                continuar
            coincidencias = res.json()
            para partido en partidos:
                begin_raw = match.get("begin_at")
                si no begin_raw:
                    continuar
                dt_utc = datetime.fromisoformat(begin_raw.replace("Z", "+00:00"))
                si no (ahora_utc <= dt_utc <= limite_jornada):
                    continuar
                dt_colombia = dt_utc.astimezone(ZONA_HORARIA_COLOMBIA)

                oponentes = match.get("oponentes", [])
                Si len(oponentes) < 2:
                    continuar

                equipo_a = oponentes[0].get("oponente", {}).get("nombre", "Equipo A")
                equipo_b = oponentes[1].get("oponente", {}).get("nombre", "Equipo B")
                nombre_liga = partido.get("liga", {}).get("nombre", "Torneo eSports")
                tipo_partido = partido.get("número_de_partidos", 3)

                lista_partidos.append({
                    "juego": juego["nombre"],
                    "torneo": nombre_de_la_liga,
                    "equipo_a": equipo_a,
                    "equipo_b": equipo_b,
                    "formato": f"Bo{match_type}",
                    "fecha": dt_colombia.strftime("%Y-%m-%d"),
                    "hora": dt_colombia.strftime("%H:%M")
                })
            tiempo.dormir(0.3)
        excepto Excepción como e:
            print(f"Error consultando {juego['nombre']}:", e)

    devolver lista_partidos

# ---------------------------------------------------------
# 3. EVALUACIÓN Y VALIDACIÓN CON IA (GÉMINIS 3.8)
# ---------------------------------------------------------
def analizar_partido_esports_ia(partido):
    si no client_gemini:
        return Ninguno, "IA no configurada"

    mensaje = (
        f"Analiza el partido de eSports: {partido['equipo_a']} vs {partido['equipo_b']} ({partido['juego']} - {partido['torneo']}).\n"
        f"Formato de serie: {partido['formato']}.\n"
        f"IMPORTANTE: Restringe tu evaluación táctica al rendimiento, racha y estado de forma de los equipos/jugadores durante los ÚLTIMOS 10 DÍAS, adaptación al parche actual y map pool reciente.\n"
        f"Establece en 'pick_principal' la mejor alternativa de valor (Ganador de Serie, Hándicap de Mapas o Total Mapas) con certeza >= 75%."
    )

    intentar:
        res = client_gemini.models.generate_content(
            modelo=MODELO_GEMINI,
            contenido=prompt,
            config={"response_mime_type": "application/json", "response_schema": AnalisisEsportsSchema}
        )
        si res y res.text:
            return json.loads(res.text), "OK"
    excepto Excepción como e:
        print(f"Error evaluando {partido['equipo_a']} vs {partido['equipo_b']}: {e}")
        devolver Ninguno, str(e)

    Devuelve None, "ERROR_GENERAL"

# ---------------------------------------------------------
# 4. ORQUESTADOR PRINCIPAL
# ---------------------------------------------------------
def ejecutar_escaneo():
    fecha_colombia = fechahora.now(ZONA_HORARIA_COLOMBIA).strftime("%Y-%m-%d")
    print(f"Iniciando escaneo de eSports Prepartido: {fecha_colombia}")
    partidos = obtener_partidos_esports()

    si no hay partidos:
        msg = f"🎮 <b>REPORTE ESPORTS - {fecha_colombia}</b>\n\n<i>Sin partidas programadas en la ventana de las próximas 36 horas.</i>"
        enviar_mensaje_telegram(msg)
        print("Finalizado: Sin partidas eSports en la ventana actual.")
        devolver

    enviar_mensaje_telegram(f"🎮 <b>PRONÓSTICOS ESPORTS VIP</b> | Escaneo: <b>{fecha_colombia}</b>")
    
    partidos_enviados = 0
    descartados_certeza = 0

    para p en partidos:
        si partidos_enviados >= MAX_PARTIDOS_ENVIAR:
            print(f"Límite alcanzado ({MAX_PARTIDOS_ENVIAR} partidas). Deteniendo envíos.")
            romper

        time.sleep(3) # Pausa de 3 segundos para evitar el error 503 por tasa de solicitudes
        analisis, estado = analizar_partido_esports_ia(p)

        si no análisis:
            continuar

        prob_max = max(analisis.get("prob_pick_principal", 0), analis.get("prob_cobertura", 0))
        si prob_max < UMBRAL_MINIMO_FILTRO:
            descartados_certeza += 1
            continuar

        mensaje = (
            f"{p['juego']} | <b>{p['torneo']}</b>\n"
            f"⚔️ <b>{p['equipo_a']} vs {p['equipo_b']}</b> (<code>{p['formato']}</code>)\n"
            f"📅 <b>Fecha:</b> <code>{p['fecha']}</code> | ⏰ <b>Hora:</b> <code>{p['hora']}</code>\n\n"
            f"🎯 <b>APUESTA PRINCIPAL: {analisis['pick_principal']}</b>\n"
            f"📊 <b>Probabilidad:</b> <code>{analisis['prob_pick_principal']}%</code> | <b>Stake:</b> <code>{analisis['stake_principal']}</code>\n"
            f"💡 <i>[Géminis] {análisis['análisis_táctico']}</i>\n\n"
            f"🛡 <b>COBERTURA ALTERNATIVA:</b> {analisis['pick_cobertura']} (<code>{analisis['prob_cobertura']}%</code>)"
        )
        
        exito_envio = enviar_mensaje_telegram(msg)
        si exito_envio:
            partidos_enviados += 1
            print(f"✅ Enviado a Telegram ({partidos_enviados}/{MAX_PARTIDOS_ENVIAR}): {p['equipo_a']} vs {p['equipo_b']}")

    msg_resumen = f"<b>Escaneo eSports completado.</b> Pronósticos enviados: {partidos_enviados}"
    si partidos_enviados == 0 y descartados_certeza > 0:
        msg_resumen += f"\n\n<b>Detalle:</b> {descartados_certeza} partida(s) analizadas no alcanzaron el {UMBRAL_MINIMO_FILTRO}% de certeza."

    enviar_mensaje_telegram(msg_resumen)
    print(f"Proceso eSports completado. Enviados: {partidos_enviados}")

if __name__ == "__main__":
    ejecutar_escaneo()
