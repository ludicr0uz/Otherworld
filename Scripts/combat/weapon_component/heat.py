"""Heating a blade: what the interact key does to a campfire, with an item
that Heats in hand (the knife, the axe).

One of interact.py's kinds, in two halves. _author_fire_candidates walks the
campfires (every CampfireClass actor) and offers them while the held item
Heats; interact.py keeps the one in reach nearest AimPoint as InteractTarget,
against the other kinds' candidates, so with an item lying by the fire the
press takes whichever the reticle is on. _author_heat_item asks whether the
target is a campfire and, if it is, asks the server to heat the held item at
it: Server_Heat(Fire), a reliable Server event (task M25, combat/fire_vars.py;
in single player a plain call). The server refuses a fire that is not one or
is out of its own copy's reach, a dead owner, and a hand whose item does not
Heat, and otherwise makes its own item Hot until HEAT_S on:

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

from net.guard import author_guard
from uebp import net
from uebp.g import _G
from uebp.graph import _connect, _loose_pin, _node, _pin, _set, out, then
from combat.fire_vars import FIRE_PARAM, HEAT_PARAMS, HEAT_REACH_CM, SERVER_HEAT
from combat.heat_tuning import COOL_VAR, HEAT_S, HEATS_VAR, HOT_VAR
from combat.light_tuning import CAMPFIRE_CLASS_VAR
from combat.paths import ITEM_CLASS_PATH
from combat.weapon_component.common import _prop
from combat.weapon_component.shot import _author_alive
from combat.weapon_component.slot_nodes import op, valid
from uebp.nodes.actor import FN_ACTOR_LOC, FN_GET_OWNER
from uebp.nodes.math import FN_ADD_FF, FN_AND, FN_CLASS_IS_CHILD, FN_DISTANCE, FN_LE_FF
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
    """E on a campfire, where the keys are: ask the server to heat the held
    item at the interact target, if that is a campfire.

    Returns (asked, idle, not_mine): the exec pin an ask leaves by, the one
    empty hands leave by, and the one a target that is no campfire leaves by.
    """
    g = _G(ed, ITEM_CLASS_PATH)
    kind = g.call(FN_OBJECT_CLASS, Object=target)
    is_fire = g.call(FN_CLASS_IS_CHILD, TestClass=out(kind),
                     ParentClass=g.get(CAMPFIRE_CLASS_VAR))
    mine, not_mine = g.branch(out(is_fire), [exec_in])
    armed, bare = g.branch(valid(g, g.get(WV.Held)), [mine])
    ask = g.keep(_node(ed, SERVER_HEAT))
    _connect(target, _pin(ask, FIRE_PARAM))
    _connect(armed, _pin(ask, "execute"))
    ed.add_comment_to_nodes(
        "An interact target that is a campfire, with something in hand: the "
        f"server is asked to heat it there ({SERVER_HEAT}, heat.py). With "
        "authority (single player) the event is the heating.", g.made)
    return (then(ask),), (bare,), not_mine


def author_heat_event(ed):
    """Server_Heat(Fire): the heating, on the machine that owns the item.
    Refused unless Fire is there and a campfire, the owner alive and within
    HEAT_REACH_CM of it on this machine, and this machine's Held Heats. Then
    the item is Hot until HEAT_S on. Before the Tick, which calls it by
    name."""
    g = _G(ed, ITEM_CLASS_PATH)
    event = g.keep(net.server_event(ed, SERVER_HEAT, HEAT_PARAMS))
    fire = out(event, FIRE_PARAM)
    go, _refused = author_guard(g, SERVER_HEAT, [then(event)])
    there, _gone = g.branch(valid(g, fire), [go])
    alive = _author_alive(g, [there])
    is_fire = g.call(FN_CLASS_IS_CHILD,
                     TestClass=out(g.call(FN_OBJECT_CLASS, Object=fire)),
                     ParentClass=g.get(CAMPFIRE_CLASS_VAR))
    here = g.call(FN_ACTOR_LOC, self=out(g.call(FN_GET_OWNER)))
    gap = g.call(FN_DISTANCE, V1=out(g.call(FN_ACTOR_LOC, self=fire)), V2=out(here))
    near = g.call(FN_LE_FF, A=out(gap))
    _set(near, "B", HEAT_REACH_CM)
    at_fire, _far = g.branch(op(g, FN_AND, out(is_fire), out(near)), alive)
    held = g.get(WV.Held)
    armed, _bare = g.branch(valid(g, held), [at_fire])
    heats, _cannot = g.branch(g.iget(held, HEATS_VAR), [armed])

    until = g.call(FN_ADD_FF, A=out(g.call(FN_TIME_SECONDS)))
    _set(until, "B", HEAT_S)
    cool = g.iput(held, COOL_VAR, out(until), [heats])
    g.iput(held, HOT_VAR, "true", [cool])
    ed.add_comment_to_nodes(
        f"{SERVER_HEAT} (heat.py): the owning client's E on a campfire. Refused "
        "unless the fire is there and a campfire, the owner alive and within "
        f"{HEAT_REACH_CM:g} cm of it on this machine, and this machine's Held "
        f"{HEATS_VAR}. Then it is {HOT_VAR} until {COOL_VAR}, {HEAT_S:g} s on: "
        "the item's own Tick shows the glow and cools it (combat/heat.py), and "
        "the record tells the clients (record.py).", g.made)
