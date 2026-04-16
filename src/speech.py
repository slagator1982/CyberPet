"""
speech.py — Burbuja de diálogo de CyberPet
============================================
Ventana flotante independiente (Tool, siempre encima, ignora clics)
que muestra texto sobre la cabeza del personaje y lo sigue en cada tick.

El posicionamiento se basa en el rect REAL del sprite (no del canvas
transparente que lo envuelve), calculado a partir de:
  - La posición global de la ventana principal (window_x, window_y)
  - El tamaño del canvas cuadrado (canvas_size)
  - El tamaño real del sprite escalado (sprite_w, sprite_h)

De esa forma la burbuja:
  1. Siempre queda centrada horizontalmente sobre el sprite
  2. Siempre queda pegada a la cabeza con un pequeño margen vertical
  3. Se mueve en cada tick junto con el personaje (drag, walk, fall, etc.)
"""

import random
from PyQt6.QtWidgets import QLabel, QWidget, QVBoxLayout, QApplication
from PyQt6.QtCore import QTimer, Qt, QPoint
from PyQt6.QtGui import QFont, QPalette, QColor


class SpeechBubble(QWidget):
    """
    Ventana flotante con texto de diálogo del personaje.

    Propiedades de la ventana:
      - Sin bordes ni barra de título
      - Siempre encima de las demás ventanas
      - No recibe eventos de ratón (WA_TransparentForMouseEvents)
      - Fondo translúcido (WA_TranslucentBackground)
    """

    # Margen vertical entre la cabeza del sprite y el borde inferior de la burbuja
    HEAD_MARGIN: int = 8

    def __init__(self):
        # SpeechBubble es una ventana independiente (sin parent),
        # lo que le permite posicionarse en coordenadas globales de pantalla.
        super().__init__(parent=None)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint       # Sin decoración
            | Qt.WindowType.WindowStaysOnTopHint    # Siempre encima
            | Qt.WindowType.Tool                    # No aparece en la barra de tareas
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # La burbuja no captura clics; el ratón "pasa a través" hacia el sprite
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        self.label = QLabel("", self)
        # Fuente estilo terminal / cyberpunk
        self.label.setFont(QFont("Monospace", 11, QFont.Weight.Bold))
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Texto en cian neón
        palette = self.label.palette()
        palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 255, 255))
        self.label.setPalette(palette)

        layout.addWidget(self.label, 0, Qt.AlignmentFlag.AlignCenter)

        # Timer de auto-ocultación; se reactiva en cada llamada a speak()
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

        self.hide()

    # ──────────────────────────────────────────────────────────────────────
    # API pública
    # ──────────────────────────────────────────────────────────────────────

    def speak(self, text: str, duration_ms: int = 2500):
        """
        Muestra un mensaje sobre el personaje durante `duration_ms` milisegundos.
        Si ya había un mensaje visible, lo reemplaza y reinicia el contador.

        Args:
            text        : texto a mostrar
            duration_ms : tiempo en ms antes de que la burbuja desaparezca
        """
        if not text:
            return

        self.label.setText(text)
        self.adjustSize()   # Redimensiona la ventana al contenido del label

        # Reiniciamos el timer aunque ya estuviera corriendo
        self._hide_timer.start(duration_ms)
        self.show()

    def update_position(
        self,
        window_x: int,
        window_y: int,
        canvas_size: int,
        sprite_w: int,
        sprite_h: int,
    ):
        """
        Reposiciona la burbuja sobre la cabeza del sprite.
        Debe llamarse en cada tick de update_animation(), tanto si la burbuja
        está visible como si no (así estará lista si aparece en medio de un frame).

        Cálculo:
          - El sprite está centrado dentro del canvas cuadrado.
          - sprite_x_global = window_x + (canvas_size - sprite_w) / 2
          - sprite_y_global = window_y + (canvas_size - sprite_h) / 2
          - La burbuja se centra horizontalmente sobre el sprite.
          - La burbuja se coloca encima de la cabeza (sprite_y - burbuja_h - margen).

        Args:
            window_x    : posición X global de la ventana principal (self.x())
            window_y    : posición Y global de la ventana principal (self.y())
            canvas_size : tamaño del canvas cuadrado en píxeles
            sprite_w    : ancho real del sprite escalado en este tick
            sprite_h    : alto real del sprite escalado en este tick
        """
        if not self.isVisible():
            return

        # Coordenadas globales del borde superior-izquierdo del sprite
        sprite_global_x = window_x + (canvas_size - sprite_w) // 2
        sprite_global_y = window_y + (canvas_size - sprite_h) // 2

        # Centramos la burbuja horizontalmente sobre el sprite
        bub_x = sprite_global_x + (sprite_w - self.width()) // 2
        # La colocamos encima de la cabeza
        bub_y = sprite_global_y - self.height() - self.HEAD_MARGIN

        # Evitar que la burbuja salga por arriba de la pantalla
        screen = QApplication.primaryScreen().availableGeometry()
        bub_y = max(screen.top(), bub_y)
        # Evitar que salga por los lados
        bub_x = max(screen.left(), min(bub_x, screen.right() - self.width()))

        self.move(QPoint(bub_x, bub_y))
