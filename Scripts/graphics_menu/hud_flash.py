"""DrawHUD: a stat bar's group blinks while the bar is low.

    opacity = FLASH_DIM  if fraction < LOW_FRACTION and frac(t * FLASH_HZ) > 0.5
              1          otherwise

Written every frame, so a bar that recovers stops blinking at full opacity.
``t`` is real time: DrawHUD runs while the game is paused (the M panel), and
game time would freeze the blink half-way. Opacity rather than visibility, so
the group keeps its space and nothing around it moves.
"""

from uebp.graph import _connect, _node, _pin, _set, out
from graphics_menu.ui_graph import _wire
from graphics_menu.umg_consts import FLASH_DIM, FLASH_HZ, LOW_FRACTION
from uebp.nodes.math import (
    FN_AND, FN_FRACTION, FN_GREATER_FF, FN_LESS_FF, FN_MUL_FF, FN_SELECT_FF)
from uebp.nodes.system import FN_REAL_TIME
from uebp.nodes.umg import FN_SET_OPACITY


def author_flash(ed, group, fraction, execs):
    """SetRenderOpacity on ``group`` from the bar's ``fraction`` (a float
    pin). Returns the exec pin to go on from."""
    low = _node(ed, FN_LESS_FF)
    _connect(fraction, _pin(low, "A"))
    _set(low, "B", LOW_FRACTION)

    now = _node(ed, FN_REAL_TIME)
    beats = _node(ed, FN_MUL_FF)
    _connect(out(now), _pin(beats, "A"))
    _set(beats, "B", FLASH_HZ)
    phase = _node(ed, FN_FRACTION)
    _connect(out(beats), _pin(phase, "A"))
    off = _node(ed, FN_GREATER_FF)
    _connect(out(phase), _pin(off, "A"))
    _set(off, "B", 0.5)

    dim = _node(ed, FN_AND)
    _connect(out(low), _pin(dim, "A"))
    _connect(out(off), _pin(dim, "B"))
    pick = _node(ed, FN_SELECT_FF)
    _set(pick, "A", FLASH_DIM)
    _set(pick, "B", 1.0)
    _connect(out(dim), _pin(pick, "bPickA"))

    fade = _node(ed, FN_SET_OPACITY)
    _connect(group, _pin(fade, "self"))
    _connect(out(pick), _pin(fade, "InOpacity"))
    return _wire(execs, fade)
