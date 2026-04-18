"""
physics.py — Motor de física de CyberPet
=========================================
Gestiona toda la simulación física del personaje:
  - Gravedad y caída libre
  - Velocidad y fricción horizontal
  - Detección de colisión con el suelo (grab_y)
  - Movimiento autónomo con desplazamiento en Z

Este módulo NO conoce nada de Qt ni de renderizado;
trabaja solo con valores numéricos y devuelve posiciones.

── Coordenadas ───────────────────────────────────────────────────────────────
grab_y es la posición Y de la ventana Qt (top-left del canvas), NO la posición
del sprite. La conversión a coords de pantalla del sprite la hace perspective.py.
El personaje "aterriza" cuando self.y() >= grab_y (su ventana baja hasta grab_y).
"""

import random


class PhysicsEngine:
    """
    Encapsula el estado físico del personaje y las operaciones
    que lo modifican en cada tick del bucle principal.
    """

    def __init__(self, config: dict):
        # ── Parámetros del config ──────────────────────────────────────────
        self.gravity_factor: float = config.get("gravity", 1.2)
        self.friction: float       = config.get("friction", 0.95)
        self.launch_mult: float    = config.get("launch_multiplier", 0.8)

        # ── Estado de velocidad ────────────────────────────────────────────
        self.vel_x: float = 0.0
        self.vel_y: float = 0.0

        # ── Flags de estado ───────────────────────────────────────────────
        self.is_falling:  bool = False
        self.is_dragging: bool = False

        # ── Suelo actual ───────────────────────────────────────────────────
        # grab_y es la coordenada Y del canvas cuando el sprite está "en el suelo".
        # El personaje aterriza cuando self.y() sube hasta alcanzar grab_y
        # cayendo (new_y >= grab_y con vel_y > 0).
        self.grab_y: float = 0.0

    # ──────────────────────────────────────────────────────────────────────
    # Caída libre
    # ──────────────────────────────────────────────────────────────────────

    def tick_fall(self, current_x: float, current_y: float) -> tuple[float, float, bool]:
        """
        Aplica un tick de gravedad y fricción.

        Devuelve (new_x, new_y, landed).
        landed = True cuando el personaje toca el suelo (grab_y) en este tick.
        """
        self.vel_y += self.gravity_factor
        self.vel_x *= self.friction

        new_x = current_x + self.vel_x
        new_y = current_y + self.vel_y

        landed = new_y >= self.grab_y and self.vel_y > 0
        if landed:
            new_y        = self.grab_y
            self.vel_x   = 0.0
            self.vel_y   = 0.0
            self.is_falling = False

        return new_x, new_y, landed

    # ──────────────────────────────────────────────────────────────────────
    # Movimiento autónomo
    # ──────────────────────────────────────────────────────────────────────

    def tick_autonomous(
        self,
        current_x: float,
        move_speed_x: float,
        move_speed_y: float,
        grab_y_min: float,
        grab_y_max: float,
    ) -> tuple[float, float]:
        """
        Calcula la nueva posición en modo autónomo (sin drag, sin caída).

        grab_y_min y grab_y_max ya están en coordenadas de grab_y
        (los proporciona perspective.walkable_bounds()).

        Devuelve (new_x, new_grab_y).
        """
        self.grab_y += move_speed_y
        self.grab_y  = max(grab_y_min, min(self.grab_y, grab_y_max))

        new_x = current_x + move_speed_x
        return new_x, self.grab_y

    # ──────────────────────────────────────────────────────────────────────
    # Arrastre
    # ──────────────────────────────────────────────────────────────────────

    def start_drag(self, locked_y: float):
        """
        Inicia el arrastre. Si el personaje no estaba cayendo, fija el suelo
        en la posición actual (locked_y = self.y() en el momento del click).
        """
        if not self.is_falling:
            self.grab_y = locked_y
        self.is_dragging = True
        self.is_falling  = False
        self.vel_x = 0.0
        self.vel_y = 0.0

    def update_drag_velocity(self, delta_x: float, delta_y: float):
        """Actualiza la velocidad de inercia durante el arrastre."""
        self.vel_x = delta_x * self.launch_mult
        self.vel_y = delta_y * self.launch_mult

    def update_grab_y_on_drag(self, window_y: float):
        """
        Durante el drag, actualiza grab_y si el personaje desciende.
        Así el suelo siempre es el punto más bajo que ha alcanzado mientras
        lo arrastraban, evitando que "caiga" hacia atrás al soltarlo.
        """
        if window_y > self.grab_y:
            self.grab_y = window_y

    def release_drag(self) -> bool:
        """
        Finaliza el drag. Decide si el personaje debe caer o posarse.

        Cae si está por encima del suelo (window_y < grab_y implícito en vel_y)
        o si tiene velocidad vertical apreciable.

        Devuelve True si debe iniciar caída libre.
        """
        self.is_dragging = False
        should_fall = (self.grab_y - self.vel_y > 10) or (abs(self.vel_y) > 2)
        if not should_fall:
            self.vel_x = 0.0
            self.vel_y = 0.0
        self.is_falling = should_fall
        return should_fall

    # ──────────────────────────────────────────────────────────────────────
    # Rebote en bordes
    # ──────────────────────────────────────────────────────────────────────

    def bounce_horizontal(self, direction: str):
        """
        Invierte y amortigua vel_x al rebotar en un borde lateral.
        direction: "left" | "right"
        """
        if direction == "left":
            self.vel_x = abs(self.vel_x) * 0.6
        else:
            self.vel_x = -abs(self.vel_x) * 0.6

    # ──────────────────────────────────────────────────────────────────────
    # Gravedad por animación
    # ──────────────────────────────────────────────────────────────────────

    def set_gravity(self, value: float):
        """Permite que cada animación sobreescriba la gravedad global."""
        self.gravity_factor = value
