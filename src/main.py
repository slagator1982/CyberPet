import sys
import os
import json
import random
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QWidget, QVBoxLayout
from PyQt6.QtCore import QTimer, Qt, QRect, QPoint
from PyQt6.QtGui import QPixmap, QFont, QPalette, QColor, QPainter, QCursor

class CyberPet(QMainWindow):
    def __init__(self, skin_folder):
        super().__init__()
        # 1. Configuración de ventana (Transparencia crítica)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # El Label es el contenedor del dibujo
        self.label = QLabel(self)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        self.skin_path = os.path.abspath(skin_folder) # Ruta absoluta para evitar fallos
        self.is_dragging = False
        self.is_falling = False       
        self.grab_y = 0               
        
        # Física básica
        self.last_mouse_pos = QPoint(0, 0)
        self.vel_x = 0.0              
        self.vel_y = 0.0              
        self.gravity_factor = 1.0     
        self.friction = 0.97          
        self.launch_mult = 1.5        

        self.current_state = "idle"
        self.current_frame = 0
        self.current_move_speed = 0
        self.current_y_speed = 0

        # Carga de configuración
        try:
            config_file = os.path.join(self.skin_path, "config.json")
            with open(config_file, "r") as f:
                self.config = json.load(f)
            print(f"JSON cargado correctamente desde: {config_file}")
        except Exception as e:
            print(f"ERROR CRÍTICO: No se pudo cargar el JSON: {e}")
            sys.exit(1)
            
        self.base_height = self.config.get("base_height", 250)
        self.locked_scale = self.base_height 
        # El canvas debe ser suficientemente grande para el escalado
        self.canvas_size_val = int(self.base_height * 2.0)
        self.setFixedSize(self.canvas_size_val, self.canvas_size_val)
        
        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.update_animation)
        
        self.ai_timer = QTimer()
        self.ai_timer.timeout.connect(self.ai_think)
        self.ai_timer.start(4000)
        
        self.load_animation(self.current_state)
        self.set_initial_position()
        self.show()

    def load_animation(self, state):
        anim_data = self.config["animations"].get(state, self.config["animations"]["idle"])
        img_path = os.path.join(self.skin_path, anim_data["file"])
        self.full_sheet = QPixmap(img_path)
        
        if self.full_sheet.isNull():
            self.full_sheet = QPixmap(100, 100)
            self.full_sheet.fill(QColor("magenta"))
            self.cols = 1
        else:
            self.cols = anim_data["cols"]

        # LÓGICA DE HERENCIA:
        # 1. Mira si la animación tiene gravedad propia.
        # 2. Si no, mira si hay una gravedad general en el JSON.
        # 3. Si no hay nada, usa 0.8 por defecto.
        self.gravity_factor = anim_data.get("gravity", self.config.get("gravity", 0.8))
        
        # También podemos hacer lo mismo con el rozamiento si quisieras
        self.friction = anim_data.get("friction", self.config.get("friction", 0.97))

        self.current_move_speed = anim_data.get("move_speed", 0)
        self.frame_w = self.full_sheet.width() // self.cols
        self.frame_h = self.full_sheet.height()
        self.current_frame = 0
        self.anim_timer.start(anim_data.get("speed", 150))

    def update_animation(self):
        # Lógica de física (se mantiene igual)
        if self.is_falling:
            self.vel_y += self.gravity_factor
            self.vel_x *= self.friction
            new_x = self.x() + self.vel_x
            new_y = self.y() + self.vel_y
            if new_y >= self.grab_y and self.vel_y > 0:
                new_y = self.grab_y
                self.is_falling = False; self.vel_x = 0; self.vel_y = 0
                self.change_state("idle")
            self.move(int(new_x), int(new_y))
            self.check_screen_bounds()
        elif not self.is_dragging:
            self.check_screen_bounds()
            self.move(int(self.x() + self.current_move_speed), int(self.y() + self.current_y_speed))

        # --- RENDERIZADO CORREGIDO ---
        new_h = self.update_scale()
        new_w = int(new_h * (self.frame_w / self.frame_h))
        
        # 1. Extraer el frame actual
        x_offset = self.current_frame * self.frame_w
        frame_rect = QRect(x_offset, 0, self.frame_w, self.frame_h)
        pix = self.full_sheet.copy(frame_rect).scaled(
            new_w, new_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        
        # 2. Dibujar sobre un canvas transparente del tamaño de la ventana completa
        canvas = QPixmap(self.width(), self.height())
        canvas.fill(Qt.GlobalColor.transparent)
        
        p = QPainter(canvas)
        # Dibujamos en el centro de la ventana
        draw_x = (self.width() - new_w) // 2
        draw_y = (self.height() - new_h) // 2
        p.drawPixmap(draw_x, draw_y, pix)
        p.end()
        
        self.label.setPixmap(canvas)
        self.label.setGeometry(0, 0, self.width(), self.height())
        self.current_frame = (self.current_frame + 1) % self.cols

    def change_state(self, new_state):
        if self.current_state != new_state:
            self.current_state = new_state
            self.load_animation(new_state)

    def update_scale(self):
        if self.is_dragging or self.is_falling: return self.locked_scale
        env = self.config.get("environment", {})
        if env.get("mode") != "perspective": return self.base_height
        screen_h = QApplication.primaryScreen().geometry().height()
        y_min = int((env.get("walkable_y_min_pc", 0) / 100) * screen_h)
        y_max = int((env.get("walkable_y_max_pc", 100) / 100) * screen_h - self.base_height)
        if y_max <= y_min: return self.base_height
        t = (self.y() - y_min) / (y_max - y_min)
        t = max(0.0, min(float(t), 1.0))
        min_f = env.get("min_scale_percent", 30) / 100
        return int(self.base_height * (min_f + (t * (1.0 - min_f))))

    def check_screen_bounds(self):
        screen = QApplication.primaryScreen().geometry()
        margin = 10
        if self.x() < margin:
            self.vel_x = abs(self.vel_x) * 0.7 
            self.current_move_speed = abs(self.current_move_speed or 2)
        elif self.x() > screen.width() - self.width() - margin:
            self.vel_x = -abs(self.vel_x) * 0.7
            self.current_move_speed = -abs(self.current_move_speed or 2)

    def set_initial_position(self):
        screen = QApplication.primaryScreen().geometry()
        env = self.config.get("environment", {})
        y_max_pc = env.get("walkable_y_max_pc", 100) / 100
        y_pos = int((screen.height() * y_max_pc) - self.base_height)
        x_pos = int((screen.width() - self.width()) // 2)
        self.move(x_pos, y_pos)
        self.grab_y = y_pos 

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.locked_scale = self.update_scale()
            if not self.is_falling: self.grab_y = self.y() 
            self.is_dragging = True
            self.is_falling = False
            self.raise_()
            self.offset = event.position().toPoint()
            self.last_mouse_pos = event.globalPosition().toPoint()
            self.change_state("drag_id")

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            curr = event.globalPosition().toPoint()
            self.vel_x = (curr.x() - self.last_mouse_pos.x()) * self.launch_mult
            self.vel_y = (curr.y() - self.last_mouse_pos.y()) * self.launch_mult
            self.last_mouse_pos = curr
            self.move(curr - self.offset)
            if self.current_state != "drag_mv": self.change_state("drag_mv")

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.is_dragging = False
            if self.y() < self.grab_y - 5 or abs(self.vel_y) > 3:
                self.is_falling = True; self.change_state("fall")
            else:
                self.vel_x = 0; self.vel_y = 0; self.change_state("idle")

    def ai_think(self):
        if self.is_dragging or self.is_falling: return
        d = random.randint(1, 100)
        if d <= 40: self.change_state("idle")
        elif d <= 85: self.change_state(random.choice(["look_l", "look_r"]))
        else: self.change_state("angry")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Buscamos la carpeta assets/skins/default
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Si main.py está en src/, subimos un nivel
    skin_dir = os.path.join(current_dir, "..", "assets", "skins", "default")
    pet = CyberPet(skin_dir)
    sys.exit(app.exec())