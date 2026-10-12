"""DrawHUD, with the I panel open: the character's portrait is the picture of
the player in what they wear (wear_consts has the names; the pictures are
item_icons/portrait.py's, one per set of the garments drawn on the body).

    WearPortraitIndex := 0
    for each garment that is drawn when worn (portrait.DRAWN_SLOTS, its bit
    its place there):
        Worn[its slot] is there (IsValidIndex, then IsValid) ->
            WearPortraitIndex += its bit
    WearPortraitIndex != WearPortraitShown ->
        WearPortraitImage's brush := WearPortraits[WearPortraitIndex]
        WearPortraitShown := WearPortraitIndex

Worn is the weapon component's, the array the worn slots are drawn from: on a
client it follows the server's record, so the picture does too. The brush is
set on a change only, and the widget starts on the bare picture, which is
index 0, WearPortraitShown's default.
"""

from graphics_menu.ui_graph import part
from graphics_menu.umg_consts import WBP_HUD
from graphics_menu.wear_consts import (
    WEAR_PORTRAIT_IMAGE, WEAR_PORTRAIT_INDEX_VAR, WEAR_PORTRAIT_SHOWN_VAR, WEAR_PORTRAITS_VAR,
)
from item_icons.portrait import DRAWN_SLOTS
from uebp.g import _G
from uebp.graph import _loose_pin, out, then
from uebp.nodes.array import FN_ARR_GET, FN_ARR_VALID
from uebp.nodes.math import FN_ADD_II, FN_NEQ_II
from uebp.nodes.system import FN_IS_VALID
from uebp.nodes.umg import FN_SET_BRUSH


def author_portrait_pick(ed, worn, in_execs):
    """The fragment (see the module docstring), off ``worn`` (the weapon
    component's Worn). Returns the exec tails."""
    g = _G(ed)
    flow = [g.put(WEAR_PORTRAIT_INDEX_VAR, "0", in_execs)]
    for bit, slot in enumerate(DRAWN_SLOTS):
        there, past = g.branch(
            out(g.call(FN_ARR_VALID, TargetArray=worn, IndexToTest=slot)), flow)
        item = _loose_pin(g.call(FN_ARR_GET, TargetArray=worn, Index=slot), "Item",
                          is_input=False)
        on, bare = g.branch(out(g.call(FN_IS_VALID, Object=item)), [there])
        more = g.call(FN_ADD_II, A=g.get(WEAR_PORTRAIT_INDEX_VAR), B=1 << bit)
        flow = [g.put(WEAR_PORTRAIT_INDEX_VAR, out(more), [on]), bare, past]
    index = g.get(WEAR_PORTRAIT_INDEX_VAR)
    changed, same = g.branch(
        out(g.call(FN_NEQ_II, A=index, B=g.get(WEAR_PORTRAIT_SHOWN_VAR))), flow)
    pictures = g.get(WEAR_PORTRAITS_VAR)
    known, wild = g.branch(
        out(g.call(FN_ARR_VALID, TargetArray=pictures, IndexToTest=index)), [changed])
    picture = _loose_pin(g.call(FN_ARR_GET, TargetArray=pictures, Index=index), "Item",
                         is_input=False)
    drawn = g.call(FN_SET_BRUSH, [known], self=part(ed, WBP_HUD, WEAR_PORTRAIT_IMAGE),
                   Texture=picture)
    shown = g.put(WEAR_PORTRAIT_SHOWN_VAR, index, [then(drawn)])
    ed.add_comment_to_nodes(
        "The character's portrait follows what is worn: one picture per set of the "
        "garments drawn on the body, its index their bits, the brush set when it "
        "changes (wear_portrait.py).", g.made)
    return [shown, same, wild]
