"""
perspective.py — Sistema de perspectiva simulada (eje Z)
=========================================================
Calcula el tamaño visual del personaje en función de su posición
vertical en pantalla, creando la ilusión de profundidad.

Cuanto más abajo esté el personaje (más cerca del espectador),
más grande se renderiza. Cuanto más arriba (más al fondo), más pequeño.

Este módulo es puramente funcional: recibe datos y devuelve un int.
No tiene estado propio ni dependencias de Qt.

── Nota sobre el sistema de coordenadas ─────────────────────────────────────
El personaje se mueve mediante `grab_y`, que es la posición Y de la esquina
superior-izquierda del CANVAS (la ventana Qt). El canvas es un cuadrado de
`canvas_size = base_height × 2` píxeles; el sprite está centrado dentro de él.

Por tanto la coordenada Y real del borde superior del sprite es:
    sprite_top = grab_y + (canvas_size - sprite_h) / 2

Como `sprite_h` varía con la escala, se usa `base_height` como aproximación
fija para el offset del canvas:
    canvas_offset = (canvas_size - base_height) / 2
                  = (base_height × 2 - base_height) / 2
                  = base_height / 2

Todos los límites internos se expresan en coordenadas de grab_y (ventana),
no en coordenadas de pantalla, para que las comparaciones sean directas.
"""


class PerspectiveSystem:
    """
    Gestiona el cálculo de escala basado en la posición Y del personaje.

    La escala se interpola linealmente entre min_scale y 1.0 (escala completa)
    dentro de la zona caminable definida en el config.

    Fórmula:
        t = (grab_y − y_min_win) / (y_max_win − y_min_win)   ∈ [0.0, 1.0]
        altura = base_height × (min_f + t × (1 − min_f))

    Donde y_min_win / y_max_win son los límites en coordenadas de ventana (grab_y),
    obtenidos restando canvas_offset a los límites en coordenadas de pantalla.
    """

    def __init__(self, config: dict, base_height: int):
        """
        Args:
            config      : dict completo del skin (config.json)
            base_height : altura en píxeles del sprite a escala 1:1
        """
        self.base_height: int = base_height

        # El canvas mide base_height × 2; el sprite está centrado.
        # El offset vertical entre el top del canvas y el top del sprite (a escala 1:1) es:
        #   canvas_offset = base_height / 2
        # Se usa como corrección constante para convertir coordenadas de pantalla
        # a coordenadas de ventana (grab_y).
        self.canvas_offset: int = base_height // 2

        env = config.get("environment", {})

        # Modo: solo "perspective" activa el escalado
        self.active: bool = env.get("mode", "") == "perspective"

        # Escala mínima expresada como fracción (ej. 30 → 0.30)
        self.min_factor: float = env.get("min_scale_percent", 30) / 100.0

        # Límites de la zona caminable como fracción de la altura de pantalla
        self.walkable_y_min_pc: float = env.get("walkable_y_min_pc", 0) / 100.0
        self.walkable_y_max_pc: float = env.get("walkable_y_max_pc", 100) / 100.0

    # ──────────────────────────────────────────────────────────────────────
    # Cálculo principal de escala
    # ──────────────────────────────────────────────────────────────────────

    def compute_scale(
        self,
        grab_y: float,
        screen_height: int,
        is_falling: bool,
        is_dragging: bool,
        window_y: float,
        locked_scale: int,
    ) -> int:
        """
        Devuelve la altura en píxeles que debe tener el sprite en este tick.

        Reglas especiales de escala:
          - Si el personaje está cayendo → devuelve locked_scale (congelada)
          - Si está siendo arrastrado y su Y está por encima del suelo → locked_scale
          - Si está siendo arrastrado pero ha bajado al suelo → calcula normalmente
          - Si el modo no es "perspective" → devuelve base_height (sin escala)

        Args:
            grab_y        : coordenada Y del canvas (= posición de la ventana Qt)
            screen_height : altura total de la pantalla disponible en píxeles
            is_falling    : True si el personaje está en caída libre
            is_dragging   : True si el usuario está arrastrando
            window_y      : posición Y actual de la ventana (top-left del canvas)
            locked_scale  : escala que se congeló al iniciar el drag o la caída

        Devuelve:
            Altura calculada en píxeles (int)
        """
        # ── Casos especiales: escala congelada ────────────────────────────
        if is_falling:
            return locked_scale
        if is_dragging and window_y < grab_y:
            return locked_scale

        # ── Sin perspectiva: tamaño fijo ──────────────────────────────────
        if not self.active:
            return self.base_height

        # ── Límites en coordenadas de ventana (grab_y) ────────────────────
        # Convertimos los límites de pantalla a coordenadas de grab_y restando
        # canvas_offset: el canvas empieza canvas_offset píxeles antes del sprite.
        y_min_win, y_max_win = self.walkable_bounds(screen_height)

        # t = 0.0 → fondo de la zona (sprite pequeño)
        # t = 1.0 → frente de la zona (sprite grande)
        if y_max_win <= y_min_win:
            # Zona caminable degenerada: devolvemos tamaño base
            return self.base_height

        t = (grab_y - y_min_win) / (y_max_win - y_min_win)
        t = max(0.0, min(t, 1.0))   # Clampear entre 0 y 1

        height = self.base_height * (self.min_factor + t * (1.0 - self.min_factor))
        return int(height)

    # ──────────────────────────────────────────────────────────────────────
    # Límites de la zona caminable (en coordenadas de grab_y / ventana)
    # ──────────────────────────────────────────────────────────────────────

    def walkable_bounds(self, screen_height: int) -> tuple[float, float]:
        """
        Devuelve los límites de la zona caminable en coordenadas de grab_y,
        es decir, en la misma escala que self.physics.grab_y (posición Y del canvas).

        La conversión desde coordenadas de pantalla es:
            grab_y = y_pantalla - canvas_offset
                   = y_pantalla - base_height / 2

        Args:
            screen_height : altura de la pantalla disponible en píxeles

        Devuelve:
            (y_min_win, y_max_win) en coordenadas de grab_y
        """
        # Límites en coordenadas de pantalla (donde está el borde superior del sprite)
        y_min_screen = self.walkable_y_min_pc * screen_height
        # Restamos base_height para que el PIE del sprite no salga por debajo de y_max
        y_max_screen = self.walkable_y_max_pc * screen_height - self.base_height

        # Convertimos a coordenadas de grab_y (posición del canvas)
        y_min_win = y_min_screen - self.canvas_offset
        y_max_win = y_max_screen - self.canvas_offset

        return y_min_win, y_max_win
