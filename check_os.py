import os
import sys
from dotenv import load_dotenv

# Asegurar que se carguen las variables
load_dotenv('.env')

from ssh_manager import _ejecutar_remoto

print("Conectando...")
codigo, salida, error = _ejecutar_remoto("cat /etc/os-release", "mv1")
print(f"Código: {codigo}")
print(f"Salida: {salida}")
print(f"Error: {error}")
