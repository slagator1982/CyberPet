"""
renderer.py — Motor de renderizado de CyberPet
===============================================
Responsable de:
  - Cargar y cachear los spritesheets de cada estado
  - Extraer el frame actual del spritesheet
  - Escalar el frame al tamaño calculado por perspective.py
  - Componer el frame centrado en un canvas transparente fijo
  - Exponer real_sprite_size para que check_screen_bounds use el tamaño correcto

No conoce física ni IA.
"""

import os
from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtGui import QColor, QPainter, QPixmap


class SpriteRenderer:
    """
    Carga spritesheets y compone frames centrados en un canvas fijo.

    El canvas tiene tamaño fijo (base_height × 2) para que la ventana Qt
    no cambie de tamaño en cada tick, evitando parpadeos.
    """

    def __init__(self, base_height: int, canvas_size: int):
        self.base_height: int = base_height
        self.canvas_size: int = canvas_size

        self.full_sheet: QPixmap = QPixmap()
        self.frame_w:    int     = 0
        self.frame_h:    int     = 0
        self.cols:       int     = 1
        self.current_frame: int  = 0

        # Inicializado a base_height (no a 0) para que check_screen_bounds
        # no calcule offset_x = canvas_size // 2 en el primer tick,
        # lo que desplazaría las paredes de colisión canvas_size//2 px
        # hacia adentro creando una "pared invisible".
        self.real_sprite_size: QSize = QSize(base_height, base_height)

    # ──────────────────────────────────────────────────────────────────────
    # Carga de spritesheet
    # ──────────────────────────────────────────────────────────────────────

    def load_sheet(self, skin_path: str, anim_data: dict):
        """
        Carga el spritesheet de una animación.
        Fallback a rectángulo magenta si el PNG no existe o está corrupto.
        """
        img_path = os.path.join(skin_path, anim_data["file"])
        sheet = QPixmap(img_path)

        if sheet.isNull():
            sheet = QPixmap(100, 100)
            sheet.fill(QColor(255, 0, 255, 180))
            self.cols = 1
        else:
            self.cols = anim_data.get("cols", 1)

        self.full_sheet = sheet
        self.frame_w    = self.full_sheet.width() // self.cols
        self.frame_h    = self.full_sheet.height()
        self.current_frame = 0

    # ──────────────────────────────────────────────────────────────────────
    # Composición del frame
    # ──────────────────────────────────────────────────────────────────────

    def render_frame(self, sprite_height: int) -> QPixmap:
        """
        Genera el QPixmap del canvas listo para asignar al QLabel.

        Proceso:
          1. Calcula el ancho proporcional
          2. Recorta el frame actual del spritesheet
          3. Escala el frame suavemente
          4. Dibuja centrado en canvas transparente
          5. Actualiza real_sprite_size
          6. Avanza current_frame

        Args:
            sprite_height : altura del sprite calculada por PerspectiveSystem
        """
        aspect   = (self.frame_w / self.frame_h) if self.frame_h > 0 else 1.0
        sprite_w = int(sprite_height * aspect)

        # Recorte del frame actual
        x_offset   = self.current_frame * self.frame_w
        frame_crop = self.full_sheet.copy(QRect(x_offset, 0, self.frame_w, self.frame_h))

        # Escalado suave manteniendo aspecto
        scaled = frame_crop.scaled(
            sprite_w, sprite_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        # Canvas transparente fijo; sprite centrado
        canvas = QPixmap(self.canvas_size, self.canvas_size)
        canvas.fill(Qt.GlobalColor.transparent)
        p = QPainter(canvas)
        p.drawPixmap(
            (self.canvas_size - sprite_w)    // 2,
            (self.canvas_size - sprite_height) // 2,
            scaled,
        )
        p.end()

        # Actualizar tamaño real ANTES de que check_screen_bounds lo use
        self.real_sprite_size = QSize(sprite_w, sprite_height)

        self.current_frame = (self.current_frame + 1) % self.cols
        return canvas
