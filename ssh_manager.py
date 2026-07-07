# ============================================================
# ssh_manager.py - Gestión de comandos locales y remotos (SSH)
# ============================================================
# Este módulo se encarga de ejecutar comandos en los servidores:
# - MV1: comandos ejecutados localmente con subprocess
# - MV2: comandos ejecutados remotamente con paramiko (SSH)
#
# Funciones principales:
# - ejecutar_comando(): enruta al método correcto según la MV
# - obtener_estado_servicio(): verifica si un servicio está activo
# - reiniciar_servicio(): reinicia un servicio con systemctl
# - obtener_logs_servicio(): obtiene las últimas líneas del log
# ============================================================

import subprocess
import paramiko
import logging
from config import SSH_CONFIG

# Configurar el logger para este módulo
logger = logging.getLogger(__name__)



_clientes_ssh = {}

def _ejecutar_remoto(comando: str, mv: str) -> tuple[int, str, str]:
    """
    Ejecuta un comando en el servidor remoto (MV1 o MV2) a través de SSH.

    Usa la librería paramiko para establecer una conexión SSH,
    ejecutar el comando y retornar el resultado.

    Utiliza CONEXIONES PERSISTENTES para acelerar los tiempos de respuesta.

    Args:
        comando: string con el comando a ejecutar
        mv: "mv1" o "mv2"

    Returns:
        tupla (código_salida, stdout, stderr)
    """
    if mv not in SSH_CONFIG:
        return -1, "", f"Error: MV '{mv}' no encontrada en la configuración SSH."

    # Intentar reusar conexión existente
    if mv in _clientes_ssh:
        cliente = _clientes_ssh[mv]
        transport = cliente.get_transport()
        if transport and transport.is_active():
            try:
                stdin, stdout, stderr = cliente.exec_command(comando, timeout=30)
                salida = stdout.read().decode("utf-8", errors="ignore").strip()
                error = stderr.read().decode("utf-8", errors="ignore").strip()
                codigo_salida = stdout.channel.recv_exit_status()
                return codigo_salida, salida, error
            except Exception as e:
                logger.warning(f"Conexión persistente falló en {mv}, reconectando: {e}")
                cliente.close()
                del _clientes_ssh[mv]

    config_mv = SSH_CONFIG[mv]

    # Crear un nuevo cliente SSH para esta operación
    cliente_ssh = paramiko.SSHClient()

    # AutoAddPolicy acepta automáticamente las claves del servidor
    # En producción se podría usar una política más estricta
    cliente_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        # Preparar los parámetros de conexión
        params_conexion = {
            "hostname": config_mv["host"],
            "port": config_mv["port"],
            "username": config_mv["username"],
            "timeout": 10,  # Timeout de conexión de 10 segundos
        }

        # Decidir si usar clave SSH o contraseña para autenticarse
        if config_mv["key_path"]:
            # Autenticación por clave SSH (más segura)
            clave = paramiko.RSAKey.from_private_key_file(
                config_mv["key_path"],
                password=config_mv["key_passphrase"] or None
            )
            params_conexion["pkey"] = clave
            logger.info(f"Conectando a {mv.upper()} con clave SSH")
        else:
            # Autenticación por contraseña
            params_conexion["password"] = config_mv["password"]
            logger.info(f"Conectando a {mv.upper()} con contraseña")

        # Establecer la conexión SSH
        cliente_ssh.connect(**params_conexion)

        # Guardar cliente abierto
        _clientes_ssh[mv] = cliente_ssh

        # Ejecutar el comando en el servidor remoto
        # exec_command retorna tres canales: stdin, stdout, stderr
        stdin, stdout, stderr = cliente_ssh.exec_command(comando, timeout=30)

        # Leer las salidas y obtener el código de retorno
        salida = stdout.read().decode("utf-8").strip()
        error = stderr.read().decode("utf-8").strip()
        codigo_salida = stdout.channel.recv_exit_status()

        return codigo_salida, salida, error

    except paramiko.AuthenticationException:
        logger.error(f"Error de autenticación SSH con {mv.upper()}")
        return -1, "", f"Error: Autenticación SSH fallida con {mv.upper()}. Verifica credenciales."
    except paramiko.SSHException as e:
        logger.error(f"Error SSH con {mv.upper()}: {e}")
        return -1, "", f"Error SSH: {str(e)}"
    except TimeoutError:
        logger.error(f"Timeout conectando a {mv.upper()} por SSH")
        return -1, "", f"Error: No se pudo conectar a {mv.upper()} (timeout)"
    except Exception as e:
        logger.error(f"Error inesperado con SSH en {mv.upper()}: {e}")
        return -1, "", f"Error: {str(e)}"
    finally:
        # NO CERRAMOS la conexión para mantenerla viva
        pass


def ejecutar_comando(comando: str, mv: str) -> tuple[int, str, str]:
    """
    Función principal que ejecuta el comando por SSH.

    Args:
        comando: string con el comando a ejecutar
        mv: "mv1" o "mv2"

    Returns:
        tupla (código_salida, stdout, stderr)
    """
    if mv in ["mv1", "mv2"]:
        logger.info(f"Ejecutando en {mv.upper()} (remoto): {comando}")
        return _ejecutar_remoto(comando, mv)
    else:
        # Si la MV no es válida, retornar error
        return -1, "", f"Error: MV '{mv}' no reconocida. Usa 'mv1' o 'mv2'."


def obtener_estado_servicio(servicio: str, mv: str) -> dict:
    """
    Verifica el estado de un servicio usando systemctl.

    Usa 'systemctl is-active' para saber si el servicio está corriendo.
    También obtiene información detallada con 'systemctl status'.

    Args:
        servicio: nombre del servicio (ej: "apache2", "mysql")
        mv: "mv1" o "mv2"

    Returns:
        diccionario con:
        - "activo": bool indicando si está corriendo
        - "estado": string con el estado ("active", "inactive", "failed", etc.)
        - "detalle": string con información detallada del servicio
        - "error": string con mensaje de error si lo hubo (vacío si todo OK)
    """
    # Primero verificamos si está activo (retorna "active", "inactive" o "failed")
    codigo, salida, error = ejecutar_comando(
        f"systemctl is-active {servicio}", mv
    )

    # systemctl is-active retorna 0 si está activo, otro código si no
    activo = (salida == "active")
    estado = salida if salida else "desconocido"

    # Obtener detalles adicionales del servicio (últimas líneas del status)
    codigo_det, detalle, _ = ejecutar_comando(
        f"systemctl status {servicio} --no-pager -l 2>/dev/null | head -15", mv
    )

    return {
        "activo": activo,
        "estado": estado,
        "detalle": detalle if detalle else "No se pudo obtener detalle",
        "error": error if codigo != 0 and not salida else "",
    }


def reiniciar_servicio(servicio: str, mv: str) -> dict:
    """
    Reinicia un servicio usando systemctl restart.

    Asume que sudo está configurado sin contraseña para el usuario
    que ejecuta el bot (en MV1) o el usuario SSH (en MV2).

    Args:
        servicio: nombre del servicio a reiniciar
        mv: "mv1" o "mv2"

    Returns:
        diccionario con:
        - "exito": bool indicando si el reinicio fue exitoso
        - "mensaje": string con detalle del resultado
    """
    logger.info(f"Reiniciando servicio '{servicio}' en {mv}")

    # Ejecutar el reinicio con sudo
    codigo, salida, error = ejecutar_comando(
        f"sudo systemctl restart {servicio}", mv
    )

    if codigo == 0:
        # Verificar que el servicio realmente arrancó después del reinicio
        estado = obtener_estado_servicio(servicio, mv)
        if estado["activo"]:
            return {
                "exito": True,
                "mensaje": f"✅ Servicio '{servicio}' reiniciado correctamente en {mv.upper()}",
            }
        else:
            return {
                "exito": False,
                "mensaje": f"⚠️ Se ejecutó el reinicio de '{servicio}' en {mv.upper()}, "
                           f"pero el servicio no está activo. Estado: {estado['estado']}",
            }
    else:
        return {
            "exito": False,
            "mensaje": f"❌ Error al reiniciar '{servicio}' en {mv.upper()}: {error}",
        }


def obtener_logs_servicio(servicio: str, mv: str, lineas: int = 20) -> dict:
    """
    Obtiene las últimas líneas del log de un servicio.

    Usa journalctl para obtener los logs del servicio gestionado por systemd.

    Args:
        servicio: nombre del servicio
        mv: "mv1" o "mv2"
        lineas: número de líneas a obtener (por defecto 20)

    Returns:
        diccionario con:
        - "exito": bool
        - "logs": string con las líneas del log
        - "error": string con mensaje de error si lo hubo
    """
    # journalctl -u filtra por unidad de servicio
    # --no-pager evita el paginado interactivo
    # -n limita el número de líneas
    # --no-hostname omite el nombre del host para ahorrar espacio
    codigo, salida, error = ejecutar_comando(
        f"sudo journalctl -u {servicio} --no-pager -n {lineas} --no-hostname", mv
    )

    if codigo == 0 and salida:
        return {
            "exito": True,
            "logs": salida,
            "error": "",
        }
    elif salida:
        # A veces journalctl retorna código no-cero pero sí tiene salida
        return {
            "exito": True,
            "logs": salida,
            "error": "",
        }
    else:
        return {
            "exito": False,
            "logs": "",
            "error": error if error else "No se encontraron logs para este servicio",
        }


def detener_servicio(servicio: str, mv: str) -> dict:
    """
    Detiene un servicio usando systemctl stop.

    Args:
        servicio: nombre del servicio a detener
        mv: "mv1" o "mv2"

    Returns:
        diccionario con "exito" (bool) y "mensaje" (str)
    """
    logger.info(f"Deteniendo servicio '{servicio}' en {mv}")

    codigo, salida, error = ejecutar_comando(
        f"sudo systemctl stop {servicio}", mv
    )

    if codigo == 0:
        # Verificar que realmente se detuvo
        estado = obtener_estado_servicio(servicio, mv)
        if not estado["activo"]:
            return {
                "exito": True,
                "mensaje": f"⏹️ Servicio *{servicio}* detenido correctamente en {mv.upper()}.",
            }
        else:
            return {
                "exito": False,
                "mensaje": f"⚠️ Se ejecutó stop para *{servicio}* en {mv.upper()}, pero sigue activo.",
            }
    else:
        return {
            "exito": False,
            "mensaje": f"❌ Error al detener *{servicio}* en {mv.upper()}: {error}",
        }


def iniciar_servicio(servicio: str, mv: str) -> dict:
    """
    Inicia un servicio usando systemctl start.

    Args:
        servicio: nombre del servicio a iniciar
        mv: "mv1" o "mv2"

    Returns:
        diccionario con "exito" (bool) y "mensaje" (str)
    """
    logger.info(f"Iniciando servicio '{servicio}' en {mv}")

    codigo, salida, error = ejecutar_comando(
        f"sudo systemctl start {servicio}", mv
    )

    if codigo == 0:
        estado = obtener_estado_servicio(servicio, mv)
        if estado["activo"]:
            return {
                "exito": True,
                "mensaje": f"▶️ Servicio *{servicio}* iniciado correctamente en {mv.upper()}.",
            }
        else:
            return {
                "exito": False,
                "mensaje": f"⚠️ Se ejecutó start para *{servicio}* en {mv.upper()}, pero no está activo. Estado: {estado['estado']}",
            }
    else:
        return {
            "exito": False,
            "mensaje": f"❌ Error al iniciar *{servicio}* en {mv.upper()}: {error}",
        }


def obtener_cpu_ram(mv: str) -> dict:
    """
    Obtiene el uso actual de CPU y RAM del servidor.

    Usa 'top -bn1' para CPU y 'free -h' para RAM.

    Args:
        mv: "mv1" o "mv2"

    Returns:
        diccionario con "exito" (bool), "cpu" (str), "ram" (str), "error" (str)
    """
    logger.info(f"Obteniendo CPU/RAM de {mv}")

    # Obtener uso de CPU (línea de %Cpu del top)
    cod_cpu, cpu_raw, _ = ejecutar_comando(
        "top -bn1 | grep '%Cpu'", mv
    )

    # Obtener uso de RAM
    cod_ram, ram_raw, _ = ejecutar_comando(
        "free -h", mv
    )

    # Obtener load average (carga del sistema)
    cod_load, load_raw, _ = ejecutar_comando(
        "uptime", mv
    )

    if cod_ram != 0 and not ram_raw:
        return {"exito": False, "cpu": "", "ram": "", "error": "No se pudo obtener información de CPU/RAM"}

    return {
        "exito": True,
        "cpu": cpu_raw if cpu_raw else "No disponible",
        "ram": ram_raw if ram_raw else "No disponible",
        "load": load_raw if load_raw else "No disponible",
        "error": "",
    }


def obtener_recursos_numerico(mv: str) -> dict:
    """
    Obtiene el porcentaje de uso de CPU y RAM como números flotantes.
    Útil para gráficos.
    """
    try:
        # Usar top -bn2 -d 0.5 y tomar la segunda lectura para tener el uso en tiempo real real, no el promedio desde que encendió
        cmd_cpu = "top -bn2 -d 0.5 | grep 'Cpu(s)' | tail -n 1"
        cmd_ram = "free | grep Mem | awk '{print $3/$2 * 100.0}'"
        cmd_load = "uptime | awk -F'load average:' '{print $2}'"
        
        cod_c, cpu_str, _ = ejecutar_comando(cmd_cpu, mv)
        cod_r, ram_str, _ = ejecutar_comando(cmd_ram, mv)
        _, load_str, _ = ejecutar_comando(cmd_load, mv)
        
        # Extraer el valor 'id' (idle) de la cadena de top usando regex
        import re
        cpu_usage = 0.0
        if cod_c == 0:
            match_id = re.search(r"([\d\.]+)\s*id", cpu_str)
            if match_id:
                idle = float(match_id.group(1))
                cpu_usage = 100.0 - idle
        
        if cod_c == 0 and cod_r == 0:
            return {
                "exito": True,
                "cpu": cpu_usage,
                "ram": float(ram_str.strip() or 0.0),
                "load": load_str.strip() or "No disponible"
            }
    except Exception as e:
        logger.error(f"Error obteniendo recursos numéricos de {mv}: {e}")
        
    return {"exito": False, "cpu": 0.0, "ram": 0.0, "load": "N/A"}

def obtener_disco(mv: str) -> dict:
    """
    Obtiene el uso del espacio en disco del servidor.
    Extrae Total, Usado, Libre y % de la partición root (/).
    """
    logger.info(f"Obteniendo uso de disco de {mv}")

    # Retorna "20G 1.5G 18G 8%"
    codigo, salida, error = ejecutar_comando(
        "df -h / | awk 'NR==2 {print $2, $3, $4, $5}'",
        mv
    )

    if codigo == 0 and salida:
        partes = salida.strip().split()
        if len(partes) >= 4:
            return {
                "exito": True, 
                "total": partes[0],
                "usado": partes[1],
                "libre": partes[2],
                "pcent": partes[3].replace('%', ''),
                "error": ""
            }
    
    return {"exito": False, "total": "", "usado": "", "libre": "", "pcent": "0", "error": error if error else "No se pudo obtener info de disco"}


def obtener_ultimo_login(mv: str) -> dict:
    """
    Obtiene los últimos accesos SSH al servidor (auditoría de seguridad).

    Usa 'last -n 8' para mostrar los últimos 8 accesos y
    'lastb -n 5' para los últimos intentos fallidos.

    Args:
        mv: "mv1" o "mv2"

    Returns:
        diccionario con "exito" (bool), "logins" (str), "fallidos" (str), "error" (str)
    """
    logger.info(f"Obteniendo últimos logins de {mv}")

    # Últimos accesos exitosos
    cod_ok, logins_raw, _ = ejecutar_comando("last -n 8 --time-format iso", mv)

    # Intentos fallidos (requiere sudo en algunos sistemas)
    cod_fail, fallidos_raw, _ = ejecutar_comando("sudo lastb -n 5 2>/dev/null || echo 'No disponible'", mv)

    if cod_ok != 0 and not logins_raw:
        return {"exito": False, "logins": "", "fallidos": "", "error": "No se pudo obtener historial de accesos"}

    return {
        "exito": True,
        "logins": logins_raw if logins_raw else "Sin registros",
        "fallidos": fallidos_raw if fallidos_raw else "Sin registros",
        "error": "",
    }


def obtener_ping(mv: str) -> dict:
    """
    Mide la latencia (ping) desde el servidor hacia google.com y consigo mismo.

    Retorna tiempos de respuesta para diagnosticar la conectividad del servidor.

    Args:
        mv: "mv1" o "mv2"

    Returns:
        diccionario con "exito" (bool), "resultado" (str), "error" (str)
    """
    logger.info(f"Haciendo ping desde {mv}")

    # Ping hacia Google (para verificar conectividad externa)
    cod, salida, error = ejecutar_comando(
        "ping -c 3 -W 2 8.8.8.8 2>&1 | tail -3", mv
    )

    if cod == 0 and salida:
        return {"exito": True, "resultado": salida, "error": ""}
    elif salida:
        return {"exito": True, "resultado": salida, "error": ""}
    else:
        return {"exito": False, "resultado": "", "error": error if error else "Sin respuesta"}


def obtener_uptime(mv: str) -> dict:
    """
    Obtiene el tiempo que lleva encendido el servidor y la carga del sistema.

    Args:
        mv: "mv1" o "mv2"

    Returns:
        diccionario con "exito" (bool), "uptime" (str), "error" (str)
    """
    logger.info(f"Obteniendo uptime de {mv}")

    # Uptime legible y boot time
    cod1, uptime_raw, _ = ejecutar_comando("uptime -p", mv)
    cod2, boot_raw, _ = ejecutar_comando("who -b", mv)
    cod3, load_raw, _ = ejecutar_comando("uptime", mv)

    if cod1 != 0 and not uptime_raw:
        return {"exito": False, "uptime": "", "error": "No se pudo obtener uptime"}

    return {
        "exito": True,
        "uptime": uptime_raw if uptime_raw else "No disponible",
        "boot": boot_raw if boot_raw else "No disponible",
        "load": load_raw if load_raw else "No disponible",
        "error": "",
    }


def ejecutar_comando_personalizado(comando: str, mv: str) -> dict:
    """
    Ejecuta un comando arbitrario en el servidor (solo para admin).

    ⚠️ Esta función es poderosa: puede ejecutar cualquier comando.
    Solo debe estar disponible para usuarios autorizados en el bot.

    Args:
        comando: el comando a ejecutar (sin restricciones)
        mv: "mv1" o "mv2"

    Returns:
        diccionario con "exito" (bool), "salida" (str), "error" (str), "codigo" (int)
    """
    logger.info(f"Ejecutando comando personalizado en {mv}: {comando}")

    codigo, salida, error = ejecutar_comando(comando, mv)

    return {
        "exito": codigo == 0,
        "salida": salida if salida else "(sin salida)",
        "error": error if error else "",
        "codigo": codigo,
    }


def obtener_usuarios_conectados(mv: str) -> dict:
    """
    Obtiene los usuarios conectados actualmente usando el comando 'who'.

    Args:
        mv: "mv1" o "mv2"

    Returns:
        diccionario con "exito" (bool), "usuarios" (str), "error" (str)
    """
    logger.info(f"Obteniendo usuarios conectados de {mv}")

    cod, salida, error = ejecutar_comando("who", mv)

    if cod == 0 and salida:
        return {"exito": True, "usuarios": salida, "error": ""}
    elif cod == 0 and not salida:
        return {"exito": True, "usuarios": "Nadie está conectado actualmente.", "error": ""}
    else:
        return {"exito": False, "usuarios": "", "error": error if error else "No se pudo obtener información"}

def generar_backup_remoto(tipo: str, mv: str) -> dict:
    """
    Genera un archivo de backup en el servidor remoto.
    """
    import time
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    
    if tipo == "web":
        ruta_remota = f"/tmp/backup_web_{mv}_{timestamp}.tar.gz"
        comando = f"sudo tar -czf {ruta_remota} /var/www/html"
    elif tipo == "mysql":
        ruta_remota = f"/tmp/backup_mysql_{mv}_{timestamp}.sql.gz"
        comando = f"sudo mysqldump --all-databases | gzip > {ruta_remota}"
    else:
        return {"exito": False, "error": "Tipo de backup no soportado"}
        
    logger.info(f"Generando backup '{tipo}' en {mv}...")
    cod, salida, error = ejecutar_comando(comando, mv)
    
    if cod == 0:
        # Dar permisos para que el usuario SSH pueda descargarlo
        ejecutar_comando(f"sudo chmod 644 {ruta_remota}", mv)
        return {"exito": True, "ruta_remota": ruta_remota, "error": ""}
    else:
        return {"exito": False, "ruta_remota": "", "error": error}

def descargar_archivo_sftp(ruta_remota: str, ruta_local: str, mv: str) -> bool:
    """
    Descarga un archivo del servidor remoto a la máquina local usando SFTP.
    """
    if mv not in _clientes_ssh:
        ejecutar_comando("echo 1", mv)
        
    cliente = _clientes_ssh.get(mv)
    if not cliente:
        return False
        
    try:
        sftp = cliente.open_sftp()
        sftp.get(ruta_remota, ruta_local)
        sftp.close()
        return True
    except Exception as e:
        logger.error(f"Error descargando {ruta_remota} por SFTP en {mv}: {e}")
        return False
