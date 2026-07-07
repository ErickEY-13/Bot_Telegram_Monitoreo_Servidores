# ============================================================
# bot.py - Lógica principal del Bot de Telegram
# ============================================================
# Este es el archivo principal que contiene toda la lógica del bot:
#
# 1. HANDLERS DE COMANDOS: procesan los comandos de texto que
#    escribe el usuario (/start, /estado, /reiniciar, etc.)
#
# 2. HANDLERS DE CALLBACKS: procesan los clicks en los botones
#    inline del menú interactivo
#
# 3. MONITOREO AUTOMÁTICO: tarea periódica que revisa el estado
#    de todos los servicios y envía alertas si hay cambios
#
# 4. AUTENTICACIÓN: verifica que solo usuarios autorizados
#    puedan ejecutar acciones críticas como reiniciar servicios
# ============================================================

import logging
import io
import warnings
from datetime import datetime

# Suprimir advertencias de deprecación de paramiko (TripleDES)
# Esto es un warning de compatibilidad interna de la librería, no un error real.
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Imports del framework python-telegram-bot v20+
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Imports de nuestros módulos propios
from config import (
    TELEGRAM_BOT_TOKEN,
    AUTHORIZED_CHAT_ID,
    ALERT_CHAT_ID,
    SERVIDORES,
    INTERVALO_MONITOREO,
    LINEAS_LOG,
    MAX_CARACTERES_MENSAJE,
    SSH_CONFIG,
)
from ssh_manager import (
    obtener_estado_servicio,
    reiniciar_servicio,
    obtener_logs_servicio,
    detener_servicio,
    iniciar_servicio,
    obtener_cpu_ram,
    obtener_disco,
    obtener_ultimo_login,
    obtener_ping,
    obtener_uptime,
    ejecutar_comando_personalizado,
    obtener_usuarios_conectados,
)
from db import (
    inicializar_db,
    registrar_evento,
    obtener_historial,
    registrar_recursos,
)
import graficos

# ---- CONFIGURACIÓN DEL LOGGING ----
# Configuramos el logging para ver qué hace el bot en la consola
# Nivel INFO muestra mensajes informativos, WARNING y ERROR
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---- ESTADO GLOBAL DEL MONITOREO ----
# Diccionario que guarda el último estado conocido de cada servicio
# Estructura: { "mv1:apache2": True/False, "mv2:nginx": True/False, ... }
# Se usa para comparar con el estado actual y detectar cambios
ultimo_estado_conocido: dict[str, bool] = {}


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def es_usuario_autorizado(chat_id: int) -> bool:
    """Verifica si el ID dado (usuario o grupo) coincide con los autorizados en config.py."""
    # Soportar múltiples IDs separados por coma
    autorizados = str(AUTHORIZED_CHAT_ID).split(',')
    str_id = str(chat_id)
    str_id_alt = str_id.replace("-100", "-")
    
    for auth in autorizados:
        auth = auth.strip()
        if str_id == auth or str_id_alt == auth.replace("-100", "-"):
            return True
    return False


def obtener_nombre_mv(mv: str) -> str:
    """
    Retorna el nombre legible de una MV.

    Busca en la configuración de SERVIDORES el nombre de la MV.
    Si no existe, retorna el identificador en mayúsculas.

    Args:
        mv: identificador de la MV ("mv1" o "mv2")

    Returns:
        nombre legible de la MV
    """
    if mv in SERVIDORES:
        return SERVIDORES[mv]["nombre"]
    return mv.upper()


def obtener_emoji_tipo(tipo: str) -> str:
    """
    Retorna un emoji según el tipo de evento para el historial.

    Args:
        tipo: tipo de evento

    Returns:
        emoji correspondiente
    """
    emojis = {
        "caida": "🔴",
        "recuperacion": "🟢",
        "reinicio_manual": "🔄",
        "error": "⚠️",
    }
    return emojis.get(tipo, "📋")


# ============================================================
# HANDLERS DE COMANDOS DE TEXTO
# ============================================================

async def comando_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler del comando /start.

    Muestra un mensaje de bienvenida con dos botones inline
    para elegir entre MV1 y MV2. Este es el punto de entrada
    del menú interactivo.
    """
    # Crear botones inline para cada servidor
    # callback_data es lo que recibe el handler de callbacks al presionar
    teclado = [
        [
            InlineKeyboardButton("🖥️ MV1 Ayma", callback_data="seleccionar_mv:mv1"),
            InlineKeyboardButton("🌐 MV2 Poma", callback_data="seleccionar_mv:mv2"),
        ]
    ]
    # InlineKeyboardMarkup convierte la lista de botones en un teclado
    markup = InlineKeyboardMarkup(teclado)

    await update.message.reply_text(
        "🤖 *Bot de Monitoreo de Servicios*\n\n"
        "Selecciona el servidor que deseas administrar:",
        reply_markup=markup,
        parse_mode="Markdown",
    )

async def comando_graficas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú de gráficos visuales."""
    if not es_usuario_autorizado(update.effective_chat.id):
        await update.message.reply_text("🚫 Acceso denegado.")
        return
        
    teclado = [
        [InlineKeyboardButton("📊 Caídas por Servicio", callback_data="grafica_caidas")],
        [InlineKeyboardButton("📈 Rendimiento MV1", callback_data="grafica_recursos:mv1")],
        [InlineKeyboardButton("📈 Rendimiento MV2", callback_data="grafica_recursos:mv2")]
    ]
    markup = InlineKeyboardMarkup(teclado)
    await update.message.reply_text(
        "📈 *Centro de Gráficos y Estadísticas*\n\n"
        "Selecciona qué gráfico deseas generar:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

async def comando_estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler del comando /estado <servicio> <mv1|mv2>.

    Permite consultar el estado de un servicio específico
    directamente por comando de texto, sin usar el menú.

    Ejemplo de uso: /estado apache2 mv1
    """
    # Verificar que se pasaron los argumentos necesarios
    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ *Uso correcto:*\n"
            "`/estado <servicio> <mv1|mv2>`\n\n"
            "*Ejemplo:* `/estado apache2 mv1`",
            parse_mode="Markdown",
        )
        return

    servicio = context.args[0].lower()  # Nombre del servicio
    mv = context.args[1].lower()        # Identificador de la MV

    # Validar que la MV existe en la configuración
    if mv not in SERVIDORES:
        await update.message.reply_text(
            f"❌ MV '{mv}' no reconocida. Usa: {', '.join(SERVIDORES.keys())}"
        )
        return

    # Enviar mensaje de "procesando" mientras se consulta
    mensaje = await update.message.reply_text(
        f"🔍 Consultando estado de *{servicio}* en *{obtener_nombre_mv(mv)}*...",
        parse_mode="Markdown",
    )

    # Obtener el estado del servicio
    estado = obtener_estado_servicio(servicio, mv)

    # Formatear y mostrar el resultado
    if estado["activo"]:
        emoji = "🟢"
        texto_estado = "ACTIVO"
    else:
        emoji = "🔴"
        texto_estado = estado["estado"].upper()

    respuesta = (
        f"{emoji} *Estado de {servicio}* en *{obtener_nombre_mv(mv)}*\n\n"
        f"📊 Estado: `{texto_estado}`\n\n"
        f"📝 Detalle:\n```\n{estado['detalle'][:1500]}\n```"
    )

    # Editar el mensaje de "procesando" con la respuesta final
    await mensaje.edit_text(respuesta, parse_mode="Markdown")


async def comando_reiniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler del comando /reiniciar <servicio> <mv1|mv2>.

    Reinicia un servicio en la MV indicada. Solo disponible
    para usuarios autorizados (verificado por chat_id).

    Ejemplo de uso: /reiniciar apache2 mv1
    """
    # Verificar autorización antes de proceder
    if not es_usuario_autorizado(update.effective_chat.id):
        await update.message.reply_text(
            "🚫 *Acceso denegado*\n\n"
            "No tienes permisos para reiniciar servicios.\n"
            "Contacta al administrador.",
            parse_mode="Markdown",
        )
        return

    # Verificar argumentos
    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ *Uso correcto:*\n"
            "`/reiniciar <servicio> <mv1|mv2>`\n\n"
            "*Ejemplo:* `/reiniciar apache2 mv1`",
            parse_mode="Markdown",
        )
        return

    servicio = context.args[0].lower()
    mv = context.args[1].lower()

    if mv not in SERVIDORES:
        await update.message.reply_text(
            f"❌ MV '{mv}' no reconocida. Usa: {', '.join(SERVIDORES.keys())}"
        )
        return

    # Pedir confirmación con botones inline antes de reiniciar
    teclado = [
        [
            InlineKeyboardButton(
                "✅ Sí, reiniciar",
                callback_data=f"confirmar_reinicio:{servicio}:{mv}",
            ),
            InlineKeyboardButton(
                "❌ Cancelar",
                callback_data="cancelar_reinicio",
            ),
        ]
    ]
    markup = InlineKeyboardMarkup(teclado)

    await update.message.reply_text(
        f"⚠️ *Confirmar reinicio*\n\n"
        f"¿Estás seguro de que deseas reiniciar "
        f"*{servicio}* en *{obtener_nombre_mv(mv)}*?",
        reply_markup=markup,
        parse_mode="Markdown",
    )


async def comando_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler del comando /logs <servicio> <mv1|mv2>.

    Obtiene las últimas líneas del log de un servicio y las envía.
    Si el texto es muy largo, lo envía como archivo adjunto.

    Ejemplo de uso: /logs apache2 mv1
    """
    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ *Uso correcto:*\n"
            "`/logs <servicio> <mv1|mv2>`\n\n"
            "*Ejemplo:* `/logs apache2 mv1`",
            parse_mode="Markdown",
        )
        return

    servicio = context.args[0].lower()
    mv = context.args[1].lower()

    if mv not in SERVIDORES:
        await update.message.reply_text(
            f"❌ MV '{mv}' no reconocida. Usa: {', '.join(SERVIDORES.keys())}"
        )
        return

    mensaje = await update.message.reply_text(
        f"📋 Obteniendo logs de *{servicio}* en *{obtener_nombre_mv(mv)}*...",
        parse_mode="Markdown",
    )

    # Obtener los logs del servicio
    resultado = obtener_logs_servicio(servicio, mv, LINEAS_LOG)

    if not resultado["exito"]:
        await mensaje.edit_text(
            f"❌ Error al obtener logs:\n`{resultado['error']}`",
            parse_mode="Markdown",
        )
        return

    logs = resultado["logs"]

    # Si el log es muy largo, enviarlo como archivo adjunto
    if len(logs) > MAX_CARACTERES_MENSAJE:
        # Crear un archivo en memoria (sin guardarlo en disco)
        archivo = io.BytesIO(logs.encode("utf-8"))
        archivo.name = f"logs_{servicio}_{mv}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        await mensaje.edit_text(
            f"📋 Logs de *{servicio}* en *{obtener_nombre_mv(mv)}* "
            f"(enviados como archivo por ser muy largos)",
            parse_mode="Markdown",
        )
        # Enviar el archivo al chat
        await update.message.reply_document(
            document=archivo,
            caption=f"📋 Logs de {servicio} en {obtener_nombre_mv(mv)}",
        )
    else:
        # Si cabe en un mensaje, enviarlo como texto con formato
        await mensaje.edit_text(
            f"📋 *Logs de {servicio}* en *{obtener_nombre_mv(mv)}*\n"
            f"(Últimas {LINEAS_LOG} líneas)\n\n"
            f"```\n{logs}\n```",
            parse_mode="Markdown",
        )


async def comando_status_general(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler del comando /status_general.

    Muestra el estado de TODOS los servicios configurados
    en ambas MVs de un solo vistazo. Útil para tener una
    visión general rápida del estado de la infraestructura.
    """
    mensaje = await update.message.reply_text(
        "🔍 Consultando estado de todos los servicios...\n"
        "Esto puede tardar unos segundos.",
    )

    # Construir el reporte iterando sobre todos los servidores y servicios
    reporte = "📊 *STATUS GENERAL DE SERVICIOS*\n"
    reporte += f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    reporte += "━" * 30 + "\n\n"

    for mv_id, mv_config in SERVIDORES.items():
        reporte += f"🖥️ *{mv_config['nombre']}*\n"

        for servicio in mv_config["servicios"]:
            # Consultar el estado de cada servicio
            estado = obtener_estado_servicio(servicio, mv_id)

            if estado["activo"]:
                reporte += f"  🟢 `{servicio}` — Activo\n"
            else:
                reporte += f"  🔴 `{servicio}` — {estado['estado'].upper()}\n"

        reporte += "\n"

    # Editar el mensaje con el reporte completo
    await mensaje.edit_text(reporte, parse_mode="Markdown")


async def comando_historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler del comando /historial.

    Muestra los últimos 10 eventos registrados en la base de datos:
    caídas, recuperaciones, reinicios manuales, etc.
    """
    eventos = obtener_historial(10)

    if not eventos:
        await update.message.reply_text(
            "📋 No hay eventos registrados en el historial aún."
        )
        return

    # Formatear los eventos para mostrarlos bonitos
    texto = "📋 *HISTORIAL DE EVENTOS*\n"
    texto += f"(Últimos {len(eventos)} eventos)\n"
    texto += "━" * 30 + "\n\n"

    for evento in eventos:
        emoji = obtener_emoji_tipo(evento["tipo"])
        texto += (
            f"{emoji} *{evento['tipo'].upper()}*\n"
            f"  📅 {evento['fecha']}\n"
            f"  🔧 Servicio: `{evento['servicio']}`\n"
            f"  🖥️ MV: `{evento['mv']}`\n"
        )

        # Mostrar usuario solo si hay uno registrado (reinicios manuales)
        if evento["usuario"]:
            texto += f"  👤 Usuario: `{evento['usuario']}`\n"

        # Mostrar detalle solo si hay
        if evento["detalle"]:
            texto += f"  📝 {evento['detalle']}\n"

        texto += "\n"

    await update.message.reply_text(texto, parse_mode="Markdown")


async def comando_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler del comando /help.

    Muestra instrucciones de uso detalladas y todos los comandos disponibles.
    """
    texto_ayuda = (
        "🤖 *BOT MONITOR DE SERVIDORES*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🚀 *¿Cómo empezar?*\n"
        "1️⃣ Envía /start → abre el menú con botones\n"
        "2️⃣ Elige *MV1 Ayma* o *MV2 Poma*\n"
        "3️⃣ Elige un servicio (apache2, mysql, vsftpd, ssh)\n"
        "4️⃣ Elige la acción que quieres realizar\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🖱️ *Acciones por servicio (botones inline):*\n"
        "📊 *Ver estado* — ¿Está corriendo o caído?\n"
        "📋 *Ver logs* — Últimas líneas del journal del servicio\n"
        "🔄 *Reiniciar* — Reinicia el servicio (pide confirmación)\n"
        "⏹️ *Detener* — Apaga el servicio (pide confirmación)\n"
        "▶️ *Iniciar* — Enciende el servicio (pide confirmación)\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⌨️ *Comandos Rápidos de Texto (Sin barra /):*\n"
        "Escribe estas frases exactas en el chat:\n"
        "• `ver espacio` → Muestra almacenamiento de ambas MVs\n"
        "• `ver memoria` → Muestra uso de RAM de ambas MVs\n"
        "• `ver cpu` → Muestra uso de CPU de ambas MVs\n"
        "• `ver usuario` → Muestra usuarios conectados en ambas MVs\n"
        "• `estado servicio apache2` → Muestra estado del apache2 en ambas MVs\n"
        "• `estado servicio mysql` → Muestra estado del mysql en ambas MVs\n"
        "• `estado servicio ftp` → Muestra estado del ftp en ambas MVs\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📡 *Otros Comandos con Barra:*\n"
        "`/reiniciar <servicio> <mv1|mv2>`\n"
        "  └ Ej: `/reiniciar mysql mv1` *(solo admin)*\n\n"
        "`/logs <servicio> <mv1|mv2>`\n"
        "  └ Ej: `/logs apache2 mv1`\n\n"
        "`/backup <mysql|web> <mv1|mv2>`\n"
        "  └ Extrae copias de seguridad por Telegram\n"
        "  └ Ej: `/backup mysql mv1` *(solo admin)*\n\n"
        "`/status_general`\n"
        "  └ Estado de todos los servicios en todas las MVs\n\n"
        "`/historial`\n"
        "  └ Últimos 10 eventos registrados (reinicios, caídas, etc.)\n\n"
        "📈 `/graficas` - Muestra estadísticas y gráficos visuales\n\n"
        "`/ping <mv1|mv2>`\n"
        "  └ Latencia del servidor hacia internet (8.8.8.8)\n"
        "  └ Ej: `/ping mv1`\n\n"
        "`/uptime <mv1|mv2>`\n"
        "  └ Cuánto tiempo lleva encendido el servidor\n"
        "  └ Ej: `/uptime mv1`\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚙️ *Administración avanzada (solo admin):*\n"
        "`/ejecutar <mv1|mv2> <comando>`\n"
        "  └ Ejecuta cualquier comando Linux directamente\n"
        "  └ Ej: `/ejecutar mv1 df -h`\n"
        "  └ Ej: `/ejecutar mv1 netstat -tlnp`\n"
        "  └ Ej: `/ejecutar mv1 who`\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔔 *Alertas automáticas (sin hacer nada):*\n"
        "🔴 Si un servicio *se cae* → recibes alerta inmediata\n"
        "🟢 Si un servicio *se recupera* → recibes notificación\n"
        "📊 Cada día a las *8:00am* → resumen de estado de todo\n"
        "⏱️ El monitoreo revisa cada *60 segundos*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔒 *Seguridad:*\n"
        "Solo el admin puede: reiniciar, detener, iniciar, ejecutar.\n"
        "Todos los demás pueden: ver estado, logs y recursos.\n"
        "Cada acción queda grabada en el historial con fecha y usuario.\n\n"
        "📌 *Servicios configurados:*\n"
    )

    # Listar los servicios de cada MV para referencia
    for mv_id, mv_config in SERVIDORES.items():
        texto_ayuda += f"\n🖥️ *{mv_config['nombre']}:*\n"
        for servicio in mv_config["servicios"]:
            texto_ayuda += f"  • `{servicio}`\n"

    await update.message.reply_text(texto_ayuda, parse_mode="Markdown")



# ============================================================
# HANDLERS DE CALLBACKS (BOTONES INLINE)
# ============================================================


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler maestro de callbacks para los botones inline.

    Cuando el usuario presiona un botón inline, Telegram envía
    un CallbackQuery con el callback_data del botón. Este handler
    lee el callback_data y enruta la acción al método correcto.

    El callback_data usa el formato "accion:param1:param2"
    para pasar información entre los distintos pasos del menú.
    """
    query = update.callback_query

    # Responder al callback para quitar el "reloj de carga" del botón
    try:
        await query.answer()
    except Exception as e:
        logger.warning(f"No se pudo responder al callback (quizás expiró): {e}")

    # Obtener los datos del callback y separarlos por ":"
    data = query.data
    partes = data.split(":")

    # Enrutar al método correcto según la acción
    accion = partes[0]

    if accion == "seleccionar_mv":
        await _callback_seleccionar_mv(query, partes)
    elif accion == "seleccionar_servicio":
        await _callback_seleccionar_servicio(query, partes)
    elif accion == "ver_estado":
        await _callback_ver_estado(query, partes)
    elif accion == "menu_reiniciar":
        await _callback_menu_reiniciar(query, partes)
    elif accion == "confirmar_reinicio":
        await _callback_confirmar_reinicio(query, partes)
    elif accion == "cancelar_reinicio":
        await _callback_cancelar_reinicio(query)
    elif accion == "menu_detener":
        await _callback_menu_detener(query, partes)
    elif accion == "confirmar_detener":
        await _callback_confirmar_detener(query, partes)
    elif accion == "menu_iniciar":
        await _callback_menu_iniciar(query, partes)
    elif accion == "confirmar_iniciar":
        await _callback_confirmar_iniciar(query, partes)
    elif accion == "ver_logs":
        await _callback_ver_logs(query, partes)
    elif accion == "volver_inicio":
        await _callback_volver_inicio(query)
    elif accion == "volver_servicios":
        await _callback_volver_servicios(query, partes)
    elif accion == "grafica_caidas":
        await _callback_grafica_caidas(query)
    elif accion == "grafica_recursos":
        await _callback_grafica_recursos(query, partes)

async def _callback_grafica_caidas(query):
    await query.edit_message_text("⏳ Generando gráfico, por favor espera...")
    buffer = graficos.generar_grafico_caidas()
    await query.message.reply_photo(photo=buffer, caption="📊 *Histórico de Caídas por Servicio*", parse_mode="Markdown")
    await query.message.delete()

async def _callback_grafica_recursos(query, partes):
    mv = partes[1]
    await query.edit_message_text(f"⏳ Generando gráfico de recursos para {mv.upper()}...")
    buffer = graficos.generar_grafico_recursos(mv)
    await query.message.reply_photo(photo=buffer, caption=f"📈 *Histórico de Rendimiento de {mv.upper()}*", parse_mode="Markdown")
    await query.message.delete()

async def _callback_seleccionar_mv(query, partes):
    """
    Callback cuando el usuario selecciona una MV (MV1 o MV2).

    Muestra los botones con los servicios disponibles en esa MV.
    Los servicios se leen de la configuración SERVIDORES.
    """
    mv = partes[1]  # "mv1" o "mv2"

    if mv not in SERVIDORES:
        await query.edit_message_text("❌ MV no reconocida.")
        return

    mv_config = SERVIDORES[mv]

    # Crear un botón por cada servicio configurado en esa MV
    # Cada fila tiene un solo botón con el nombre del servicio
    botones = []
    for servicio in mv_config["servicios"]:
        botones.append([
            InlineKeyboardButton(
                f"🔧 {servicio}",
                callback_data=f"seleccionar_servicio:{servicio}:{mv}",
            )
        ])

    # Agregar botón para volver al menú principal
    botones.append([
        InlineKeyboardButton("⬅️ Volver", callback_data="volver_inicio")
    ])

    markup = InlineKeyboardMarkup(botones)

    await query.edit_message_text(
        f"🖥️ *{mv_config['nombre']}*\n\n"
        f"Selecciona el servicio que deseas administrar:",
        reply_markup=markup,
        parse_mode="Markdown",
    )


async def _callback_seleccionar_servicio(query, partes):
    """
    Callback cuando el usuario selecciona un servicio.

    Muestra tres opciones: Ver estado, Reiniciar, Ver logs.
    Estas son las acciones que se pueden realizar sobre el servicio.
    """
    servicio = partes[1]
    mv = partes[2]

    # Crear botones de acciones disponibles para el servicio
    teclado = [
        [
            InlineKeyboardButton(
                "📊 Ver estado",
                callback_data=f"ver_estado:{servicio}:{mv}",
            ),
            InlineKeyboardButton(
                "📋 Ver logs",
                callback_data=f"ver_logs:{servicio}:{mv}",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔄 Reiniciar",
                callback_data=f"menu_reiniciar:{servicio}:{mv}",
            ),
            InlineKeyboardButton(
                "⏹️ Detener",
                callback_data=f"menu_detener:{servicio}:{mv}",
            ),
            InlineKeyboardButton(
                "▶️ Iniciar",
                callback_data=f"menu_iniciar:{servicio}:{mv}",
            ),
        ],
        [
            InlineKeyboardButton(
                "⬅️ Volver a servicios",
                callback_data=f"volver_servicios:{mv}",
            )
        ],
    ]
    markup = InlineKeyboardMarkup(teclado)

    await query.edit_message_text(
        f"🔧 *Servicio: {servicio}*\n"
        f"🖥️ *MV: {obtener_nombre_mv(mv)}*\n\n"
        f"¿Qué deseas hacer?",
        reply_markup=markup,
        parse_mode="Markdown",
    )


async def _callback_ver_estado(query, partes):
    """
    Callback para ver el estado de un servicio.

    Consulta el estado con systemctl y muestra el resultado
    con un emoji indicando si está activo o no.
    """
    servicio = partes[1]
    mv = partes[2]

    # Mostrar mensaje temporal mientras se consulta
    await query.edit_message_text(
        f"🔍 Consultando estado de *{servicio}*...",
        parse_mode="Markdown",
    )

    # Obtener el estado real del servicio
    estado = obtener_estado_servicio(servicio, mv)

    # Formatear la respuesta
    if estado["activo"]:
        emoji = "🟢"
        texto_estado = "ACTIVO"
    else:
        emoji = "🔴"
        texto_estado = estado["estado"].upper()

    # Botón para volver al menú del servicio
    teclado = [
        [
            InlineKeyboardButton(
                "⬅️ Volver",
                callback_data=f"seleccionar_servicio:{servicio}:{mv}",
            )
        ]
    ]
    markup = InlineKeyboardMarkup(teclado)

    respuesta = (
        f"{emoji} *Estado de {servicio}*\n"
        f"🖥️ {obtener_nombre_mv(mv)}\n\n"
        f"📊 Estado: `{texto_estado}`\n\n"
        f"📝 Detalle:\n```\n{estado['detalle'][:1500]}\n```"
    )

    await query.edit_message_text(
        respuesta,
        reply_markup=markup,
        parse_mode="Markdown",
    )


async def _callback_menu_reiniciar(query, partes):
    """
    Callback que muestra la confirmación de reinicio.

    Antes de reiniciar, se pide confirmación al usuario con
    botones de "Sí, reiniciar" y "Cancelar" para evitar
    reinicios accidentales.
    """
    servicio = partes[1]
    mv = partes[2]

    # Verificar que el usuario está autorizado
    if not es_usuario_autorizado(query.message.chat.id):
        teclado = [
            [
                InlineKeyboardButton(
                    "⬅️ Volver",
                    callback_data=f"seleccionar_servicio:{servicio}:{mv}",
                )
            ]
        ]
        markup = InlineKeyboardMarkup(teclado)

        await query.edit_message_text(
            "🚫 *Acceso denegado*\n\n"
            "No tienes permisos para reiniciar servicios.\n"
            "Contacta al administrador.",
            reply_markup=markup,
            parse_mode="Markdown",
        )
        return

    # Mostrar botones de confirmación
    teclado = [
        [
            InlineKeyboardButton(
                "✅ Sí, reiniciar",
                callback_data=f"confirmar_reinicio:{servicio}:{mv}",
            ),
            InlineKeyboardButton(
                "❌ Cancelar",
                callback_data="cancelar_reinicio",
            ),
        ]
    ]
    markup = InlineKeyboardMarkup(teclado)

    await query.edit_message_text(
        f"⚠️ *Confirmar reinicio*\n\n"
        f"¿Estás seguro de que deseas reiniciar "
        f"*{servicio}* en *{obtener_nombre_mv(mv)}*?\n\n"
        f"⚡ Esta acción reiniciará el servicio inmediatamente.",
        reply_markup=markup,
        parse_mode="Markdown",
    )


async def _callback_confirmar_reinicio(query, partes):
    """
    Callback que ejecuta el reinicio del servicio.

    Se llama cuando el usuario confirma el reinicio presionando
    el botón "Sí, reiniciar". Ejecuta systemctl restart y
    registra el evento en la base de datos.
    """
    servicio = partes[1]
    mv = partes[2]

    # Doble verificación de autorización (seguridad)
    if not es_usuario_autorizado(query.message.chat.id):
        await query.edit_message_text("🚫 Acceso denegado.")
        return

    # Mostrar mensaje de progreso
    await query.edit_message_text(
        f"🔄 Reiniciando *{servicio}* en *{obtener_nombre_mv(mv)}*...\n"
        f"Por favor espera...",
        parse_mode="Markdown",
    )

    # Ejecutar el reinicio
    resultado = reiniciar_servicio(servicio, mv)

    # Registrar el evento en la base de datos
    usuario_info = f"{query.from_user.first_name} ({query.from_user.id})"
    registrar_evento(
        tipo="reinicio_manual",
        servicio=servicio,
        mv=mv,
        usuario=usuario_info,
        detalle=resultado["mensaje"],
    )

    # Botón para volver
    teclado = [
        [
            InlineKeyboardButton(
                "⬅️ Volver al menú",
                callback_data=f"seleccionar_servicio:{servicio}:{mv}",
            )
        ]
    ]
    markup = InlineKeyboardMarkup(teclado)

    await query.edit_message_text(
        f"{resultado['mensaje']}\n\n"
        f"👤 Ejecutado por: {query.from_user.first_name}\n"
        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        reply_markup=markup,
        parse_mode="Markdown",
    )


async def _callback_cancelar_reinicio(query):
    """
    Callback cuando el usuario cancela el reinicio.

    Simplemente muestra un mensaje de cancelación y ofrece
    volver al menú principal.
    """
    teclado = [
        [
            InlineKeyboardButton(
                "⬅️ Volver al inicio",
                callback_data="volver_inicio",
            )
        ]
    ]
    markup = InlineKeyboardMarkup(teclado)

    await query.edit_message_text(
        "❌ Reinicio cancelado.\n\n"
        "No se realizó ninguna acción.",
        reply_markup=markup,
    )


async def _callback_menu_detener(query, partes):
    """Muestra confirmación antes de detener el servicio."""
    servicio = partes[1]
    mv = partes[2]

    if not es_usuario_autorizado(query.message.chat.id):
        await query.edit_message_text("🚫 *Acceso denegado*\n\nNo tienes permisos para detener servicios.", parse_mode="Markdown")
        return

    teclado = [
        [
            InlineKeyboardButton("✅ Sí, detener", callback_data=f"confirmar_detener:{servicio}:{mv}"),
            InlineKeyboardButton("❌ Cancelar", callback_data=f"seleccionar_servicio:{servicio}:{mv}"),
        ]
    ]
    markup = InlineKeyboardMarkup(teclado)

    await query.edit_message_text(
        f"⚠️ *Confirmar detención*\n\n"
        f"¿Estás seguro de que deseas *detener* el servicio *{servicio}* en *{obtener_nombre_mv(mv)}*?\n\n"
        f"⚡ El servicio dejará de responder hasta que lo inicies manualmente.",
        reply_markup=markup,
        parse_mode="Markdown",
    )


async def _callback_confirmar_detener(query, partes):
    """Ejecuta la detención del servicio tras confirmación."""
    servicio = partes[1]
    mv = partes[2]

    if not es_usuario_autorizado(query.message.chat.id):
        await query.edit_message_text("🚫 Acceso denegado.")
        return

    await query.edit_message_text(
        f"⏹️ Deteniendo *{servicio}* en *{obtener_nombre_mv(mv)}*...\nPor favor espera...",
        parse_mode="Markdown",
    )

    resultado = detener_servicio(servicio, mv)

    usuario_info = f"{query.from_user.first_name} ({query.from_user.id})"
    registrar_evento(tipo="detener_manual", servicio=servicio, mv=mv, usuario=usuario_info, detalle=resultado["mensaje"])

    teclado = [[InlineKeyboardButton("⬅️ Volver al menú", callback_data=f"seleccionar_servicio:{servicio}:{mv}")]]
    markup = InlineKeyboardMarkup(teclado)

    await query.edit_message_text(
        f"{resultado['mensaje']}\n\n"
        f"👤 Ejecutado por: {query.from_user.first_name}\n"
        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        reply_markup=markup,
        parse_mode="Markdown",
    )


async def _callback_menu_iniciar(query, partes):
    """Muestra confirmación antes de iniciar el servicio."""
    servicio = partes[1]
    mv = partes[2]

    if not es_usuario_autorizado(query.message.chat.id):
        await query.edit_message_text("🚫 *Acceso denegado*\n\nNo tienes permisos para iniciar servicios.", parse_mode="Markdown")
        return

    teclado = [
        [
            InlineKeyboardButton("✅ Sí, iniciar", callback_data=f"confirmar_iniciar:{servicio}:{mv}"),
            InlineKeyboardButton("❌ Cancelar", callback_data=f"seleccionar_servicio:{servicio}:{mv}"),
        ]
    ]
    markup = InlineKeyboardMarkup(teclado)

    await query.edit_message_text(
        f"▶️ *Confirmar inicio*\n\n"
        f"¿Estás seguro de que deseas *iniciar* el servicio *{servicio}* en *{obtener_nombre_mv(mv)}*?",
        reply_markup=markup,
        parse_mode="Markdown",
    )


async def _callback_confirmar_iniciar(query, partes):
    """Ejecuta el inicio del servicio tras confirmación."""
    servicio = partes[1]
    mv = partes[2]

    if not es_usuario_autorizado(query.message.chat.id):
        await query.edit_message_text("🚫 Acceso denegado.")
        return

    await query.edit_message_text(
        f"▶️ Iniciando *{servicio}* en *{obtener_nombre_mv(mv)}*...\nPor favor espera...",
        parse_mode="Markdown",
    )

    resultado = iniciar_servicio(servicio, mv)

    usuario_info = f"{query.from_user.first_name} ({query.from_user.id})"
    registrar_evento(tipo="iniciar_manual", servicio=servicio, mv=mv, usuario=usuario_info, detalle=resultado["mensaje"])

    teclado = [[InlineKeyboardButton("⬅️ Volver al menú", callback_data=f"seleccionar_servicio:{servicio}:{mv}")]]
    markup = InlineKeyboardMarkup(teclado)

    await query.edit_message_text(
        f"{resultado['mensaje']}\n\n"
        f"👤 Ejecutado por: {query.from_user.first_name}\n"
        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        reply_markup=markup,
        parse_mode="Markdown",
    )


async def _callback_ver_logs(query, partes):
    """
    Callback para ver los logs de un servicio.

    Obtiene las últimas líneas del log con journalctl y las muestra.
    Si el log es muy largo, lo envía como archivo adjunto.
    """
    servicio = partes[1]
    mv = partes[2]

    await query.edit_message_text(
        f"📋 Obteniendo logs de *{servicio}*...",
        parse_mode="Markdown",
    )

    resultado = obtener_logs_servicio(servicio, mv, LINEAS_LOG)

    # Botón para volver
    teclado = [
        [
            InlineKeyboardButton(
                "⬅️ Volver",
                callback_data=f"seleccionar_servicio:{servicio}:{mv}",
            )
        ]
    ]
    markup = InlineKeyboardMarkup(teclado)

    if not resultado["exito"]:
        await query.edit_message_text(
            f"❌ Error al obtener logs:\n`{resultado['error']}`",
            reply_markup=markup,
            parse_mode="Markdown",
        )
        return

    logs = resultado["logs"]

    # Si el log es muy largo, enviarlo como archivo
    if len(logs) > MAX_CARACTERES_MENSAJE:
        await query.edit_message_text(
            f"📋 Logs de *{servicio}* en *{obtener_nombre_mv(mv)}*\n"
            f"(Enviados como archivo por ser muy largos)",
            reply_markup=markup,
            parse_mode="Markdown",
        )

        # Crear archivo en memoria y enviarlo
        archivo = io.BytesIO(logs.encode("utf-8"))
        archivo.name = f"logs_{servicio}_{mv}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        await query.message.reply_document(
            document=archivo,
            caption=f"📋 Logs de {servicio} en {obtener_nombre_mv(mv)}",
        )
    else:
        await query.edit_message_text(
            f"📋 *Logs de {servicio}* en *{obtener_nombre_mv(mv)}*\n"
            f"(Últimas {LINEAS_LOG} líneas)\n\n"
            f"```\n{logs}\n```",
            reply_markup=markup,
            parse_mode="Markdown",
        )


async def _callback_volver_inicio(query):
    """
    Callback para volver al menú principal (selección de MV).
    """
    teclado = [
        [
            InlineKeyboardButton("🖥️ MV1 Ayma", callback_data="seleccionar_mv:mv1"),
            InlineKeyboardButton("🌐 MV2 Poma", callback_data="seleccionar_mv:mv2"),
        ]
    ]
    markup = InlineKeyboardMarkup(teclado)

    await query.edit_message_text(
        "🤖 *Bot de Monitoreo de Servicios*\n\n"
        "Selecciona el servidor que deseas administrar:",
        reply_markup=markup,
        parse_mode="Markdown",
    )


async def _callback_volver_servicios(query, partes):
    """
    Callback para volver a la lista de servicios de una MV.
    """
    mv = partes[1]
    # Reutilizamos el callback de seleccionar_mv para mostrar los servicios
    await _callback_seleccionar_mv(query, ["seleccionar_mv", mv])


# ============================================================
# COMANDOS DE DIAGNÓSTICO Y ADMINISTRACIÓN AVANZADA
# ============================================================

async def comando_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler del comando /ping <mv1|mv2>.

    Ejecuta un ping desde el servidor hacia internet (8.8.8.8)
    para verificar su conectividad y medir latencia.
    """
    if len(context.args) < 1:
        await update.message.reply_text(
            "⚠️ *Uso:* `/ping <mv1|mv2>`\n*Ejemplo:* `/ping mv1`",
            parse_mode="Markdown",
        )
        return

    mv = context.args[0].lower()
    if mv not in SERVIDORES:
        await update.message.reply_text(f"❌ MV `{mv}` no reconocida.", parse_mode="Markdown")
        return

    msg = await update.message.reply_text(
        f"📡 Haciendo ping desde *{obtener_nombre_mv(mv)}*...",
        parse_mode="Markdown",
    )

    resultado = obtener_ping(mv)

    if not resultado["exito"]:
        await msg.edit_text(f"❌ Sin respuesta: {resultado['error']}")
        return

    resultado_ping = resultado["resultado"]
    
    import re
    loss = "Desconocida"
    latencia = "Desconocida"
    
    match_loss = re.search(r"(\d+)% packet loss", resultado_ping)
    if match_loss:
        loss = f"{match_loss.group(1)}%"
        
    if "=" in resultado_ping:
        partes_lat = resultado_ping.split("=")[-1].strip().split("/")
        if len(partes_lat) >= 2:
            latencia = f"{partes_lat[1]} ms"

    await msg.edit_text(
        f"🌐 *Conectividad a Internet — {obtener_nombre_mv(mv)}*\n\n"
        f"📶 *Latencia Promedio:* `{latencia}`\n"
        f"📦 *Paquetes perdidos:* `{loss}`\n\n"
        f"_(Ping hacia 8.8.8.8 Google)_",
        parse_mode="Markdown",
    )


async def comando_uptime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler del comando /uptime <mv1|mv2>.

    Muestra cuánto tiempo lleva encendido el servidor y la carga del sistema.
    """
    if len(context.args) < 1:
        await update.message.reply_text(
            "⚠️ *Uso:* `/uptime <mv1|mv2>`\n*Ejemplo:* `/uptime mv1`",
            parse_mode="Markdown",
        )
        return

    mv = context.args[0].lower()
    if mv not in SERVIDORES:
        await update.message.reply_text(f"❌ MV `{mv}` no reconocida.", parse_mode="Markdown")
        return

    msg = await update.message.reply_text(
        f"⏱️ Consultando uptime de *{obtener_nombre_mv(mv)}*...",
        parse_mode="Markdown",
    )

    resultado = obtener_uptime(mv)

    if not resultado["exito"]:
        await msg.edit_text(f"❌ Error al consultar uptime.")
        return

    up_str = resultado["uptime"].replace("up ", "")
    up_str = up_str.replace("days", "días").replace("day", "día")
    up_str = up_str.replace("hours", "horas").replace("hour", "hora")
    up_str = up_str.replace("minutes", "minutos").replace("minute", "minuto")

    boot_str = resultado["boot"].replace("system boot", "").strip()
    load_str = resultado["load"].split("load average:")[-1].strip() if "load average:" in resultado["load"] else resultado["load"]

    await msg.edit_text(
        f"⏱️ *Tiempo en línea — {obtener_nombre_mv(mv)}*\n\n"
        f"🟢 *Encendido sin interrupciones por:*\n`{up_str}`\n\n"
        f"📅 *Último arranque (Boot):*\n`{boot_str}`\n\n"
        f"📈 *Carga (Load):*\n`{load_str}`",
        parse_mode="Markdown",
    )


async def comando_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler del comando /backup <mysql|web> <mv1|mv2>.
    Genera un backup y lo envía por Telegram.
    """
    if not es_usuario_autorizado(update.effective_chat.id):
        await update.message.reply_text("🚫 *Acceso denegado*", parse_mode="Markdown")
        return

    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Uso incorrecto. Ejemplo: `/backup mysql mv1`", parse_mode="Markdown")
        return

    tipo = context.args[0].lower()
    mv = context.args[1].lower()

    if mv not in SERVIDORES:
        await update.message.reply_text("⚠️ Máquina no encontrada. Usa mv1 o mv2.")
        return

    if tipo not in ["mysql", "web"]:
        await update.message.reply_text("⚠️ Tipo de backup no soportado. Usa 'mysql' o 'web'.")
        return

    msg = await update.message.reply_text(f"📦 Generando backup de *{tipo}* en *{obtener_nombre_mv(mv)}*...\nEsto puede tardar unos segundos.", parse_mode="Markdown")

    from ssh_manager import generar_backup_remoto, descargar_archivo_sftp
    import os

    res = generar_backup_remoto(tipo, mv)
    if not res["exito"]:
        await msg.edit_text(f"❌ Error al generar backup:\n```\n{res['error']}\n```", parse_mode="Markdown")
        return

    ruta_remota = res["ruta_remota"]
    nombre_archivo = os.path.basename(ruta_remota)
    ruta_local = os.path.join(os.path.dirname(os.path.abspath(__file__)), nombre_archivo)

    await msg.edit_text(f"⬇️ Descargando `{nombre_archivo}` al servidor central...", parse_mode="Markdown")

    descargado = descargar_archivo_sftp(ruta_remota, ruta_local, mv)
    
    if descargado and os.path.exists(ruta_local):
        await msg.edit_text(f"🚀 Enviando archivo a Telegram...")
        with open(ruta_local, "rb") as f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=f,
                caption=f"✅ Backup de *{tipo}* generado con éxito en *{obtener_nombre_mv(mv)}*.",
                parse_mode="Markdown"
            )
        # Limpiar
        os.remove(ruta_local)
        from ssh_manager import ejecutar_comando
        ejecutar_comando(f"sudo rm {ruta_remota}", mv)
    else:
        await msg.edit_text("❌ Error: No se pudo descargar el archivo al servidor central.")



async def comando_ejecutar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler del comando /ejecutar <mv1|mv2> <comando...>.

    Ejecuta cualquier comando en el servidor. SOLO para el administrador.
    Ejemplo: /ejecutar mv1 df -h
    """
    if not es_usuario_autorizado(update.effective_chat.id):
        await update.message.reply_text(
            "🚫 *Acceso denegado.*\nEste comando es solo para el administrador.",
            parse_mode="Markdown",
        )
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ *Uso:* `/ejecutar <mv1|mv2> <comando>`\n"
            "*Ejemplo:* `/ejecutar mv1 df -h`\n"
            "*Ejemplo:* `/ejecutar mv1 netstat -tlnp`",
            parse_mode="Markdown",
        )
        return

    mv = context.args[0].lower()
    if mv not in SERVIDORES:
        await update.message.reply_text(f"❌ MV `{mv}` no reconocida.", parse_mode="Markdown")
        return

    # El comando es todo lo que viene después de la MV
    comando = " ".join(context.args[1:])

    msg = await update.message.reply_text(
        f"⚙️ Ejecutando en *{obtener_nombre_mv(mv)}*:\n`{comando}`",
        parse_mode="Markdown",
    )

    resultado = ejecutar_comando_personalizado(comando, mv)

    # Registrar en historial
    registrar_evento(
        tipo="cmd_personalizado",
        servicio="-",
        mv=mv,
        usuario=f"{update.effective_user.first_name} ({update.effective_user.id})",
        detalle=comando,
    )

    emoji = "✅" if resultado["exito"] else "⚠️"
    salida_text = resultado["salida"][:3000]  # límite de Telegram
    error_text = resultado["error"][:500] if resultado["error"] else ""

    respuesta = (
        f"{emoji} *Resultado en {obtener_nombre_mv(mv)}*\n"
        f"📟 Comando: `{comando}`\n"
        f"🔢 Código: `{resultado['codigo']}`\n\n"
        f"```\n{salida_text}\n```"
    )
    if error_text:
        respuesta += f"\n\n⚠️ *Stderr:*\n```\n{error_text}\n```"

    await msg.edit_text(respuesta[:4000], parse_mode="Markdown")


# ============================================================
# MONITOREO AUTOMÁTICO (JobQueue)
# ============================================================

async def tarea_monitoreo(context: ContextTypes.DEFAULT_TYPE):
    """
    Tarea periódica de monitoreo que se ejecuta automáticamente.

    Esta función es llamada por el JobQueue cada INTERVALO_MONITOREO
    segundos (por defecto 5 minutos). Su trabajo es:

    1. Recorrer todos los servicios de todas las MVs
    2. Verificar su estado actual
    3. Comparar con el último estado conocido
    4. Si hay cambios (caída o recuperación), enviar alerta
    5. Actualizar el último estado conocido

    El diccionario global 'ultimo_estado_conocido' almacena el
    estado anterior de cada servicio con la clave "mv:servicio".
    """
    global ultimo_estado_conocido

    logger.info("Ejecutando monitoreo automático de servicios...")

    for mv_id, mv_config in SERVIDORES.items():
        for servicio in mv_config["servicios"]:
            # Clave única para identificar el servicio en el diccionario
            clave = f"{mv_id}:{servicio}"

            try:
                # Obtener el estado actual del servicio
                estado = obtener_estado_servicio(servicio, mv_id)
                activo_ahora = estado["activo"]

                # Obtener el estado anterior (None si es la primera vez)
                estado_anterior = ultimo_estado_conocido.get(clave)

                # Solo enviar alertas si hay un cambio de estado
                # (y si no es la primera vez que revisamos)
                if estado_anterior is not None:
                    if estado_anterior and not activo_ahora:
                        # El servicio pasó de ACTIVO a INACTIVO → ALERTA DE CAÍDA
                        hora = datetime.now().strftime("%H:%M:%S")
                        mensaje_alerta = (
                            f"🔴 *ALERTA: Servicio caído*\n\n"
                            f"🔧 Servicio: `{servicio}`\n"
                            f"🖥️ Servidor: {mv_config['nombre']}\n"
                            f"⏰ Hora: {hora}\n"
                            f"📊 Estado: `{estado['estado']}`"
                        )

                        # Enviar la alerta al chat configurado
                        await context.bot.send_message(
                            chat_id=ALERT_CHAT_ID,
                            text=mensaje_alerta,
                            parse_mode="Markdown",
                        )

                        # Registrar el evento de caída en la base de datos
                        registrar_evento(
                            tipo="caida",
                            servicio=servicio,
                            mv=mv_id,
                            detalle=f"Estado: {estado['estado']}",
                        )

                        logger.warning(
                            f"ALERTA: {servicio} caído en {mv_id}"
                        )

                    elif not estado_anterior and activo_ahora:
                        # El servicio pasó de INACTIVO a ACTIVO → RECUPERACIÓN
                        hora = datetime.now().strftime("%H:%M:%S")
                        mensaje_recuperacion = (
                            f"🟢 *Servicio recuperado*\n\n"
                            f"🔧 Servicio: `{servicio}`\n"
                            f"🖥️ Servidor: {mv_config['nombre']}\n"
                            f"⏰ Hora: {hora}"
                        )

                        await context.bot.send_message(
                            chat_id=ALERT_CHAT_ID,
                            text=mensaje_recuperacion,
                            parse_mode="Markdown",
                        )

                        # Registrar el evento de recuperación
                        registrar_evento(
                            tipo="recuperacion",
                            servicio=servicio,
                            mv=mv_id,
                            detalle="Servicio recuperado automáticamente",
                        )

                        logger.info(
                            f"RECUPERACIÓN: {servicio} recuperado en {mv_id}"
                        )

                # Actualizar el último estado conocido
                ultimo_estado_conocido[clave] = activo_ahora

            except Exception as e:
                logger.error(
                    f"Error monitoreando {servicio} en {mv_id}: {e}"
                )

    # Recopilar métricas de CPU y RAM
    from ssh_manager import obtener_recursos_numerico
    for mv_id in SERVIDORES.keys():
        try:
            datos_recursos = obtener_recursos_numerico(mv_id)
            if datos_recursos["exito"]:
                registrar_recursos(mv_id, datos_recursos["cpu"], datos_recursos["ram"])
        except Exception as e:
            logger.error(f"Error registrando recursos de {mv_id}: {e}")

    logger.info("Monitoreo automático completado.")


async def tarea_resumen_diario(context: ContextTypes.DEFAULT_TYPE):
    """
    Envía un resumen diario del estado de todos los servicios a las 8am.

    Esta tarea corre una vez al día y resume:
    - Estado actual de cada servicio en cada MV
    - Conteo de servicios activos e inactivos
    """
    logger.info("Generando resumen diario...")

    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
    lineas = [
        f"📊 *RESUMEN DIARIO DE SERVIDORES*",
        f"📅 {ahora}\n",
    ]

    total_activos = 0
    total_caidos = 0

    for mv_id, mv_config in SERVIDORES.items():
        lineas.append(f"🖥️ *{mv_config['nombre']}*")
        for servicio in mv_config["servicios"]:
            try:
                estado = obtener_estado_servicio(servicio, mv_id)
                if estado["activo"]:
                    lineas.append(f"  🟢 `{servicio}` — Activo")
                    total_activos += 1
                else:
                    lineas.append(f"  🔴 `{servicio}` — {estado['estado'].upper()}")
                    total_caidos += 1
            except Exception:
                lineas.append(f"  ⚪ `{servicio}` — Sin datos")
        lineas.append("")

    lineas.append(f"━━━━━━━━━━━━━━━━━━━━━━")
    lineas.append(f"✅ Activos: {total_activos} | ❌ Caídos: {total_caidos}")
    if total_caidos > 0:
        lineas.append(f"\n⚠️ *¡Hay {total_caidos} servicio(s) fuera de línea!*")
    else:
        lineas.append(f"\n🎉 *Todos los servicios funcionando correctamente.*")

    mensaje = "\n".join(lineas)

    await context.bot.send_message(
        chat_id=ALERT_CHAT_ID,
        text=mensaje,
        parse_mode="Markdown",
    )

    logger.info("Resumen diario enviado.")


async def handler_mensajes_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Procesa mensajes de texto plano (sin /) para cumplir con el requisito de comandos
    naturales: 'estado servicio X', 'ver espacio', 'ver memoria', 'ver usuario', 'ver cpu'.
    Responde con la información combinada de AMBOS servidores incluyendo sus IPs.
    """
    texto = update.message.text.lower().strip()
    
    if not texto:
        return
        
    # Comando secreto para descubrir el verdadero Chat ID
    if texto == "dame mi id":
        await update.message.reply_text(f"🤖 El verdadero ID exacto de este chat es: `{update.effective_chat.id}`", parse_mode="Markdown")
        return
        
    # Verificar si es "estado servicio <algo>"
    import re
    match_estado = re.match(r"^estado servicio (.+)$", texto)
    
    # Comandos esperados
    if match_estado:
        servicio = match_estado.group(1).strip()
        
        # Alias para el profesor que pide "ftp" pero en debian es "vsftpd"
        if servicio == "ftp":
            servicio = "vsftpd"
            
        msg = await update.message.reply_text(f"🔍 Consultando estado de *{servicio}* en todos los servidores...", parse_mode="Markdown")
        
        respuesta = f"📊 *Estado de servicio: {servicio}*\n\n"
        for mv_id, mv_config in SERVIDORES.items():
            ip = SSH_CONFIG[mv_id]['host']
            nombre = mv_config['nombre']
            estado = obtener_estado_servicio(servicio, mv_id)
            icono = "🟢" if estado["activo"] else "🔴"
            respuesta += f"🖥️ *{nombre}* (`{ip}`)\n"
            respuesta += f"{icono} Estado: `{estado['estado'].upper()}`\n\n"
            
        await msg.edit_text(respuesta, parse_mode="Markdown")
        return

    if texto == "ver espacio":
        msg = await update.message.reply_text("💾 Consultando espacio en disco en todos los servidores...", parse_mode="Markdown")
        respuesta = f"💾 *Espacio en disco*\n\n"
        for mv_id, mv_config in SERVIDORES.items():
            ip = SSH_CONFIG[mv_id]['host']
            nombre = mv_config['nombre']
            disco = obtener_disco(mv_id)
            respuesta += f"🖥️ *{nombre}* (`{ip}`)\n"
            if disco["exito"]:
                respuesta += f"Uso: `{disco['usado']} / {disco['total']}` (`{disco['pcent']}%`)\n"
                respuesta += f"Libre: `{disco['libre']}`\n\n"
            else:
                respuesta += f"⚠️ Error: `{disco['error']}`\n\n"
        await msg.edit_text(respuesta, parse_mode="Markdown")
        return

    if texto == "ver memoria":
        msg = await update.message.reply_text("🧠 Consultando memoria RAM en todos los servidores...", parse_mode="Markdown")
        respuesta = f"🧠 *Memoria RAM*\n\n"
        for mv_id, mv_config in SERVIDORES.items():
            ip = SSH_CONFIG[mv_id]['host']
            nombre = mv_config['nombre']
            # Usar obtener_cpu_ram que trae la ram string de free -h
            recursos = obtener_cpu_ram(mv_id)
            respuesta += f"🖥️ *{nombre}* (`{ip}`)\n"
            if recursos["exito"]:
                respuesta += f"```\n{recursos['ram']}\n```\n\n"
            else:
                respuesta += f"⚠️ Error: `{recursos['error']}`\n\n"
        await msg.edit_text(respuesta, parse_mode="Markdown")
        return

    if texto == "ver cpu":
        msg = await update.message.reply_text("⚙️ Consultando uso de CPU en todos los servidores...", parse_mode="Markdown")
        respuesta = f"⚙️ *Uso de CPU*\n\n"
        for mv_id, mv_config in SERVIDORES.items():
            from ssh_manager import obtener_recursos_numerico
            ip = SSH_CONFIG[mv_id]['host']
            nombre = mv_config['nombre']
            num = obtener_recursos_numerico(mv_id)
            respuesta += f"🖥️ *{nombre}* (`{ip}`)\n"
            if num["exito"]:
                respuesta += f"Uso actual: `{num['cpu']:.1f}%`\n"
                respuesta += f"Carga (Load): `{num['load']}`\n\n"
            else:
                respuesta += f"⚠️ Error: No disponible\n\n"
        await msg.edit_text(respuesta, parse_mode="Markdown")
        return

    if texto == "ver usuario":
        msg = await update.message.reply_text("👤 Consultando usuarios conectados en todos los servidores...", parse_mode="Markdown")
        respuesta = f"👤 *Usuarios conectados*\n\n"
        for mv_id, mv_config in SERVIDORES.items():
            ip = SSH_CONFIG[mv_id]['host']
            nombre = mv_config['nombre']
            users = obtener_usuarios_conectados(mv_id)
            respuesta += f"🖥️ *{nombre}* (`{ip}`)\n"
            if users["exito"]:
                respuesta += f"```\n{users['usuarios']}\n```\n\n"
            else:
                respuesta += f"⚠️ Error: `{users['error']}`\n\n"
        await msg.edit_text(respuesta, parse_mode="Markdown")
        return


# ============================================================
# FUNCIÓN PRINCIPAL - INICIALIZACIÓN DEL BOT
# ============================================================

def main():
    """
    Función principal que configura e inicia el bot.

    Pasos:
    1. Inicializa la base de datos
    2. Crea la aplicación del bot con el token
    3. Registra todos los handlers de comandos y callbacks
    4. Configura la tarea periódica de monitoreo
    5. Inicia el bot en modo polling (espera mensajes)
    """
    # ---- Paso 1: Inicializar la base de datos ----
    logger.info("Inicializando base de datos...")
    inicializar_db()

    # ---- Paso 2: Crear la aplicación del bot ----
    # Application es la clase principal de python-telegram-bot v20+
    # El token lo obtuvimos de @BotFather
    logger.info("Creando aplicación del bot...")
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # ---- Paso 3: Registrar handlers de comandos ----
    # Cada handler asocia un comando con su función
    # CommandHandler procesa los comandos que empiezan con /
    app.add_handler(CommandHandler("start", comando_start))
    app.add_handler(CommandHandler("help", comando_ayuda))
    app.add_handler(CommandHandler("estado", comando_estado))
    app.add_handler(CommandHandler("reiniciar", comando_reiniciar))
    app.add_handler(CommandHandler("logs", comando_logs))
    app.add_handler(CommandHandler("status_general", comando_status_general))
    app.add_handler(CommandHandler("historial", comando_historial))
    app.add_handler(CommandHandler("ping", comando_ping))
    app.add_handler(CommandHandler("uptime", comando_uptime))
    app.add_handler(CommandHandler("backup", comando_backup))
    app.add_handler(CommandHandler("ejecutar", comando_ejecutar))
    app.add_handler(CommandHandler("graficas", comando_graficas))

    # Handler para los mensajes de texto natural requeridos por el profe
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler_mensajes_texto))

    # ---- Paso 4: Registrar handler de callbacks (botones) ----
    # CallbackQueryHandler procesa los clicks en botones inline
    # Un solo handler maneja todos los callbacks y los enruta internamente
    app.add_handler(CallbackQueryHandler(callback_handler))

    # ---- Paso 5: Configurar monitoreo automático ----
    # JobQueue permite programar tareas periódicas
    # run_repeating ejecuta la tarea cada INTERVALO_MONITOREO segundos
    # first=30 significa que la primera ejecución será 30 segundos después
    # de iniciar el bot (para dar tiempo a que todo arranque)
    job_queue = app.job_queue
    job_queue.run_repeating(
        tarea_monitoreo,                  # Función a ejecutar
        interval=INTERVALO_MONITOREO,     # Cada cuánto (en segundos)
        first=30,                          # Primera ejecución a los 30s
        name="monitoreo_servicios",        # Nombre del job (para identificarlo)
    )

    # ---- Resumen diario a las 8:00am ----
    from datetime import time as dtime
    job_queue.run_daily(
        tarea_resumen_diario,
        time=dtime(hour=8, minute=0, second=0),
        name="resumen_diario",
    )

    logger.info(
        f"Monitoreo automático configurado cada {INTERVALO_MONITOREO} segundos"
    )
    logger.info("Resumen diario programado a las 08:00am")

    # ---- Paso 6: Iniciar el bot ----
    # run_polling inicia el bot y espera mensajes de Telegram
    # allowed_updates=Update.ALL_TYPES recibe todos los tipos de actualizaciones
    # drop_pending_updates=True descarta mensajes que llegaron mientras el bot
    # estaba apagado (para evitar procesar comandos viejos)
    logger.info("🤖 Bot iniciado. Esperando mensajes...")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


# Punto de entrada: si se ejecuta directamente este archivo, inicia el bot
if __name__ == "__main__":
    main()
