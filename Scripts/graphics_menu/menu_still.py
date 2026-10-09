"""The M panel holds the player still: while it is open the arrows (and the
move keys) work the menu, not the character.

    every Tick:
        MenuOpen != MenuStill  ->  MenuStill = MenuOpen
                                   controller.SetIgnoreMoveInput(MenuOpen)

The panel does not pause the game, and the stock input mapping walks the
character on the arrow keys as well as on WASD, so Up / Down on a row also
walked it off. Only the walk is taken: the view is already still (the panel
frees the cursor, which stops the mouse-look, cursor.py) and the weapon
component's keys are its own.

SetIgnoreMoveInput counts its calls, so it is made on the edge only, as the
loot window's is (loot_kneel.py; the two counts stack, and each gives back
its own). MenuStill is that edge's memory. Tick, not DrawHUD: a -nullrhi run
never draws, and the probe has to see it.

The same on the title, where the menu is held open: the world is paused
under it, the HUD ticks all the same (menu_main.py), and the first row gives
the walk back as it starts the game. The death screen needs none of this.
"""

from uebp.graph import _connect, _pin, out, then
from graphics_menu.dev_guns import _branch, _call, _get
from graphics_menu.loot_find import put
from uebp.nodes.actor import FN_IGNORE_MOVE
from uebp.nodes.math import FN_NEQ_BB
from graphics_menu import hud_vars as MV

MENU_STILL_VAR = MV.MenuStill


def author_menu_still(ed, pc_out, in_execs):
    """The fragment (see the module docstring). Returns the exec tails."""
    made = []
    changed = _call(ed, FN_NEQ_BB, made,
                    A=_get(ed, MV.MenuOpen, made),
                    B=_get(ed, MENU_STILL_VAR, made))
    edge, same = _branch(ed, out(changed), in_execs, made)
    flow = put(ed, MENU_STILL_VAR, _get(ed, MV.MenuOpen, made), [edge], made)
    still = _call(ed, FN_IGNORE_MOVE, made, self=pc_out, bNewMoveInput=_get(ed, MV.MenuOpen, made))
    _connect(flow, _pin(still, "execute"))
    ed.add_comment_to_nodes(
        "The M panel holds the player still: the controller ignores move input "
        "while it is open, taken and given back on MenuOpen's edges, so the "
        "arrows only work the menu.", made)
    return [then(still), same]
