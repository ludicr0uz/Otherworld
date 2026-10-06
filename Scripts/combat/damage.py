"""Damage: the one way health is taken off a body, and how a client hears of it.

Health is the server's (M14). A blow does not write it: it calls TakeHit on
the target's BP_HealthComponent, saying how much, which way it came from, who
struck it and with what:

    hit(ed, as_health, amount, came_from, instigator, cause, execs)

TakeHit runs behind the authority switch (the server, and single player), so
a call on a client's copy changes nothing there:

    HitCount + 1                  where the blow takes health off (see below)
    Health = max(Health - Amount, 0)
    LastDamageTime = now          the bar over a wanderer, the grunt, save-and-exit
    LastHitFrom = From            the flinch's direction
    LastInstigator, LastCause     the controller a kill is credited to (death.py),
                                  and the gun, the blade or the wanderer
    DamagedByPlayer = true        where the instigator is a PlayerController

What travels (replicate_health): Health as a RepNotify, MaxHealth, Dead,
HitCount, LastHitFrom and the wanderer's number. A client's copy ticks as the
server's does and reads them: the HUD's bar and the heartbeat off Health, the
death's collapse off Health at 0. OnRep_Health is what makes the rest of it
right there, on a client only:

    HitCount moved    a blow: LastDamageTime = this machine's clock, and
                      PrevHealth is left behind Health, so the Tick flinches
    it did not        a drain, a heal, a wanderer's maximum: PrevHealth =
                      Health, as the drain itself keeps it on the server

LastDamageTime is each machine's own clock, so it is not replicated. HitCount
rises only with Health (a blow on a body already at 0 changes no Health and
calls no OnRep, and would be answered at the next drain instead).

Not through TakeHit: the drain and the world-floor net (the component's own
Tick, behind the same switch: nobody struck those), a heal, a wanderer's
maximum at possession and a loaded profile, which are written on the server.
"""

import unreal

from combat import health_vars as HV
from combat.game_state import DAMAGED_BY_PLAYER_VAR, LAST_DAMAGE_VAR, NPC_ID_VAR
from combat.hit_reaction import LAST_HIT_FROM_VAR, PREV_HEALTH_VAR
from combat.paths import HEALTH_CLASS_PATH
from uebp import net
from uebp.g import _G
from uebp.graph import _connect, _node, _palette, _pin, _set, out, then
from uebp.layout import arrange
from uebp.nodes.actor import FN_GET_INSTIGATOR_CONTROLLER, FN_GET_OWNER
from uebp.nodes.math import (
    FN_ADD_II, FN_AND, FN_CLAMP, FN_GREATER_FF, FN_NEQ_II, FN_SUB_FF, INF)
from uebp.nodes.palette import MACRO_SWITCH_AUTHORITY_COMP, NODE_CAST_PLAYER_CONTROLLER
from uebp.nodes.system import FN_TIME_SECONDS
from uebp.vars import FLOAT, VECTOR, obj

TAKE_HIT = "TakeHit"
AMOUNT, FROM, INSTIGATOR, CAUSE = "Amount", "From", "InstigatedBy", "Cause"
TAKE_HIT_PARAMS = (
    (AMOUNT, FLOAT), (FROM, VECTOR),
    (INSTIGATOR, obj("/Script/Engine.Controller")), (CAUSE, obj("/Script/Engine.Actor")),
)
# What a client is sent, and to whom: everyone (the bar over a wanderer, and
# another player's flinch and collapse, are drawn on every machine).
REPLICATED = (HV.MaxHealth, HV.Dead, HV.HitCount, LAST_HIT_FROM_VAR, NPC_ID_VAR)


def hit(ed, as_health, amount, came_from, instigator, cause, execs):
    """Call TakeHit on ``as_health`` (the cast's pin). ``amount`` is a float
    pin or a literal, ``came_from`` a vector pin, ``instigator`` a controller
    pin and ``cause`` an actor pin. Returns the call's then pin, and the node."""
    call = _node(ed, f"{HEALTH_CLASS_PATH}:{TAKE_HIT}")
    _connect(as_health, _pin(call, "self"))
    if isinstance(amount, (int, float)):
        _set(call, AMOUNT, float(amount))
    else:
        _connect(amount, _pin(call, AMOUNT))
    _connect(came_from, _pin(call, FROM))
    _connect(instigator, _pin(call, INSTIGATOR))
    _connect(cause, _pin(call, CAUSE))
    for e in execs:
        _connect(e, _pin(call, "execute"))
    return then(call), call


def owner_instigator(ed):
    """Who strikes, for a blow struck from a component's graph: the controller
    of the pawn that owns it (a pawn is its own instigator, so no cast). Pure;
    returns the pin and the nodes."""
    owner = _node(ed, FN_GET_OWNER)
    who = _node(ed, FN_GET_INSTIGATOR_CONTROLLER)
    _connect(out(owner), _pin(who, "self"))
    return out(who), [owner, who]


def _author_take_hit(ed):
    """The event, in BP_HealthComponent's event graph (the module docstring
    has what it writes). Its parameters are read once each write: none is
    changed on the way, and Health is read before its own Set."""
    g = _G(ed)
    event = g.keep(net.custom_event(ed, TAKE_HIT, TAKE_HIT_PARAMS))
    server = g.keep(ed.add_macro_node(MACRO_SWITCH_AUTHORITY_COMP))
    _connect(then(event), _pin(server, "execute"))

    # A blow that takes health off: the count a client tells it by.
    alive = g.call(FN_GREATER_FF, A=g.get(HV.Health))
    _set(alive, "B", 0.0)
    some = g.call(FN_GREATER_FF, A=out(event, AMOUNT))
    _set(some, "B", 0.0)
    lands, not_felt = g.branch(out(g.call(FN_AND, A=out(alive), B=out(some))),
                               [out(server, "Authority")])
    more = g.call(FN_ADD_II, A=g.get(HV.HitCount))
    _set(more, "B", 1)
    counted = g.put(HV.HitCount, out(more), [lands])

    left = g.call(FN_SUB_FF, A=g.get(HV.Health), B=out(event, AMOUNT))
    floor = g.call(FN_CLAMP, Value=out(left))
    _set(floor, "Min", 0.0)
    _set(floor, "Max", INF)
    e = g.put(HV.Health, out(floor), [counted, not_felt])
    e = g.put(LAST_DAMAGE_VAR, out(g.call(FN_TIME_SECONDS)), [e])
    e = g.put(LAST_HIT_FROM_VAR, out(event, FROM), [e])
    e = g.put(HV.LastInstigator, out(event, INSTIGATOR), [e])
    e = g.put(HV.LastCause, out(event, CAUSE), [e])
    player = g.keep(_palette(ed, NODE_CAST_PLAYER_CONTROLLER))
    _connect(out(event, INSTIGATOR), _pin(player, "Object"))
    _connect(e, _pin(player, "execute"))
    blame = g.keep(ed.add_set_member_variable_node(DAMAGED_BY_PLAYER_VAR))
    _set(blame, DAMAGED_BY_PLAYER_VAR, True)
    _connect(then(player), _pin(blame, "execute"))

    ed.add_comment_to_nodes(
        f"{TAKE_HIT}: the one way a blow takes health off this body, and only where this "
        "machine has authority (the server, single player). Health is floored at zero; the "
        "blow is stamped with when, which way, who (the controller a kill is credited to) "
        "and with what; DamagedByPlayer where a player struck it. HitCount rises with "
        "Health, and is how a client tells a blow from a drain.", g.made)
    return g.made


def _author_on_rep_health(bp):
    """OnRep_Health: what a client does about a Health that arrived. Blueprint
    calls it on the machine that set Health as well, which has done all of
    this already: hence the switch's Remote arm."""
    ed = net.rep_notify(bp, HV.Health)
    stale = [n for n in ed.list_all_nodes() if not isinstance(n, unreal.K2Node_FunctionEntry)]
    if stale:
        ed.remove_nodes(stale)
    entry = ed.find_graph_entry_pin()
    g = _G(ed)
    server = g.keep(ed.add_macro_node(MACRO_SWITCH_AUTHORITY_COMP))
    _connect(entry, _pin(server, "execute"))
    moved = g.call(FN_NEQ_II, A=g.get(HV.HitCount), B=g.get(HV.SeenHits))
    blow, other = g.branch(out(moved), [out(server, "Remote")])
    seen = g.put(HV.SeenHits, g.get(HV.HitCount), [blow])
    g.put(LAST_DAMAGE_VAR, out(g.call(FN_TIME_SECONDS)), [seen])
    g.put(PREV_HEALTH_VAR, g.get(HV.Health), [other])
    ed.add_comment_to_nodes(
        "A client's copy, told a new Health. HitCount moved with it: a blow, stamped with "
        "this machine's own clock (the bar, the grunt), and the Tick flinches at the drop. "
        "It did not: a drain or a heal, and PrevHealth follows so nothing flinches.", g.made)
    arrange(ed)
    return ed


def replicate_health(bp):
    """Mark what travels, and author OnRep_Health. After every declare (a
    re-declared variable loses its replication) and before the compile."""
    for var in REPLICATED:
        net.replicate(bp, var)
    return _author_on_rep_health(bp)
