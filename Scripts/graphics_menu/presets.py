"""The quality presets' names, and what picking one does in the HUD graph: it
sets Quality, and nothing else.

What a preset *is* -- its scalability level, console overrides, grass layers
and lighting, and the look numbers shared by all four -- is one row of the
graphics table (gfx_stats.py, graphics_tuning.csv). gfx_tune_tick.py hands
the row to the HUD's BP_GraphicsTuner component whenever Quality moves, and
gfx_tuner.py applies it. So the GRAPHICS TUNING tab's preset row (the one
place the player picks a preset) and BeginPlay's default go through one path.
"""

from collections import namedtuple

from combat.graph import _at, _connect, _pin, _set
from graphics_menu.gfx_stats import PRESET_LABELS

# One preset, in the order the GRAPHICS TUNING tab's preset row steps through.
Preset = namedtuple("Preset", "label")
PRESETS = tuple(Preset(label) for label in PRESET_LABELS)
# The preset every session starts at. Settings are never saved, so every
# launch starts here; the first Tick applies it (gfx_tune_tick.py).
DEFAULT_PRESET = 0  # Low


def emit_apply(ed, index, x, y, in_exec):
    """Set Quality to preset ``index``, hooked to ``in_exec``.

    BeginPlay's, for the startup default; the tab's preset row sets Quality
    from its pick (gfx_tune_tick.py).
    Returns the nodes it made, for the caller to wrap in a comment.
    """
    set_q = _at(ed.add_set_member_variable_node("Quality"), x, y)
    _set(set_q, "Quality", index)
    _connect(in_exec, _pin(set_q, "execute"))
    return [set_q]
