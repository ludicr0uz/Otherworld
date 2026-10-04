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
from uebp.graph import (
    _connect, _loose_pin, _node, _palette, _pin, _set, _vec, else_, out, then)
from combat.light_tuning import (
    CAMPFIRE_AHEAD_CM, CAMPFIRE_CLASS_VAR, CAMPFIRE_FEET_CM, CAMPFIRE_TRACE_DOWN_CM,
    CAMPFIRE_TRACE_UP_CM, LIGHT_WOOD_VAR, LIGHTS_VAR,
)
from combat.weapon_component.common import _prop, _trace_defaults
from uebp.nodes.actor import FN_ACTOR_FORWARD, FN_ACTOR_LOC, FN_DESTROY
from uebp.nodes.array import FN_ARR_FIND, FN_ARR_REMOVE_ITEM
from uebp.nodes.math import (
    FN_ADD_VV, FN_CLASS_EQ, FN_MAKE_TRANSFORM, FN_MUL_VF, FN_SELECT_VECTOR)
from uebp.nodes.palette import MACRO_FOR_EACH, NODE_BREAK_HIT, NODE_SPAWN
from uebp.nodes.system import FN_IS_VALID, FN_IS_VALID_CLASS, FN_OBJECT_CLASS, FN_TRACE
from combat.weapon_component import vars as WV
from combat.weapon_component.sounds import _author_sound


def _get(ed, name):
    return out(ed.add_get_member_variable_node(name), name)


def _author_light_press(ed, held, owner, tap, not_lighter):
    """Branch an item that Lights off the fire gate; a tap strikes it. Anything
    else goes on to ``not_lighter`` (the ready gate). Returns (the gate's exec
    input, its exits)."""
    lights, lights_n = _prop(ed, LIGHTS_VAR, held)
    gate = ed.add_branch_node()
    _connect(lights, _pin(gate, "Condition"))
    _connect(else_(gate), not_lighter)
    press = ed.add_branch_node()
    _connect(tap, _pin(press, "Condition"))
    _connect(then(gate), _pin(press, "execute"))
    exits = _author_campfire(ed, held, owner, then(press))
    ed.add_comment_to_nodes(
        "The held item Lights (the matches): a tap strikes it (light.py) "
        "instead of firing it. Anything else goes on to the guns' ready gate.",
        [lights_n, gate, press])
    return _pin(gate, "execute"), exits + (else_(press),)


def _author_campfire(ed, held, owner, exec_in):
    """The strike: spend a piece of wood from Inventory, and spawn
    CampfireClass on the ground in front of ``owner``. Returns its exits."""
    cls = _get(ed, CAMPFIRE_CLASS_VAR)
    is_fire = _node(ed, FN_IS_VALID_CLASS)
    _connect(cls, _pin(is_fire, "Class"))
    known = ed.add_branch_node()
    _connect(out(is_fire), _pin(known, "Condition"))
    _connect(exec_in, _pin(known, "execute"))

    # --- the wood to burn -----------------------------------------------------
    # Set with its input unconnected: None, so last strike's wood is forgotten.
    forget = ed.add_set_member_variable_node(LIGHT_WOOD_VAR)
    _connect(then(known), _pin(forget, "execute"))
    inv = _get(ed, WV.Inventory)
    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    loop
    _connect(inv, _loose_pin(loop, "Array"))
    _connect(then(forget), _loose_pin(loop, "Exec"))
    item = _loose_pin(loop, "ArrayElement", is_input=False)
    kind = _node(ed, FN_OBJECT_CLASS)
    _connect(item, _pin(kind, "Object"))
    is_wood = _node(ed, FN_CLASS_EQ)
    _connect(out(kind), _pin(is_wood, "A"))
    _connect(_get(ed, WOOD_CLASS_VAR), _pin(is_wood, "B"))
    burns = ed.add_branch_node()
    _connect(out(is_wood), _pin(burns, "Condition"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(burns, "execute"))
    pick = ed.add_set_member_variable_node(LIGHT_WOOD_VAR)
    _connect(item, _pin(pick, LIGHT_WOOD_VAR))
    _connect(then(burns), _pin(pick, "execute"))

    wood = _get(ed, LIGHT_WOOD_VAR)
    is_there = _node(ed, FN_IS_VALID)
    _connect(wood, _pin(is_there, "Object"))
    has_wood = ed.add_branch_node()
    _connect(out(is_there), _pin(has_wood, "Condition"))
    _connect(_loose_pin(loop, "Completed", is_input=False), _pin(has_wood, "execute"))

    # --- spend it -------------------------------------------------------------
    remove = _node(ed, FN_ARR_REMOVE_ITEM)
    _connect(inv, _pin(remove, "TargetArray"))
    _connect(wood, _pin(remove, "Item"))
    _connect(then(has_wood), _pin(remove, "execute"))
    gone = _node(ed, FN_DESTROY)
    _connect(wood, _pin(gone, "self"))
    _connect(then(remove), _pin(gone, "execute"))
    # Find is pure: read here, after the removal, it sees the shorter array.
    slot = _node(ed, FN_ARR_FIND)
    _connect(inv, _pin(slot, "TargetArray"))
    _connect(held, _pin(slot, "ItemToFind"))
    stay = ed.add_set_member_variable_node(WV.EquippedIndex)
    _connect(out(slot), _pin(stay, WV.EquippedIndex))
    _connect(then(gone), _pin(stay, "execute"))

    # --- the ground in front of the player, and the fire ----------------------
    here = _node(ed, FN_ACTOR_LOC)
    _connect(owner, _pin(here, "self"))
    ahead = _node(ed, FN_ACTOR_FORWARD)
    _connect(owner, _pin(ahead, "self"))
    # Multiply_VectorFloat's B is promoted to a vector: drive it with one.
    reach = _node(ed, FN_MUL_VF)
    _connect(out(ahead), _pin(reach, "A"))
    r = CAMPFIRE_AHEAD_CM
    _connect(_vec(ed, r, r, r), _pin(reach, "B"))
    spot = _node(ed, FN_ADD_VV)
    _connect(out(here), _pin(spot, "A"))
    _connect(out(reach), _pin(spot, "B"))

    def offset(z):
        n = _node(ed, FN_ADD_VV)
        _connect(out(spot), _pin(n, "A"))
        _connect(_vec(ed, 0.0, 0.0, z), _pin(n, "B"))
        return out(n)

    floor = _node(ed, FN_TRACE)
    _connect(offset(CAMPFIRE_TRACE_UP_CM), _pin(floor, "Start"))
    _connect(offset(-CAMPFIRE_TRACE_DOWN_CM), _pin(floor, "End"))
    _trace_defaults(floor)
    _connect(then(stay), _pin(floor, "execute"))
    ground = _palette(ed, NODE_BREAK_HIT)
    _connect(out(floor, "OutHit"), _loose_pin(ground, "Hit"))
    # No ground under it (the map's edge): at the height of the player's feet.
    rests = _node(ed, FN_SELECT_VECTOR)
    _connect(_loose_pin(ground, "Location", is_input=False), _pin(rests, "A"))
    _connect(offset(-CAMPFIRE_FEET_CM), _pin(rests, "B"))
    _connect(out(floor), _pin(rests, "bPickA"))
    at = _node(ed, FN_MAKE_TRANSFORM)
    _connect(out(rests), _pin(at, "Location"))
    fire = _palette(ed, NODE_SPAWN)
    _connect(cls, _pin(fire, "Class"))
    _connect(out(at), _pin(fire, "SpawnTransform"))
    _set(fire, "CollisionHandlingOverride", "AlwaysSpawn")
    _connect(then(floor), _pin(fire, "execute"))
    # The match itself, heard where the fire is laid.
    struck = _author_sound(ed, WV.MatchSounds, out(rests), then(fire))

    ed.add_comment_to_nodes(
        "A strike of the matches. With a campfire class to spawn and a piece "
        "of wood in the bag (the last one the loop meets), the wood is taken "
        "out of Inventory and destroyed, EquippedIndex follows Held to its "
        f"new slot, and CampfireClass is spawned {CAMPFIRE_AHEAD_CM:.0f} cm in "
        "front of the player, on the ground a trace finds there. The matches "
        "are not spent; with no wood, nothing happens.",
        [known, forget, loop, burns, pick, has_wood, remove, gone, stay, floor, fire])
    return (struck, else_(known), else_(has_wood))
