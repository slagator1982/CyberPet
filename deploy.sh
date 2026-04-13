#!/bin/bash

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Iniciando despliegue y limpieza del proyecto...${NC}"

# --- 1. LIMPIEZA DE BASURA ---
# Borramos archivos temporales de Python y posibles restos de la estructura antigua
echo "Borrando archivos innecesarios..."
rm -f src/*.py             # Borra versiones viejas de los scripts en src
rm -rf src/__pycache__      # Borra el caché de Python
rm -f start.sh             # Borra el lanzador viejo para renovarlo
# No borramos assets/ para no perder tus imágenes, solo nos aseguramos de que exista
mkdir -p assets/skins/default
mkdir -p src

# --- 2. SETTINGS.PY ---
cat <<EOF > src/settings.py
import json
import os

class Settings:
    """Maneja la carga y lectura del archivo config.json de la skin."""
    def __init__(self, skin_path):
        self.skin_path = os.path.abspath(skin_path)
        self.config = self._load_config()

    def _load_config(self):
        path = os.path.join(self.skin_path, "config.json")
        if not os.path.exists(path):
            raise FileNotFoundError(f"No se encuentra config.json en {path}")
        with open(path, "r") as f:
            return json.load(f)

    def get_anim(self, state):
        """Devuelve el diccionario de datos de una animación específica."""
        return self.config["animations"].get(state, self.config["animations"]["idle"])

    def get_global(self, key, default):
        """Obtiene un valor global del JSON."""
        return self.config.get(key, default)
EOF

# --- 3. PHYSICS.PY ---
cat <<EOF > src/physics.py
class PhysicsEngine:
    """Motor de físicas: gravedad, fricción y colisiones."""
    def __init__(self, settings):
        self.settings = settings
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.is_falling = False
        self.grab_y = 0 # El suelo lógico

    def apply_gravity(self, gravity):
        self.vel_y += gravity

    def apply_friction(self, friction):
        self.vel_x *= friction

    def check_bounds(self, x, y, sprite_w, window_w, screen_rect):
        """Ajusta la posición para que el sprite no se salga de la pantalla."""
        offset_x = (window_w - sprite_w) // 2
        actual_left = x + offset_x
        actual_right = actual_left + sprite_w
        
        new_x = x
        hit = None

        if actual_left < screen_rect.left():
            new_x = screen_rect.left() - offset_x
            self.vel_x = abs(self.vel_x) * 0.6
            hit = "left"
        elif actual_right > screen_rect.right():
            new_x = screen_rect.right() - sprite_w - offset_x
            self.vel_x = -abs(self.vel_x) * 0.6
            hit = "right"
            
        return int(new_x), hit
EOF

# --- 4. RENDERER.PY ---
cat <<EOF > src/renderer.py
from PyQt6.QtGui import QPixmap, QPainter, QColor
from PyQt6.QtCore import QRect, Qt

class Renderer:
    """Se encarga de procesar y centrar las imágenes en el canvas."""
    def load_sheet(self, path):
        sheet = QPixmap(path)
        if sheet.isNull():
            sheet = QPixmap(200, 200)
            sheet.fill(QColor(255, 0, 255, 180))
        return sheet

    def create_canvas(self, full_sheet, frame_idx, cols, target_w, target_h, canvas_size):
        frame_w = full_sheet.width() // cols
        frame_h = full_sheet.height()
        
        pix = full_sheet.copy(QRect(frame_idx * frame_w, 0, frame_w, frame_h)).scaled(
            target_w, target_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        
        canvas = QPixmap(canvas_size, canvas_size)
        canvas.fill(Qt.GlobalColor.transparent)
        p = QPainter(canvas)
        p.drawPixmap((canvas_size - target_w)//2, (canvas_size - target_h)//2, pix)
        p.end()
        return canvas
EOF

# --- 5. DEBUG.PY ---
cat <<EOF > src/debug.py
import sys

class Debugger:
    """Centraliza la información de depuración en la terminal."""
    @staticmethod
    def log(state, x, y, vel_x, vel_y, g_factor):
        info = (
            f"ESTADO: {state.upper():<8} | "
            f"POS: {int(x):>4},{int(y):>4} | "
            f"VEL: {vel_x:>4.1f},{vel_y:>4.1f} | "
            f"GRAV: {g_factor:>3.2f}"
        )
        sys.stdout.write(f"\r\033[2K{info}")
        sys.stdout.flush()
EOF

# --- 6. MAIN.PY ---
cat <<EOF > src/main.py
import sys, os, random
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel
from PyQt6.QtCore import QTimer, Qt, QPoint
from settings import Settings
from physics import PhysicsEngine
from renderer import Renderer
from debug import Debugger

class CyberPet(QMainWindow):
    def __init__(self, skin_path):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.settings = Settings(skin_path)
        self.physics = PhysicsEngine(self.settings)
        self.renderer = Renderer()
        
        self.label = QLabel(self)
        self.base_h = self.settings.get_global("base_height", 250)
        self.setFixedSize(self.base_h * 2, self.base_h * 2)
        
        self.state = "idle"
        self.frame = 0
        self.is_dragging = False
        self.locked_scale = self.base_h
        
        self.load_state("idle")
        
        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.loop)
        self.anim_timer.start(150)
        
        self.ai_timer = QTimer()
        self.ai_timer.timeout.connect(self.ai_think)
        self.ai_timer.start(4000)

        self.set_initial_position()
        self.show()

    def load_state(self, state):
        if self.state != state or not hasattr(self, 'full_sheet'):
            self.state = state
            self.anim_data = self.settings.get_anim(state)
            self.full_sheet = self.renderer.load_sheet(os.path.join(self.settings.skin_path, self.anim_data["file"]))
            self.anim_timer.setInterval(self.anim_data.get("speed", 150))
            self.frame = 0

    def set_initial_position(self):
        screen = QApplication.primaryScreen().availableGeometry()
        env = self.settings.get_global("environment", {})
        y_max_pc = env.get("walkable_y_max_pc", 100) / 100
        y_pos = int((screen.height() * y_max_pc) - self.base_h)
        self.move((screen.width() - self.width()) // 2, y_pos)
        self.physics.grab_y = y_pos

    def loop(self):
        if self.physics.is_falling:
            self.physics.apply_gravity(self.anim_data.get("gravity", self.settings.get_global("gravity", 1.2)))
            self.physics.apply_friction(self.settings.get_global("friction", 0.95))
            new_x, new_y = self.x() + self.physics.vel_x, self.y() + self.physics.vel_y
            if new_y >= self.physics.grab_y and self.physics.vel_y > 0:
                new_y, self.physics.is_falling = self.physics.grab_y, False
                self.physics.vel_x = self.physics.vel_y = 0
                self.load_state("idle")
            self.move(int(new_x), int(new_y))
        elif not self.is_dragging:
            self.move(int(self.x() + self.anim_data.get("move_speed", 0)), self.y())

        screen = QApplication.primaryScreen().availableGeometry()
        target_h = self.update_scale()
        target_w = int(target_h * (self.full_sheet.width()/self.anim_data["cols"] / self.full_sheet.height()))
        
        final_x, hit = self.physics.check_bounds(self.x(), self.y(), target_w, self.width(), screen)
        if final_x != self.x(): self.move(final_x, self.y())
        if hit and not self.physics.is_falling:
            self.load_state("look_r" if hit == "left" else "look_l")

        canvas = self.renderer.create_canvas(self.full_sheet, self.frame, self.anim_data["cols"], 
                                           target_w, target_h, self.width())
        self.label.setPixmap(canvas)
        self.setMask(canvas.mask())

        Debugger.log(self.state, self.x(), self.y(), self.physics.vel_x, self.physics.vel_y, 
                    self.anim_data.get("gravity", self.settings.get_global("gravity", 1.2)))
        self.frame = (self.frame + 1) % self.anim_data["cols"]

    def update_scale(self):
        if self.is_dragging or self.physics.is_falling: return self.locked_scale
        env = self.settings.get_global("environment", {})
        if env.get("mode") != "perspective": return self.base_h
        screen = QApplication.primaryScreen().availableGeometry()
        y_min = (env.get("walkable_y_min_pc", 0) / 100) * screen.height()
        y_max = (env.get("walkable_y_max_pc", 100) / 100) * screen.height() - self.base_h
        t = max(0.0, min((self.y() - y_min) / (y_max - y_min), 1.0))
        min_f = env.get("min_scale_percent", 30) / 100
        return int(self.base_h * (min_f + (t * (1.0 - min_f))))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.locked_scale, self.is_dragging, self.physics.is_falling = self.update_scale(), True, False
            self.offset, self.last_mouse_pos = event.position().toPoint(), event.globalPosition().toPoint()
            self.load_state("drag_id")

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            curr = event.globalPosition().toPoint()
            m = self.settings.get_global("launch_multiplier", 0.8)
            self.physics.vel_x, self.physics.vel_y = (curr.x()-self.last_mouse_pos.x())*m, (curr.y()-self.last_mouse_pos.y())*m
            self.last_mouse_pos = curr
            self.move(curr - self.offset)
            self.load_state("drag_mv")

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.is_dragging = False
            if self.y() < self.physics.grab_y - 10 or abs(self.physics.vel_y) > 2:
                self.physics.is_falling = True
                self.load_state("fall")
            else:
                self.physics.vel_x = self.physics.vel_y = 0
                self.load_state("idle")

    def ai_think(self):
        if self.is_dragging or self.physics.is_falling: return
        d = random.randint(1, 100)
        if d > 85: self.load_state(random.choice(["look_l", "look_r", "angry"]))
        elif d > 50: self.load_state("idle")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "skins", "default"))
    pet = CyberPet(path)
    sys.exit(app.exec())
EOF

# --- 7. START.SH ---
cat <<EOF > start.sh
#!/bin/bash
# Forzamos que reconozca el directorio src para los imports
export PYTHONPATH=\$PYTHONPATH:\$(pwd)/src
python3 src/main.py
EOF

chmod +x start.sh

echo -e "${GREEN}✔ Proyecto limpio y regenerado con éxito.${NC}"