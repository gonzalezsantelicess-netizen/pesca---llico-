#!/usr/bin/env python3
"""
Sistema de deteccion automatica de dias ideales de pesca (corvina) en Llico, Chile.

Cruza pronostico de viento + oleaje (Open-Meteo, gratis) contra tus criterios:
- Viento predominante del sector Norte (rango amplio NO-N-NE)
- Viento < 16 km/h
- Altura de ola entre 1.3 y 2.2 m
- Periodo de ola entre 10 y 13 s
- (Coeficiente de marea: ver nota abajo, no automatizado 100%)

Si encuentra coincidencias en los proximos dias, envia un WhatsApp via CallMeBot.

NOTA SOBRE MAREAS:
No existe una API publica gratuita y confiable con el "coeficiente de marea"
para localidades chilenas especificas. Las dos rutas posibles son:
1) Revisar manualmente tablademareas.com / mareas.shoa.cl antes de confirmar
la salida (recomendado, toma 30 segundos).
2) Si mas adelante quieres automatizarlo tambien, se puede armar un scraper
puntual (1 consulta diaria) a mareas.shoa.cl, pero requiere revisar su
estructura HTML y no esta garantizado que sea estable en el tiempo.
Por ahora, este script te avisa cuando VIENTO + OLEAJE estan buenos, y te
recuerda revisar el coeficiente de marea antes de confirmar.
"""

import os
import sys
from datetime import datetime, timezone
import requests

# ============ CONFIGURACION - AJUSTA AQUI TUS CRITERIOS ============

# Coordenadas de Llico, Arauco (Golfo de Arauco). Ajusta si tu spot es otro.
LATITUD = -37.19
LONGITUD = -73.34

# Criterios de pesca ideal (version flexibilizada)
VIENTO_MAX_KMH = 16.0
VIENTO_DIRECCION_MIN = 280 # sector Noroeste
VIENTO_DIRECCION_MAX = 100 # sector Este-Noreste
OLA_ALTURA_MIN = 1.3
OLA_ALTURA_MAX = 2.2
OLA_PERIODO_MIN = 10.0
OLA_PERIODO_MAX = 13.0

# Cuantos dias hacia adelante revisar
DIAS_PRONOSTICO = 10

# ============ CALLMEBOT (WhatsApp gratis) ============
CALLMEBOT_PHONE = os.environ.get("CALLMEBOT_PHONE", "")
CALLMEBOT_APIKEY = os.environ.get("CALLMEBOT_APIKEY", "")


def es_direccion_norte(grados: float) -> bool:
"""Verifica si el viento sopla desde el sector Norte (rango amplio)."""
return grados >= VIENTO_DIRECCION_MIN or grados <= VIENTO_DIRECCION_MAX


def obtener_pronostico():
"""Consulta Open-Meteo: viento (weather API) + oleaje (marine API)."""

weather_url = (
"https://api.open-meteo.com/v1/forecast"
f"?latitude={LATITUD}&longitude={LONGITUD}"
"&hourly=wind_speed_10m,wind_direction_10m"
"&wind_speed_unit=kmh"
f"&forecast_days={DIAS_PRONOSTICO}"
"&timezone=America%2FSantiago"
)
r_wind = requests.get(weather_url, timeout=30)
r_wind.raise_for_status()
wind_data = r_wind.json()["hourly"]

marine_url = (
"https://marine-api.open-meteo.com/v1/marine"
f"?latitude={LATITUD}&longitude={LONGITUD}"
"&hourly=wave_height,wave_period,wave_direction"
f"&forecast_days={DIAS_PRONOSTICO}"
"&timezone=America%2FSantiago"
)
r_marine = requests.get(marine_url, timeout=30)
r_marine.raise_for_status()
marine_data = r_marine.json()["hourly"]

return wind_data, marine_data


def encontrar_ventanas_ideales(wind_data, marine_data):
"""Cruza ambos datasets hora por hora y devuelve las que cumplen todo."""
resultados = []

tiempos_wind = wind_data["time"]
tiempos_marine = marine_data["time"]

marine_idx = {t: i for i, t in enumerate(tiempos_marine)}

for i, t in enumerate(tiempos_wind):
if t not in marine_idx:
continue
j = marine_idx[t]

viento_kmh = wind_data["wind_speed_10m"][i]
viento_dir = wind_data["wind_direction_10m"][i]
ola_altura = marine_data["wave_height"][j]
ola_periodo = marine_data["wave_period"][j]

if viento_kmh is None or viento_dir is None or ola_altura is None or ola_periodo is None:
continue

cumple = (
viento_kmh < VIENTO_MAX_KMH
and es_direccion_norte(viento_dir)
and OLA_ALTURA_MIN <= ola_altura <= OLA_ALTURA_MAX
and OLA_PERIODO_MIN <= ola_periodo <= OLA_PERIODO_MAX
)

if cumple:
resultados.append({
"fecha_hora": t,
"viento_kmh": round(viento_kmh, 1),
"viento_dir": round(viento_dir, 0),
"ola_altura": round(ola_altura, 2),
"ola_periodo": round(ola_periodo, 1),
})

return resultados


def formatear_mensaje(resultados):
if not resultados:
return None

lineas = ["Dias ideales de pesca detectados en Llico", ""]
for r in resultados:
fecha = r["fecha_hora"].replace("T", " ")
lineas.append(
f"{fecha}\n"
f" Viento: {r['viento_kmh']} km/h ({r['viento_dir']} grados)\n"
f" Ola: {r['ola_altura']}m / periodo {r['ola_periodo']}s\n"
)
lineas.append("Revisa el coeficiente de marea antes de salir:")
lineas.append("https://www.tablademareas.com/cl")
return "\n".join(lineas)


def enviar_whatsapp(mensaje: str):
if not CALLMEBOT_PHONE or not CALLMEBOT_APIKEY:
print("CALLMEBOT_PHONE / CALLMEBOT_APIKEY no configurados. "
"No se envia WhatsApp, solo se imprime el resultado.")
print(mensaje)
return

url = "https://api.callmebot.com/whatsapp.php"
params = {
"phone": CALLMEBOT_PHON
