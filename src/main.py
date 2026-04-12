import sys
import os
import json
import random
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QWidget, QVBoxLayout
from PyQt6.QtCore import QTimer, Qt, QRect, QPoint, QSize
from PyQt6.QtGui import QPixmap, QFont, QPalette, QColor

class SpeechBubble(QWidget):
    """Una ventana flotante transparente para el texto del robot"""
    def __init__(self, parent=None):
        super().__init__(parent)
        # Ventana transparente, sin bordes, siempre encima, ignora clics
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5) # Margen interno
        
        self.label = QLabel("", self)
        # Usamos una fuente monoespaciada ciberbótica
        self.label.setFont(QFont("Monospace", 12, QFont.Weight.Bold))
        self.label.setWordWrap(True) # Permitir varias líneas si es largo
        
        # Color del texto (azul neón corrupto)
        palette = self.label.palette()
        palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 255, 255)) 
        self.label.setPalette(palette)
        
        layout.addWidget(self.label, 0, Qt.AlignmentFlag.AlignCenter)
        self.hide()

    def speak(self, text, duration_ms=2500):
        self.label.setText(text)
        self.adjustSize()
        self.show()
        # Timer para ocultar el bocadillo automáticamente
        QTimer.singleShot(duration_ms, self.hide)

class CyberPet(QMainWindow):
    def __init__(self, skin_folder):
        super().__init__()
        # Configuración de ventana (Transparente y siempre encima)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.label = QLabel(self)
        self.skin_path = skin_folder
        self.is_dragging = False # Bloquea la IA mientras lo arrastras
        
        # Cargar Configuración
        config_file = os.path.join(self.skin_path, "config.json")
        try:
            with open(config_file, "r") as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"Error cargando config.json: {e}")
            sys.exit(1)
            
        self.base_height = self.config.get("base_height", 200)
        self.current_state = "idle"
        self.current_frame = 0
        
        # Crear el Bocadillo de diálogo
        self.bubble = SpeechBubble()
        
        # Timer de Animación (Frames)
        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.update_animation)
        
        # Timer de IA (Decisiones)
        self.ai_timer = QTimer()
        self.ai_timer.timeout.connect(self.ai_think)
        self.ai_timer.start(3000) # El robot "piensa" cada 3 segundos
        
        self.load_animation(self.current_state)
        self.show()

    def load_animation(self, state):
        """Carga el archivo y calcula dimensiones de corte"""
        anim_data = self.config["animations"][state]
        file_path = os.path.join(self.skin_path, anim_data["file"])
        
        if not os.path.exists(file_path):
            print(f"Error: No se encuentra {file_path}")
            return

        self.full_sheet = QPixmap(file_path)
        self.cols = anim_data["cols"]
        self.frame_w = self.full_sheet.width() // self.cols
        self.frame_h = self.full_sheet.height()
        self.current_frame = 0
        
        # Aplicar la velocidad específica de esta animación
        speed = anim_data.get("speed", 150)
        self.anim_timer.start(speed)

    def update_animation(self):
        """Corta, escala y ajusta la ventana"""
        x = self.current_frame * self.frame_w
        rect = QRect(x, 0, self.frame_w, self.frame_h)
        
        frame = self.full_sheet.copy(rect)
        
        # ESCALADO DINÁMICO: Forzamos la altura del JSON manteniendo la proporción
        frame_scaled = frame.scaledToHeight(
            self.base_height, 
            Qt.TransformationMode.SmoothTransformation
        )
        
        self.label.setPixmap(frame_scaled)
        self.label.adjustSize()
        self.resize(self.label.size())
        
        self.current_frame = (self.current_frame + 1) % self.cols
        
        # Sincronizar la posición del bocadillo sobre la cabeza
        if self.bubble.isVisible():
            # Posición relativa sobre el robot
            bubble_pos = self.frameGeometry().topLeft() - QPoint(0, self.bubble.height() + 10)
            # Centrar el bocadillo horizontalmente
            bubble_pos.setX(self.frameGeometry().left() + (self.width() // 2) - (self.bubble.width() // 2))
            self.bubble.move(bubble_pos)

    def change_state(self, new_state, speech_type=None):
        if self.current_state != new_state:
            self.current_state = new_state
            self.load_animation(new_state)
            
            # Si hay un tipo de discurso definido en el JSON, dice algo aleatorio
            if speech_type and speech_type in self.config["dialogs"]:
                phrases = self.config["dialogs"][speech_type]
                self.bubble.speak(random.choice(phrases))

    def ai_think(self):
        """El cerebro: decide qué hacer basándose en probabilidades"""
        if self.is_dragging:
            return

        dice = random.randint(1, 100)
        
        if dice <= 50: # 50% Idle
            self.change_state("idle")
        elif dice <= 70: # 20% Mirar L/R
            state = random.choice(["look_l", "look_r"])
            self.change_state(state, "glitch") # Dice algo corrupto al mirar
        elif dice <= 85: # 15% Enfadarse
            self.change_state("angry", "alarm") # Grita una alarma
        elif dice <= 95: # 10% Binary_Corrupt
            self.change_state("idle", "binary_corrupt") # Dice binario al azar
        else: # 5% Dormir
            self.change_state("sleep")
            self.bubble.hide() # Ocultar diálogo al dormir

    # --- Lógica de Arrastre (Bloquea la IA) ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.change_state("drag_id")
            self.bubble.hide() # Ocultar diálogo al arrastrar

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            self.change_state("drag_mv")

    def mouseReleaseEvent(self, event):
        self.is_dragging = False
        self.change_state("idle")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    path = os.path.join(os.getcwd(), "assets/skins/default")
    pet = CyberPet(path)
    sys.exit(app.exec())