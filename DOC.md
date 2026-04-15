# CyberPet — Documentación técnica (v2)

## Descripción general

CyberPet es una mascota virtual de escritorio construida con **Python + PyQt6**. Se renderiza como una ventana transparente y sin bordes que flota sobre todas las aplicaciones. El personaje está animado mediante spritesheets y reacciona al ratón (arrastre y lanzamiento). Incorpora un sistema de perspectiva simulada mediante un eje Z ficticio que escala al personaje según su posición vertical en pantalla.

---

## Estructura del proyecto

```
Archivador/
├── src/
│   ├── main.py          # Coordinador principal (CyberPet + punto de entrada)
│   ├── physics.py       # Motor de física (gravedad, fricción, drag, rebotes)
│   ├── perspective.py   # Sistema de perspectiva simulada (eje Z)
│   ├── renderer.py      # Carga de spritesheets y composición de frames
│   ├── ai.py            # Inteligencia artificial autónoma
│   └── debug.py         # HUD de debug en consola (in-place)
├── assets/
│   └── skins/
│       └── default/
│           ├── config.json  # Configuración del skin (física + animaciones)
│           └── *.png        # Spritesheets de cada estado
└── data/
    └── config.json          # Configuración global (referencial)
```

---

## Arquitectura de módulos

La lógica que antes residía en un único archivo (`main.py`) está ahora repartida en módulos con responsabilidades bien definidas. La clase `CyberPet` en `main.py` actúa como **coordinador**: recibe eventos de Qt y delega la lógica en los subsistemas.

```
main.py (CyberPet)
    ├── physics.py      → PhysicsEngine
    ├── perspective.py  → PerspectiveSystem
    ├── renderer.py     → SpriteRenderer
    ├── ai.py           → AIBrain
    └── debug.py        → DebugHUD
```

### Regla de dependencias

Los módulos de lógica pura (`physics`, `perspective`, `ai`, `debug`) **no importan Qt**. Solo `main.py` y `renderer.py` dependen de PyQt6, lo que facilita el testing unitario de la lógica sin necesidad de un entorno gráfico.

---

## Archivos de configuración

### `assets/skins/default/config.json` — Configuración del skin

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

| Clave | Tipo | Descripción |
|---|---|---|
| `mode` | string | `"perspective"` activa el escalado por profundidad |
| `min_scale_percent` | int | Porcentaje mínimo de `base_height` cuando el personaje está al fondo |
| `walkable_y_min_pc` | int | Límite superior del área caminable (% del alto de pantalla) |
| `walkable_y_max_pc` | int | Límite inferior del área caminable (% del alto de pantalla) |

#### Subsección `animations`

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
| `file` | Nombre del PNG dentro de la carpeta del skin |
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

---

## Módulo `physics.py` — PhysicsEngine

Encapsula todo el estado físico del personaje. No conoce Qt ni renderizado.

### Variables de estado

| Variable | Tipo | Descripción |
|---|---|---|
| `vel_x` | float | Velocidad horizontal actual (px/tick) |
| `vel_y` | float | Velocidad vertical actual (px/tick) |
| `is_falling` | bool | True mientras el personaje está en caída libre |
| `is_dragging` | bool | True mientras el usuario arrastra |
| `grab_y` | float | Coordenada Y del suelo actual. El personaje aterriza cuando `y >= grab_y` |
| `gravity_factor` | float | Aceleración por tick (px/tick²); puede sobreescribirse por animación |
| `friction` | float | Factor de fricción horizontal en caída (0–1) |
| `launch_mult` | float | Multiplicador de velocidad al soltar el drag |
| `z_step` | float | Variación máxima de grab_y por tick (profundidad) |

### Métodos principales

| Método | Descripción |
|---|---|
| `tick_fall(x, y)` | Aplica gravedad y fricción; devuelve `(new_x, new_y, landed)` |
| `tick_autonomous(x, speed, state, y_min, y_max)` | Movimiento autónomo con variación Z; devuelve `(new_x, new_grab_y)` |
| `start_drag(locked_y)` | Inicializa el estado de arrastre |
| `update_drag_velocity(dx, dy)` | Actualiza velocidad durante el drag |
| `update_grab_y_on_drag(window_y)` | Actualiza el suelo si el personaje desciende durante el drag |
| `release_drag()` | Finaliza el drag; devuelve `True` si debe iniciar caída |
| `bounce_horizontal(direction)` | Invierte y amortigua vel_x al rebotar en un borde |
| `set_gravity(value)` | Actualiza gravity_factor (llamado por cada animación) |

---

## Módulo `perspective.py` — PerspectiveSystem

Calcula la altura visual del sprite en función de su posición Y.

### Fórmula de escala

```
t = clamp((grab_y − y_min) / (y_max − y_min), 0.0, 1.0)
altura = base_height × (min_factor + t × (1 − min_factor))
```

Con `min_scale_percent=10` y zona caminable 50%–100%:
- En `y_min` → sprite de 25 px (10% de 250)
- En `y_max` → sprite de 250 px (100% de 250)

### Reglas de escala en situaciones especiales

| Situación | Comportamiento |
|---|---|
| `is_falling = True` | Devuelve `locked_scale` (escala congelada) |
| `is_dragging = True` y `window_y < grab_y` | Devuelve `locked_scale` (en el aire) |
| `is_dragging = True` y `window_y >= grab_y` | Calcula escala normal |
| `mode != "perspective"` | Devuelve `base_height` (sin escalado) |

### Métodos

| Método | Descripción |
|---|---|
| `compute_scale(...)` | Devuelve la altura del sprite en píxeles para este tick |
| `walkable_bounds(screen_height)` | Devuelve `(y_min, y_max)` en píxeles absolutos |

---

## Módulo `renderer.py` — SpriteRenderer

Gestiona la carga de spritesheets y la composición de cada frame.

### Proceso de renderizado (por tick)

1. Calcula el ancho proporcional a `sprite_height` (ratio del frame)
2. Recorta el frame actual del spritesheet con `QPixmap.copy(QRect(...))`
3. Escala el frame al tamaño calculado (smooth, mantiene aspecto)
4. Dibuja el frame centrado en un canvas transparente de `canvas_size × canvas_size`
5. Avanza `current_frame` al siguiente (con wrap-around)

### Variables de estado

| Variable | Descripción |
|---|---|
| `full_sheet` | QPixmap con el spritesheet completo del estado actual |
| `frame_w` / `frame_h` | Dimensiones de un frame individual |
| `cols` | Número de frames en el spritesheet |
| `current_frame` | Índice del frame que se está mostrando |
| `real_sprite_size` | QSize con el tamaño real del sprite escalado (usado por colisión) |

### Fallback

Si el PNG no existe o está corrupto, `load_sheet()` genera un rectángulo magenta semitransparente para facilitar la depuración visual.

---

## Módulo `ai.py` — AIBrain

Decide el estado del personaje de forma autónoma cada 4 000 ms.

### Tabla de decisiones

| Rango | Estado resultante | Probabilidad |
|---|---|---|
| 1–40 | `idle` | 40% |
| 41–85 | Aleatorio entre `look_l`, `look_r`, `walk_l`, `walk_r` | 45% |
| 86–100 | `angry` | 15% |

Para añadir nuevos comportamientos, modifica la constante `DECISION_TABLE` en `ai.py`. La tabla usa probabilidad acumulada y debe sumar 100.

### Método principal

| Método | Descripción |
|---|---|
| `think(is_dragging, is_falling)` | Ejecuta un ciclo de decisión; no hace nada si el personaje está siendo controlado |

---

## Módulo `debug.py` — DebugHUD

Imprime una línea de estado en el terminal sobreescribiéndola en cada tick.

### Formato de salida

```
ESTADO: IDLE         | POS:  940, 980 | SPRITE: 250x250 | VEL: x: +0.0, y: +0.0 | G:1.20 F:0.95 L:0.80
```

Usa los códigos ANSI `\r\033[2K` para volver al inicio de la línea y borrarla antes de escribir. En terminales sin soporte ANSI (ej. CMD de Windows sin modo ANSI), degrada a simples retornos de carro.

### Métodos auxiliares

| Método | Descripción |
|---|---|
| `print(...)` | Sobreescribe la línea actual con el estado del personaje |
| `DebugHUD.error(msg)` | Imprime un error en una nueva línea |
| `DebugHUD.warn(msg)` | Imprime un aviso en una nueva línea |
| `DebugHUD.info(msg)` | Imprime un mensaje informativo en una nueva línea |

---

## Clase principal: `CyberPet` (main.py)

Hereda de `QMainWindow`. Actúa como coordinador de todos los subsistemas.

### Flags de la ventana Qt

- `FramelessWindowHint` — sin barra de título ni bordes
- `WindowStaysOnTopHint` — siempre encima de otras ventanas
- `Tool` — no aparece en la barra de tareas
- `WA_TranslucentBackground` — fondo transparente

### Timers

| Timer | Intervalo | Callback | Propósito |
|---|---|---|---|
| `anim_timer` | Variable (del JSON, por defecto 150 ms) | `update_animation` | Bucle principal: física + render |
| `ai_timer` | 4 000 ms | `ai_brain.think` | Toma de decisiones autónomas |

### Flujo de `update_animation()`

```
1. Física
   ├── is_falling  → _tick_falling()  → physics.tick_fall()
   └── autónomo    → _tick_autonomous() → physics.tick_autonomous()

2. Colisión con bordes → _check_screen_bounds() → physics.bounce_horizontal()

3. Perspectiva → perspective.compute_scale()

4. Renderizado → renderer.render_frame() → label.setPixmap() + setMask()

5. Debug → hud.print()
```

### Eventos de ratón

#### `mousePressEvent`
1. Cursor → mano cerrada
2. Congela la escala (`locked_scale = perspective.compute_scale(...)`)
3. `physics.start_drag(y_actual)`
4. Eleva la ventana al frente (`raise_()`)
5. Guarda offset del click y posición del ratón
6. `change_state("drag_id")`

#### `mouseMoveEvent`
1. Calcula delta del ratón y actualiza `physics.update_drag_velocity(dx, dy)`
2. Mueve la ventana: `self.move(cursor − offset)`
3. `physics.update_grab_y_on_drag(y_actual)`
4. `change_state("drag_mv")`

#### `mouseReleaseEvent`
1. Cursor → mano abierta
2. `physics.release_drag()` → devuelve `should_fall`
3. Si `should_fall` → `change_state("fall")`; si no → `change_state("idle")`

---

## Bucle de animación detallado

### Caída libre (`_tick_falling`)

```
vel_y += gravity_factor
vel_x *= friction
new_x = x + vel_x
new_y = y + vel_y

si new_y >= grab_y y vel_y > 0:
    aterrizar → is_falling = False, vel = 0, change_state("idle")

mover ventana a (new_x, new_y)
_check_screen_bounds()
```

### Movimiento autónomo (`_tick_autonomous`)

```
si estado en {look_l, look_r, walk_l, walk_r}:
    grab_y += random.choice([-1, 0, 1]) * z_step
    grab_y = clamp(grab_y, y_min, y_max)

new_x = x + current_move_speed
mover ventana a (new_x, grab_y)
_check_screen_bounds()
```

---

## Colisión con bordes de pantalla

`_check_screen_bounds()` calcula la posición real del sprite (no del canvas) y actúa si sobresale:

- **Borde izquierdo:** recoloca el sprite en el margen; `vel_x = +abs(vel_x) × 0.6`; `change_state("look_r")`
- **Borde derecho:** idem en sentido contrario; `vel_x = -abs(vel_x) × 0.6`; `change_state("look_l")`

La amortiguación de 0.6 evita rebotes infinitos y da naturalidad al movimiento.

---

## Cómo añadir un nuevo estado

1. Añadir el spritesheet PNG en `assets/skins/default/`.
2. Añadir la entrada en `config.json` dentro de `"animations"`.
3. Llamar a `change_state("nombre_nuevo")` desde `ai.py` (tabla `DECISION_TABLE`) o desde `main.py`.

## Cómo crear un nuevo skin

1. Crear una carpeta nueva en `assets/skins/nombre_skin/`.
2. Copiar y adaptar `config.json`.
3. Añadir los PNGs de cada animación.
4. Cambiar `skin_path` en el punto de entrada de `main.py`.

## Cómo desactivar el debug

En `main.py`, al crear el `DebugHUD`:

```python
self.hud = DebugHUD(enabled=False)
```

## Punto de entrada

```python
if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_dir  = os.path.dirname(os.path.abspath(__file__))
    skin_path = os.path.abspath(os.path.join(main_dir, "..", "assets", "skins", "default"))
    pet = CyberPet(skin_path)
    sys.exit(app.exec())
```

Lanzar siempre desde la carpeta `src/` o mediante el script `start.sh` del proyecto.
