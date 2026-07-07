# 🤖 Bot de Telegram — Monitor de Servidores Linux

Bot de Telegram para monitorear y administrar servicios en dos servidores Linux remotos (**MV1 Ayma** y **MV2 Poma**). El bot corre en tu computadora local (Windows) y se conecta a los servidores mediante SSH.

---

## 📋 Funcionalidades

- **Menú interactivo** con botones para elegir máquina y servicio
- **Ver estado** de servicios (activo/inactivo/fallido)
- **Reiniciar, Detener e Iniciar** servicios con confirmación previa
- **Ver logs** en tiempo real desde Telegram
- **Recursos del servidor**: CPU, RAM, disco duro
- **Auditoría de accesos SSH**: últimos logins y intentos fallidos
- **Monitoreo automático** con alertas si un servicio cae o se recupera
- **Historial de eventos** guardado en SQLite
- **Control de acceso**: solo el admin puede realizar acciones críticas

---

## 📁 Estructura del Proyecto

```
proyecto-taco/
├── bot.py              # Lógica principal del bot
├── config.py           # Configuración (tokens, servicios, SSH)
├── ssh_manager.py      # Ejecución de comandos remotos por SSH
├── db.py               # Base de datos SQLite (historial)
├── requirements.txt    # Dependencias de Python
├── .env                # Variables de entorno (NO subir a Git)
├── GUIA_INICIO.md      # ⬅️ Instrucciones para ejecutar el proyecto
├── MANUAL_MV2.md       # Instrucciones para configurar la segunda MV
└── historial.db        # Base de datos (se crea automáticamente)
```

---

## 🏗️ Arquitectura del Sistema

```
[Tu celular / Telegram]
        ↕ HTTPS
[Telegram API]
        ↕ HTTPS
[Bot Python - Windows] ──── SSH ──▶ [MV1 Ayma - 174.138.52.116]
                       ──── SSH ──▶ [MV2 Poma - IP futura]
```

El bot actúa como intermediario: recibe tus botones de Telegram, abre una conexión SSH al servidor correspondiente, ejecuta el comando (ej. `systemctl restart nginx`) y te devuelve el resultado en Telegram.

---

## 🚀 Cómo ejecutar el proyecto

> **Lee el archivo [GUIA_INICIO.md](GUIA_INICIO.md)** — tiene el paso a paso completo con capturas de ejemplo.

**Resumen rápido:**
```powershell
# 1. Activa el entorno virtual
.\venv\Scripts\activate

# 2. Inicia el bot
python bot.py

# 3. Ve a Telegram y escribe /start en @EYACFEPM_BOT
```

---

## ⚙️ Configuración (.env)

Edita el archivo `.env` con tus credenciales:

```env
# Token del bot (de @BotFather)
TELEGRAM_BOT_TOKEN=8745997202:AAG...

# Tu Chat ID (de @userinfobot)
AUTHORIZED_CHAT_ID=6536181396
ALERT_CHAT_ID=6536181396

# SSH para MV1 Ayma
MV1_SSH_HOST=174.138.52.116
MV1_SSH_PORT=22
MV1_SSH_USER=root
MV1_SSH_PASSWORD=tu_contraseña

# SSH para MV2 Poma (cuando la tengas)
MV2_SSH_HOST=ip_de_mv2
MV2_SSH_PORT=22
MV2_SSH_USER=root
MV2_SSH_PASSWORD=contraseña_mv2
```

---

## 🖥️ Servicios monitoreados

| MV | Servicios |
|----|-----------|
| **MV1 Ayma** | nginx, mysql, ufw, ssh |
| **MV2 Poma** | apache2, redis-server, fail2ban, ssh |

Para cambiar los servicios, edita el diccionario `SERVIDORES` en [config.py](config.py).

---

## 📱 Comandos disponibles en Telegram

| Comando | Ejemplo | Descripción |
|---------|---------|-------------|
| `/start` | `/start` | Menú interactivo con botones |
| `/help` | `/help` | Instrucciones completas |
| `/estado` | `/estado nginx mv1` | Estado de un servicio |
| `/reiniciar` | `/reiniciar mysql mv1` | Reiniciar servicio |
| `/logs` | `/logs nginx mv1` | Últimas líneas del log |
| `/status_general` | `/status_general` | Estado general de todo |
| `/historial` | `/historial` | Últimos 10 eventos |
| `/cpu_ram` | `/cpu_ram mv1` | Uso de CPU y RAM |
| `/disco` | `/disco mv1` | Espacio en disco |
| `/ultimo_login` | `/ultimo_login mv1` | Auditoría de accesos SSH |

---

## 🔒 Seguridad

- Solo el `AUTHORIZED_CHAT_ID` puede **reiniciar, detener o iniciar** servicios
- Todos los demás usuarios pueden **ver estado y logs**
- Cada acción crítica pide **confirmación** con botones antes de ejecutarse
- Todas las acciones quedan registradas en el **historial** con fecha y usuario

---

## 🔧 Configurar MV2

Cuando tengas tu segunda máquina virtual, sigue las instrucciones en [MANUAL_MV2.md](MANUAL_MV2.md).
