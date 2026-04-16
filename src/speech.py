import random
from PyQt6.QtWidgets import QLabel, QWidget, QVBoxLayout
from PyQt6.QtCore import QTimer, Qt, QPoint
from PyQt6.QtGui import QFont, QPalette, QColor

class SpeechBubble(QWidget):
    """Ventana flotante transparente para los diálogos de CyberPet."""
    def __init__(self, parent=None):
        super().__init__(parent)
        # Configuración de ventana: sin bordes, siempre encima, ignora clics
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        self.label = QLabel("", self)
        # Fuente estilo terminal / ciberbótica
        self.label.setFont(QFont("Monospace", 12, QFont.Weight.Bold))
        self.label.setWordWrap(True)
        
        # Color cian neón
        palette = self.label.palette()
        palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 255, 255)) 
        self.label.setPalette(palette)
        
        layout.addWidget(self.label, 0, Qt.AlignmentFlag.AlignCenter)
        self.hide()

    def speak(self, text: str, duration_ms: int = 2500):
        """Muestra un texto y lo oculta tras el tiempo especificado."""
        if not text:
            return
        self.label.setText(text)
        self.adjustSize()
        self.show()
        QTimer.singleShot(duration_ms, self.hide)

    def update_position(self, parent_rect):
        """Sincroniza la posición sobre la 'cabeza' del personaje."""
        if not self.isVisible():
            return
            
        # Calcular posición centrada sobre el robot
        x = parent_rect.left() + (parent_rect.width() // 2) - (self.width() // 2)
        y = parent_rect.top() - self.height() - 10
        self.move(QPoint(x, y))