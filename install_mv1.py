import os
import sys
import time
from dotenv import load_dotenv

load_dotenv('.env')

from ssh_manager import _ejecutar_remoto

comandos = [
    # Actualizar lista de paquetes
    "apt-get update -y",
    # Instalar paquetes (DEBIAN_FRONTEND evita que pida confirmaciones interactivas como la zona horaria)
    "DEBIAN_FRONTEND=noninteractive apt-get install -y nginx mysql-server ufw",
    # Habilitar servicios para que arranquen con el sistema
    "systemctl enable nginx mysql ssh",
    # Configurar y habilitar UFW (Firewall)
    "ufw allow 22/tcp",
    "ufw allow 80/tcp",
    "ufw --force enable"
]

print("Iniciando instalación de servicios en MV1...")

for cmd in comandos:
    print(f"\nEjecutando: {cmd}")
    codigo, salida, error = _ejecutar_remoto(cmd, "mv1")
    print(f"Código: {codigo}")
    if salida:
        print(f"Salida: {salida[:500]}...") # Imprimir un resumen
    if error:
        print(f"Error: {error[:500]}...")

print("\n¡Instalación completa!")
