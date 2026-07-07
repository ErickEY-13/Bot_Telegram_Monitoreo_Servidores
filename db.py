# ============================================================
# db.py - Módulo de base de datos (SQLite)
# ============================================================
# Este módulo maneja la persistencia del historial de eventos.
# Usa SQLite, que es una base de datos ligera que no necesita
# un servidor aparte (se guarda en un archivo .db).
#
# Funciones principales:
# - inicializar_db(): crea la tabla si no existe
# - registrar_evento(): guarda un nuevo evento en el historial
# - obtener_historial(): recupera los últimos N eventos
# ============================================================

import sqlite3
import logging
from datetime import datetime
from config import DB_PATH

# Configurar el logger para este módulo
logger = logging.getLogger(__name__)


def inicializar_db():
    """
    Crea la tabla de historial si no existe.

    Se llama al iniciar el bot para asegurarse de que la base de datos
    está lista para guardar eventos. Si ya existe, no hace nada.

    La tabla 'historial' tiene estos campos:
    - id: identificador único auto-incremental
    - fecha: fecha y hora del evento (formato texto ISO)
    - tipo: tipo de evento ("caida", "recuperacion", "reinicio_manual", "error")
    - servicio: nombre del servicio afectado
    - mv: identificador de la MV ("mv1" o "mv2")
    - usuario: quién ejecutó la acción (para reinicios manuales)
    - detalle: información adicional del evento
    """
    try:
        # Conectar a la base de datos (se crea el archivo si no existe)
        conexion = sqlite3.connect(DB_PATH)
        cursor = conexion.cursor()

        # Crear la tabla con IF NOT EXISTS para que sea idempotente
        # (se puede ejecutar muchas veces sin error)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                tipo TEXT NOT NULL,
                servicio TEXT NOT NULL,
                mv TEXT NOT NULL,
                usuario TEXT DEFAULT '',
                detalle TEXT DEFAULT ''
            )
        """)

        # Crear un índice en la columna 'fecha' para acelerar las consultas
        # ordenadas por fecha (que son las más comunes)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_historial_fecha
            ON historial (fecha DESC)
        """)

        # Crear la tabla de recursos para el histórico de CPU y RAM
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recursos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                mv TEXT NOT NULL,
                cpu_porcentaje REAL NOT NULL,
                ram_porcentaje REAL NOT NULL
            )
        """)

        # Índice para acelerar consultas de recursos por MV y fecha
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_recursos_mv_fecha
            ON recursos (mv, fecha DESC)
        """)

        # Guardar los cambios y cerrar la conexión
        conexion.commit()
        conexion.close()

        logger.info(f"Base de datos inicializada en: {DB_PATH}")

    except sqlite3.Error as e:
        logger.error(f"Error al inicializar la base de datos: {e}")
        raise


def registrar_evento(
    tipo: str,
    servicio: str,
    mv: str,
    usuario: str = "",
    detalle: str = ""
):
    """
    Registra un nuevo evento en el historial.

    Cada acción importante se guarda: caídas de servicios, recuperaciones,
    reinicios manuales, etc. Esto permite llevar un registro completo
    de todo lo que pasa con los servicios monitoreados.

    Args:
        tipo: tipo de evento. Valores posibles:
              "caida"              - un servicio pasó de activo a inactivo
              "recuperacion"       - un servicio pasó de inactivo a activo
              "reinicio_manual"    - un usuario reinició el servicio manualmente
              "error"              - ocurrió un error al ejecutar una acción
        servicio: nombre del servicio (ej: "apache2", "mysql")
        mv: identificador de la MV ("mv1" o "mv2")
        usuario: nombre/id del usuario que ejecutó la acción (opcional)
        detalle: información adicional sobre el evento (opcional)
    """
    try:
        conexion = sqlite3.connect(DB_PATH)
        cursor = conexion.cursor()

        # Obtener la fecha y hora actual en formato legible
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Insertar el evento en la tabla
        cursor.execute(
            """
            INSERT INTO historial (fecha, tipo, servicio, mv, usuario, detalle)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (fecha_actual, tipo, servicio, mv, usuario, detalle),
        )

        conexion.commit()
        conexion.close()

        logger.info(
            f"Evento registrado: tipo={tipo}, servicio={servicio}, "
            f"mv={mv}, usuario={usuario}"
        )

    except sqlite3.Error as e:
        logger.error(f"Error al registrar evento en la base de datos: {e}")


def obtener_historial(limite: int = 10) -> list[dict]:
    """
    Obtiene los últimos N eventos del historial.

    Retorna los eventos más recientes ordenados de más nuevo a más antiguo.

    Args:
        limite: cantidad máxima de eventos a retornar (por defecto 10)

    Returns:
        lista de diccionarios, cada uno con:
        - "id": int
        - "fecha": str
        - "tipo": str
        - "servicio": str
        - "mv": str
        - "usuario": str
        - "detalle": str
    """
    try:
        conexion = sqlite3.connect(DB_PATH)
        # row_factory permite acceder a las columnas por nombre
        conexion.row_factory = sqlite3.Row
        cursor = conexion.cursor()

        # Obtener los últimos N eventos ordenados por fecha descendente
        cursor.execute(
            """
            SELECT id, fecha, tipo, servicio, mv, usuario, detalle
            FROM historial
            ORDER BY fecha DESC, id DESC
            LIMIT ?
            """,
            (limite,),
        )

        # Convertir cada fila a un diccionario para fácil manipulación
        filas = cursor.fetchall()
        eventos = []
        for fila in filas:
            eventos.append({
                "id": fila["id"],
                "fecha": fila["fecha"],
                "tipo": fila["tipo"],
                "servicio": fila["servicio"],
                "mv": fila["mv"],
                "usuario": fila["usuario"],
                "detalle": fila["detalle"],
            })

        conexion.close()
        return eventos

    except sqlite3.Error as e:
        logger.error(f"Error al obtener historial: {e}")
        return []


def obtener_historial_servicio(servicio: str, mv: str, limite: int = 5) -> list[dict]:
    """
    Obtiene el historial de un servicio específico en una MV.

    Útil para ver el historial de un servicio en particular.

    Args:
        servicio: nombre del servicio
        mv: identificador de la MV
        limite: cantidad máxima de eventos

    Returns:
        lista de diccionarios con los eventos
    """
    try:
        conexion = sqlite3.connect(DB_PATH)
        conexion.row_factory = sqlite3.Row
        cursor = conexion.cursor()

        cursor.execute(
            """
            SELECT id, fecha, tipo, servicio, mv, usuario, detalle
            FROM historial
            WHERE servicio = ? AND mv = ?
            ORDER BY fecha DESC, id DESC
            LIMIT ?
            """,
            (servicio, mv, limite),
        )

        filas = cursor.fetchall()
        eventos = []
        for fila in filas:
            eventos.append({
                "id": fila["id"],
                "fecha": fila["fecha"],
                "tipo": fila["tipo"],
                "servicio": fila["servicio"],
                "mv": fila["mv"],
                "usuario": fila["usuario"],
                "detalle": fila["detalle"],
            })

        conexion.close()
        return eventos

    except sqlite3.Error as e:
        logger.error(f"Error al obtener historial del servicio: {e}")
        return []


def registrar_recursos(mv: str, cpu: float, ram: float):
    """
    Registra el estado actual de CPU y RAM para las gráficas.
    """
    try:
        conexion = sqlite3.connect(DB_PATH)
        cursor = conexion.cursor()
        
        # Guardar fecha en formato ISO
        fecha_actual = datetime.utcnow().isoformat()
        
        cursor.execute(
            "INSERT INTO recursos (fecha, mv, cpu_porcentaje, ram_porcentaje) VALUES (?, ?, ?, ?)",
            (fecha_actual, mv, cpu, ram)
        )
        conexion.commit()
        conexion.close()
    except sqlite3.Error as e:
        logger.error(f"Error al registrar recursos en BD: {e}")

def obtener_conteo_caidas() -> dict:
    """
    Retorna cuántas caídas ha tenido cada servicio en cada MV.
    Retorna: { "mv1": {"apache2": 5, "mysql": 2}, "mv2": {...} }
    """
    try:
        conexion = sqlite3.connect(DB_PATH)
        conexion.row_factory = sqlite3.Row
        cursor = conexion.cursor()
        
        cursor.execute("SELECT mv, servicio, COUNT(*) as cantidad FROM historial WHERE tipo = 'caida' GROUP BY mv, servicio")
        filas = cursor.fetchall()
        
        resultados = {}
        for fila in filas:
            mv = fila["mv"]
            servicio = fila["servicio"]
            cantidad = fila["cantidad"]
            
            if mv not in resultados:
                resultados[mv] = {}
            resultados[mv][servicio] = cantidad
            
        conexion.close()
        return resultados
    except sqlite3.Error as e:
        logger.error(f"Error al obtener conteo de caídas: {e}")
        return {}

def obtener_historico_recursos(mv: str, limite: int = 50) -> list:
    """
    Retorna los últimos registros de recursos para graficar.
    """
    try:
        conexion = sqlite3.connect(DB_PATH)
        conexion.row_factory = sqlite3.Row
        cursor = conexion.cursor()
        
        cursor.execute(
            "SELECT fecha, cpu_porcentaje, ram_porcentaje FROM recursos WHERE mv = ? ORDER BY fecha DESC LIMIT ?",
            (mv, limite)
        )
        
        # Volteamos la lista para que vaya de más antiguo a más reciente
        filas = cursor.fetchall()[::-1]
        
        datos = []
        for fila in filas:
            datos.append({
                "fecha": fila["fecha"],
                "cpu": fila["cpu_porcentaje"],
                "ram": fila["ram_porcentaje"]
            })
            
        conexion.close()
        return datos
    except sqlite3.Error as e:
        logger.error(f"Error al obtener recursos de {mv}: {e}")
        return []
