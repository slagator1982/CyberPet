import os
from PyQt6.QtGui import QImage

def analizar_skins(ruta_skin):
    print(f"{'Archivo':<20} | {'Resolución (WxH)':<18} | {'Frame Individual (WxH)':<20}")
    print("-" * 65)
    
    if not os.path.exists(ruta_skin):
        print(f"Error: La ruta {ruta_skin} no existe.")
        return

    archivos = sorted([f for f in os.listdir(ruta_skin) if f.endswith(('.png', '.jpg', '.jpeg'))])
    
    for archivo in archivos:
        ruta_completa = os.path.join(ruta_skin, archivo)
        img = QImage(ruta_completa)
        
        if img.isNull():
            print(f"{archivo:<20} | Error al cargar")
            continue
            
        ancho = img.width()
        alto = img.height()
        
        # Asumiendo que siempre son 6 columnas
        frame_w = ancho // 6
        frame_h = alto
        
        print(f"{archivo:<20} | {ancho:>5}x{alto:<10} | {frame_w:>5}x{frame_h:<12}")

if __name__ == "__main__":
    # Ajusta esta ruta si es necesario
    ruta = "assets/skins/default"
    analizar_skins(ruta)
