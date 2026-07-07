# 🤖 Guía Completa de Comandos - Bot de Monitoreo

## 🖱️ Menú Interactivo (Botones)

| Comando | Qué hace |
|---|---|
| `/start` | Abre el menú principal con botones para elegir **MV1 Ayma** o **MV2 Poma** |

Al seleccionar un servidor → eliges un servicio → y aparecen estas acciones:

| Botón | Acción |
|---|---|
| 📊 **Ver estado** | ¿Está corriendo o caído? |
| 📋 **Ver logs** | Últimas 20 líneas del journal del servicio |
| 🔄 **Reiniciar** | Reinicia el servicio (pide confirmación) 🔒 |
| ⏹️ **Detener** | Apaga el servicio (pide confirmación) 🔒 |
| ▶️ **Iniciar** | Enciende el servicio (pide confirmación) 🔒 |

> 🔒 = Solo usuarios autorizados (admin)

---

## ⌨️ Comandos con Barra `/`

### Consulta (cualquier usuario)

| Comando | Ejemplo | Descripción |
|---|---|---|
| `/start` | `/start` | Menú principal con botones |
| `/help` | `/help` | Muestra toda la ayuda del bot |
| `/estado <servicio> <mv>` | `/estado apache2 mv1` | Estado de un servicio específico |
| `/logs <servicio> <mv>` | `/logs mysql mv2` | Últimas líneas del log de un servicio |
| `/status_general` | `/status_general` | Estado de **TODOS** los servicios en ambas MVs |
| `/historial` | `/historial` | Últimos 10 eventos (caídas, reinicios, etc.) |
| `/ping <mv>` | `/ping mv1` | Latencia del servidor hacia internet (8.8.8.8) |
| `/uptime <mv>` | `/uptime mv2` | Tiempo que lleva encendido el servidor |
| `/graficas` | `/graficas` | Menú de gráficos y estadísticas visuales |

### Administración (solo admin 🔒)

| Comando | Ejemplo | Descripción |
|---|---|---|
| `/reiniciar <servicio> <mv>` | `/reiniciar apache2 mv1` | Reinicia un servicio (pide confirmación) |
| `/backup <tipo> <mv>` | `/backup mysql mv1` | Genera backup y lo envía por Telegram |
| `/backup <tipo> <mv>` | `/backup web mv2` | Tipos: `mysql` o `web` |
| `/ejecutar <mv> <comando>` | `/ejecutar mv1 df -h` | Ejecuta **cualquier comando Linux** en el servidor |
| `/ejecutar <mv> <comando>` | `/ejecutar mv1 netstat -tlnp` | Otro ejemplo |
| `/ejecutar <mv> <comando>` | `/ejecutar mv2 who` | Ver quién está conectado |

---

## 💬 Comandos de Texto Natural (sin `/`)

Escribe estas frases exactas en el chat:

| Texto | Qué muestra |
|---|---|
| `ver espacio` | 💾 Almacenamiento en disco de ambas MVs (usado/total/libre) |
| `ver memoria` | 🧠 Uso de RAM de ambas MVs |
| `ver cpu` | ⚙️ Uso de CPU y carga del sistema de ambas MVs |
| `ver usuario` | 👤 Usuarios conectados en ambas MVs |
| `estado servicio apache2` | Estado de apache2 en ambas MVs |
| `estado servicio mysql` | Estado de mysql en ambas MVs |
| `estado servicio ftp` | Estado de FTP en ambas MVs (alias → vsftpd) |
| `estado servicio ssh` | Estado de SSH en ambas MVs |
| `dame mi id` | 🤫 Muestra tu Chat ID real (comando secreto) |

---

## 📊 Gráficos (desde `/graficas`)

| Botón | Gráfico |
|---|---|
| 📊 Caídas por Servicio | Histórico de caídas de todos los servicios |
| 📈 Rendimiento MV1 | CPU y RAM histórico de MV1 Ayma |
| 📈 Rendimiento MV2 | CPU y RAM histórico de MV2 Poma |

---

## 🔔 Alertas Automáticas (sin hacer nada)

| Evento | Alerta |
|---|---|
| 🔴 Servicio se cae | Alerta inmediata al chat configurado |
| 🟢 Servicio se recupera | Notificación de recuperación |
| 📊 Cada día a las **8:00am** | Resumen completo del estado de todo |
| ⏱️ Revisión cada **60 segundos** | Monitoreo continuo automático |

---

## 🖥️ Servidores Monitoreados

| Servidor | IP | Servicios |
|---|---|---|
| **MV1 Ayma** | `174.138.52.116` | apache2, mysql, vsftpd, ssh |
| **MV2 Poma** | `52.162.237.197` | apache2, mysql, vsftpd, ssh |

---

## 🛠️ Comandos del Servidor (SSH a 161.132.4.32)

Para administrar el bot en el servidor:

```bash
# Ver estado del bot
systemctl status bot_monitoreo

# Ver logs en tiempo real
journalctl -u bot_monitoreo -f

# Reiniciar el bot
systemctl restart bot_monitoreo

# Detener el bot
systemctl stop bot_monitoreo

# Actualizar el bot (tras push a GitHub)
cd /opt/bot_monitoreo && git pull origin main
source venv/bin/activate && pip install -r requirements.txt
systemctl restart bot_monitoreo
```

---

## 🔒 Permisos

| Rol | Puede hacer |
|---|---|
| **Cualquier usuario** | Ver estado, logs, recursos, ping, uptime, gráficas |
| **Admin** (Chat IDs autorizados) | Todo lo anterior + reiniciar, detener, iniciar, ejecutar comandos, backups |

> Chat IDs autorizados: `-5360731046` (grupo) y `6536181396` (privado)
