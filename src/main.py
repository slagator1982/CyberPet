"""
main.py — Coordinador principal de CyberPet
============================================
Orquesta PhysicsEngine, PerspectiveSystem, SpriteRenderer, AIBrain,
DebugHUD y SpeechBubble.

── Orden del bucle de animación ─────────────────────────────────────────────
  1. compute_scale()      → sprite_height con posición actual
  2. render_frame()       → dibuja y actualiza real_sprite_size
  3. Física               → tick_fall / tick_autonomous
  4. check_screen_bounds  → colisiones laterales (usa real_sprite_size correcto)
  5. bubble / hud

render_frame() ANTES de la física para que check_screen_bounds use
el real_sprite_size del tick actual (si fuese al revés, el primer tick
usaría QSize(0,0) → offset_x = canvas_size//2 → pared invisible 250px adentro).

── Coordenadas ───────────────────────────────────────────────────────────────
Todas las posiciones usan coordenadas absolutas de escritorio.
screen = availableGeometry() → rect con .x(), .y(), .width(), .height()
Las fórmulas siempre añaden screen.x() / screen.y() como base para que
funcionen con barras de tareas, múltiples monitores y factores de escala DPI.
"""

import sys
import os
import json
import random

from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow
from PyQt6.QtCore import QTimer, Qt, QPoint, QSize
from PyQt6.QtGui import QPixmap

from physics     import PhysicsEngine
from perspective import PerspectiveSystem
from renderer    import SpriteRenderer
from ai          import AIBrain
from debug       import DebugHUD
from speech      import SpeechBubble


class CyberPet(QMainWindow):
    """Ventana principal de la mascota virtual."""

    def __init__(self, skin_folder: str):
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.label = QLabel(self)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        self.skin_path = os.path.abspath(skin_folder)
        self.config    = self._load_config()

        self.base_height:     int = self.config.get("base_height", 250)
        self.canvas_size_val: int = self.base_height * 2
        self.setFixedSize(self.canvas_size_val, self.canvas_size_val)

        self.physics     = PhysicsEngine(self.config)
        self.perspective = PerspectiveSystem(self.config, self.base_height)
        self.renderer    = SpriteRenderer(self.base_height, self.canvas_size_val)
        self.hud         = DebugHUD(enabled=True)
        self.ai_brain    = AIBrain(on_state_change=self.change_state)
        self.bubble      = SpeechBubble()

        self.offset:          QPoint = QPoint(0, 0)
        self.last_mouse_pos:  QPoint = QPoint(0, 0)
        self.locked_scale:    int    = self.base_height

        self.current_state:         str   = "idle"
        self._current_move_speed_x: float = 0.0
        self._current_move_speed_y: float = 0.0

        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.update_animation)

        self.ai_timer = QTimer()
        self.ai_timer.timeout.connect(
            lambda: self.ai_brain.think(self.physics.is_dragging, self.physics.is_falling)
        )
        self.ai_timer.start(4000)

        self.load_animation("idle")
        self._set_initial_position()
        self.show()

    # ──────────────────────────────────────────────────────────────────────
    # Helpers: geometría de pantalla
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _screen():
        """Devuelve availableGeometry() de la pantalla primaria."""
        return QApplication.primaryScreen().availableGeometry()

    def _screen_params(self):
        """
        Devuelve (screen_top, screen_height) listos para pasar a perspective.

        screen_top    = coordenada Y absoluta del borde superior del área disponible.
        screen_height = altura del área disponible en píxeles.

        Usar estos valores garantiza que las coordenadas de grab_y
        coincidan con self.y(), que también es absoluto en el escritorio.
        """
        s = self._screen()
        return float(s.y()), s.height()

    # ──────────────────────────────────────────────────────────────────────
    # Config
    # ──────────────────────────────────────────────────────────────────────

    def _load_config(self) -> dict:
        config_file = os.path.join(self.skin_path, "config.json")
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            DebugHUD.error(f"No se pudo cargar config.json: {e}")
            sys.exit(1)

    # ──────────────────────────────────────────────────────────────────────
    # Posición inicial
    # ──────────────────────────────────────────────────────────────────────

    def _set_initial_position(self):
        """
        Coloca la ventana según start_x_pc / start_y_pc del config
        y decide si el personaje aparece en el suelo o cayendo.

        ── Modo "free" ───────────────────────────────────────────────────
        Aparece en start_y_pc. grab_y = clamp(y_pos, -inf, floor).
        El suelo (floor) es el borde inferior de pantalla.
        No inicia caída.

        ── Modo "toolbar" ────────────────────────────────────────────────
        grab_y = floor fijo (única línea de suelo).
        La ventana se coloca en ese grab_y. No inicia caída.

        ── Modo "perspective" ────────────────────────────────────────────
        Se calcula y_pos a partir de start_y_pc.

          · y_pos < grab_y_min  → spawn ENCIMA de la zona caminable.
            El personaje cae hasta un punto aleatorio dentro del rango.
            Esto incluye spawns fuera de pantalla (y_pos muy negativo).

          · grab_y_min ≤ y_pos ≤ grab_y_max  → spawn DENTRO de la zona.
            El personaje aparece en esa posición sin caída.

          · y_pos > grab_y_max  → spawn DEBAJO del suelo.
            Se clampea a grab_y_max (suelo). Sin caída.
        """
        s = self._screen()
        screen_top  = float(s.y())
        screen_h    = s.height()
        screen_left = float(s.x())
        screen_w    = s.width()

        start_x_pc = self.config.get("start_x_pc", 50) / 100.0
        start_y_pc = self.config.get("start_y_pc", 90) / 100.0

        # Posición del canvas (top-left) en coordenadas absolutas de escritorio.
        # Se usa screen.x()/screen.y() como base para que funcione con
        # barras de tareas y múltiples monitores.
        x_pos = int(screen_left + screen_w  * start_x_pc - self.canvas_size_val / 2)
        y_pos = int(screen_top  + screen_h  * start_y_pc - self.canvas_size_val / 2)

        grab_y_min, grab_y_max = self.perspective.walkable_bounds(screen_top, screen_h)
        mode = self.perspective.mode

        if mode == "free":
            clamped = min(float(y_pos), grab_y_max)   # no salirse por abajo
            self.physics.grab_y = clamped
            self.move(x_pos, int(clamped))

        elif mode == "toolbar":
            # grab_y_min == grab_y_max == suelo fijo
            self.physics.grab_y = grab_y_max
            self.move(x_pos, int(grab_y_max))

        else:  # "perspective"
            if y_pos < grab_y_min:
                # Encima de la zona → cae hasta punto aleatorio del suelo
                grab_y_target = random.uniform(grab_y_min, grab_y_max)
                self.physics.grab_y    = grab_y_target
                self.physics.is_falling = True
                self.move(x_pos, y_pos)
                self.change_state("fall")
            else:
                # Dentro o debajo → clampear al suelo y colocar
                clamped = max(grab_y_min, min(float(y_pos), grab_y_max))
                self.physics.grab_y = clamped
                self.move(x_pos, int(clamped))

    # ──────────────────────────────────────────────────────────────────────
    # Animación
    # ──────────────────────────────────────────────────────────────────────

    def load_animation(self, state: str):
        animations = self.config.get("animations", {})
        anim_data  = animations.get(state, animations.get("idle", {}))
        if not anim_data:
            DebugHUD.error(f"No hay datos de animación para '{state}' ni para 'idle'.")
            return

        self.renderer.load_sheet(self.skin_path, anim_data)
        self.physics.set_gravity(anim_data.get("gravity", self.config.get("gravity", 1.2)))

        self._current_move_speed_x = float(anim_data.get("move_speed_x", 0))
        self._current_move_speed_y = float(anim_data.get("move_speed_y", 0))

        z_mode = anim_data.get("z_mode", "none")
        if z_mode == "random":
            self._current_move_speed_y *= random.choice([-1, 0, 1])
        elif z_mode == "none":
            self._current_move_speed_y = 0.0

        self.anim_timer.start(anim_data.get("speed", 150))

    # ──────────────────────────────────────────────────────────────────────
    # Bucle principal
    # ──────────────────────────────────────────────────────────────────────

    def update_animation(self):
        screen_top, screen_h = self._screen_params()

        # 1. Escala (con posición actual, antes de mover)
        sprite_height = self.perspective.compute_scale(
            grab_y       = self.physics.grab_y,
            screen_top   = screen_top,
            screen_height= screen_h,
            is_dragging  = self.physics.is_dragging,
            window_y     = float(self.y()),
            locked_scale = self.locked_scale,
        )

        # 2. Renderizado → actualiza real_sprite_size para check_screen_bounds
        canvas = self.renderer.render_frame(sprite_height)
        self.label.setPixmap(canvas)
        self.label.setGeometry(0, 0, self.width(), self.height())
        self.setMask(canvas.mask())

        # 3. Física
        if self.physics.is_falling:
            self._tick_falling()
        elif not self.physics.is_dragging:
            self._tick_autonomous()

        # 4. Burbuja de diálogo
        sz = self.renderer.real_sprite_size
        self.bubble.update_position(
            window_x    = self.x(),
            window_y    = self.y(),
            canvas_size = self.canvas_size_val,
            sprite_w    = sz.width(),
            sprite_h    = sz.height(),
        )

        # 5. HUD de debug
        self.hud.print(
            state       = self.current_state,
            x           = self.x(),
            y           = self.y(),
            sprite_w    = sz.width(),
            sprite_h    = sz.height(),
            vel_x       = self.physics.vel_x,
            vel_y       = self.physics.vel_y,
            gravity     = self.physics.gravity_factor,
            friction    = self.physics.friction,
            launch_mult = self.physics.launch_mult,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Sub-ticks
    # ──────────────────────────────────────────────────────────────────────

    def _tick_falling(self):
        """Caída libre. Aterriza cuando self.y() >= grab_y."""
        new_x, new_y, landed = self.physics.tick_fall(float(self.x()), float(self.y()))
        self.move(int(new_x), int(new_y))
        self._check_screen_bounds()
        if landed:
            self.change_state("idle")

    def _tick_autonomous(self):
        """Movimiento autónomo dentro de la zona caminable."""
        screen_top, screen_h = self._screen_params()
        grab_y_min, grab_y_max = self.perspective.walkable_bounds(screen_top, screen_h)

        # En modo free, grab_y_min es -inf: el personaje no tiene límite superior.
        # Pero sí tiene límite inferior (grab_y_max = suelo).
        if grab_y_min == float("-inf"):
            grab_y_min = float(self.y()) - self.canvas_size_val  # límite práctico

        new_x, new_grab_y = self.physics.tick_autonomous(
            current_x    = float(self.x()),
            move_speed_x = self._current_move_speed_x,
            move_speed_y = self._current_move_speed_y,
            grab_y_min   = grab_y_min,
            grab_y_max   = grab_y_max,
        )
        self.move(int(new_x), int(new_grab_y))
        self._check_screen_bounds()

    # ──────────────────────────────────────────────────────────────────────
    # Colisión con bordes laterales
    # ──────────────────────────────────────────────────────────────────────

    def _check_screen_bounds(self):
        """
        Rebote en los bordes izquierdo y derecho de la pantalla.

        El sprite está centrado en el canvas. offset_x es el margen
        horizontal entre el borde del canvas y el borde del sprite.

        actual_left  = self.x() + offset_x
        actual_right = actual_left + sprite_w

        Cuando actual_right > screen.right(), el sprite toca el borde derecho.
        La recolocación mueve la ventana para que el sprite quede exactamente
        en el borde, con el margen transparente del canvas sobrando por fuera.
        """
        s        = self._screen()
        sprite_w = self.renderer.real_sprite_size.width()
        offset_x = (self.canvas_size_val - sprite_w) // 2

        actual_left  = self.x() + offset_x
        actual_right = actual_left + sprite_w

        if actual_left < s.left():
            self.move(s.left() - offset_x, self.y())
            self.physics.bounce_horizontal("left")
            if not self.physics.is_falling:
                self.change_state("look_r")

        elif actual_right > s.right():
            self.move(s.right() - sprite_w - offset_x, self.y())
            self.physics.bounce_horizontal("right")
            if not self.physics.is_falling:
                self.change_state("look_l")

    # ──────────────────────────────────────────────────────────────────────
    # Cambio de estado
    # ──────────────────────────────────────────────────────────────────────

    def change_state(self, new_state: str, speech_key=None):
        if self.current_state != new_state:
            self.current_state = new_state
            self.load_animation(new_state)

        if speech_key and "dialogs" in self.config:
            phrases = self.config["dialogs"].get(speech_key, [])
            if phrases:
                self.bubble.speak(random.choice(phrases))

    # ──────────────────────────────────────────────────────────────────────
    # Eventos de ratón
    # ──────────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

            screen_top, screen_h = self._screen_params()
            self.locked_scale = self.perspective.compute_scale(
                grab_y       = self.physics.grab_y,
                screen_top   = screen_top,
                screen_height= screen_h,
                is_dragging  = self.physics.is_dragging,
                window_y     = float(self.y()),
                locked_scale = self.locked_scale,
            )

            self.physics.start_drag(locked_y=float(self.y()))
            self.raise_()
            self.offset         = event.position().toPoint()
            self.last_mouse_pos = event.globalPosition().toPoint()
            self.change_state("drag_id")

    def mouseMoveEvent(self, event):
        if self.physics.is_dragging:
            curr    = event.globalPosition().toPoint()
            delta_x = curr.x() - self.last_mouse_pos.x()
            delta_y = curr.y() - self.last_mouse_pos.y()
            self.physics.update_drag_velocity(delta_x, delta_y)
            self.last_mouse_pos = curr
            self.move(curr - self.offset)
            self.physics.update_grab_y_on_drag(float(self.y()))
            if self.current_state != "drag_mv":
                self.change_state("drag_mv")

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            should_fall = self.physics.release_drag()
            self.change_state("fall" if should_fall else "idle")


# ──────────────────────────────────────────────────────────────────────────────
# Punto de entrada
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_dir  = os.path.dirname(os.path.abspath(__file__))
    skin_path = os.path.abspath(os.path.join(main_dir, "..", "assets", "skins", "default"))
    pet = CyberPet(skin_path)
    sys.exit(app.exec())
