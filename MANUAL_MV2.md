# Manual de Configuración para MV2

Este manual te guiará paso a paso para configurar tu segunda máquina virtual (MV2) cuando la adquieras, para que el bot de Telegram pueda monitorearla y controlarla igual que a la MV1.

## 1. Instalación de Servicios en MV2
Una vez que tengas acceso SSH a la MV2, ingresa mediante la terminal y ejecuta los siguientes comandos. Estos comandos instalarán Apache (Servidor web), Redis (Base de datos en caché) y Fail2ban (Seguridad).

```bash
# 1. Actualizar el sistema
sudo apt-get update -y

# 2. Instalar Apache, Redis y Fail2ban
sudo apt-get install -y apache2 redis-server fail2ban

# 3. Asegurar que los servicios arranquen con el servidor
sudo systemctl enable apache2 redis-server fail2ban ssh

# 4. Habilitar y configurar el Firewall (UFW)
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP (Apache)
sudo ufw enable
```

## 2. Actualizar las credenciales en el Bot
En la computadora Windows donde tienes el bot corriendo, abre el archivo `.env` y busca la sección de configuración de MV2.

Actualiza los valores con la IP y la contraseña de tu nueva máquina:

```env
# Configuración SSH para MV2 (servidor remoto secundario)
MV2_SSH_HOST=ip_de_tu_mv2_aqui
MV2_SSH_PORT=22
MV2_SSH_USER=root
MV2_SSH_PASSWORD=contraseña_de_tu_mv2_aqui
```

## 3. Consideraciones Adicionales
- Si tu proveedor de nube te da un usuario diferente a `root` (por ejemplo, `ubuntu`), debes cambiar `MV2_SSH_USER=ubuntu` en el archivo `.env`.
- Si usas un usuario diferente a `root`, necesitarás ejecutar `sudo visudo` en la MV2 y agregar: `tu_usuario ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart *, /usr/bin/journalctl *` (para que el bot pueda reiniciar servicios sin contraseña). Si usas `root`, ignora esto.

## 4. Probar la Conexión
1. Reinicia el bot en tu computadora (`Ctrl + C` y vuelve a correr `python bot.py`).
2. Ve a Telegram, escribe `/start` y haz clic en el botón de **MV2**.
3. Selecciona un servicio (como `apache2` o `redis-server`) y haz clic en **Ver estado**.
4. ¡Si aparece verde 🟢, lo has logrado exitosamente!
