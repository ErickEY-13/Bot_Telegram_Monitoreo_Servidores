import matplotlib
# Usar el backend 'Agg' para generar imágenes en memoria (sin interfaz gráfica)
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import db
from datetime import datetime

# Estilo hacker/oscuro global
plt.style.use('dark_background')

def generar_grafico_caidas() -> io.BytesIO:
    """
    Genera un gráfico de barras horizontales mostrando las caídas por servicio.
    Retorna un objeto BytesIO con la imagen PNG en memoria.
    """
    datos = db.obtener_conteo_caidas()
    
    servicios = []
    caidas = []
    
    # Extraer datos
    for mv, servicios_dict in datos.items():
        for servicio, cantidad in servicios_dict.items():
            servicios.append(f"{servicio} ({mv})")
            caidas.append(cantidad)
            
    fig, ax = plt.subplots(figsize=(8, 5))
    
    if not servicios:
        # Si no hay caídas
        ax.text(0.5, 0.5, "SIN INCIDENCIAS\n(Todo está perfecto)", 
                horizontalalignment='center', verticalalignment='center',
                fontsize=16, color='#00ff00')
        ax.set_xticks([])
        ax.set_yticks([])
    else:
        # Dibujar gráfico de barras
        barras = ax.barh(servicios, caidas, color='#ff3333', edgecolor='white')
        ax.set_xlabel('Número de Caídas', fontsize=12)
        ax.set_title('Incidencias de Servicios (Histórico)', fontsize=14, color='#00ff00', pad=20)
        
        # Ajustar los saltos del eje X para que sean enteros
        ax.xaxis.get_major_locator().set_params(integer=True)
        
        # Añadir las cantidades al final de cada barra
        for barra in barras:
            ax.text(barra.get_width() + 0.1, barra.get_y() + barra.get_height()/2, 
                    str(int(barra.get_width())), 
                    va='center', color='white', fontweight='bold')

    plt.tight_layout()
    
    # Guardar en memoria
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=100, facecolor='#111111')
    buffer.seek(0)
    plt.close(fig)
    
    return buffer

def generar_grafico_recursos(mv: str) -> io.BytesIO:
    """
    Genera un gráfico de líneas con el histórico de CPU y RAM de una MV.
    Retorna un objeto BytesIO con la imagen PNG.
    """
    datos = db.obtener_historico_recursos(mv, limite=30)
    
    fig, ax = plt.subplots(figsize=(10, 5))
    
    if len(datos) < 2:
        ax.text(0.5, 0.5, "RECOPILANDO DATOS...\n(Espera unos minutos más)", 
                horizontalalignment='center', verticalalignment='center',
                fontsize=16, color='#00aaff')
        ax.set_xticks([])
        ax.set_yticks([])
    else:
        # Procesar datos
        # datos viene ordenado de más antiguo a más reciente
        fechas = []
        cpu = []
        ram = []
        for d in datos:
            # d["fecha"] es ISO: "2026-07-05T06:45:00.123"
            try:
                dt = datetime.fromisoformat(d["fecha"])
                # formato de hora hh:mm
                fechas.append(dt.strftime("%H:%M"))
            except:
                fechas.append("?")
            cpu.append(d["cpu"])
            ram.append(d["ram"])
            
        ax.plot(fechas, cpu, label='CPU %', color='#00ff00', marker='o', linewidth=2)
        ax.plot(fechas, ram, label='RAM %', color='#00aaff', marker='s', linewidth=2)
        
        ax.set_ylim(0, 100)
        ax.set_ylabel('Porcentaje de Uso (%)', fontsize=12)
        ax.set_title(f'Histórico de Rendimiento - {mv.upper()}', fontsize=14, color='white', pad=20)
        ax.legend(loc='upper left', frameon=True, facecolor='#222222')
        
        # Rotar fechas para que quepan
        plt.xticks(rotation=45, ha='right')
        
        # Grid discreto
        ax.grid(True, linestyle='--', alpha=0.3)

    plt.tight_layout()
    
    # Guardar en memoria
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=100, facecolor='#111111')
    buffer.seek(0)
    plt.close(fig)
    
    return buffer
