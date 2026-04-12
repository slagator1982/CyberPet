import sys
import os
import json
import random
# Añadimos QSize y QPainter, que son necesarios
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QWidget, QVBoxLayout
from PyQt6.QtCore import QTimer, Qt, QRect, QPoint, QSize
from PyQt6.QtGui import QPixmap, QFont, QPalette, QColor, QPainter

class SpeechBubble(QWidget):
    """Una ventana flotante transparente para el texto del robot"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5) 
        
        self.label = QLabel("", self)
        # Fuente ciberbótica
        self.label.setFont(QFont("Monospace", 10, QFont.Weight.Bold))
        self.label.setWordWrap(True)
        
        palette = self.label.palette()
        palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 255, 255)) 
        self.label.setPalette(palette)
        
        layout.addWidget(self.label, 0, Qt.AlignmentFlag.AlignCenter)
        self.hide()

    def speak(self, text):
        self.label.setText(text)
        self.adjustSize()
        self.show()
        QTimer.singleShot(3000, self.hide)

class CyberPet(QMainWindow):
    def __init__(self, skin_folder):
        super().__init__()
        # Configuración de ventana (Transparente y X11 forzado por start.sh)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.label = QLabel(self)
        # CRÍTICO para que el arrastre funcione en X11
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        self.skin_path = skin_folder
        
        # --- Variables de estado iniciales ---
        self.is_dragging = False
        self.current_state = "idle"
        self.current_frame = 0
        self.current_move_speed = 0
        self.current_y_speed = 0 # Velocidad vertical actual
        
        # Cargar Configuración
        config_file = os.path.join(self.skin_path, "config.json")
        try:
            with open(config_file, "r") as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"Error cargando config.json: {e}")
            sys.exit(1)
            
        self.base_height = self.config.get("base_height", 180)
        # Margen para el lienzo centrado
        self.canvas_margin = 1.2 
        
        self.bubble = SpeechBubble()
        
        # Timer de Animación (Frames)
        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.update_animation)
        
        # Timer de IA (Decisiones)
        self.ai_timer = QTimer()
        self.ai_timer.timeout.connect(self.ai_think)
        self.ai_timer.start(4000) # Piensa cada 4 segs
        
        self.load_animation(self.current_state)
        self.show()

    def load_animation(self, state):
        anim_data = self.config["animations"][state]
        self.full_sheet = QPixmap(os.path.join(self.skin_path, anim_data["file"]))
        self.cols = anim_data["cols"]
        
        # Leer velocidades horizontal y vertical
        self.current_move_speed = anim_data.get("move_speed", 0)
        self.current_y_speed = anim_data.get("move_speed_y", 0)
        
        self.frame_w = self.full_sheet.width() // self.cols
        self.frame_h = self.full_sheet.height()
        self.current_frame = 0
        self.anim_timer.start(anim_data.get("speed", 150))

    def update_scale(self):
        """Calcula la altura base basándose en la posición Y (Perspectiva)"""
        # Obtenemos la geometría de la pantalla
        screen = QApplication.primaryScreen().geometry()
        screen_height = screen.height()
        
        # Obtenemos la posición Y actual del robot (Y=0 es arriba)
        current_y = self.y()
        
        # Definimos el rango de escalado (min y max)
        # El robot se encogerá hasta el 60% de su base_height
        min_scale = 0.6 
        max_scale = 1.0
        
        # Calculamos el factor de escala (normalizado entre 0.0 y 1.0)
        # 0.0 es arriba de la pantalla, 1.0 es abajo.
        scale_factor = current_y / screen_height
        
        # Invertimos para que arriba sea pequeño y abajo grande
        scale_factor = 1.0 - scale_factor
        
        # Aplicamos el rango (clamp)
        scale_factor = max(min_scale, min(scale_factor, max_scale))
        
        # Retornamos la altura calculada
        return int(self.base_height * scale_factor)

    def update_animation(self):
        # 1. Movimiento físico (IA y Arrastre)
        if not self.is_dragging:
            # Movimiento Diagonal: Sumamos ambas velocidades
            self.move(self.pos() + QPoint(self.current_move_speed, self.current_y_speed))

        # 2. Perspectiva: Calcular la altura actual
        dynamic_height = self.update_scale()

        # 3. Recorte y escalado centrado
        x = self.current_frame * self.frame_w
        rect = QRect(x, 0, self.frame_w, self.frame_h)
        original_frame = self.full_sheet.copy(rect)
        
        # Escalamos el frame a la altura dinámica
        frame_scaled = original_frame.scaledToHeight(
            dynamic_height, Qt.TransformationMode.SmoothTransformation
        )
        
        # Definimos el tamaño fijo del lienzo centrado
        # Usamos el base_height original para que el contenedor no cambie
        canvas_w = int(self.base_height * self.canvas_margin)
        canvas_h = int(self.base_height * self.canvas_margin)
        canvas_size = QSize(canvas_w, canvas_h)
        
        # Creamos el lienzo transparente
        final_pixmap = QPixmap(canvas_size)
        final_pixmap.fill(Qt.GlobalColor.transparent)
        
        # Dibujamos centrado
        painter = QPainter(final_pixmap)
        x_offset = (canvas_size.width() - frame_scaled.width()) // 2
        y_offset = (canvas_size.height() - frame_scaled.height()) // 2
        painter.drawPixmap(x_offset, y_offset, frame_scaled)
        painter.end()

        # 4. Render final y tamaño fijo
        self.label.setPixmap(final_pixmap)
        # FIJAMOS EL TAMAÑO para que no tiemble
        self.setFixedSize(canvas_size) 
        self.label.setFixedSize(canvas_size)
        
        self.current_frame = (self.current_frame + 1) % self.cols
        
        # 5. Sincronizar bocadillo
        if self.bubble.isVisible():
            self.bubble.move(self.x() + (self.width()//2) - (self.bubble.width()//2), self.y() - 40)

    def change_state(self, new_state, speech_type=None):
        if self.current_state != new_state:
            self.current_state = new_state
            self.load_animation(new_state)
            if speech_type and random.random() < 0.3:
                phrases = self.config["dialogs"].get(speech_type, [])
                if phrases: self.bubble.speak(random.choice(phrases))

    def ai_think(self):
        if self.is_dragging: return
        
        dice = random.randint(1, 100)
        
        # 1. Decidir el estado principal
        if dice <= 40: 
            self.change_state("idle")
            self.current_y_speed = 0 # Se detiene en Y
        elif dice <= 80: 
            # Decidir dirección horizontal
            state = random.choice(["look_l", "look_r"])
            self.change_state(state)
            
            # 2. DECISIÓN ALEATORIA DE EJE Y (Subir/Bajar/Recto)
            y_dice = random.randint(1, 3)
            if y_dice == 1: # Sube
                self.current_y_speed = -2
            elif y_dice == 2: # Baja
                self.current_y_speed = 2
            else: # Recto
                self.current_y_speed = 0
                
        elif dice <= 90: 
            self.change_state("sleep")
            self.current_y_speed = 0
        else: 
            self.change_state("angry", "alarm")
            self.current_y_speed = 0

    # --- Arrastre X11 compatible ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            # Usamos position() para Qt6
            self.offset = event.position().toPoint()
            self.change_state("drag_id")
            self.bubble.hide()

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            # Cálculo de posición global estable
            new_pos = event.globalPosition().toPoint() - self.offset
            self.move(new_pos)
            if self.current_state != "drag_mv":
                self.change_state("drag_mv")

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
            self.change_state("idle")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    path = os.path.join(os.getcwd(), "assets/skins/default")
    pet = CyberPet(path)
    sys.exit(app.exec())