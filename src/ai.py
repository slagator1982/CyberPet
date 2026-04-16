"""
ai.py — Sistema de inteligencia artificial autónoma de CyberPet
===============================================================
Decide qué estado adopta el personaje de forma aleatoria cuando
no está siendo controlado por el usuario (sin drag, sin caída).

La toma de decisiones se basa en una tabla de probabilidades simple
que puede extenderse fácilmente añadiendo nuevas entradas.

Este módulo es puramente lógico: no tiene dependencias de Qt.
"""

import random
from typing import Callable


# ──────────────────────────────────────────────────────────────────────────────
# Tabla de decisiones
# ──────────────────────────────────────────────────────────────────────────────
# Cada entrada es (probabilidad_acumulada, estado_o_lista_de_estados).
# La lista se usa para elegir aleatoriamente entre varios estados equivalentes.
# La suma de pesos debe ser 100.
#
# Para añadir un nuevo comportamiento:
#   1. Reduce el peso de algún estado existente
#   2. Añade una nueva entrada con el nombre del estado y su peso
#   3. Asegúrate de que el estado esté definido en config.json
#

# DECISION_TABLE = [
#     (40, ("idle", None)),
#     (85, (["look_l", "look_r", "walk_l", "walk_r"], "glitch")),
#     (100, ("angry", "alarm")),
# ]
DECISION_TABLE = [
    (40, ("idle", None)),
    (85, (["look_l", "look_r", "walk_l", "walk_r"], "glitch")),
    (100, ("angry", "alarm")),
]



class AIBrain:
    """
    Motor de IA autónoma del personaje.

    Cada vez que se llama a `think()`, genera un número aleatorio
    y selecciona un estado según la tabla de probabilidades.
    La decisión se comunica a través de un callback para no acoplar
    este módulo a la clase principal.
    """

    def __init__(self, on_state_change: Callable[[str], None]):
        """
        Args:
            on_state_change : función que se llamará con el nombre del nuevo estado.
                              Normalmente es `CyberPet.change_state`.
        """
        self._on_state_change = on_state_change

    # ──────────────────────────────────────────────────────────────────────
    # Toma de decisión
    # ──────────────────────────────────────────────────────────────────────

    def think(self, is_dragging: bool, is_falling: bool, speech_key=None):
        """
        Ejecuta un ciclo de decisión autónoma.

        No hace nada si el personaje está siendo controlado por el usuario
        (arrastre) o si está en caída libre.

        Args:
            is_dragging : True si el usuario está arrastrando el personaje
            is_falling  : True si el personaje está en caída libre
        """
        # No interrumpir acciones controladas por el usuario o por la física
        if is_dragging or is_falling:
            return

        roll = random.randint(1, 100)
        for threshold, outcome in DECISION_TABLE:
            if roll <= threshold:
                states, speech_key = outcome # Desempaquetamos la tupla
                chosen_state = random.choice(states) if isinstance(states, list) else states
                
                # Pasamos ambos parámetros al callback
                self._on_state_change(chosen_state, speech_key) 
                return
