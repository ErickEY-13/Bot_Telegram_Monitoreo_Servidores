import paramiko
import time

host = '52.162.237.197'
user = 'fpoma'
password = '050.Ada00000'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print(f"Conectando a {host}...")
    client.connect(hostname=host, username=user, password=password, timeout=10)
    print("Conectado exitosamente.")
    
    comandos = [
        "sudo apt-get update -y",
        "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y apache2 redis-server fail2ban",
        "sudo systemctl enable apache2 redis-server fail2ban ssh",
        "sudo systemctl start apache2 redis-server fail2ban ssh"
    ]
    
    for cmd in comandos:
        print(f"\nEjecutando: {cmd}")
        stdin, stdout, stderr = client.exec_command(cmd)
        
        # Wait for the command to finish
        exit_status = stdout.channel.recv_exit_status()
        print(f"Código: {exit_status}")
        
        salida = stdout.read().decode()
        error = stderr.read().decode()
        
        if salida:
            print(f"Salida: {salida[:500]}...")
        if error:
            print(f"Error: {error[:500]}...")
            
    print("\n¡Instalación en MV2 completa!")
finally:
    client.close()
