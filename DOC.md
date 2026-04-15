# CyberPet — Documentación técnica

## Descripción general

CyberPet es una mascota virtual de escritorio construida con **Python + PyQt6**. Se renderiza como una ventana transparente y sin bordes que flota sobre todas las aplicaciones. El personaje está animado mediante spritesheets y reacciona al ratón (arrastre y lanzamiento). Incorpora un sistema de perspectiva simulada mediante un eje Z ficticio que escala al personaje según su posición vertical en pantalla.

---

## Estructura del proyecto

```
Archivador/
├── src/
│   └── main.py              # Código fuente principal
├── assets/
│   └── skins/
│       └── default/
│           ├── config.json  # Configuración del skin (física + animaciones)
│           └── *.png        # Spritesheets de cada estado
└── data/
    └── config.json          # Configuración global de la mascota
```

---

## Archivos de configuración

### `assets/skins/default/config.json` — Configuración del skin

Este es el archivo más importante. Controla toda la física, el entorno y las animaciones.

| Clave | Tipo | Valor por defecto | Descripción |
|---|---|---|---|
| `skin_name` | string | "CyberDroid Original" | Nombre del skin |
| `base_height` | int | 250 | Altura en píxeles del personaje a escala 1:1 |
| `start_x_pc` | float | 50 | Posición X inicial como % del ancho de pantalla |
| `start_y_pc` | float | 90 | Posición Y inicial como % del alto de pantalla |
| `gravity` | float | 1.2 | Aceleración gravitatoria en píxeles/tick² |
| `launch_multiplier` | float | 0.8 | Factor que amplifica la velocidad al soltar el personaje |
| `friction` | float | 0.95 | Fricción horizontal aplicada cada tick durante la caída |
| `z_step` | float | 5 | Variación máxima de `grab_y` por tick (profundidad Z) |

#### Subsección `environment`

Controla el sistema de perspectiva simulada.

| Clave | Tipo | Descripción |
|---|---|---|
| `mode` | string | `"perspective"` activa el escalado por profundidad; cualquier otro valor lo desactiva |
| `min_scale_percent` | int | Porcentaje mínimo de `base_height` cuando el personaje está al fondo (10 = 10%) |
| `walkable_y_min_pc` | int | Límite superior del área caminable (% del alto de pantalla) |
| `walkable_y_max_pc` | int | Límite inferior del área caminable (% del alto de pantalla) |

#### Subsección `animations`

Cada estado tiene una entrada con la siguiente estructura:

```json
"nombre_estado": {
    "file": "spritesheet.png",
    "cols": 6,
    "speed": 150,
    "move_speed": 0
}
```

| Clave | Descripción |
|---|---|
| `file` | Nombre del archivo PNG dentro de la carpeta del skin |
| `cols` | Número de columnas (frames) en el spritesheet horizontal |
| `speed` | Milisegundos entre frames |
| `move_speed` | Píxeles por tick que se desplaza en X (negativo = izquierda) |
| `gravity` | *(opcional)* Sobreescribe la gravedad global para este estado |

**Estados disponibles:**

| Estado | Descripción |
|---|---|
| `idle` | Animación de reposo |
| `look_l` / `look_r` | Mira a la izquierda/derecha sin moverse |
| `walk_l` / `walk_r` | Camina a la izquierda/derecha (`move_speed` ≠ 0) |
| `angry` | Animación de enfado |
| `drag_id` | Personaje cogido pero sin mover |
| `drag_mv` | Personaje siendo arrastrado activamente |
| `fall` | Personaje en caída libre tras ser lanzado |

### `data/config.json` — Configuración global

Actualmente es referencial. Los campos `pet_name`, `opacity`, `always_on_top` y `current_skin` están definidos aquí pero el código lee directamente la carpeta del skin.

---

## Clase principal: `CyberPet`

Hereda de `QMainWindow`. La ventana tiene tres flags de Qt:
- `FramelessWindowHint` — sin barra de título ni bordes
- `WindowStaysOnTopHint` — siempre encima de otras ventanas
- `Tool` — no aparece en la barra de tareas
- `WA_TranslucentBackground` — fondo transparente

### Variables de instancia

#### Posición y física

| Variable | Tipo | Inicialización | Descripción |
|---|---|---|---|
| `grab_y` | float | `set_initial_position()` | Posición Y del "suelo" actual del personaje. Todo lo que esté por encima se considera "aire". Es la referencia de la gravedad. |
| `vel_x` | float | 0.0 | Velocidad horizontal en píxeles/tick |
| `vel_y` | float | 0.0 | Velocidad vertical en píxeles/tick |
| `is_falling` | bool | False | True cuando el personaje está en caída libre |
| `is_dragging` | bool | False | True mientras el usuario arrastra |
| `last_mouse_pos` | QPoint | (0,0) | Posición del ratón en el tick anterior (para calcular velocidad) |
| `offset` | QPoint | set en mousePressEvent | Offset del click respecto a la esquina de la ventana |

#### Configuración de física (leídas del JSON)

| Variable | Descripción |
|---|---|
| `base_height` | Altura base del sprite en píxeles |
| `launch_mult` | Multiplicador de velocidad al lanzar |
| `friction` | Factor de fricción horizontal en caída (0-1) |
| `gravity_factor` | Aceleración gravitatoria por tick |
| `z_step` | Paso de variación Z por tick |

#### Renderizado

| Variable | Descripción |
|---|---|
| `locked_scale` | Escala fijada en el momento del drag (no varía mientras se arrastra) |
| `canvas_size_val` | Tamaño del canvas (= `base_height × 2`) |
| `real_sprite_size` | QSize con el tamaño real del sprite escalado en el tick actual |
| `full_sheet` | QPixmap con el spritesheet completo del estado actual |
| `frame_w` / `frame_h` | Dimensiones de un frame individual del spritesheet |
| `cols` | Número de columnas del spritesheet actual |
| `current_frame` | Índice del frame que se está mostrando |

#### Estado de la IA

| Variable | Descripción |
|---|---|
| `current_state` | String con el nombre del estado actual |
| `current_move_speed` | Velocidad X de movimiento autónomo (del JSON de la animación) |

---

## Inicialización del personaje

El flujo de `__init__` sigue este orden:

1. Se configura la ventana Qt (transparente, sin bordes, siempre encima).
2. Se crea un `QLabel` interno que actúa como lienzo de píxeles.
3. Se lee `config.json` del skin. Si falla, el proceso termina.
4. Se cargan las variables de física desde el JSON.
5. Se calcula el tamaño del canvas: `canvas_size_val = base_height × 2`.
6. Se llama a `load_animation("idle")` para cargar el primer spritesheet.
7. Se llama a `set_initial_position()` para colocar la ventana.
8. Se arrancan los dos timers (`anim_timer` y `ai_timer`).
9. Se hace visible la ventana (`show()`).

### `set_initial_position()`

Lee `start_x_pc` y `start_y_pc` del JSON (con defaults del 50% y 90%) y posiciona la ventana centrando el canvas en esas coordenadas. Al finalizar, `grab_y` queda igual que `self.y()`, estableciendo el suelo inicial.

---

## Bucle de animación: `update_animation()`

Se llama cada `speed` ms (por defecto 150 ms). Es el corazón del sistema. Ejecuta en orden:

### 1. Física (cuando `is_falling = True`)

```
vel_y += gravity_factor      # Aceleración
vel_x *= friction            # Fricción horizontal
new_x = x() + vel_x
new_y = y() + vel_y

si new_y >= grab_y y vel_y > 0:
    aterrizar → is_falling = False, cambiar a "idle"
```

### 2. Movimiento autónomo (cuando no está cayendo ni siendo arrastrado)

- Si el estado es `look_l`, `look_r`, `walk_l` o `walk_r`, aplica una variación aleatoria de `grab_y` de ±z_step para simular movimiento en profundidad.
- Clampea `grab_y` dentro de los límites `walkable_y_min_pc` y `walkable_y_max_pc`.
- Mueve la ventana a `(x + current_move_speed, grab_y)`.
- Llama a `check_screen_bounds()` para detectar colisiones con los bordes de pantalla.

### 3. Renderizado

- Llama a `update_scale()` para obtener la altura escalada.
- Recorta el frame actual del spritesheet con `full_sheet.copy(QRect(...))`.
- Escala el frame al tamaño calculado.
- Dibuja el frame centrado en un canvas transparente del tamaño de la ventana.
- Aplica el canvas al `QLabel` y actualiza la máscara de la ventana (para que solo sea clickable el área del sprite).
- Avanza `current_frame` al siguiente.

---

## Sistema de perspectiva (eje Z simulado)

La profundidad se simula escalando el tamaño del personaje según su posición Y. Cuanto más abajo en pantalla (más cerca del espectador), más grande; cuanto más arriba (más al fondo), más pequeño.

### `update_scale()` — Cálculo de escala

Solo funciona si `environment.mode == "perspective"`.

```
y_min = walkable_y_min_pc% de screen.height
y_max = walkable_y_max_pc% de screen.height − base_height
t = (grab_y − y_min) / (y_max − y_min)      # valor entre 0.0 y 1.0
min_f = min_scale_percent / 100              # ej: 0.10
altura = base_height × (min_f + t × (1 − min_f))
```

Con los valores del config por defecto (`min_scale_percent=10`, zona caminable 50%-100%):
- En el extremo superior de la zona: el sprite mide `base_height × 0.10` = 25 px
- En el extremo inferior: el sprite mide `base_height × 1.0` = 250 px

### Reglas de escala en situaciones especiales

| Situación | Comportamiento de escala |
|---|---|
| `is_falling = True` | Devuelve `locked_scale` (congelada) |
| `is_dragging = True` y `y < grab_y` | Devuelve `locked_scale` (en el aire) |
| `is_dragging = True` y `y >= grab_y` | Calcula escala normal según posición |

---

## Sistema de arrastre y lanzamiento

### `mousePressEvent()`

1. Cambia cursor a mano cerrada.
2. Congela la escala: `locked_scale = update_scale()`.
3. Si no está cayendo, fija `grab_y = y()`.
4. Activa `is_dragging = True`, cancela `is_falling`.
5. Eleva la ventana al frente (`raise_()`).
6. Guarda el offset del click y la posición del ratón.
7. Cambia el estado a `drag_id`.

### `mouseMoveEvent()`

1. Calcula la velocidad como diferencia entre la posición actual y la anterior del ratón, multiplicada por `launch_multiplier`.
2. Mueve la ventana a la posición del cursor menos el offset.
3. Actualiza `grab_y` si el personaje está siendo arrastrado hacia abajo.
4. Cambia el estado a `drag_mv`.

### `mouseReleaseEvent()`

Analiza si el personaje debe caer o posarse:

```
si y() < grab_y − 10  O  abs(vel_y) > 2:
    is_falling = True → estado "fall"
si no:
    vel_x = vel_y = 0 → estado "idle"
```

---

## IA autónoma: `ai_think()`

Se ejecuta cada 4 000 ms. Si el personaje está siendo arrastrado o cayendo, no hace nada. En caso contrario, genera un número aleatorio entre 1 y 100 y decide:

| Rango | Estado resultante | Probabilidad |
|---|---|---|
| 1–40 | `idle` | 40% |
| 41–85 | Aleatorio entre `look_l`, `look_r`, `walk_l`, `walk_r` | 45% |
| 86–100 | `angry` | 15% |

---

## Colisión con bordes de pantalla: `check_screen_bounds()`

Calcula la posición real del sprite (teniendo en cuenta que el canvas es más grande que el sprite) y comprueba si sobresale por la izquierda o la derecha:

- **Borde izquierdo:** mueve la ventana para que el sprite quede en el margen izquierdo; invierte `vel_x` con amortiguación × 0.6; cambia el estado a `look_r`.
- **Borde derecho:** idem en sentido contrario; cambia el estado a `look_l`.

---

## Cambio de estado: `change_state()`

Solo actúa si el nuevo estado es diferente al actual. Actualiza `current_state` y llama a `load_animation()` con el nuevo estado.

### `load_animation(state)`

1. Busca la entrada del estado en `config["animations"]`.
2. Carga el spritesheet con `QPixmap`.
3. Si la imagen falla, usa un rectángulo magenta como fallback.
4. Actualiza `gravity_factor`, `current_move_speed`, `frame_w`, `frame_h`, `cols`.
5. Reinicia `current_frame = 0`.
6. Reinicia `anim_timer` con la velocidad del nuevo estado.

---

## Timers

| Timer | Intervalo | Callback | Propósito |
|---|---|---|---|
| `anim_timer` | Variable (del JSON, por defecto 150 ms) | `update_animation` | Bucle principal: física + render |
| `ai_timer` | 4 000 ms | `ai_think` | Toma de decisiones autónomas |

---

## Punto de entrada

```python
if __name__ == "__main__":
    app = QApplication(sys.argv)
    skin_path = <directorio_del_script>/../assets/skins/default
    pet = CyberPet(skin_path)
    sys.exit(app.exec())
```

La ruta del skin se construye de forma relativa al script, por lo que el ejecutable debe lanzarse desde la carpeta `src/` o mediante el script `start.sh`.

---

## Debug en consola

En cada tick de `update_animation` se sobreescribe la misma línea de la consola con:

```
ESTADO: IDLE | POS: 940,980 | SPRITE: 250x250 | VEL: x:0.0, y:0.0 | G:1.2 F:0.95 L:0.8
```

Esto permite monitorear en tiempo real el estado, posición, tamaño del sprite y valores de física sin saturar el terminal.

---

## Cómo añadir un nuevo estado

1. Añadir el spritesheet PNG en `assets/skins/default/`.
2. Añadir la entrada en `config.json` dentro de `"animations"` con `file`, `cols`, `speed` y `move_speed`.
3. Llamar a `change_state("nombre_nuevo")` desde el código donde corresponda (por ejemplo en `ai_think` o en un evento de teclado).

## Cómo crear un nuevo skin

1. Crear una carpeta nueva en `assets/skins/nombre_skin/`.
2. Copiar y adaptar `config.json`.
3. Añadir los PNGs de cada animación.
4. Cambiar `skin_path` en el punto de entrada (o implementar la lectura de `data/config.json`).
