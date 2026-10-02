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

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _pin, _set
from combat.heat_tuning import COOL_VAR, HEAT_S, HEATS_VAR, HOT_VAR
from combat.light_tuning import CAMPFIRE_CLASS_VAR
from combat.nodes import (
    FN_ADD_FF, FN_ALL_ACTORS, FN_IS_VALID, FN_OBJECT_CLASS, FN_TIME_SECONDS,
    MACRO_FOR_EACH,
)
from combat.paths import ITEM_CLASS_PATH
from combat.weapon_component.common import _prop

FN_CLASS_IS_CHILD = "/Script/Engine.KismetMathLibrary.ClassIsChildOf"


def _out(node, name="ReturnValue"):
    return _pin(node, name, is_input=False)


def _author_fire_candidates(ed, exec_in, x0, y0):
    """Walk every campfire, offering each while the held item Heats.

    Returns (candidate, offered, body, completed), as interact.py's kinds do:
    ``body`` is the true arm of IsValid(Held), where ``offered`` (Held.Heats)
    may be read.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    cls = keep(_at(ed.add_get_member_variable_node(CAMPFIRE_CLASS_VAR),
                   x0 + 780, y0 + 240))
    every = keep(_at(_node(ed, FN_ALL_ACTORS), x0 + 1040, y0))
    _connect(_out(cls, CAMPFIRE_CLASS_VAR), _pin(every, "ActorClass"))
    _connect(exec_in, _pin(every, "execute"))

    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    keep(_at(loop, x0 + 1320, y0))
    _connect(_out(every, "OutActors"), _loose_pin(loop, "Array"))
    _connect(BEL.find_then_pin(every), _loose_pin(loop, "Exec"))

    held = keep(_at(ed.add_get_member_variable_node("Held"), x0 + 1320, y0 + 300))
    armed = keep(_at(_node(ed, FN_IS_VALID), x0 + 1560, y0 + 300))
    _connect(_out(held, "Held"), _pin(armed, "Object"))
    gate = keep(_at(ed.add_branch_node(), x0 + 1620, y0))
    _connect(_out(armed), _pin(gate, "Condition"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(gate, "execute"))
    heats_pin, heats_n = _prop(ed, HEATS_VAR, _out(held, "Held"), x0 + 1900, y0 + 260)
    keep(heats_n)

    ed.add_comment_to_nodes(
        "The campfires the interact key may heat a blade at: every "
        f"{CAMPFIRE_CLASS_VAR} actor, while the held item {HEATS_VAR}.",
        made)
    return (_loose_pin(loop, "ArrayElement", is_input=False), heats_pin,
            BEL.find_then_pin(gate), _loose_pin(loop, "Completed", is_input=False))


def _author_heat_item(ed, target, exec_in, x0, y1):
    """Make the held item Hot, if the interact target is a campfire.

    Returns (heated, idle, not_mine): the exec pin a heating leaves by, the
    one empty hands leave by, and the one a target that is no campfire leaves
    by.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    kind = keep(_at(_node(ed, FN_OBJECT_CLASS), x0 + 1840, y1 + 300))
    _connect(target, _pin(kind, "Object"))
    fire_cls = keep(_at(ed.add_get_member_variable_node(CAMPFIRE_CLASS_VAR),
                        x0 + 1840, y1 + 420))
    is_fire = keep(_at(_node(ed, FN_CLASS_IS_CHILD), x0 + 2080, y1 + 340))
    _connect(_out(kind), _pin(is_fire, "TestClass"))
    _connect(_out(fire_cls, CAMPFIRE_CLASS_VAR), _pin(is_fire, "ParentClass"))
    mine = keep(_at(ed.add_branch_node(), x0 + 2340, y1))
    _connect(_out(is_fire), _pin(mine, "Condition"))
    _connect(exec_in, _pin(mine, "execute"))

    held_n = keep(_at(ed.add_get_member_variable_node("Held"), x0 + 2340, y1 + 300))
    held = _out(held_n, "Held")
    armed = keep(_at(_node(ed, FN_IS_VALID), x0 + 2580, y1 + 300))
    _connect(held, _pin(armed, "Object"))
    gate = keep(_at(ed.add_branch_node(), x0 + 2840, y1))
    _connect(_out(armed), _pin(gate, "Condition"))
    _connect(BEL.find_then_pin(mine), _pin(gate, "execute"))

    now = keep(_at(_node(ed, FN_TIME_SECONDS), x0 + 2840, y1 + 300))
    until = keep(_at(_node(ed, FN_ADD_FF), x0 + 3080, y1 + 300))
    _connect(_out(now), _pin(until, "A"))
    _set(until, "B", HEAT_S)
    cool = keep(_at(ed.add_set_member_variable_node(COOL_VAR, ITEM_CLASS_PATH),
                    x0 + 3340, y1))
    _connect(held, _pin(cool, "self"))
    _connect(_out(until), _pin(cool, COOL_VAR))
    _connect(BEL.find_then_pin(gate), _pin(cool, "execute"))
    hot = keep(_at(ed.add_set_member_variable_node(HOT_VAR, ITEM_CLASS_PATH),
                   x0 + 3600, y1))
    _connect(held, _pin(hot, "self"))
    _set(hot, HOT_VAR, "true")
    _connect(BEL.find_then_pin(cool), _pin(hot, "execute"))

    ed.add_comment_to_nodes(
        "An interact target that is a campfire heats the held item: it is "
        f"{HOT_VAR} until {COOL_VAR}, {HEAT_S:g} s on. The item's own Tick "
        "shows the glow and cools it (combat/heat.py).",
        made)
    return (BEL.find_then_pin(hot),), (BEL.find_else_pin(gate),), BEL.find_else_pin(mine)
