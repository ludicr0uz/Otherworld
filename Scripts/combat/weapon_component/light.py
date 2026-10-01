"""Lighting a campfire: the fire key, pressed with an item that Lights in hand
(the matches), burns one piece of wood from the bag into a campfire on the
ground in front of the player.

It sits inside the fire gate, on the Melee branch's False arm, because Lights
is read off Held; anything that does not Light goes on to the guns' ready gate.

    Held.Lights --> tap --> IsValidClass(CampfireClass)
      --> LightWood = None; for each item in Inventory: its class is
          WoodClass --> LightWood = it
      --> IsValid(LightWood): take it out of Inventory and destroy it;
          EquippedIndex = where Held is now
      --> trace down in front of the player; spawn CampfireClass on the ground

The matches are never spent, and a strike with no wood in the bag does
nothing. The wood is an actor in the bag like any item, so spending it is the
consumable's removal (consume.py) for an item that is not the one in hand:
Held stays, and EquippedIndex is found again because the removal may have
moved it down a slot. The wood in hand cannot be the one burned (the matches
are).

The campfire's class is a default build_survival.py writes (survival/
campfire.py): combat knows nothing about warmth. Until it has, the strike is
refused before any wood is spent.

ForEachLoop has no break pin: the loop keeps the last piece of wood it met,
and the take runs once, off Completed. Tuning is light_tuning.py.
"""

from combat.chop_tuning import WOOD_CLASS_VAR
from combat.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set, _vec
from combat.light_tuning import (
    CAMPFIRE_AHEAD_CM, CAMPFIRE_CLASS_VAR, CAMPFIRE_FEET_CM, CAMPFIRE_TRACE_DOWN_CM,
    CAMPFIRE_TRACE_UP_CM, LIGHT_WOOD_VAR, LIGHTS_VAR,
)
from combat.nodes import (
    FN_ACTOR_FORWARD, FN_ACTOR_LOC, FN_ADD_VV, FN_DESTROY, FN_IS_VALID,
    FN_IS_VALID_CLASS, FN_MAKE_TRANSFORM, FN_MUL_VF, FN_OBJECT_CLASS, FN_SELECT_VECTOR,
    FN_TRACE, MACRO_FOR_EACH, NODE_BREAK_HIT, NODE_SPAWN,
)
from combat.weapon_component.common import _prop, _trace_defaults

FN_EQ_CLASSES = "/Script/Engine.KismetMathLibrary.EqualEqual_ClassClass"
FN_ARR_REMOVE_ITEM = "/Script/Engine.KismetArrayLibrary.Array_RemoveItem"
FN_ARR_FIND = "/Script/Engine.KismetArrayLibrary.Array_Find"


def _out(n, name="ReturnValue"):
    return _pin(n, name, is_input=False)


def _get(ed, name, x, y):
    return _pin(_at(ed.add_get_member_variable_node(name), x, y), name, is_input=False)


def _author_light_press(ed, held, owner, tap, not_lighter, x0, y0):
    """Branch an item that Lights off the fire gate; a tap strikes it. Anything
    else goes on to ``not_lighter`` (the ready gate). Returns (the gate's exec
    input, its exits)."""
    lights, lights_n = _prop(ed, LIGHTS_VAR, held, x0, y0 + 160)
    gate = _at(ed.add_branch_node(), x0 + 240, y0)
    _connect(lights, _pin(gate, "Condition"))
    _connect(BEL.find_else_pin(gate), not_lighter)
    press = _at(ed.add_branch_node(), x0 + 480, y0)
    _connect(tap, _pin(press, "Condition"))
    _connect(BEL.find_then_pin(gate), _pin(press, "execute"))
    exits = _author_campfire(ed, held, owner, BEL.find_then_pin(press),
                             x0 + 160, y0 + 16000)
    ed.add_comment_to_nodes(
        "The held item Lights (the matches): a tap strikes it (light.py) "
        "instead of firing it. Anything else goes on to the guns' ready gate.",
        [lights_n, gate, press])
    return _pin(gate, "execute"), exits + (BEL.find_else_pin(press),)


def _author_campfire(ed, held, owner, exec_in, x0, y0):
    """The strike: spend a piece of wood from Inventory, and spawn
    CampfireClass on the ground in front of ``owner``. Returns its exits."""
    cls = _get(ed, CAMPFIRE_CLASS_VAR, x0, y0 + 200)
    is_fire = _at(_node(ed, FN_IS_VALID_CLASS), x0 + 240, y0 + 200)
    _connect(cls, _pin(is_fire, "Class"))
    known = _at(ed.add_branch_node(), x0 + 480, y0)
    _connect(_out(is_fire), _pin(known, "Condition"))
    _connect(exec_in, _pin(known, "execute"))

    # --- the wood to burn -----------------------------------------------------
    # Set with its input unconnected: None, so last strike's wood is forgotten.
    forget = _at(ed.add_set_member_variable_node(LIGHT_WOOD_VAR), x0 + 740, y0)
    _connect(BEL.find_then_pin(known), _pin(forget, "execute"))
    inv = _get(ed, "Inventory", x0 + 740, y0 + 300)
    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    _at(loop, x0 + 1000, y0)
    _connect(inv, _loose_pin(loop, "Array"))
    _connect(BEL.find_then_pin(forget), _loose_pin(loop, "Exec"))
    item = _loose_pin(loop, "ArrayElement", is_input=False)
    kind = _at(_node(ed, FN_OBJECT_CLASS), x0 + 1300, y0 + 300)
    _connect(item, _pin(kind, "Object"))
    is_wood = _at(_node(ed, FN_EQ_CLASSES), x0 + 1560, y0 + 300)
    _connect(_out(kind), _pin(is_wood, "A"))
    _connect(_get(ed, WOOD_CLASS_VAR, x0 + 1300, y0 + 460), _pin(is_wood, "B"))
    burns = _at(ed.add_branch_node(), x0 + 1820, y0 + 160)
    _connect(_out(is_wood), _pin(burns, "Condition"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(burns, "execute"))
    pick = _at(ed.add_set_member_variable_node(LIGHT_WOOD_VAR), x0 + 2080, y0 + 160)
    _connect(item, _pin(pick, LIGHT_WOOD_VAR))
    _connect(BEL.find_then_pin(burns), _pin(pick, "execute"))

    wood = _get(ed, LIGHT_WOOD_VAR, x0 + 2080, y0 + 460)
    is_there = _at(_node(ed, FN_IS_VALID), x0 + 2340, y0 + 460)
    _connect(wood, _pin(is_there, "Object"))
    has_wood = _at(ed.add_branch_node(), x0 + 2600, y0)
    _connect(_out(is_there), _pin(has_wood, "Condition"))
    _connect(_loose_pin(loop, "Completed", is_input=False), _pin(has_wood, "execute"))

    # --- spend it -------------------------------------------------------------
    remove = _at(_node(ed, FN_ARR_REMOVE_ITEM), x0 + 2860, y0)
    _connect(inv, _pin(remove, "TargetArray"))
    _connect(wood, _pin(remove, "Item"))
    _connect(BEL.find_then_pin(has_wood), _pin(remove, "execute"))
    gone = _at(_node(ed, FN_DESTROY), x0 + 3120, y0)
    _connect(wood, _pin(gone, "self"))
    _connect(BEL.find_then_pin(remove), _pin(gone, "execute"))
    # Find is pure: read here, after the removal, it sees the shorter array.
    slot = _at(_node(ed, FN_ARR_FIND), x0 + 3120, y0 + 300)
    _connect(inv, _pin(slot, "TargetArray"))
    _connect(held, _pin(slot, "ItemToFind"))
    stay = _at(ed.add_set_member_variable_node("EquippedIndex"), x0 + 3380, y0)
    _connect(_out(slot), _pin(stay, "EquippedIndex"))
    _connect(BEL.find_then_pin(gone), _pin(stay, "execute"))

    # --- the ground in front of the player, and the fire ----------------------
    here = _at(_node(ed, FN_ACTOR_LOC), x0 + 3380, y0 + 300)
    _connect(owner, _pin(here, "self"))
    ahead = _at(_node(ed, FN_ACTOR_FORWARD), x0 + 3380, y0 + 460)
    _connect(owner, _pin(ahead, "self"))
    # Multiply_VectorFloat's B is promoted to a vector: drive it with one.
    reach = _at(_node(ed, FN_MUL_VF), x0 + 3640, y0 + 460)
    _connect(_out(ahead), _pin(reach, "A"))
    r = CAMPFIRE_AHEAD_CM
    _connect(_vec(ed, r, r, r, x0 + 3380, y0 + 620), _pin(reach, "B"))
    spot = _at(_node(ed, FN_ADD_VV), x0 + 3900, y0 + 300)
    _connect(_out(here), _pin(spot, "A"))
    _connect(_out(reach), _pin(spot, "B"))

    def offset(z, x, y):
        n = _at(_node(ed, FN_ADD_VV), x, y)
        _connect(_out(spot), _pin(n, "A"))
        _connect(_vec(ed, 0.0, 0.0, z, x - 260, y + 140), _pin(n, "B"))
        return _out(n)

    floor = _at(_node(ed, FN_TRACE), x0 + 4420, y0)
    _connect(offset(CAMPFIRE_TRACE_UP_CM, x0 + 4160, y0 + 300), _pin(floor, "Start"))
    _connect(offset(-CAMPFIRE_TRACE_DOWN_CM, x0 + 4160, y0 + 600), _pin(floor, "End"))
    _trace_defaults(floor)
    _connect(BEL.find_then_pin(stay), _pin(floor, "execute"))
    ground = _at(_palette(ed, NODE_BREAK_HIT), x0 + 4700, y0 + 300)
    _connect(_out(floor, "OutHit"), _loose_pin(ground, "Hit"))
    # No ground under it (the map's edge): at the height of the player's feet.
    rests = _at(_node(ed, FN_SELECT_VECTOR), x0 + 4960, y0 + 300)
    _connect(_loose_pin(ground, "Location", is_input=False), _pin(rests, "A"))
    _connect(offset(-CAMPFIRE_FEET_CM, x0 + 4700, y0 + 900), _pin(rests, "B"))
    _connect(_out(floor), _pin(rests, "bPickA"))
    at = _at(_node(ed, FN_MAKE_TRANSFORM), x0 + 5220, y0 + 300)
    _connect(_out(rests), _pin(at, "Location"))
    fire = _at(_palette(ed, NODE_SPAWN), x0 + 5480, y0)
    _connect(cls, _pin(fire, "Class"))
    _connect(_out(at), _pin(fire, "SpawnTransform"))
    _set(fire, "CollisionHandlingOverride", "AlwaysSpawn")
    _connect(BEL.find_then_pin(floor), _pin(fire, "execute"))

    ed.add_comment_to_nodes(
        "A strike of the matches. With a campfire class to spawn and a piece "
        "of wood in the bag (the last one the loop meets), the wood is taken "
        "out of Inventory and destroyed, EquippedIndex follows Held to its "
        f"new slot, and CampfireClass is spawned {CAMPFIRE_AHEAD_CM:.0f} cm in "
        "front of the player, on the ground a trace finds there. The matches "
        "are not spent; with no wood, nothing happens.",
        [known, forget, loop, burns, pick, has_wood, remove, gone, stay, floor, fire])
    return (BEL.find_then_pin(fire), BEL.find_else_pin(known),
            BEL.find_else_pin(has_wood))
