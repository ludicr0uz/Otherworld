"""Heating a blade: what the interact key does to a campfire, with an item
that Heats in hand (the knife, the axe).

One of interact.py's kinds, in two halves. _author_fire_candidates walks the
campfires (every CampfireClass actor) and offers them while the held item
Heats; interact.py keeps the one in reach nearest AimPoint as InteractTarget,
against the other kinds' candidates, so with an item lying by the fire the
press takes whichever the reticle is on. _author_heat_item asks whether the
target is a campfire and, if it is, makes the held item Hot until HEAT_S on:

    Held.CoolTime = now + HEAT_S;  Held.Hot = true

That is all the component does. The glow, and the cooling, are the item's own
Tick (combat/heat.py), so a hot blade put away or dropped still cools. A
press on a blade already hot starts its time again.

A campfire is survival's (survival/campfire.py) and built after this graph,
so there is no cast to it: the target's class is tested against CampfireClass,
the variable the matches spawn from, and with none set (survival not built)
the walk is over nothing and the test is false. Held is read behind its own
IsValid Branch in both halves: empty hands are offered nothing.
"""

from uebp.graph import _connect, _loose_pin, _node, _pin, _set, else_, out, then
from combat.heat_tuning import COOL_VAR, HEAT_S, HEATS_VAR, HOT_VAR
from combat.light_tuning import CAMPFIRE_CLASS_VAR
from combat.paths import ITEM_CLASS_PATH
from combat.weapon_component.common import _prop
from uebp.nodes.math import FN_ADD_FF, FN_CLASS_IS_CHILD
from uebp.nodes.palette import MACRO_FOR_EACH
from uebp.nodes.system import FN_ALL_ACTORS, FN_IS_VALID, FN_OBJECT_CLASS, FN_TIME_SECONDS
from combat.weapon_component import vars as WV


def _author_fire_candidates(ed, exec_in):
    """Walk every campfire, offering each while the held item Heats.

    Returns (candidate, offered, body, completed), as interact.py's kinds do:
    ``body`` is the true arm of IsValid(Held), where ``offered`` (Held.Heats)
    may be read.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    cls = keep(ed.add_get_member_variable_node(CAMPFIRE_CLASS_VAR))
    every = keep(_node(ed, FN_ALL_ACTORS))
    _connect(out(cls, CAMPFIRE_CLASS_VAR), _pin(every, "ActorClass"))
    _connect(exec_in, _pin(every, "execute"))

    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    keep(loop)
    _connect(out(every, "OutActors"), _loose_pin(loop, "Array"))
    _connect(then(every), _loose_pin(loop, "Exec"))

    held = keep(ed.add_get_member_variable_node(WV.Held))
    armed = keep(_node(ed, FN_IS_VALID))
    _connect(out(held, WV.Held), _pin(armed, "Object"))
    gate = keep(ed.add_branch_node())
    _connect(out(armed), _pin(gate, "Condition"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(gate, "execute"))
    heats_pin, heats_n = _prop(ed, HEATS_VAR, out(held, WV.Held))
    keep(heats_n)

    ed.add_comment_to_nodes(
        "The campfires the interact key may heat a blade at: every "
        f"{CAMPFIRE_CLASS_VAR} actor, while the held item {HEATS_VAR}.",
        made)
    return (_loose_pin(loop, "ArrayElement", is_input=False), heats_pin,
            then(gate), _loose_pin(loop, "Completed", is_input=False))


def _author_heat_item(ed, target, exec_in):
    """Make the held item Hot, if the interact target is a campfire.

    Returns (heated, idle, not_mine): the exec pin a heating leaves by, the
    one empty hands leave by, and the one a target that is no campfire leaves
    by.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    kind = keep(_node(ed, FN_OBJECT_CLASS))
    _connect(target, _pin(kind, "Object"))
    fire_cls = keep(ed.add_get_member_variable_node(CAMPFIRE_CLASS_VAR))
    is_fire = keep(_node(ed, FN_CLASS_IS_CHILD))
    _connect(out(kind), _pin(is_fire, "TestClass"))
    _connect(out(fire_cls, CAMPFIRE_CLASS_VAR), _pin(is_fire, "ParentClass"))
    mine = keep(ed.add_branch_node())
    _connect(out(is_fire), _pin(mine, "Condition"))
    _connect(exec_in, _pin(mine, "execute"))

    held_n = keep(ed.add_get_member_variable_node(WV.Held))
    held = out(held_n, WV.Held)
    armed = keep(_node(ed, FN_IS_VALID))
    _connect(held, _pin(armed, "Object"))
    gate = keep(ed.add_branch_node())
    _connect(out(armed), _pin(gate, "Condition"))
    _connect(then(mine), _pin(gate, "execute"))

    now = keep(_node(ed, FN_TIME_SECONDS))
    until = keep(_node(ed, FN_ADD_FF))
    _connect(out(now), _pin(until, "A"))
    _set(until, "B", HEAT_S)
    cool = keep(ed.add_set_member_variable_node(COOL_VAR, ITEM_CLASS_PATH))
    _connect(held, _pin(cool, "self"))
    _connect(out(until), _pin(cool, COOL_VAR))
    _connect(then(gate), _pin(cool, "execute"))
    hot = keep(ed.add_set_member_variable_node(HOT_VAR, ITEM_CLASS_PATH))
    _connect(held, _pin(hot, "self"))
    _set(hot, HOT_VAR, "true")
    _connect(then(cool), _pin(hot, "execute"))

    ed.add_comment_to_nodes(
        "An interact target that is a campfire heats the held item: it is "
        f"{HOT_VAR} until {COOL_VAR}, {HEAT_S:g} s on. The item's own Tick "
        "shows the glow and cools it (combat/heat.py).",
        made)
    return (then(hot),), (else_(gate),), else_(mine)
