#!/bin/bash
# ============================================================
# deploy.sh - Script de despliegue del Bot en el servidor
# ============================================================
# Ejecutar como root en el servidor: bash deploy.sh
# ============================================================

set -e

echo "========================================"
echo " Desplegando Bot de Monitoreo Telegram"
echo "========================================"

# 1. Instalar dependencias del sistema
echo ""
echo "[1/6] Instalando dependencias del sistema..."
apt update -y
apt install -y python3 python3-pip python3-venv git

# 2. Crear directorio del proyecto
echo ""
echo "[2/6] Creando directorio del proyecto..."
mkdir -p /opt/bot_monitoreo
cd /opt/bot_monitoreo

# 3. Clonar el repositorio (si no existe) o actualizar
echo ""
echo "[3/6] Descargando código del repositorio..."
if [ -d ".git" ]; then
    echo "Repositorio ya existe, actualizando..."
    git pull origin main
else
    git clone https://github.com/ErickEY-13/Bot_Telegram_Monitoreo_Servidores.git .
fi

# 4. Crear entorno virtual e instalar dependencias
echo ""
echo "[4/6] Configurando entorno virtual Python..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 5. Verificar que existe el archivo .env
echo ""
echo "[5/6] Verificando configuración..."
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  IMPORTANTE: No se encontró el archivo .env"
    echo "   Debes crear el archivo /opt/bot_monitoreo/.env con tus credenciales."
    echo "   Puedes usar .env.example como plantilla:"
    echo "   cp .env.example .env && nano .env"
    echo ""
fi

# 6. Configurar servicio systemd
echo ""
echo "[6/6] Configurando servicio systemd..."
cp bot_monitoreo.service /etc/systemd/system/bot_monitoreo.service
systemctl daemon-reload
systemctl enable bot_monitoreo
systemctl start bot_monitoreo

echo ""
echo "========================================"
echo " ✅ Despliegue completado!"
echo "========================================"
echo ""
echo "Comandos útiles:"
echo "  Ver estado:    systemctl status bot_monitoreo"
echo "  Ver logs:      journalctl -u bot_monitoreo -f"
echo "  Reiniciar:     systemctl restart bot_monitoreo"
echo "  Detener:       systemctl stop bot_monitoreo"
echo ""
