import sys
import os
import json
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPixmap

class CyberPet(QMainWindow):
    def __init__(self):
        super().__init__()
        self.load_config()
        self.initUI()
        self.oldPos = self.pos()

    def load_config(self):
        config_path = os.path.join("data", "config.json")
        try:
            with open(config_path, "r") as f:
                self.config = json.load(f)
        except:
            self.config = {"scale_factor": 1.0}

    def initUI(self):
        # Configuración de ventana transparente y siempre encima
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Tamaño basado en la resolución de pantalla (Escalado dinámico)
        screen = QApplication.primaryScreen().geometry()
        base_size = int(screen.height() * 0.15 * self.config.get("scale_factor", 1.0))
        
        self.label = QLabel(self)
        # Placeholder visual (Emoji) hasta tener los Sprites de la Fase 3
        self.label.setText("🤖")
        self.label.setStyleSheet(f"font-size: {int(base_size*0.6)}px;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.setCentralWidget(self.label)
        self.resize(base_size, base_size)
        self.show()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            delta = QPoint(event.globalPosition().toPoint() - self.oldPos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPosition().toPoint()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    pet = CyberPet()
    sys.exit(app.exec())
