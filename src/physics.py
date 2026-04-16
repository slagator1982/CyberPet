"""
physics.py — Motor de física de CyberPet
=========================================
Gestiona toda la simulación física del personaje:
  - Gravedad y caída libre
  - Velocidad y fricción horizontal
  - Detección de colisión con el suelo (grab_y)
  - Movimiento autónomo con variación de profundidad (eje Z)

Este módulo NO conoce nada de Qt ni de renderizado;
trabaja solo con valores numéricos y devuelve posiciones.
"""

import random


class PhysicsEngine:
    """
    Encapsula el estado físico del personaje y las operaciones
    que lo modifican en cada tick del bucle principal.

    Parámetros de configuración (leídos del config.json del skin):
      - gravity       : aceleración por tick (px/tick²)
      - friction      : factor multiplicativo de vel_x en caída (0–1)
      - launch_mult   : amplificador de velocidad al soltar el drag
      - z_step        : variación máxima de grab_y por tick (profundidad)
    """

    def __init__(self, config: dict):
        # ── Parámetros del config ──────────────────────────────────────────
        self.gravity_factor: float = config.get("gravity", 1.2)
        self.friction: float       = config.get("friction", 0.95)
        self.launch_mult: float    = config.get("launch_multiplier", 0.8)
        self.z_step: float         = config.get("z_step", 5.0)

        # ── Estado de velocidad ────────────────────────────────────────────
        self.vel_x: float = 0.0   # Velocidad horizontal actual (px/tick)
        self.vel_y: float = 0.0   # Velocidad vertical actual   (px/tick)

        # ── Flags de estado ───────────────────────────────────────────────
        self.is_falling: bool  = False  # True mientras el personaje está en el aire
        self.is_dragging: bool = False  # True mientras el usuario arrastra

        # ── Referencia de suelo ───────────────────────────────────────────
        # grab_y es la coordenada Y de la ventana que se considera "suelo".
        # El personaje aterriza cuando su Y >= grab_y.
        self.grab_y: float = 0.0

    # ──────────────────────────────────────────────────────────────────────
    # Actualización de gravedad
    # ──────────────────────────────────────────────────────────────────────

    def tick_fall(self, current_x: float, current_y: float) -> tuple[float, float, bool]:
        """
        Aplica un tick de gravedad y fricción cuando el personaje está cayendo.

        Devuelve:
            (new_x, new_y, landed)
            - new_x/new_y : nueva posición propuesta
            - landed       : True si el personaje ha tocado el suelo en este tick
        """
        # Aceleramos hacia abajo
        self.vel_y += self.gravity_factor
        # Aplicamos fricción al movimiento horizontal
        self.vel_x *= self.friction

        new_x = current_x + self.vel_x
        new_y = current_y + self.vel_y

        # Comprobamos si hemos alcanzado o superado el suelo
        landed = new_y >= self.grab_y and self.vel_y > 0
        if landed:
            new_y = self.grab_y
            self.vel_x = 0.0
            self.vel_y = 0.0
            self.is_falling = False

        return new_x, new_y, landed

    # ──────────────────────────────────────────────────────────────────────
    # Movimiento autónomo con eje Z (profundidad simulada)
    # ──────────────────────────────────────────────────────────────────────

    def tick_autonomous(
        self,
        current_x: float,
        move_speed_x: float,
        current_y: float,
        move_speed_y: float,
        z_mode: str,
        state: str,
        y_min: float,
        y_max: float,
    ) -> tuple[float, float]:
        """
        Calcula la nueva posición del personaje en modo autónomo (sin drag, sin caída).

        Si el estado es de movimiento/mirada, aplica una variación aleatoria
        de grab_y en el rango ±z_step para simular desplazamiento en profundidad.

        Args:
            current_x    : posición X actual de la ventana
            move_speed_x : desplazamiento X por tick (del JSON de la animación)
            current_y    : posición X actual de la ventana
            move_speed_y : desplazamiento Y por tick (del JSON de la animación)
            z_mode       : modo del dezplazamiento z none/fixed/random 
            y_min        : límite superior de la zona caminable (px)
            y_max        : límite inferior de la zona caminable (px)
            state        : estado actual del personaje (ej. "walk_l", "idle")

        Devuelve:
            (new_x, new_grab_y)
        """
        # # Solo los estados de movimiento o mirada generan variación Z
        # mobile_states = {"look_l", "look_r", "walk_l", "walk_r"}
        # if state in mobile_states:
        #     delta_z = random.choice([-1, 0, 1]) * self.z_step
        #     self.grab_y += delta_z
        #     # Clampear dentro de los límites del área caminable
        #     self.grab_y = max(y_min, min(self.grab_y, y_max))

        y_min = 160 # Eliminar cuando se arregle el problema de las perspectivas
        y_max = 487 #
        self.grab_y += move_speed_y
        self.grab_y = max(y_min, min(self.grab_y, y_max))

        new_x = current_x + move_speed_x
        return new_x, self.grab_y

    # ──────────────────────────────────────────────────────────────────────
    # Eventos de arrastre
    # ──────────────────────────────────────────────────────────────────────

    def start_drag(self, locked_y: float):
        """
        Inicializa el estado de arrastre.
        Si el personaje no estaba cayendo, fija el suelo en la posición actual.

        Args:
            locked_y : posición Y de la ventana en el momento de iniciar el drag
        """
        if not self.is_falling:
            self.grab_y = locked_y
        self.is_dragging = True
        self.is_falling = False
        self.vel_x = 0.0
        self.vel_y = 0.0

    def update_drag_velocity(self, delta_x: float, delta_y: float):
        """
        Actualiza la velocidad a partir del movimiento del ratón durante el drag.
        Aplica el multiplicador de lanzamiento (launch_mult).

        Args:
            delta_x : diferencia X entre la posición actual y la anterior del ratón
            delta_y : diferencia Y entre la posición actual y la anterior del ratón
        """
        self.vel_x = delta_x * self.launch_mult
        self.vel_y = delta_y * self.launch_mult

    def update_grab_y_on_drag(self, window_y: float):
        """
        Durante el arrastre, actualiza grab_y si el personaje desciende más
        de lo que estaba. Esto evita que 'caiga' a una posición anterior.

        Args:
            window_y : posición Y actual de la ventana durante el drag
        """
        if window_y > self.grab_y:
            self.grab_y = window_y

    def release_drag(self) -> bool:
        """
        Finaliza el arrastre y decide si el personaje debe caer o posarse.

        Devuelve:
            True  → el personaje debe iniciar caída libre
            False → el personaje aterriza en el sitio (idle)
        """
        self.is_dragging = False

        # Cae si está claramente por encima del suelo o tiene velocidad vertical apreciable
        should_fall = (self.grab_y - self.vel_y > 10) or (abs(self.vel_y) > 2)

        if not should_fall:
            self.vel_x = 0.0
            self.vel_y = 0.0

        self.is_falling = should_fall
        return should_fall

    # ──────────────────────────────────────────────────────────────────────
    # Colisión con bordes de pantalla
    # ──────────────────────────────────────────────────────────────────────

    def bounce_horizontal(self, direction: str):
        """
        Invierte y amortigua la velocidad horizontal al rebotar en un borde.

        Args:
            direction : "left"  → el personaje golpeó el borde izquierdo
                        "right" → el personaje golpeó el borde derecho
        """
        if direction == "left":
            self.vel_x = abs(self.vel_x) * 0.6
        else:
            self.vel_x = -abs(self.vel_x) * 0.6

    # ──────────────────────────────────────────────────────────────────────
    # Actualización de gravity_factor por animación
    # ──────────────────────────────────────────────────────────────────────

    def set_gravity(self, value: float):
        """
        Permite que cada animación sobreescriba la gravedad global
        (campo opcional 'gravity' en la entrada de animación del config).

        Args:
            value : nuevo valor de gravedad (px/tick²)
        """
        self.gravity_factor = value
