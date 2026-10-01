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

The title, settings and death screens need none of this: the world is paused
under them.
"""

from combat.graph import BEL, _connect, _pin
from combat.nodes import FN_NEQ_BB
from graphics_menu.dev_guns import _branch, _call, _get, _out
from graphics_menu.loot_find import put
from graphics_menu.loot_kneel import FN_IGNORE_MOVE

MENU_STILL_VAR = "MenuStill"


def author_menu_still(ed, pc_out, in_execs, x0, y0):
    """The fragment (see the module docstring). Returns the exec tails."""
    made = []
    changed = _call(ed, FN_NEQ_BB, x0 + 240, y0 + 300, made,
                    A=_get(ed, "MenuOpen", x0, y0 + 300, made),
                    B=_get(ed, MENU_STILL_VAR, x0, y0 + 440, made))
    edge, same = _branch(ed, _out(changed), in_execs, x0 + 500, y0, made)
    flow = put(ed, MENU_STILL_VAR, _get(ed, "MenuOpen", x0 + 520, y0 + 300, made),
               [edge], x0 + 760, y0, made)
    still = _call(ed, FN_IGNORE_MOVE, x0 + 1020, y0, made, self=pc_out,
                  bNewMoveInput=_get(ed, "MenuOpen", x0 + 780, y0 + 300, made))
    _connect(flow, _pin(still, "execute"))
    ed.add_comment_to_nodes(
        "The M panel holds the player still: the controller ignores move input "
        "while it is open, taken and given back on MenuOpen's edges, so the "
        "arrows only work the menu.", made)
    return [BEL.find_then_pin(still), same]
