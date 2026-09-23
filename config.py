# -*- coding: utf-8 -*-
"""Configuración central de BlockDesktop.

Aquí se definen las constantes globales: directorio de datos, PIN de
seguridad y parámetros de monitorización. El PIN pedido es fijo y
obligatorio: 18032008.
"""
import os
from pathlib import Path

NOMBRE_APP = "BlockDesktop"
VERSION = "1.0.0"

# Código PIN obligatorio para desbloquear la interfaz y para poder cerrar
# la propia aplicación. Si se desea cambiar, basta con modificar esta línea.
SECURITY_PIN = "18032008"

# Datos persistentes: se guardan dentro de la carpeta personal del usuario
# (%USERPROFILE%) para que sobrevivan al apagado del equipo.
DATA_DIR = Path.home() / ".blockdesktop"
RULES_FILE = DATA_DIR / "rules.json"
USAGE_FILE = DATA_DIR / "usage.json"

# Monitorización
POLL_INTERVAL = 2          # muestrear la ventana activa cada N segundos
SAVE_EVERY_TICKS = 10      # guardar a disco cada N muestras (~20 s)
ALERT_COOLDOWN = 15        # segundos mínimos entre avisos de un mismo proceso
ALERT_DURATION = 4000      # milisegundos que la alerta permanece en pantalla

# Plataforma: la detección de ventana activa solo funciona en Windows
IS_WINDOWS = os.name == "nt"

# Formato de fechas usado en los ficheros JSON
DATE_FMT = "%Y-%m-%d"