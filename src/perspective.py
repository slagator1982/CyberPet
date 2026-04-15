"""
perspective.py — Sistema de perspectiva simulada (eje Z)
=========================================================
Calcula el tamaño visual del personaje en función de su posición
vertical en pantalla, creando la ilusión de profundidad.

Cuanto más abajo esté el personaje (más cerca del espectador),
más grande se renderiza. Cuanto más arriba (más al fondo), más pequeño.

Este módulo es puramente funcional: recibe datos y devuelve un int.
No tiene estado propio ni dependencias de Qt.
"""


class PerspectiveSystem:
    """
    Gestiona el cálculo de escala basado en la posición Y del personaje.

    La escala se interpola linealmente entre min_scale y 1.0 (escala completa)
    dentro de la zona caminable definida en el config.

    Fórmula:
        t = (grab_y − y_min) / (y_max − y_min)   ∈ [0.0, 1.0]
        altura = base_height × (min_f + t × (1 − min_f))

    Con min_scale_percent=10 y zona 50%–100%:
        - En y_min → sprite de 25 px  (10% de 250)
        - En y_max → sprite de 250 px (100% de 250)
    """

    def __init__(self, config: dict, base_height: int):
        """
        Args:
            config      : dict completo del skin (config.json)
            base_height : altura en píxeles del sprite a escala 1:1
        """
        self.base_height: int = base_height

        env = config.get("environment", {})

        # Modo: solo "perspective" activa el escalado
        self.active: bool = env.get("mode", "") == "perspective"

        # Escala mínima expresada como fracción (ej. 10 → 0.10)
        self.min_factor: float = env.get("min_scale_percent", 30) / 100.0

        # Límites de la zona caminable como porcentaje de la altura de pantalla
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
            grab_y        : coordenada Y del suelo actual del personaje
            screen_height : altura total de la pantalla en píxeles
            is_falling    : True si el personaje está en caída libre
            is_dragging   : True si el usuario está arrastrando
            window_y      : posición Y actual de la ventana (top-left)
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

        # ── Cálculo de perspectiva ────────────────────────────────────────
        y_min = self.walkable_y_min_pc * screen_height
        # Restamos base_height para que el pie del personaje no salga de pantalla
        y_max = self.walkable_y_max_pc * screen_height - self.base_height

        # t = 0.0 → fondo (pequeño) | t = 1.0 → primer plano (grande)
        if y_max <= y_min:
            # Zona caminable degenerada: devolvemos tamaño base
            return self.base_height

        t = (grab_y - y_min) / (y_max - y_min)
        t = max(0.0, min(t, 1.0))   # Clampear entre 0 y 1

        height = self.base_height * (self.min_factor + t * (1.0 - self.min_factor))
        return int(height)

    # ──────────────────────────────────────────────────────────────────────
    # Límites de la zona caminable (en píxeles)
    # ──────────────────────────────────────────────────────────────────────

    def walkable_bounds(self, screen_height: int) -> tuple[float, float]:
        """
        Calcula los límites superior e inferior de la zona caminable
        expresados en píxeles absolutos.

        Args:
            screen_height : altura de la pantalla disponible en píxeles

        Devuelve:
            (y_min, y_max) en píxeles
        """
        y_min = self.walkable_y_min_pc * screen_height
        y_max = self.walkable_y_max_pc * screen_height
        return y_min, y_max
