import sys
import os
import json
import random
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QWidget, QVBoxLayout
from PyQt6.QtCore import QTimer, Qt, QRect, QPoint, QSize
from PyQt6.QtGui import QPixmap, QFont, QPalette, QColor, QPainter

class SpeechBubble(QWidget):
    """Bocadillo de texto ciberbótico"""
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
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        self.skin_path = skin_folder
        self.is_dragging = False
        self.current_state = "idle"
        self.current_frame = 0
        self.current_move_speed = 0
        self.current_y_speed = 0

        # Cargar configuración
        try:
            with open(os.path.join(self.skin_path, "config.json"), "r") as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"Error cargando config.json: {e}")
            sys.exit(1)
            
        self.base_height = self.config.get("base_height", 255)
        # El canvas es fijo y un 30% más grande para evitar 'jitter' al escalar
        self.canvas_size = int(self.base_height * 1.3) 
        self.setFixedSize(self.canvas_size, self.canvas_size)
        
        self.bubble = SpeechBubble()
        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.update_animation)
        
        self.ai_timer = QTimer()
        self.ai_timer.timeout.connect(self.ai_think)
        self.ai_timer.start(4000)
        
        self.load_animation(self.current_state)
        # Forzar renderizado inicial para posicionar correctamente
        self.update_animation()
        self.set_initial_position()
        self.show()

    def set_initial_position(self):
        """Ubica al robot en el límite inferior al inicio"""
        screen = QApplication.primaryScreen().geometry()
        env = self.config.get("environment", {})
        y_max_pc = env.get("walkable_y_max_pc", 100) / 100
        
        y_pos = int((screen.height() * y_max_pc) - self.height())
        x_pos = int((screen.width() - self.width()) // 2)
        self.move(x_pos, y_pos)

    def update_scale(self):
        """Calcula escala LERP basada en posición Y y modo"""
        env = self.config.get("environment", {})
        
        # Si el modo no es perspective, no escala
        if env.get("mode") != "perspective":
            return self.base_height

        screen_h = QApplication.primaryScreen().geometry().height()
        y_min = int((env.get("walkable_y_min_pc", 0) / 100) * screen_h)
        y_max = int((env.get("walkable_y_max_pc", 100) / 100) * screen_h - self.height())
        
        if y_max <= y_min: return self.base_height

        min_scale = env.get("min_scale_percent", 60) / 100
        
        # t: 0.0 arriba (lejos), 1.0 abajo (cerca)
        t = (self.y() - y_min) / (y_max - y_min)
        t = max(0.0, min(float(t), 1.0))
        
        return int(self.base_height * (min_scale + t * (1.0 - min_scale)))

    def check_screen_bounds(self):
        """Límites de pantalla y rebotes"""
        env = self.config.get("environment", {})
        mode = env.get("mode", "perspective")
        screen = QApplication.primaryScreen().geometry()
        margin = 10
        
        y_min = int((env.get("walkable_y_min_pc", 0) / 100) * screen.height())
        y_max = int((env.get("walkable_y_max_pc", 100) / 100) * screen.height() - self.height())

        if mode == "floor":
            self.move(self.x(), y_max)
            self.current_y_speed = 0
        else:
            if self.y() < y_min: self.current_y_speed = abs(self.current_y_speed or 2)
            elif self.y() > y_max: self.current_y_speed = -abs(self.current_y_speed or 2)

        if self.x() < margin:
            self.current_move_speed = abs(self.current_move_speed or 2)
            self.change_state("look_r")
        elif self.x() > screen.width() - self.width() - margin:
            self.current_move_speed = -abs(self.current_move_speed or 2)
            self.change_state("look_l")

    def load_animation(self, state):
        anim_data = self.config["animations"].get(state, self.config["animations"]["idle"])
        self.full_sheet = QPixmap(os.path.join(self.skin_path, anim_data["file"]))
        self.cols = anim_data["cols"]
        self.current_move_speed = anim_data.get("move_speed", 0)
        self.frame_w = self.full_sheet.width() // self.cols
        self.frame_h = self.full_sheet.height()
        self.current_frame = 0
        self.anim_timer.start(anim_data.get("speed", 150))

    def update_animation(self):
        if not self.is_dragging:
            self.check_screen_bounds()
            self.move(int(self.x() + self.current_move_speed), int(self.y() + self.current_y_speed))

        # Calcular nueva altura y ancho proporcional
        target_h = self.update_scale()
        target_w = int(target_h * (self.frame_w / self.frame_h))

        # Extraer frame del spritesheet
        x_src = self.current_frame * self.frame_w
        rect_src = QRect(x_src, 0, self.frame_w, self.frame_h)
        pix_frame = self.full_sheet.copy(rect_src).scaled(
            target_w, target_h, 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )
        
        # Dibujar sobre lienzo transparente centrado
        canvas = QPixmap(self.canvas_size, self.canvas_size)
        canvas.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(canvas)
        painter.drawPixmap(
            int((self.canvas_size - target_w) / 2), 
            int((self.canvas_size - target_h) / 2), 
            pix_frame
        )
        painter.end()

        self.label.setPixmap(canvas)
        self.label.setFixedSize(self.canvas_size, self.canvas_size)
        self.current_frame = (self.current_frame + 1) % self.cols
        
        # Seguir con el bocadillo
        if self.bubble.isVisible():
            self.bubble.move(self.x() + (self.width()//2) - (self.bubble.width()//2), self.y() - 40)

    def ai_think(self):
        if self.is_dragging: return
        dice = random.randint(1, 100)
        if dice <= 40:
            self.change_state("idle")
            self.current_y_speed = 0
        elif dice <= 85:
            self.change_state(random.choice(["look_l", "look_r"]))
            self.current_y_speed = random.choice([-2, 0, 2])
        else:
            self.change_state("sleep")
            self.current_y_speed = 0

    def change_state(self, new_state):
        if self.current_state != new_state:
            self.current_state = new_state
            self.load_animation(new_state)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self.offset = event.position().toPoint()
            self.change_state("drag_id")

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            self.move(event.globalPosition().toPoint() - self.offset)
            if self.current_state != "drag_mv": self.change_state("drag_mv")

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
            self.change_state("idle")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Ruta basada en el directorio de ejecución
    path = os.path.join(os.getcwd(), "assets/skins/default")
    pet = CyberPet(path)
    sys.exit(app.exec())