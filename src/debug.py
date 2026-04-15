"""
debug.py — Sistema de debug en consola de CyberPet
===================================================
Muestra información en tiempo real del estado del personaje
sobreescribiendo siempre la misma línea del terminal,
sin saturar la salida con nuevas líneas en cada tick.

Formato de salida:
    ESTADO: IDLE | POS: 940,980 | SPRITE: 250x250 | VEL: x:0.0, y:0.0 | G:1.2 F:0.95 L:0.8

Este módulo no tiene dependencias de Qt ni de los demás módulos del proyecto.
"""

import sys


class DebugHUD:
    """
    Renderiza una línea de debug en la consola que se actualiza in-place.

    Usa el código ANSI \\r\\033[2K para volver al inicio de la línea y
    borrar su contenido antes de escribir los nuevos datos.
    En terminales que no soporten ANSI (ej. CMD de Windows sin ANSI),
    el comportamiento degrada a simples retornos de carro.
    """

    def __init__(self, enabled: bool = True):
        """
        Args:
            enabled : si False, el HUD no imprime nada (útil para tests).
        """
        self.enabled = enabled

    # ──────────────────────────────────────────────────────────────────────
    # Impresión del HUD
    # ──────────────────────────────────────────────────────────────────────

    def print(
        self,
        state: str,
        x: int,
        y: int,
        sprite_w: int,
        sprite_h: int,
        vel_x: float,
        vel_y: float,
        gravity: float,
        friction: float,
        launch_mult: float,
    ):
        """
        Sobreescribe la línea actual del terminal con el estado actual del personaje.

        Args:
            state       : nombre del estado actual (ej. "idle", "walk_l")
            x, y        : posición de la ventana en pantalla (píxeles)
            sprite_w    : ancho real del sprite escalado (píxeles)
            sprite_h    : alto real del sprite escalado (píxeles)
            vel_x       : velocidad horizontal actual (px/tick)
            vel_y       : velocidad vertical actual (px/tick)
            gravity     : valor de gravedad activo (px/tick²)
            friction    : factor de fricción horizontal activo (0–1)
            launch_mult : multiplicador de velocidad de lanzamiento
        """
        if not self.enabled:
            return

        line = (
            f"ESTADO: {state.upper():12s} | "
            f"POS: {x:4d},{y:4d} | "
            f"SPRITE: {sprite_w:3d}x{sprite_h:3d} | "
            f"VEL: x:{vel_x:+6.1f}, y:{vel_y:+6.1f} | "
            f"G:{gravity:.2f} F:{friction:.2f} L:{launch_mult:.2f}"
        )

        # \r vuelve al inicio de la línea; \033[2K borra la línea completa (ANSI)
        sys.stdout.write(f"\r\033[2K{line}")
        sys.stdout.flush()

    # ──────────────────────────────────────────────────────────────────────
    # Mensajes de error y advertencia
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def error(message: str):
        """
        Imprime un mensaje de error en una nueva línea para que no se mezcle
        con la línea de debug en curso.

        Args:
            message : texto del error a mostrar
        """
        sys.stdout.write(f"\n[ERROR] {message}\n")
        sys.stdout.flush()

    @staticmethod
    def warn(message: str):
        """
        Imprime un aviso en una nueva línea.

        Args:
            message : texto del aviso
        """
        sys.stdout.write(f"\n[WARN]  {message}\n")
        sys.stdout.flush()

    @staticmethod
    def info(message: str):
        """
        Imprime un mensaje informativo en una nueva línea.

        Args:
            message : texto informativo
        """
        sys.stdout.write(f"\n[INFO]  {message}\n")
        sys.stdout.flush()
