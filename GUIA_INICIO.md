# 🚀 Guía de Inicio — Bot Monitor de Servidores

Esta guía explica paso a paso cómo encender el bot y cómo usarlo desde cero.

---

## ✅ Requisitos previos
Antes de empezar, asegúrate de tener:
- **Python 3.10+** instalado en tu computadora Windows
- **La carpeta del proyecto** (la que tiene `bot.py`, `config.py`, etc.)
- **Conexión a internet**
- **Las máquinas virtuales** encendidas y accesibles

---

## 🔌 Paso 1: Abrir la terminal correcta

1. Abre la carpeta del proyecto en el **Explorador de Archivos** de Windows
2. Haz **clic derecho** en un espacio vacío dentro de la carpeta
3. Selecciona **"Abrir en Terminal"** (o **"Abrir ventana de PowerShell aquí"**)

> Si no tienes esa opción, abre PowerShell y escribe:
> ```powershell
> cd "C:\Users\Hyperion\Downloads\proyecto taco"
> ```

---

## ⚙️ Paso 2: Activar el entorno virtual

Escribe esto en la terminal y presiona Enter:

```powershell
.\venv\Scripts\activate
```

Sabrás que funcionó cuando el prompt cambie y muestre `(venv)` al inicio:
```
(venv) PS C:\Users\Hyperion\Downloads\proyecto taco>
```

> ⚠️ **Importante:** Debes hacer este paso SIEMPRE antes de iniciar el bot. Sin el entorno virtual, Python no encontrará las librerías instaladas.

---

## ▶️ Paso 3: Iniciar el bot

Con el entorno virtual activo, escribe:

```powershell
python bot.py
```

Deberías ver en la terminal algo como esto:
```
INFO - Base de datos inicializada
INFO - Creando aplicación del bot...
INFO - Monitoreo automático configurado cada 300 segundos
INFO - 🤖 Bot iniciado. Esperando mensajes...
```

¡El bot ya está corriendo! Ahora puedes ir a Telegram y usarlo.

---

## 📱 Paso 4: Usar el bot en Telegram

1. Abre Telegram en tu celular o computadora
2. Busca tu bot: **@EYACFEPM_BOT**
3. Presiona el botón **INICIAR** o escribe `/start`

### Flujo básico del menú:
```
/start
  → [MV1 Ayma]  [MV2 Poma]
      ↓
  Selecciona un servicio (nginx, mysql, ufw, ssh)
      ↓
  [📊 Ver estado] [📋 Ver logs]
  [🔄 Reiniciar]  [⏹️ Detener]  [▶️ Iniciar]
```

### Comandos disponibles:
| Comando | Ejemplo | Descripción |
|---------|---------|-------------|
| `/start` | `/start` | Abre el menú interactivo |
| `/help` | `/help` | Muestra todas las instrucciones |
| `/estado` | `/estado nginx mv1` | Ver estado de un servicio |
| `/reiniciar` | `/reiniciar mysql mv1` | Reiniciar un servicio |
| `/logs` | `/logs nginx mv1` | Ver los últimos logs |
| `/status_general` | `/status_general` | Estado de todos los servicios |
| `/historial` | `/historial` | Últimas 10 acciones registradas |
| `/cpu_ram` | `/cpu_ram mv1` | Ver uso de CPU y RAM |
| `/disco` | `/disco mv1` | Ver espacio en disco |
| `/ultimo_login` | `/ultimo_login mv1` | Ver últimos accesos SSH |

---

## ⏹️ Paso 5: Detener el bot

Para apagar el bot, ve a la terminal donde está corriendo y presiona:
```
Ctrl + C
```

---

## 🔄 Volver a iniciar el bot (la próxima vez)

La próxima vez que quieras usar el bot, solo repite los pasos 1, 2 y 3:
1. Abrir terminal en la carpeta del proyecto
2. `.\venv\Scripts\activate`
3. `python bot.py`

---

## ❓ Problemas comunes

### El bot no responde en Telegram
- Verifica que la terminal esté abierta y mostrando "Esperando mensajes..."
- Asegúrate de tener internet en tu computadora

### Aparece "Timeout" al consultar servicios
- Verifica que la MV esté encendida
- Verifica que el puerto 22 (SSH) esté abierto en el proveedor de nube

### Error "No module named..."
- Olvidaste activar el entorno virtual. Ejecuta `.\venv\Scripts\activate` primero

### El bot ya está corriendo (error "Conflict")
- Ya hay una instancia activa. Cierra esa terminal o ejecuta:
  ```powershell
  taskkill /F /IM python.exe
  ```
  Y luego vuelve a ejecutar `python bot.py`

### Error: "la ejecución de scripts está deshabilitada en este sistema"
Este es un error de seguridad de Windows al intentar activar el entorno virtual (`.\venv\Scripts\activate`).
**Solución:** Escribe este comando en la terminal, presiona Enter y luego escribe "S" (o "Y") para aceptar:
```powershell
Set-ExecutionPolicy Unrestricted -Scope CurrentUser
```
Una vez hecho eso, vuelve a intentar activar el entorno virtual.
