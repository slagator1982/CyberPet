import sys
import os
import json
import random
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow
from PyQt6.QtCore import QTimer, Qt, QRect, QPoint, QSize
from PyQt6.QtGui import QPixmap, QColor, QPainter

class CyberPet(QMainWindow):
    def __init__(self, skin_folder):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.label = QLabel(self)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        
        self.skin_path = os.path.abspath(skin_folder)
        self.is_dragging = False
        self.is_falling = False       
        self.grab_y = 0               
        self.real_sprite_size = QSize(0, 0)
        self.last_mouse_pos = QPoint(0, 0)
        self.vel_x = 0.0              
        self.vel_y = 0.0              

        try:
            config_file = os.path.join(self.skin_path, "config.json")
            with open(config_file, "r") as f:
                self.config = json.load(f)
        except Exception as e:
            sys.stdout.write(f"\n[ERROR] JSON: {e}\n")
            sys.exit(1)
            
        self.base_height = self.config.get("base_height", 250)
        self.launch_mult = self.config.get("launch_multiplier", 0.8)
        self.friction = self.config.get("friction", 0.95)
        self.gravity_factor = self.config.get("gravity", 1.2)
        
        self.locked_scale = self.base_height 
        self.canvas_size_val = int(self.base_height * 2.0)
        self.setFixedSize(self.canvas_size_val, self.canvas_size_val)
        
        self.current_state = "idle"
        self.current_frame = 0
        self.current_move_speed = 0

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
            self.full_sheet.fill(QColor(255, 0, 255, 180))
            self.cols = 1
        else:
            self.cols = anim_data["cols"]

        self.gravity_factor = anim_data.get("gravity", self.config.get("gravity", 1.2))
        self.current_move_speed = anim_data.get("move_speed", 0)
        self.frame_w = self.full_sheet.width() // self.cols
        self.frame_h = self.full_sheet.height()
        self.current_frame = 0
        self.anim_timer.start(anim_data.get("speed", 150))

    def update_animation(self):
        # Físicas
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
            self.move(int(self.x() + self.current_move_speed), self.y())

        # Renderizado (Lógica restaurada que funcionaba)
        new_h = self.update_scale()
        new_w = int(new_h * (self.frame_w / self.frame_h))
        self.real_sprite_size = QSize(new_w, new_h)

        x_offset = self.current_frame * self.frame_w
        pix = self.full_sheet.copy(QRect(x_offset, 0, self.frame_w, self.frame_h)).scaled(
            new_w, new_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        
        canvas = QPixmap(self.width(), self.height())
        canvas.fill(Qt.GlobalColor.transparent)
        p = QPainter(canvas)
        p.drawPixmap((self.width() - new_w)//2, (self.height() - new_h)//2, pix)
        p.end()
        
        self.label.setPixmap(canvas)
        self.label.setGeometry(0, 0, self.width(), self.height())
        self.setMask(canvas.mask())
        
        # Barra de Debug (Corregida para que sea fija y no se repita)
        debug_info = (
            f"ESTADO: {self.current_state.upper()} | "
            f"POS: {self.x()},{self.y()} | "
            f"SPRITE: {new_w}x{new_h} | "
            f"VEL: x:{self.vel_x:.1f}, y:{self.vel_y:.1f} | "
            f"G:{self.gravity_factor} F:{self.friction} L:{self.launch_mult}"
        )
        sys.stdout.write(f"\r\033[2K{debug_info}")
        sys.stdout.flush()
        
        self.current_frame = (self.current_frame + 1) % self.cols

    def check_screen_bounds(self):
        screen = QApplication.primaryScreen().availableGeometry()
        offset_x = (self.width() - self.real_sprite_size.width()) // 2
        actual_left = self.x() + offset_x
        actual_right = actual_left + self.real_sprite_size.width()

        if actual_left < screen.left():
            self.move(screen.left() - offset_x, self.y())
            self.vel_x = abs(self.vel_x) * 0.6
            if not self.is_falling: self.change_state("look_r")
        elif actual_right > screen.right():
            self.move(screen.right() - self.real_sprite_size.width() - offset_x, self.y())
            self.vel_x = -abs(self.vel_x) * 0.6
            if not self.is_falling: self.change_state("look_l")

    def change_state(self, new_state):
        if self.current_state != new_state:
            self.current_state = new_state
            self.load_animation(new_state)

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
            if self.y() > self.grab_y: self.grab_y = self.y()
            if self.current_state != "drag_mv": self.change_state("drag_mv")

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.is_dragging = False
            if self.y() < self.grab_y - 10 or abs(self.vel_y) > 2:
                self.is_falling = True
                self.change_state("fall")
            else:
                self.vel_x = 0; self.vel_y = 0; self.change_state("idle")

    def update_scale(self):
        if self.is_falling: return self.locked_scale
        if self.is_dragging:
            if self.y() < self.grab_y: return self.locked_scale
        env = self.config.get("environment", {})
        if env.get("mode") != "perspective": return self.base_height
        screen = QApplication.primaryScreen().availableGeometry()
        y_min = int((env.get("walkable_y_min_pc", 0) / 100) * screen.height())
        y_max = int((env.get("walkable_y_max_pc", 100) / 100) * screen.height() - self.base_height)
        t = max(0.0, min((self.y() - y_min) / (y_max - y_min), 1.0))
        min_f = env.get("min_scale_percent", 30) / 100
        return int(self.base_height * (min_f + (t * (1.0 - min_f))))

    def set_initial_position(self):
        screen = QApplication.primaryScreen().availableGeometry()
        env = self.config.get("environment", {})
        y_max_pc = env.get("walkable_y_max_pc", 100) / 100
        y_pos = int((screen.height() * y_max_pc) - self.base_height)
        self.move((screen.width() - self.width()) // 2, y_pos)
        self.grab_y = y_pos 

    def ai_think(self):
        if self.is_dragging or self.is_falling: return
        d = random.randint(1, 100)
        if d <= 40: self.change_state("idle")
        elif d <= 85: self.change_state(random.choice(["look_l", "look_r"]))
        else: self.change_state("angry")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_dir = os.path.dirname(os.path.abspath(__file__))
    skin_path = os.path.abspath(os.path.join(main_dir, "..", "assets", "skins", "default"))
    pet = CyberPet(skin_path)
    sys.exit(app.exec())