import sys
import os
import json
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow
from PyQt6.QtCore import QTimer, Qt, QRect
from PyQt6.QtGui import QPixmap

class CyberPet(QMainWindow):
    def __init__(self, skin_folder):
        super().__init__()
        # Configuración de ventana (Transparente y siempre encima)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.label = QLabel(self)
        self.skin_path = skin_folder
        
        # 1. CARGA DEL JSON: Leemos las instrucciones de la skin
        config_file = os.path.join(self.skin_path, "config.json")
        with open(config_file, "r") as f:
            self.config = json.load(f)
        
        self.current_state = "idle"
        self.current_frame = 0
        
        # 2. INICIO DINÁMICO: Cargamos la primera animación definida en el JSON
        self.load_animation(self.current_state)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(150)
        self.show()

    def load_animation(self, state):
        """Busca en el JSON qué archivo y cuántas columnas usar"""
        anim_data = self.config["animations"][state]
        file_path = os.path.join(self.skin_path, anim_data["file"])
        
        self.full_sheet = QPixmap(file_path)
        self.cols = anim_data["cols"]
        
        # MEDIDA AUTOMÁTICA: Aquí es donde el script 'mira' la imagen
        self.frame_w = self.full_sheet.width() // self.cols
        self.frame_h = self.full_sheet.height()
        self.current_frame = 0

    def update_animation(self):
        x = self.current_frame * self.frame_w
        rect = QRect(x, 0, self.frame_w, self.frame_h)
        
        frame = self.full_sheet.copy(rect)
        
        # --- NUEVA LÓGICA DE ESCALADO ---
        # Forzamos a que el frame siempre mida 200px de alto, manteniendo la proporción
        alto_objetivo = 200 
        frame_escalado = frame.scaledToHeight(alto_objetivo, Qt.TransformationMode.SmoothTransformation)
        
        self.label.setPixmap(frame_escalado)
        # --------------------------------
        
        self.label.adjustSize()
        self.resize(self.label.size())
        self.current_frame = (self.current_frame + 1) % self.cols

    def change_state(self, new_state):
        """Cambia de animación solo si es un estado distinto"""
        if self.current_state != new_state:
            self.current_state = new_state
            self.load_animation(new_state)

    # --- Lógica de Interacción ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.change_state("drag_id")

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            self.change_state("drag_mv")

    def mouseReleaseEvent(self, event):
        self.change_state("idle")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # IMPORTANTE: Asegúrate de que esta ruta apunte a tu carpeta default
    path = os.path.join(os.getcwd(), "assets/skins/default")
    pet = CyberPet(path)
    sys.exit(app.exec())