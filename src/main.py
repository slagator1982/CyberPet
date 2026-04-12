import sys
import os
import json
import random
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QWidget, QVBoxLayout
from PyQt6.QtCore import QTimer, Qt, QRect, QPoint, QSize
from PyQt6.QtGui import QPixmap, QFont, QPalette, QColor, QPainter

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
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        self.skin_path = skin_folder
        self.is_dragging = False
        self.current_state = "idle"
        self.current_frame = 0
        self.current_move_speed = 0
        self.current_y_speed = 0

        # Cargar configuración segura
        try:
            with open(os.path.join(self.skin_path, "config.json"), "r") as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"Error cargando config: {e}")
            sys.exit(1)
            
        self.base_height = self.config.get("base_height", 255)
        # El canvas es fijo y grande para evitar que el escalado mueva la ventana
        self.canvas_size = int(self.base_height * 1.3) 
        self.setFixedSize(self.canvas_size, self.canvas_size)
        
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
        screen = QApplication.primaryScreen().geometry()
        env = self.config.get("environment", {})
        y_max_pc = env.get("walkable_y_max_pc", 100) / 100
        # Empezar abajo en el centro
        y_pos = int((screen.height() * y_max_pc) - self.height())
        x_pos = int((screen.width() - self.width()) // 2)
        self.move(x_pos, y_pos)

   def update_scale(self):
        """
        Calcula el tamaño del robot basado en su posición Y dentro del pasillo configurable.
        Utiliza una interpolación lineal (LERP).
        """
        env = self.config.get("environment", {})
        
        # Si el modo no es perspectiva, devolvemos el tamaño original (100%)
        if env.get("mode") != "perspective":
            return self.base_height

        # 1. Obtener dimensiones de pantalla y configuración
        screen_h = QApplication.primaryScreen().geometry().height()
        y_min_pc = env.get("walkable_y_min_pc", 0) / 100
        y_max_pc = env.get("walkable_y_max_pc", 100) / 100
        min_scale_factor = env.get("min_scale_percent", 60) / 100

        # 2. Convertir porcentajes a píxeles reales de pantalla
        y_min_px = int(screen_h * y_min_pc)
        y_max_px = int(screen_h * y_max_pc) - self.height()
        
        # Seguridad: evitar división por cero si los límites son iguales
        if y_max_px <= y_min_px: 
            return self.base_height

        # 3. Calcular 't' (factor de posición entre 0.0 y 1.0)
        # 0.0 = límite superior (más lejos)
        # 1.0 = límite inferior (más cerca)
        current_y = self.y()
        t = (current_y - y_min_px) / (y_max_px - y_min_px)
        t = max(0.0, min(float(t), 1.0)) # Aseguramos que t no se salga del rango

        # 4. Interpolación Lineal (LERP)
        # Escala = Mínimo + (Diferencia * t)
        scale_factor = min_scale_factor + (t * (1.0 - min_scale_factor))
        
        return int(self.base_height * scale_factor)

    def check_screen_bounds(self):
        env = self.config.get("environment", {})
        mode = env.get("mode", "perspective")
        screen = QApplication.primaryScreen().geometry()
        margin = 10
        
        y_min = int((env.get("walkable_y_min_pc", 0) / 100) * screen.height())
        y_max = int((env.get("walkable_y_max_pc", 100) / 100) * screen.height() - self.height())

        # Rebote vertical
        if mode == "floor":
            self.move(self.x(), y_max)
            self.current_y_speed = 0
        else:
            if self.y() < y_min: self.current_y_speed = abs(self.current_y_speed or 2)
            elif self.y() > y_max: self.current_y_speed = -abs(self.current_y_speed or 2)

        # Rebote horizontal
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
            # Mover siempre con enteros
            self.move(int(self.x() + self.current_move_speed), int(self.y() + self.current_y_speed))

        target_h = self.update_scale()
        # Escalar manteniendo la proporción real del frame
        target_w = int(target_h * (self.frame_w / self.frame_h))

        # Extraer frame
        x_src = self.current_frame * self.frame_w
        rect_src = QRect(x_src, 0, self.frame_w, self.frame_h)
        pix_frame = self.full_sheet.copy(rect_src).scaled(
            target_w, target_h, 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )
        
        # Dibujar en el centro del canvas estático para evitar "temblores"
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
        self.is_dragging = False
        self.change_state("idle")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    path = os.path.join(os.getcwd(), "assets/skins/default")
    pet = CyberPet(path)
    sys.exit(app.exec())