"""
renderer.py — Motor de renderizado de CyberPet
===============================================
Responsable de:
  - Cargar y cachear los spritesheets de cada estado
  - Extraer el frame actual del spritesheet
  - Escalar el frame al tamaño calculado por el sistema de perspectiva
  - Componer el frame sobre un canvas transparente centrado
  - Generar la máscara de hit-test (solo el área del sprite es clickable)

No conoce física ni IA; solo sabe "dame el pixmap del frame N a tamaño S".
"""

import os
from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtGui import QColor, QPainter, QPixmap


class SpriteRenderer:
    """
    Gestiona la carga de spritesheets y la composición de cada frame.

    El canvas tiene tamaño fijo (base_height × 2) para que la ventana Qt
    no cambie de tamaño en cada tick, lo que causaría parpadeo.
    El sprite se centra dentro de ese canvas.
    """

    def __init__(self, base_height: int, canvas_size: int):
        """
        Args:
            base_height : altura base del sprite en píxeles (a escala 1:1)
            canvas_size : tamaño del lienzo cuadrado de la ventana (base_height × 2)
        """
        self.base_height: int  = base_height
        self.canvas_size: int  = canvas_size

        # ── Estado del spritesheet activo ──────────────────────────────────
        self.full_sheet: QPixmap = QPixmap()   # Spritesheet completo cargado
        self.frame_w: int        = 0            # Ancho de un frame individual
        self.frame_h: int        = 0            # Alto de un frame individual
        self.cols: int           = 1            # Número de frames en el sheet
        self.current_frame: int  = 0            # Índice del frame actual

        # ── Tamaño real del sprite renderizado en el último tick ───────────
        # Lo usan otros módulos (p.ej. colisión con bordes) para conocer
        # el área real del sprite dentro del canvas.
        self.real_sprite_size: QSize = QSize(0, 0)

    # ──────────────────────────────────────────────────────────────────────
    # Carga de spritesheet
    # ──────────────────────────────────────────────────────────────────────

    def load_sheet(self, skin_path: str, anim_data: dict):
        """
        Carga el spritesheet correspondiente a un estado de animación.

        Si el archivo no existe o está corrupto, usa un rectángulo
        magenta como fallback visual para facilitar el debug.

        Args:
            skin_path : ruta absoluta a la carpeta del skin
            anim_data : dict con las claves 'file', 'cols' del config.json
        """
        img_path = os.path.join(skin_path, anim_data["file"])
        sheet = QPixmap(img_path)

        if sheet.isNull():
            # ── Fallback magenta ─────────────────────────────────────────
            # Si el PNG no carga, creamos un cuadrado magenta fácilmente visible
            sheet = QPixmap(100, 100)
            sheet.fill(QColor(255, 0, 255, 180))
            self.cols = 1
        else:
            self.cols = anim_data.get("cols", 1)

        self.full_sheet = sheet
        # El spritesheet es horizontal: todos los frames tienen el mismo alto
        self.frame_w = self.full_sheet.width() // self.cols
        self.frame_h = self.full_sheet.height()
        self.current_frame = 0   # Reiniciamos la animación desde el primer frame

    # ──────────────────────────────────────────────────────────────────────
    # Composición del frame
    # ──────────────────────────────────────────────────────────────────────

    def render_frame(self, sprite_height: int) -> QPixmap:
        """
        Genera el pixmap final listo para asignar al QLabel de la ventana.

        Proceso:
          1. Calculamos el ancho proporcional al sprite_height
          2. Recortamos el frame actual del spritesheet
          3. Escalamos el frame al tamaño calculado (smooth)
          4. Dibujamos el frame centrado en un canvas transparente
          5. Guardamos real_sprite_size para que la colisión pueda usarlo

        Args:
            sprite_height : altura del sprite en píxeles (calculada por PerspectiveSystem)

        Devuelve:
            QPixmap del canvas completo listo para mostrar
        """
        # ── 1. Tamaño proporcional ─────────────────────────────────────────
        if self.frame_h > 0:
            aspect = self.frame_w / self.frame_h
        else:
            aspect = 1.0
        sprite_w = int(sprite_height * aspect)
        self.real_sprite_size = QSize(sprite_w, sprite_height)

        # ── 2. Recorte del frame actual ────────────────────────────────────
        x_offset = self.current_frame * self.frame_w
        frame_crop = self.full_sheet.copy(QRect(x_offset, 0, self.frame_w, self.frame_h))

        # ── 3. Escaldo suave ───────────────────────────────────────────────
        scaled_frame = frame_crop.scaled(
            sprite_w,
            sprite_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        # ── 4. Composición sobre canvas transparente ───────────────────────
        # El canvas es siempre canvas_size × canvas_size; el sprite se centra.
        canvas = QPixmap(self.canvas_size, self.canvas_size)
        canvas.fill(Qt.GlobalColor.transparent)

        painter = QPainter(canvas)
        draw_x = (self.canvas_size - sprite_w) // 2
        draw_y = (self.canvas_size - sprite_height) // 2
        painter.drawPixmap(draw_x, draw_y, scaled_frame)
        painter.end()

        # ── 5. Avanzar al siguiente frame (con wrap-around) ───────────────
        self.current_frame = (self.current_frame + 1) % self.cols

        return canvas
