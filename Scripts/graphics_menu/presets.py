"""The quality presets' names, and what picking one does in the HUD graph: it
sets Quality, and nothing else.

What a preset *is* -- its scalability level, console overrides, grass layers
and lighting, and the look numbers shared by all four -- is one row of the
graphics table (gfx_stats.py, graphics_tuning.csv). gfx_tune_tick.py hands
the row to the HUD's BP_GraphicsTuner component whenever Quality moves, and
gfx_tuner.py applies it. So the GRAPHICS SETTINGS tab's preset row (the one
place the player picks a preset) and BeginPlay's default go through one path.
"""

from collections import namedtuple

from combat.graph import _connect, _pin, _set
from graphics_menu.gfx_stats import PRESET_LABELS, default_preset

# One preset, in the order the GRAPHICS SETTINGS tab's preset row steps through.
Preset = namedtuple("Preset", "label")
PRESETS = tuple(Preset(label) for label in PRESET_LABELS)
# The preset a player with no graphics save starts on: the row
# graphics_tuning.csv marks in its "default" column, as it stood at the
# build. BeginPlay then lays the save over it (gfx_save.py), and the first
# Tick applies whichever it is (gfx_tune_tick.py).
DEFAULT_PRESET = default_preset()


def emit_apply(ed, index, in_exec):
    """Set Quality to preset ``index``, hooked to ``in_exec``.

    BeginPlay's, for the startup default; the tab's preset row sets Quality
    from its pick (gfx_tune_tick.py).
    Returns the nodes it made, for the caller to wrap in a comment.
    """
    set_q = ed.add_set_member_variable_node("Quality")
    _set(set_q, "Quality", index)
    _connect(in_exec, _pin(set_q, "execute"))
    return [set_q]
