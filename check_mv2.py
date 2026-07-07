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
    
    stdin, stdout, stderr = client.exec_command('uname -a && cat /etc/os-release')
    print("SO Info:", stdout.read().decode())
    
    print("Probando sudo...")
    stdin, stdout, stderr = client.exec_command('sudo -S -l')
    stdin.write(password + '\n')
    stdin.flush()
    time.sleep(1)
    print("Sudo Info:", stdout.read().decode())
    print("Sudo Errors:", stderr.read().decode())
    
finally:
    client.close()
