"""What a player starts out wearing: the pants, on from the first frame.

BeginPlay, with authority, after the loadout (inventory.py calls this):

    StarterPantsClass a class (build_clothing.py fills it, clothing/starter.py;
    None until then, and the player starts bare) -->
        one spawned, not Dropped, UNPLACED and hidden, as a wear leaves a
        garment (wear.py), put into Worn[its ClothingSlot] (grown to fit) and
        drawn on the body (DrawWorn: wear_draw.py)

It never passes through the bag or the hand. It is a worn garment like any
other from there: the record carries it to the clients (view_worn.py draws
it there; a dedicated server draws no one), the I panel takes it off, a
saved profile keeps what it found (a profile saved with the pants off takes
these off again: its ViewWorn of none for the slot), and the figure on the
title, which is this character, stands in them.
"""

from uebp.g import _G
from uebp.graph import _connect, _palette, _pin, _set, out, then
from combat import item_vars as IV
from combat.paths import ITEM_CLASS_PATH
from combat.slot_tuning import SLOT_VAR, UNPLACED
from combat.wear_tuning import CLOTHING_SLOT_VAR, STARTER_PANTS_CLASS_VAR, WORN_VAR
from combat.weapon_component.wear_draw import draw_worn
from uebp.nodes.actor import FN_SET_HIDDEN
from uebp.nodes.array import FN_ARR_SET
from uebp.nodes.palette import NODE_SPAWN
from uebp.nodes.system import FN_IS_VALID_CLASS


def author_starter_worn(ed, spawn_at, exec_in, made):
    """The starting garment worn (see the module docstring). Returns the
    exec tails: worn, and no class to wear."""
    g = _G(ed, ITEM_CLASS_PATH)
    cls = g.get(STARTER_PANTS_CLASS_VAR)
    some, none = g.branch(out(g.call(FN_IS_VALID_CLASS, Class=cls)), [exec_in])
    spawn = g.keep(_palette(ed, NODE_SPAWN))
    _connect(cls, _pin(spawn, "Class"))
    _connect(spawn_at, _pin(spawn, "SpawnTransform"))
    _set(spawn, "CollisionHandlingOverride", "AlwaysSpawn")
    _connect(some, _pin(spawn, "execute"))
    item = out(spawn)
    flow = g.iput(item, IV.Dropped, "false", [then(spawn)])
    flow = g.iput(item, SLOT_VAR, str(UNPLACED), [flow])
    slot_n = g.keep(ed.add_get_member_variable_node(CLOTHING_SLOT_VAR, ITEM_CLASS_PATH))
    _connect(item, _pin(slot_n, "self"))
    put = g.call(FN_ARR_SET, [flow], TargetArray=g.get(WORN_VAR),
                 Index=out(slot_n, CLOTHING_SLOT_VAR), Item=item)
    _set(put, "bSizeToFit", True)
    hide = g.call(FN_SET_HIDDEN, [then(put)], self=item)
    _set(hide, "bNewHidden", True)
    worn = draw_worn(g, item, True, [then(hide)])
    made += g.made
    return [worn, none]
