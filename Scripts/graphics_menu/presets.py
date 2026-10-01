"""The quality presets' names and keys, and what picking one does in the HUD
graph: it sets Quality, and nothing else.

What a preset *is* -- its scalability level, console overrides, grass layers
and lighting, and the look numbers shared by all four -- is one row of the
graphics table (gfx_stats.py, graphics_tuning.csv). gfx_tune_tick.py hands
the row to the HUD's BP_GraphicsTuner component whenever Quality moves, and
gfx_tuner.py applies it. So a key press, a click, the GRAPHICS TUNING tab's
preset row and BeginPlay's default all go through one path.
"""

from collections import namedtuple

from combat.graph import _at, _connect, _pin, _set
from graphics_menu.gfx_stats import PRESET_LABELS

# One preset, in menu order: the M panel's rows, top to bottom.
Preset = namedtuple("Preset", "label")
PRESETS = tuple(Preset(label) for label in PRESET_LABELS)
# Keys 1-4.  UE's FKey names for the number row are One/Two/Three/Four.
#
# These go into the pin verbatim, NOT as struct text: FKey overrides
# ExportTextItem to write just the key name, so a pin set to '(KeyName="M")'
# imports back as a key literally called "(" -- it compiles, it saves, and the
# key silently never matches at runtime.
PRESET_KEYS = ("One", "Two", "Three", "Four")
assert len(PRESET_KEYS) == len(PRESETS)

# The preset every session starts at. Settings are never saved, so every
# launch starts here; the first Tick applies it (gfx_tune_tick.py).
DEFAULT_PRESET = 0  # Low


def emit_apply(ed, index, x, y, in_exec):
    """Set Quality to preset ``index``, hooked to ``in_exec``.

    Shared by BeginPlay (the startup default) and by each preset key.
    Returns the nodes it made, for the caller to wrap in a comment.
    """
    set_q = _at(ed.add_set_member_variable_node("Quality"), x, y)
    _set(set_q, "Quality", index)
    _connect(in_exec, _pin(set_q, "execute"))
    return [set_q]
