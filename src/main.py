import sys
import os
import json
import random
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QWidget, QVBoxLayout
from PyQt6.QtCore import QTimer, Qt, QRect, QPoint
from PyQt6.QtGui import QPixmap, QFont, QPalette, QColor, QPainter

class SpeechBubble(QWidget):
    """Bocadillo de texto para comunicación del robot"""
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
        # Configuración de ventana: siempre encima y transparente
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.label = QLabel(self)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        self.skin_path = skin_folder
        self.is_dragging = False
        self.is_falling = False       # Estado de caída física
        self.grab_y = 0               # Altura del suelo donde se recogió
        self.locked_scale = 250       # Escala congelada durante el vuelo
        
        # Variables para inercia (lanzamiento)
        self.last_mouse_pos = QPoint(0, 0)
        self.inertia_x = 0

        self.current_state = "idle"
        self.current_frame = 0
        self.current_move_speed = 0
        self.current_y_speed = 0

        # Carga de configuración
        try:
            with open(os.path.join(self.skin_path, "config.json"), "r") as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
            
        self.base_height = self.config.get("base_height", 250)
        self.canvas_size_val = int(self.base_height * 1.5)
        self.setFixedSize(self.canvas_size_val, self.canvas_size_val)
        
        self.bubble = SpeechBubble()
        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.update_animation)
        
        self.ai_timer = QTimer()
        self.ai_timer.timeout.connect(self.ai_think)
        self.ai_timer.start(4000)
        
        self.load_animation(self.current_state)
        self.set_initial_position()
        self.show()

    def set_initial_position(self):
        """Posiciona al bot en el suelo inicial"""
        screen = QApplication.primaryScreen().geometry()
        env = self.config.get("environment", {})
        y_max_pc = env.get("walkable_y_max_pc", 100) / 100
        y_pos = int((screen.height() * y_max_pc) - self.height())
        x_pos = int((screen.width() - self.width()) // 2)
        self.move(x_pos, y_pos)

    def update_scale(self):
        """Calcula el tamaño según profundidad (PERSPECTIVA)"""
        if self.is_dragging or self.is_falling:
            return self.locked_scale

        env = self.config.get("environment", {})
        if env.get("mode") != "perspective":
            return self.base_height

        screen_h = QApplication.primaryScreen().geometry().height()
        y_min = int((env.get("walkable_y_min_pc", 0) / 100) * screen_h)
        y_max = int((env.get("walkable_y_max_pc", 100) / 100) * screen_h - self.height())
        
        if y_max <= y_min: return self.base_height

        min_scale = env.get("min_scale_percent", 30) / 100
        t = (self.y() - y_min) / (y_max - y_min)
        t = max(0.0, min(float(t), 1.0))
        
        return int(self.base_height * (min_scale + (t * (1.0 - min_scale))))

    def check_screen_bounds(self):
        """Control de colisiones y rebotes"""
        env = self.config.get("environment", {})
        screen = QApplication.primaryScreen().geometry()
        margin = 10
        y_min = int((env.get("walkable_y_min_pc", 0) / 100) * screen.height())
        y_max = int((env.get("walkable_y_max_pc", 100) / 100) * screen.height() - self.height())

        # Rebote Y
        if self.y() < y_min: self.current_y_speed = abs(self.current_y_speed or 2)
        elif self.y() > y_max: self.current_y_speed = -abs(self.current_y_speed or 2)

        # Rebote X (afecta a move_speed o a la inercia)
        if self.x() < margin:
            if self.is_falling: self.inertia_x = abs(self.inertia_x)
            self.current_move_speed = abs(self.current_move_speed or 2)
            if not self.is_falling: self.change_state("look_r")
        elif self.x() > screen.width() - self.width() - margin:
            if self.is_falling: self.inertia_x = -abs(self.inertia_x)
            self.current_move_speed = -abs(self.current_move_speed or 2)
            if not self.is_falling: self.change_state("look_l")

    def load_animation(self, state):
        """Carga frames y velocidades del JSON"""
        anim_data = self.config["animations"].get(state, self.config["animations"]["idle"])
        self.full_sheet = QPixmap(os.path.join(self.skin_path, anim_data["file"]))
        self.cols = anim_data["cols"]
        self.current_move_speed = anim_data.get("move_speed", 0)
        
        # Uso unificado de move_speed_y para la caída
        if "move_speed_y" in anim_data:
            self.current_y_speed = anim_data["move_speed_y"]
            
        self.frame_w = self.full_sheet.width() // self.cols
        self.frame_h = self.full_sheet.height()
        self.current_frame = 0
        self.anim_timer.start(anim_data.get("speed", 150))

    def update_animation(self):
        """Bucle principal: físicas y renderizado"""
        if self.is_falling:
            # Física de proyectil: Caída vertical + Inercia horizontal
            new_y = self.y() + self.current_y_speed
            new_x = self.x() + self.inertia_x
            
            # Fricción del aire (reduce velocidad X poco a poco)
            self.inertia_x *= 0.96 
            
            # Aterrizaje
            if new_y >= self.grab_y:
                new_y = self.grab_y
                self.is_falling = False
                self.inertia_x = 0
                self.change_state("idle")
            
            self.move(int(new_x), int(new_y))
            self.check_screen_bounds() # Rebota en paredes mientras cae
            
        elif not self.is_dragging:
            self.check_screen_bounds()
            self.move(int(self.x() + self.current_move_speed), int(self.y() + self.current_y_speed))

        # Dibujado del frame escalado
        new_h = self.update_scale()
        new_w = int(new_h * (self.frame_w / self.frame_h))
        x_offset_sheet = self.current_frame * self.frame_w
        rect = QRect(x_offset_sheet, 0, self.frame_w, self.frame_h)
        frame_pix = self.full_sheet.copy(rect).scaled(new_w, new_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        canvas = QPixmap(self.canvas_size_val, self.canvas_size_val)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.drawPixmap(int((self.canvas_size_val - new_w) / 2), int((self.canvas_size_val - new_h) / 2), frame_pix)
        painter.end()

        self.label.setPixmap(canvas)
        self.label.setFixedSize(self.canvas_size_val, self.canvas_size_val) # Fija tamaño para evitar parpadeos
        self.current_frame = (self.current_frame + 1) % self.cols

    def ai_think(self):
        """Comportamiento autónomo"""
        if self.is_dragging or self.is_falling: return
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
            if not self.is_falling:
                self.locked_scale = self.update_scale()
                self.grab_y = self.y() # Recordar dónde estaba el suelo

            self.is_dragging = True
            self.is_falling = False
            self.raise_() # Traer al frente
            self.offset = event.position().toPoint()
            self.last_mouse_pos = event.globalPosition().toPoint()
            self.change_state("drag_id")

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            current_pos = event.globalPosition().toPoint()
            # Cálculo de velocidad de arrastre para la inercia
            self.inertia_x = current_pos.x() - self.last_mouse_pos.x()
            self.last_mouse_pos = current_pos
            
            self.move(current_pos - self.offset)
            if self.current_state != "drag_mv": self.change_state("drag_mv")

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
            # Activar caída si está por encima del nivel del suelo
            if self.y() < self.grab_y:
                self.is_falling = True
                self.change_state("fall")
            else:
                self.inertia_x = 0
                self.change_state("idle")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    path = os.path.join(os.getcwd(), "assets/skins/default")
    pet = CyberPet(path)
    sys.exit(app.exec())