# 👥 Manual de Gestión de Usuarios y Seguridad

Por defecto, el bot está diseñado con una seguridad estricta: **solo una persona** (el administrador con su Chat ID en el archivo `.env`) puede apagar, encender o reiniciar servicios. Los demás usuarios solo pueden ver información (estado, CPU, logs).

Si necesitas que **varias personas** puedan administrar los servidores, o si quieres dejar el bot **completamente abierto** para que cualquier usuario pueda reiniciarlos, aquí te explicamos cómo modificar el código.

---

## 🛠️ Opción 1: Agregar más administradores (Recomendado)

El bot ya está programado para aceptar múltiples administradores de forma nativa. Solo necesitas modificar tu archivo `.env`.

### Paso Único: Modificar el `.env`
Abre tu archivo `.env` y agrega los IDs de tus compañeros (o el ID del grupo) separados por comas. (Para saber el ID de alguien, esa persona debe hablarle a `@userinfobot` en Telegram).

```env
# Ejemplo con tu ID privado y el ID del Grupo Universitario:
AUTHORIZED_CHAT_ID=-1005360731046,6536181396,1122334455
```

¡Listo! Reinicia el bot (`Ctrl+C` y `python bot.py`) y todas esas personas/grupos tendrán permisos de administrador al instante. No necesitas tocar nada de código Python.

---

## 🔓 Opción 2: Hacer el bot libre para TODOS (Peligroso)

Si esto es para un proyecto estudiantil, una demostración interna o una red cerrada y **no te importa la seguridad**, puedes hacer que el bot ignore los bloqueos y deje que **cualquier persona en el mundo** que encuentre el bot pueda reiniciar y apagar tus servidores.

> ⚠️ **ADVERTENCIA:** Cualquiera que use el bot podrá ejecutar comandos en tus máquinas virtuales. ¡Úsalo bajo tu propio riesgo!

Para hacer el bot totalmente libre, solo necesitas modificar 1 sola línea de código en `bot.py`.

Abre el archivo `bot.py`, busca la función `es_usuario_autorizado` (cerca de la línea 90) y cámbiala para que siempre diga que sí (`True`):

```python
def es_usuario_autorizado(chat_id: int) -> bool:
    """
    MODO LIBRE: Ignora la seguridad y permite todo a todos.
    """
    return True
```

### ¿Qué pasa cuando haces esto?
Al retornar siempre `True`, el bot creerá que **todos** los usuarios son administradores. 
- Ya no revisará el `.env`.
- Todos los botones de Reiniciar/Detener/Iniciar funcionarán para cualquier persona.
- Cualquiera podrá usar el comando `/ejecutar`.

### ¿Cómo revertirlo?
Si alguien hace estragos y quieres volver a bloquear el bot, simplemente vuelve a dejar la función como estaba originalmente:

```python
def es_usuario_autorizado(chat_id: int) -> bool:
    from config import AUTHORIZED_CHAT_ID
    return chat_id == AUTHORIZED_CHAT_ID
```
