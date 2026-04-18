"""
perspective.py — Sistema de perspectiva simulada (eje Z)
=========================================================
Gestiona el escalado del sprite según posición Y y los límites
de la zona caminable según el modo del entorno.

Modos (config["environment"]["mode"]):
  "perspective" — sprite escala con Y. Zona caminable delimitada.
  "free"        — sprite siempre a base_height. Toda la pantalla es caminable,
                  con suelo en el borde inferior.
  "toolbar"     — sprite siempre a base_height. Una sola línea de suelo
                  en el borde inferior de la pantalla.

── Sistema de coordenadas ────────────────────────────────────────────────────
grab_y  = self.y() = posición Y de la esquina superior del canvas Qt
canvas  = cuadrado de canvas_size = base_height × 2 px
sprite  = centrado verticalmente dentro del canvas

Relaciones clave (sprite a escala máxima = base_height):
  canvas_offset  = (canvas_size - base_height) / 2 = base_height / 2
  sprite_top     = grab_y + canvas_offset
  sprite_bottom  = grab_y + canvas_offset + base_height
                 = grab_y + canvas_offset + base_height

Para que sprite_top   == y_min_screen: grab_y_min = y_min_screen - canvas_offset
Para que sprite_bottom == y_max_screen: grab_y_max = y_max_screen - canvas_offset - base_height

IMPORTANTE: y_min_screen e y_max_screen incluyen screen.top() para que las
coordenadas sean absolutas en el escritorio, coincidiendo con self.y().
"""


class PerspectiveSystem:

    def __init__(self, config: dict, base_height: int):
        self.base_height:   int   = base_height
        self.canvas_size:   int   = base_height * 2
        self.canvas_offset: int   = base_height // 2  # margen canvas→sprite

        env = config.get("environment", {})
        self.mode: str = env.get("mode", "free")

        self.min_factor: float = env.get("min_scale_percent", 30) / 100.0

        self.walkable_y_min_pc: float = env.get("walkable_y_min_pc", 0)   / 100.0
        self.walkable_y_max_pc: float = env.get("walkable_y_max_pc", 100) / 100.0

    # ──────────────────────────────────────────────────────────────────────
    # Límites en coordenadas de grab_y
    # ──────────────────────────────────────────────────────────────────────

    def walkable_bounds(self, screen_top: float, screen_height: int) -> tuple[float, float]:
        """
        Devuelve (grab_y_min, grab_y_max) en coordenadas absolutas de escritorio.

        screen_top    = availableGeometry().y()  — puede ser != 0 si hay
                        barra de tareas arriba u otro panel.
        screen_height = availableGeometry().height()

        La fórmula general para convertir porcentaje a grab_y:
          y_screen = screen_top + pc * screen_height
          grab_y   = y_screen - canvas_offset          (para el borde superior)
                   = y_screen - canvas_offset - base_height  (para el borde inferior)
        """
        if self.mode == "toolbar":
            # Una línea fija de suelo al borde inferior de la pantalla.
            # grab_y_min == grab_y_max → no hay rango vertical.
            y_max_screen = screen_top + self.walkable_y_max_pc * screen_height
            floor = y_max_screen - self.canvas_offset - self.base_height
            return floor, floor

        if self.mode == "free":
            # Sin restricciones verticales. El suelo es el borde inferior de pantalla.
            # grab_y_min = 0 (o negativo si la pantalla tiene offset): sin límite superior.
            # grab_y_max: los PIES del sprite (a escala máxima) tocan el borde inferior.
            floor = screen_top + screen_height - self.canvas_offset - self.base_height
            return -float("inf"), floor

        # ── Modo "perspective" ─────────────────────────────────────────────
        # Techo: el TECHO del sprite queda en el porcentaje mínimo de pantalla.
        y_min_screen = screen_top + self.walkable_y_min_pc * screen_height
        grab_y_min   = y_min_screen - self.canvas_offset

        # Suelo: los PIES del sprite (a escala máxima) quedan en el porcentaje máximo.
        y_max_screen = screen_top + self.walkable_y_max_pc * screen_height
        grab_y_max   = y_max_screen - self.canvas_offset - self.base_height

        return grab_y_min, grab_y_max

    # ──────────────────────────────────────────────────────────────────────
    # Escala del sprite
    # ──────────────────────────────────────────────────────────────────────

    def compute_scale(
        self,
        grab_y: float,
        screen_top: float,
        screen_height: int,
        is_dragging: bool,
        window_y: float,
        locked_scale: int,
    ) -> int:
        """
        Devuelve la altura en píxeles del sprite para este tick.

        Modos "free" y "toolbar": siempre base_height.

        Modo "perspective":
          - Drag aéreo (window_y < grab_y): locked_scale congelada.
            Solo se congela si el usuario arrastra por encima del suelo.
          - Resto (suelo, caída, walk): interpolación por posición Y.
            La caída tiene escala dinámica — el sprite crece al acercarse
            al primer plano, lo que es más realista y correcto en spawns.
        """
        if self.mode != "perspective":
            return self.base_height

        # Drag aéreo: congelar escala
        if is_dragging and window_y < grab_y:
            return locked_scale

        grab_y_min, grab_y_max = self.walkable_bounds(screen_top, screen_height)

        if grab_y_max <= grab_y_min:
            return self.base_height

        t = (grab_y - grab_y_min) / (grab_y_max - grab_y_min)
        t = max(0.0, min(t, 1.0))

        return int(self.base_height * (self.min_factor + t * (1.0 - self.min_factor)))
