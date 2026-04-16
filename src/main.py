"""
main.py — Punto de entrada y clase principal de CyberPet
=========================================================
Orquesta todos los subsistemas del proyecto:

    PhysicsEngine     → física de gravedad, fricción, rebotes
    PerspectiveSystem → escalado del sprite según posición Y (eje Z)
    SpriteRenderer    → carga de spritesheets y composición de frames
    AIBrain           → decisiones autónomas del personaje
    DebugHUD          → línea de debug en consola (in-place)

La clase CyberPet hereda de QMainWindow y actúa como coordinador:
recibe eventos de Qt (ratón, timers) y delega la lógica en los módulos.

Estructura de archivos del proyecto:
    Archivador/
    ├── src/
    │   ├── main.py          ← este archivo
    │   ├── physics.py       ← motor de física
    │   ├── perspective.py   ← sistema de perspectiva (eje Z)
    │   ├── renderer.py      ← renderizado de sprites
    │   ├── ai.py            ← inteligencia artificial autónoma
    │   └── debug.py         ← HUD de debug en consola
    ├── assets/
    │   └── skins/
    │       └── default/
    │           ├── config.json
    │           └── *.png
    └── data/
        └── config.json
"""

import sys
import os
import json
import random

from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow
from PyQt6.QtCore import QTimer, Qt, QPoint, QSize
from PyQt6.QtGui import QPixmap

# ── Módulos propios ────────────────────────────────────────────────────────────
from physics     import PhysicsEngine
from perspective import PerspectiveSystem
from renderer    import SpriteRenderer
from ai          import AIBrain
from debug       import DebugHUD
from speech      import SpeechBubble

class CyberPet(QMainWindow):
    """
    Ventana principal de la mascota virtual.

    Es una ventana transparente, sin bordes y siempre encima de las demás.
    Coordina los subsistemas en cada tick del bucle de animación.

    Timers activos:
        anim_timer (variable, por defecto 150 ms) → update_animation()
        ai_timer   (4 000 ms fijo)                → ai_brain.think()
    """

    # ──────────────────────────────────────────────────────────────────────
    # Inicialización
    # ──────────────────────────────────────────────────────────────────────

    def __init__(self, skin_folder: str):
        """
        Args:
            skin_folder : ruta absoluta a la carpeta del skin activo
                          (debe contener config.json y los PNGs de animación)
        """
        super().__init__()

        # ── Configuración de la ventana Qt ────────────────────────────────
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint      # Sin barra de título
            | Qt.WindowType.WindowStaysOnTopHint   # Siempre encima
            | Qt.WindowType.Tool                   # No aparece en la barra de tareas
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # QLabel interno que actúa como lienzo de píxeles
        self.label = QLabel(self)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        self.skin_path = os.path.abspath(skin_folder)

        # ── Carga del config.json ─────────────────────────────────────────
        self.config = self._load_config()

        # ── Dimensiones del canvas ────────────────────────────────────────
        # El canvas es cuadrado y siempre tiene el doble del tamaño base
        # del sprite para que éste quepa en cualquier posición de escala.
        self.base_height:    int = self.config.get("base_height", 250)
        self.canvas_size_val: int = int(self.base_height * 2.0)
        self.setFixedSize(self.canvas_size_val, self.canvas_size_val)

        # ── Subsistemas ───────────────────────────────────────────────────
        self.physics     = PhysicsEngine(self.config)
        self.perspective = PerspectiveSystem(self.config, self.base_height)
        self.renderer    = SpriteRenderer(self.base_height, self.canvas_size_val)
        self.hud         = DebugHUD(enabled=True)
        self.ai_brain    = AIBrain(on_state_change=self.change_state)

        # ── Estado interno de arrastre ────────────────────────────────────
        # Estos valores son exclusivos del manejo de eventos Qt y no
        # tienen cabida en PhysicsEngine (que no conoce Qt).
        self.offset:          QPoint = QPoint(0, 0)  # Offset del click sobre el sprite
        self.last_mouse_pos:  QPoint = QPoint(0, 0)  # Posición del ratón en el tick anterior
        self.locked_scale:    int    = self.base_height  # Escala congelada durante drag/caída

        # ── Estado de la animación ────────────────────────────────────────
        self.current_state: str = "idle"

        # ── Para los dialogos del personaje
        self.bubble = SpeechBubble()

        # ── Timers ────────────────────────────────────────────────────────
        # anim_timer: bucle principal (física + render)
        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.update_animation)

        # ai_timer: toma de decisiones autónomas cada 4 segundos
        self.ai_timer = QTimer()
        self.ai_timer.timeout.connect(
            lambda: self.ai_brain.think(self.physics.is_dragging, self.physics.is_falling)
        )
        self.ai_timer.start(4000)

        # ── Carga inicial y arranque ──────────────────────────────────────
        self.load_animation("idle")
        self._set_initial_position()
        self.show()

    # ──────────────────────────────────────────────────────────────────────
    # Carga de configuración
    # ──────────────────────────────────────────────────────────────────────

    def _load_config(self) -> dict:
        """
        Lee y parsea el config.json del skin.
        Termina el proceso con un error si el archivo falta o está malformado.

        Devuelve:
            dict con la configuración completa del skin
        """
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
        Coloca la ventana en la posición de inicio definida en el config.

        Las coordenadas start_x_pc y start_y_pc se expresan como porcentaje
        del tamaño de pantalla (0–100). El canvas se centra en ese punto.
        Al terminar, grab_y queda fijado en la posición Y inicial (suelo de inicio).
        """
        screen = QApplication.primaryScreen().availableGeometry()

        start_x_pc = self.config.get("start_x_pc", 50) / 100.0
        start_y_pc = self.config.get("start_y_pc", 90) / 100.0

        # Centramos el canvas en el punto de inicio
        x_pos = int(screen.width()  * start_x_pc - self.width()  / 2)
        y_pos = int(screen.height() * start_y_pc - self.height() / 2)

        self.move(x_pos, y_pos)
        self.physics.grab_y = float(y_pos)   # El suelo inicial es la posición Y de arranque

    # ──────────────────────────────────────────────────────────────────────
    # Carga de animación
    # ──────────────────────────────────────────────────────────────────────

    def load_animation(self, state: str):
        """
        Carga el spritesheet del estado indicado y configura el timer de animación.

        Si el estado no existe en el config, usa 'idle' como fallback.
        También actualiza la gravedad activa (cada estado puede tener la suya propia).

        Args:
            state : nombre del estado (ej. "idle", "walk_l", "fall")
        """
        # Obtenemos los datos de la animación, con fallback a 'idle'
        animations = self.config.get("animations", {})
        anim_data  = animations.get(state, animations.get("idle", {}))

        if not anim_data:
            DebugHUD.error(f"No hay datos de animación para '{state}' ni para 'idle'.")
            return

        # Delegamos la carga del spritesheet al renderer
        self.renderer.load_sheet(self.skin_path, anim_data)

        # Actualizamos la gravedad: cada animación puede sobreescribir la global
        gravity = anim_data.get("gravity", self.config.get("gravity", 1.2))
        self.physics.set_gravity(gravity)

        # Guardamos la velocidad de movimiento autónomo de esta animación
        self._current_move_speed_x: float = anim_data.get("move_speed_x", 0)
        self._current_move_speed_y: float = anim_data.get("move_speed_y", 0)
        if anim_data.get("z_mode", "none") == "random":
            self._current_move_speed_y = self._current_move_speed_y * random.choice([-1, 0, 1])
        if anim_data.get("z_mode", "none") == "none":
            self._current_move_speed_y = 0

        # Reiniciamos el timer con la velocidad de esta animación
        self.anim_timer.start(anim_data.get("speed", 150))

    # ──────────────────────────────────────────────────────────────────────
    # Bucle principal de animación
    # ──────────────────────────────────────────────────────────────────────

    def update_animation(self):
        """
        Tick principal del juego. Se ejecuta en cada disparo de anim_timer.

        Orden de operaciones:
          1. Física (caída libre o movimiento autónomo)
          2. Comprobación de colisión con bordes de pantalla
          3. Cálculo de escala (perspectiva)
          4. Renderizado del frame actual
          5. Actualización de la máscara de la ventana
          6. Impresión del HUD de debug
        """
        # ── 1. Física ─────────────────────────────────────────────────────
        if self.physics.is_falling:
            self._tick_falling()
        elif not self.physics.is_dragging:
            self._tick_autonomous()

        # ── 2. Perspectiva y escala ───────────────────────────────────────
        screen = QApplication.primaryScreen().availableGeometry()

        sprite_height = self.perspective.compute_scale(
            grab_y      = self.physics.grab_y,
            screen_height = screen.height(),
            is_falling  = self.physics.is_falling,
            is_dragging = self.physics.is_dragging,
            window_y    = float(self.y()),
            locked_scale= self.locked_scale,
        )

        # ── 3. Renderizado ────────────────────────────────────────────────
        canvas = self.renderer.render_frame(sprite_height)
        # ── Dialogo del personaje ─────────────────────────────────────────
        self.bubble.update_position(self.frameGeometry())

        # Aplicamos el canvas al QLabel y actualizamos la máscara de click
        self.label.setPixmap(canvas)
        self.label.setGeometry(0, 0, self.width(), self.height())
        self.setMask(canvas.mask())   # Solo el área del sprite recibe eventos de ratón

        # ── 4. Debug HUD ──────────────────────────────────────────────────
        sz = self.renderer.real_sprite_size
        self.hud.print(
            state      = self.current_state,
            x          = self.x(),
            y          = self.y(),
            sprite_w   = sz.width(),
            sprite_h   = sz.height(),
            vel_x      = self.physics.vel_x,
            vel_y      = self.physics.vel_y,
            gravity    = self.physics.gravity_factor,
            friction   = self.physics.friction,
            launch_mult= self.physics.launch_mult,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Sub-ticks de física
    # ──────────────────────────────────────────────────────────────────────

    def _tick_falling(self):
        """
        Aplica física de caída libre y mueve la ventana.
        Detecta el aterrizaje y transiciona a 'idle'.
        """
        new_x, new_y, landed = self.physics.tick_fall(float(self.x()), float(self.y()))
        self.move(int(new_x), int(new_y))
        self._check_screen_bounds()

        if landed:
            self.change_state("idle")

    def _tick_autonomous(self):
        """
        Aplica movimiento autónomo (IA) cuando el personaje camina o mira.
        Incluye la variación de profundidad (eje Z) y la colisión con bordes.
        """
        screen = QApplication.primaryScreen().availableGeometry()
        y_min, y_max = self.perspective.walkable_bounds(screen.height())

        new_x, new_grab_y = self.physics.tick_autonomous(
            current_x  = float(self.x()),
            move_speed_x = self._current_move_speed_x,
            current_y  = float(self.y()),
            move_speed_y = self._current_move_speed_y,
            state      = self.current_state,
            y_min      = y_min,
            y_max      = y_max,
        )

        self.move(int(new_x), int(new_grab_y))
        self._check_screen_bounds()

    # ──────────────────────────────────────────────────────────────────────
    # Colisión con bordes de pantalla
    # ──────────────────────────────────────────────────────────────────────

    def _check_screen_bounds(self):
        """
        Comprueba si el sprite ha salido de los bordes de la pantalla.

        Calcula la posición real del sprite (no del canvas) y,
        si sobresale por algún lado:
          - Recoloca la ventana para que el sprite quede en el borde
          - Invierte y amortigua la velocidad horizontal (rebote × 0.6)
          - Cambia el estado a look_r (borde izquierdo) o look_l (borde derecho)
        """
        screen = QApplication.primaryScreen().availableGeometry()
        sprite_w = self.renderer.real_sprite_size.width()

        # El sprite está centrado dentro del canvas, así que calculamos su
        # posición absoluta en pantalla a partir de la posición de la ventana
        offset_x   = (self.canvas_size_val - sprite_w) // 2
        actual_left = self.x() + offset_x
        actual_right = actual_left + sprite_w

        if actual_left < screen.left():
            # Rebote en el borde izquierdo
            self.move(screen.left() - offset_x, self.y())
            self.physics.bounce_horizontal("left")
            if not self.physics.is_falling:
                self.change_state("look_r")

        elif actual_right > screen.right():
            # Rebote en el borde derecho
            self.move(screen.right() - sprite_w - offset_x, self.y())
            self.physics.bounce_horizontal("right")
            if not self.physics.is_falling:
                self.change_state("look_l")

    # ──────────────────────────────────────────────────────────────────────
    # Cambio de estado
    # ──────────────────────────────────────────────────────────────────────

    def change_state(self, new_state: str, speech_key=None):
        """
        Transiciona el personaje a un nuevo estado de animación.
        Solo actúa si el estado es diferente al actual (evita recargas innecesarias).

        Args:
            new_state : nombre del estado destino (debe existir en config.json)
        """
        if self.current_state != new_state:
            self.current_state = new_state
            self.load_animation(new_state)

        # Lógica de diálogo
        if speech_key and "dialogs" in self.config:
            phrases = self.config["dialogs"].get(speech_key, [])
            if phrases:
                self.bubble.speak(random.choice(phrases))

    # ──────────────────────────────────────────────────────────────────────
    # Eventos de ratón
    # ──────────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        """
        Inicia el arrastre cuando el usuario hace clic izquierdo sobre el sprite.

        Pasos:
          1. Cambia el cursor a mano cerrada
          2. Congela la escala actual (locked_scale) para que no cambie durante el drag
          3. Delega el inicio del drag al PhysicsEngine
          4. Eleva la ventana al frente de todas las demás
          5. Guarda el offset del click para mover la ventana de forma relativa
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

            # Congelamos la escala antes de iniciar el drag
            screen = QApplication.primaryScreen().availableGeometry()
            self.locked_scale = self.perspective.compute_scale(
                grab_y       = self.physics.grab_y,
                screen_height= screen.height(),
                is_falling   = self.physics.is_falling,
                is_dragging  = self.physics.is_dragging,
                window_y     = float(self.y()),
                locked_scale = self.locked_scale,
            )

            self.physics.start_drag(locked_y=float(self.y()))
            self.raise_()   # Ventana al frente

            # Offset: distancia entre el punto de click y la esquina superior-izquierda
            self.offset = event.position().toPoint()
            self.last_mouse_pos = event.globalPosition().toPoint()

            self.change_state("drag_id")   # Estado: cogido pero sin mover

    def mouseMoveEvent(self, event):
        """
        Mueve el personaje mientras el usuario arrastra.

        Calcula la velocidad de arrastre como diferencia entre la posición
        actual y la anterior del ratón (multiplicada por launch_mult),
        de forma que al soltar se conserve esa inercia.
        """
        if self.physics.is_dragging:
            curr = event.globalPosition().toPoint()

            # Velocidad = desplazamiento del ratón desde el último tick
            delta_x = curr.x() - self.last_mouse_pos.x()
            delta_y = curr.y() - self.last_mouse_pos.y()
            self.physics.update_drag_velocity(delta_x, delta_y)
            self.last_mouse_pos = curr

            # Movemos la ventana siguiendo el cursor con el offset aplicado
            self.move(curr - self.offset)

            # Actualizamos grab_y si el personaje ha bajado (nuevo suelo)
            self.physics.update_grab_y_on_drag(float(self.y()))

            # Cambiamos al estado de arrastre activo (si no estábamos ya en él)
            if self.current_state != "drag_mv":
                self.change_state("drag_mv")

    def mouseReleaseEvent(self, event):
        """
        Finaliza el arrastre y decide si el personaje cae o se posa.

        Si el personaje está por encima del suelo (grab_y) o tiene
        velocidad vertical apreciable, inicia la caída libre.
        En caso contrario, aterriza en el sitio y pasa a 'idle'.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

            should_fall = self.physics.release_drag()

            if should_fall:
                self.change_state("fall")
            else:
                self.change_state("idle")


# ──────────────────────────────────────────────────────────────────────────────
# Punto de entrada
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # La ruta del skin se construye de forma relativa al script.
    # Lanzar desde la carpeta src/ o usando el script start.sh del proyecto.
    main_dir  = os.path.dirname(os.path.abspath(__file__))
    skin_path = os.path.abspath(os.path.join(main_dir, "..", "assets", "skins", "default"))

    pet = CyberPet(skin_path)
    sys.exit(app.exec())
