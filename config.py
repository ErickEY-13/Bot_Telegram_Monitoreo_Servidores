# ============================================================
# config.py - Configuración central del bot
# ============================================================
# Este archivo centraliza toda la configuración del proyecto:
# - Credenciales del bot y SSH
# - Lista de servicios a monitorear en cada servidor
# - Intervalos de monitoreo
# ============================================================

import os
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
# Esto permite que las credenciales no estén hardcodeadas en el código
load_dotenv()

# ---- TOKEN DEL BOT DE TELEGRAM ----
# Se obtiene de @BotFather al crear el bot
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ---- CHAT IDs AUTORIZADOS ----
# Chat ID del usuario autorizado para ejecutar comandos de reinicio
# Solo este usuario puede reiniciar servicios (seguridad básica)
AUTHORIZED_CHAT_ID = os.getenv("AUTHORIZED_CHAT_ID", "0")

# Chat ID donde se envían las alertas automáticas de monitoreo
# Puede ser el mismo usuario, un grupo, o un canal
ALERT_CHAT_ID = os.getenv("ALERT_CHAT_ID", "0")

# ---- CONFIGURACIÓN SSH PARA MV1 Y MV2 (Servidores remotos) ----
# Ahora el bot corre localmente en Windows y se conecta a ambas MVs por SSH
SSH_CONFIG = {
    "mv1": {
        "host": os.getenv("MV1_SSH_HOST", "174.138.52.116"),
        "port": int(os.getenv("MV1_SSH_PORT", "22")),
        "username": os.getenv("MV1_SSH_USER", "usuario"),
        "password": os.getenv("MV1_SSH_PASSWORD", ""),
        "key_path": os.getenv("MV1_SSH_KEY_PATH", ""),
        "key_passphrase": os.getenv("MV1_SSH_KEY_PASSPHRASE", ""),
    },
    "mv2": {
        "host": os.getenv("MV2_SSH_HOST", "192.168.1.100"),
        "port": int(os.getenv("MV2_SSH_PORT", "22")),
        "username": os.getenv("MV2_SSH_USER", "usuario"),
        "password": os.getenv("MV2_SSH_PASSWORD", ""),
        "key_path": os.getenv("MV2_SSH_KEY_PATH", ""),
        "key_passphrase": os.getenv("MV2_SSH_KEY_PASSPHRASE", ""),
    }
}

# ---- SERVICIOS A MONITOREAR ----
SERVIDORES = {
    "mv1": {
        "nombre": "MV1 Ayma",
        "servicios": [
            "apache2",
            "mysql",
            "vsftpd",
            "ssh",
        ],
    },
    "mv2": {
        "nombre": "MV2 Poma",
        "servicios": [
            "apache2",
            "mysql",
            "vsftpd",
            "ssh",
        ],
    },
}

# ---- INTERVALO DE MONITOREO ----
# Cada cuántos segundos se revisa el estado de todos los servicios
# 60 segundos = 1 minuto (ideal para demos y pruebas rápidas)
INTERVALO_MONITOREO = 60

# ---- CONFIGURACIÓN DE LOGS ----
# Cuántas líneas del log del servicio mostrar por defecto
LINEAS_LOG = 20

# Si el mensaje de log supera este número de caracteres,
# se envía como archivo en lugar de como mensaje de texto
MAX_CARACTERES_MENSAJE = 3500

# ---- RUTA DE LA BASE DE DATOS ----
# Archivo SQLite donde se guarda el historial de eventos
# Se crea automáticamente si no existe
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "historial.db")
