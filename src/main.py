import sys
import os
import json
import random
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QWidget, QVBoxLayout
from PyQt6.QtCore import QTimer, Qt, QRect, QPoint
from PyQt6.QtGui import QPixmap, QFont, QPalette, QColor

class SpeechBubble(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout = QVBoxLayout(self)
        self.label = QLabel("", self)
        self.label.setFont(QFont("Monospace", 10, QFont.Weight.Bold))
        palette = self.label.palette()
        palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 255, 255)) 
        self.label.setPalette(palette)
        layout.addWidget(self.label)
        self.hide()

    def speak(self, text):
        self.label.setText(text)
        self.adjustSize()
        self.show()
        QTimer.singleShot(3000, self.hide)

class CyberPet(QMainWindow):
    def __init__(self, skin_folder):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.label = QLabel(self)
        # CRÍTICO: El label no debe capturar el ratón, para que lo haga la ventana
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        self.skin_path = skin_folder
        self.is_dragging = False
        self.current_state = ""
        self.current_frame = 0
        self.current_move_speed = 0
        
        with open(os.path.join(self.skin_path, "config.json"), "r") as f:
            self.config = json.load(f)
            
        self.base_height = self.config.get("base_height", 180)
        self.bubble = SpeechBubble()
        
        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.update_animation)
        
        self.ai_timer = QTimer()
        self.ai_timer.timeout.connect(self.ai_think)
        self.ai_timer.start(4000) 
        
        self.change_state("idle")
        self.show()

    def load_animation(self, state):
        anim_data = self.config["animations"][state]
        file_path = os.path.join(self.skin_path, anim_data["file"])
        self.full_sheet = QPixmap(file_path)
        self.cols = anim_data["cols"]
        self.current_move_speed = anim_data.get("move_speed", 0)
        self.frame_w = self.full_sheet.width() // self.cols
        self.frame_h = self.full_sheet.height()
        self.current_frame = 0
        self.anim_timer.start(anim_data.get("speed", 150))

    def update_animation(self):
        # Movimiento IA
        if self.current_move_speed != 0 and not self.is_dragging:
            self.move(self.pos() + QPoint(self.current_move_speed, 0))

        # Render
        x = self.current_frame * self.frame_w
        rect = QRect(x, 0, self.frame_w, self.frame_h)
        frame_scaled = self.full_sheet.copy(rect).scaledToHeight(self.base_height, Qt.TransformationMode.SmoothTransformation)
        
        self.label.setPixmap(frame_scaled)
        self.label.adjustSize()
        self.resize(self.label.size())
        self.current_frame = (self.current_frame + 1) % self.cols
        
        if self.bubble.isVisible():
            self.bubble.move(self.x() + (self.width()//2) - (self.bubble.width()//2), self.y() - 40)

    def change_state(self, new_state, speech_type=None):
        if self.current_state != new_state:
            self.current_state = new_state
            self.load_animation(new_state)
            if speech_type and random.random() < 0.3:
                phrases = self.config["dialogs"].get(speech_type, [])
                if phrases: self.bubble.speak(random.choice(phrases))

    def ai_think(self):
        if self.is_dragging: return
        dice = random.randint(1, 100)
        if dice <= 40: self.change_state("idle")
        elif dice <= 60: self.change_state("look_l")
        elif dice <= 80: self.change_state("look_r")
        elif dice <= 90: self.change_state("sleep")
        else: self.change_state("angry", "alarm")

    # --- EVENTOS DE RATÓN RE-INGENIERIZADOS ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            # Usamos position() para compatibilidad con Qt6 moderno
            self.offset = event.position().toPoint()
            self.change_state("drag_id")
            self.bubble.hide()

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            # Cálculo de posición global estable
            new_pos = event.globalPosition().toPoint() - self.offset
            self.move(new_pos)
            if self.current_state != "drag_mv":
                self.change_state("drag_mv")

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
            self.change_state("idle")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    path = os.path.join(os.getcwd(), "assets/skins/default")
    pet = CyberPet(path)
    sys.exit(app.exec())