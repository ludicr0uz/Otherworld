"""Reading one stat of the preset being applied, in BP_GraphicsTuner's graph:
Values[Base + index]. Pure nodes, made afresh at each use.

The index is the literal on the Add's B pin, which is how gfx_tuner_checks
tells which stat a wire carries. The table is in a person's units
(gfx_stats.py); applied() is the number in the engine's.
"""

from combat.graph import _connect, _pin
from uebp.graph import out
from combat.nodes import FN_ADD_II, FN_ARR_GET, FN_MUL_FF
from graphics_menu.dev_guns import _call, _get
from graphics_menu.gfx_stats import GFX_STATS, index_of
from graphics_menu.gfx_tune_consts import TUNER_BASE_VAR, TUNER_VALUES_VAR

FN_ROUND = "/Script/Engine.KismetMathLibrary.Round"


def stat(ed, index, x, y, made):
    """Stat ``index`` of the applied preset: a float pin."""
    at = _call(ed, FN_ADD_II, x, y, made, A=_get(ed, TUNER_BASE_VAR, x - 240, y, made),
               B=index)
    cell = _call(ed, FN_ARR_GET, x + 240, y, made,
                 TargetArray=_get(ed, TUNER_VALUES_VAR, x, y + 140, made))
    _connect(out(at), _pin(cell, "Index"))
    return _pin(cell, "Item", is_input=False)


def applied(ed, index, x, y, made):
    """Stat ``index`` as the engine takes it: the table's number x the stat's
    scale (a percentage as a fraction). A float pin."""
    cell = stat(ed, index, x, y, made)
    scale = GFX_STATS[index].scale
    if scale == 1:
        return cell
    return out(_call(ed, FN_MUL_FF, x + 480, y, made, A=cell, B=scale))


def whole(ed, index, x, y, made):
    """The same, rounded: an int pin."""
    return out(_call(ed, FN_ROUND, x + 480, y, made, A=stat(ed, index, x, y, made)))


def column(ed, name, x, y, made, rounded=False):
    """A stat by its CSV column."""
    return (whole if rounded else stat)(ed, index_of(name), x, y, made)
