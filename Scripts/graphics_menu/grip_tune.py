"""The GUN SETTINGS tab's grip rows: the last six rows of the tab are the
HELD item's row of the nudge table (combat/grip_nudges.py), whichever weapon
the tab shows.

    TuneOpen, before the tab's keys and nudge:
        TuneValues[shown weapon's grip cells] := the held item's row
                                                 (zeros with empty hands)
    TuneOpen, after them:
        the held item's row := those cells; where one changed, the item is
        seated anew that frame and grip_nudges.csv is written

Both halves are one C++ node each (UOtherworldGripLibrary: ReadGripCells,
WriteGripCells), which hold the table every machine seats by. So the tab's
own nudge (tune_tick._author_nudge) steps a grip cell like any other, and
nothing here knows which row the caret is on. The cells are a working copy
for the one Tick: the table in C++ is the truth, which is why a kept save
(tune_keep.py) of them is never read by anything, and why Enter's CSV save
(tune_save.py) leaves them out.

A nudge reaches this machine's table alone: on a server the other machines
keep the file's rows until they are launched again.
"""

from uebp.graph import _connect, _pin, out, then
from graphics_menu.dev_guns import _branch, _call, _get
from graphics_menu.tune_consts import (
    GRIP_FIRST, STAT_COUNT, TUNE_OPEN_VAR, TUNE_VALUES_VAR, TUNE_WEAPON_VAR,
)
from uebp.nodes.actor import FN_GET_OWNING_PAWN
from uebp.nodes.grip import FN_HELD_ITEM_OF, FN_READ_GRIP_CELLS, FN_WRITE_GRIP_CELLS
from uebp.nodes.math import FN_ADD_II, FN_MUL_II


def _author_cells(ed, fn, in_execs, made):
    """``fn`` (the read or the write) over the held item and the shown
    weapon's grip cells, while the tab is open. Returns the exec tails."""
    go, shut = _branch(ed, _get(ed, TUNE_OPEN_VAR, made), in_execs, made)
    pawn = out(_call(ed, FN_GET_OWNING_PAWN, made))
    held = out(_call(ed, FN_HELD_ITEM_OF, made, Pawn=pawn))
    base = _call(ed, FN_MUL_II, made, A=_get(ed, TUNE_WEAPON_VAR, made), B=STAT_COUNT)
    first = out(_call(ed, FN_ADD_II, made, A=out(base), B=GRIP_FIRST))
    cells = _call(ed, fn, made, Item=held, Table=_get(ed, TUNE_VALUES_VAR, made),
                  First=first)
    _connect(go, _pin(cells, "execute"))
    return [then(cells), shut]


def author_grip_read(ed, in_execs, made):
    """Before the tab's flow: the grip cells show the held item's row."""
    return _author_cells(ed, FN_READ_GRIP_CELLS, in_execs, made)


def author_grip_write(ed, in_execs, made):
    """After the tab's flow: a grip cell the nudge moved moves the item."""
    return _author_cells(ed, FN_WRITE_GRIP_CELLS, in_execs, made)
