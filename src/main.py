import sys
import os
import json
import random
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QWidget, QVBoxLayout
from PyQt6.QtCore import QTimer, Qt, QRect, QPoint, QSize
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
        # Mantener siempre encima y sin bordes
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.label = QLabel(self)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        self.skin_path = skin_folder
        self.is_dragging = False
        self.is_falling = False       # NUEVO: Estado de caída
        self.grab_y = 0               # NUEVO: Memoria del suelo
        self.locked_scale = 255       # NUEVO: Memoria del tamaño
        
        self.current_state = "idle"
        self.current_frame = 0
        self.current_move_speed = 0
        self.current_y_speed = 0

        # Cargar configuración desde JSON
        try:
            with open(os.path.join(self.skin_path, "config.json"), "r") as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"Error crítico cargando JSON: {e}")
            sys.exit(1)
            
        self.base_height = self.config.get("base_height", 255)
        # Lienzo fijo para evitar vibraciones al escalar
        self.canvas_size = int(self.base_height * 1.3) 
        self.setFixedSize(self.canvas_size, self.canvas_size)
        
        self.bubble = SpeechBubble()
        
        # Timer principal de animación
        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.update_animation)
        
        # Timer de IA para toma de decisiones
        self.ai_timer = QTimer()
        self.ai_timer.timeout.connect(self.ai_think)
        self.ai_timer.start(4000)
        
        self.load_animation(self.current_state)
        # Renderizado inicial para establecer dimensiones
        self.update_animation()
        self.set_initial_position()
        self.show()

    def set_initial_position(self):
        """Ubica al robot en el límite inferior configurado al arrancar"""
        screen = QApplication.primaryScreen().geometry()
        env = self.config.get("environment", {})
        y_max_pc = env.get("walkable_y_max_pc", 100) / 100
        
        y_pos = int((screen.height() * y_max_pc) - self.height())
        x_pos = int((screen.width() - self.width()) // 2)
        self.move(x_pos, y_pos)

    def update_scale(self):
        """Calcula la escala LERP según la posición vertical"""
        # NUEVO: Si está agarrado o cayendo, devolver la escala bloqueada
        if self.is_dragging or self.is_falling:
            return self.locked_scale

        env = self.config.get("environment", {})
        
        if env.get("mode") != "perspective":
            return self.base_height

        screen_h = QApplication.primaryScreen().geometry().height()
        y_min = int((env.get("walkable_y_min_pc", 0) / 100) * screen_h)
        y_max = int((env.get("walkable_y_max_pc", 100) / 100) * screen_h - self.height())
        
        if y_max <= y_min: return self.base_height

        min_scale = env.get("min_scale_percent", 60) / 100
        
        # t: posición relativa de 0.0 (lejos) a 1.0 (cerca)
        t = (self.y() - y_min) / (y_max - y_min)
        t = max(0.0, min(float(t), 1.0))
        
        return int(self.base_height * (min_scale + t * (1.0 - min_scale)))

    def check_screen_bounds(self):
        """Gestiona colisiones y rebotes con los bordes"""
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

        # Rebote horizontal
        if self.x() < margin:
            self.current_move_speed = abs(self.current_move_speed or 2)
            self.change_state("look_r")
        elif self.x() > screen.width() - self.width() - margin:
            self.current_move_speed = -abs(self.current_move_speed or 2)
            self.change_state("look_l")

    def load_animation(self, state):
        """Carga el spritesheet correspondiente al estado"""
        anim_data = self.config["animations"].get(state, self.config["animations"]["idle"])
        self.full_sheet = QPixmap(os.path.join(self.skin_path, anim_data["file"]))
        self.cols = anim_data["cols"]
        self.current_move_speed = anim_data.get("move_speed", 0)
        self.frame_w = self.full_sheet.width() // self.cols
        self.frame_h = self.full_sheet.height()
        self.current_frame = 0
        self.anim_timer.start(anim_data.get("speed", 150))

    def update_animation(self):
        """Ciclo principal de físicas y dibujado"""
        # --- NUEVAS FÍSICAS DE CAÍDA ---
        if self.is_falling:
            # Cae varios píxeles por frame para simular gravedad rápida
            new_y = self.y() + 35 
            
            # Si cruza la línea del suelo original, aterriza
            if new_y >= self.grab_y:
                new_y = self.grab_y
                self.is_falling = False
                self.change_state("idle")
            
            self.move(self.x(), new_y)
            
        elif not self.is_dragging:
            self.check_screen_bounds()
            self.move(int(self.x() + self.current_move_speed), int(self.y() + self.current_y_speed))

        # --- DIBUJADO Y ESCALADO ---
        target_h = self.update_scale()
        target_w = int(target_h * (self.frame_w / self.frame_h))

        x_src = self.current_frame * self.frame_w
        rect_src = QRect(x_src, 0, self.frame_w, self.frame_h)
        pix_frame = self.full_sheet.copy(rect_src).scaled(
            target_w, target_h, 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )
        
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
        
        if self.bubble.isVisible():
            self.bubble.move(self.x() + (self.width()//2) - (self.bubble.width()//2), self.y() - 40)

    def ai_think(self):
        """Lógica de comportamiento aleatorio"""
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
            # NUEVO: Guardar escala y posición del suelo antes de levantarlo
            # (Si lo pillas al vuelo mientras cae, mantiene el suelo original)
            if not self.is_falling:
                self.locked_scale = self.update_scale()
                self.grab_y = self.y()

            self.is_dragging = True
            self.is_falling = False # Detiene la caída si lo coges en el aire
            
            self.raise_()
            if self.bubble.isVisible(): self.bubble.raise_()
            
            self.offset = event.position().toPoint()
            self.change_state("drag_id")

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            self.move(event.globalPosition().toPoint() - self.offset)
            if self.current_state != "drag_mv": self.change_state("drag_mv")
            if self.bubble.isVisible(): self.bubble.raise_()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
            
            # NUEVO: Física de caída al soltar
            if self.y() < self.grab_y:
                # Si lo soltaste más alto que el suelo original, cae
                self.is_falling = True
                self.change_state("drag_mv")
            else:
                # Si lo arrastraste hacia abajo (por debajo de su suelo),
                # se considera que lo has posado en una nueva zona más cercana.
                self.change_state("idle")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    path = os.path.join(os.getcwd(), "assets/skins/default")
    pet = CyberPet(path)
    sys.exit(app.exec())