"""DrawHUD: a stat bar's group blinks while the bar is low.

    opacity = FLASH_DIM  if fraction < LOW_FRACTION and frac(t * FLASH_HZ) > 0.5
              1          otherwise

Written every frame, so a bar that recovers stops blinking at full opacity.
``t`` is real time: DrawHUD runs while the game is paused (the M panel), and
game time would freeze the blink half-way. Opacity rather than visibility, so
the group keeps its space and nothing around it moves.
"""

from combat.graph import _connect, _node, _pin, _set
from graphics_menu.ui_graph import FN_SELECT_FLOAT, FN_SET_OPACITY, _wire
from graphics_menu.umg_consts import FLASH_DIM, FLASH_HZ, LOW_FRACTION

FN_REAL_TIME = "/Script/Engine.GameplayStatics.GetRealTimeSeconds"
FN_MUL = "/Script/Engine.KismetMathLibrary.Multiply_DoubleDouble"
FN_FRACTION = "/Script/Engine.KismetMathLibrary.Fraction"
FN_LESS = "/Script/Engine.KismetMathLibrary.Less_DoubleDouble"
FN_GREATER = "/Script/Engine.KismetMathLibrary.Greater_DoubleDouble"
FN_AND = "/Script/Engine.KismetMathLibrary.BooleanAND"


def author_flash(ed, group, fraction, execs):
    """SetRenderOpacity on ``group`` from the bar's ``fraction`` (a float
    pin). Returns the exec pin to go on from."""
    low = _node(ed, FN_LESS)
    _connect(fraction, _pin(low, "A"))
    _set(low, "B", LOW_FRACTION)

    now = _node(ed, FN_REAL_TIME)
    beats = _node(ed, FN_MUL)
    _connect(_pin(now, "ReturnValue", is_input=False), _pin(beats, "A"))
    _set(beats, "B", FLASH_HZ)
    phase = _node(ed, FN_FRACTION)
    _connect(_pin(beats, "ReturnValue", is_input=False), _pin(phase, "A"))
    off = _node(ed, FN_GREATER)
    _connect(_pin(phase, "ReturnValue", is_input=False), _pin(off, "A"))
    _set(off, "B", 0.5)

    dim = _node(ed, FN_AND)
    _connect(_pin(low, "ReturnValue", is_input=False), _pin(dim, "A"))
    _connect(_pin(off, "ReturnValue", is_input=False), _pin(dim, "B"))
    pick = _node(ed, FN_SELECT_FLOAT)
    _set(pick, "A", FLASH_DIM)
    _set(pick, "B", 1.0)
    _connect(_pin(dim, "ReturnValue", is_input=False), _pin(pick, "bPickA"))

    fade = _node(ed, FN_SET_OPACITY)
    _connect(group, _pin(fade, "self"))
    _connect(_pin(pick, "ReturnValue", is_input=False), _pin(fade, "InOpacity"))
    return _wire(execs, fade)
