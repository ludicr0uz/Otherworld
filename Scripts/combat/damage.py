"""Damage: the one way health is taken off a body, and how a client hears of it.

Health is the server's (M14). A blow does not write it: it calls TakeHit on
the target's BP_HealthComponent, saying how much, which way it came from, who
struck it and with what:

    hit(ed, as_health, amount, came_from, instigator, cause, execs)

TakeHit is C++ (task W3: UOtherworldHealthComponent, the Blueprint's native
parent, Source/Otherworld/Public/OtherworldHealthComponent.h), as are the
properties it writes (health_vars.NATIVE). It runs with authority alone (the
server, and single player), so a call on a client's copy changes nothing there:

    HitCount + 1                  where the blow takes health off (see below)
    Health = max(Health - Amount, 0)
    LastDamageTime = now          the bar over a wanderer, the grunt, save-and-exit
    LastHitFrom = From            the flinch's direction
    LastInstigator, LastCause     the controller a kill is credited to (death.py),
                                  and the gun, the blade or the wanderer
    DamagedByPlayer = true        where the instigator is a PlayerController

What travels: Health and Dead as RepNotifies, HitCount and LastHitFrom (all
four the base's), and MaxHealth and the wanderer's number (replicate_health).
A client's copy ticks as the server's does and reads them: the HUD's bar and
the heartbeat off Health. Dead arriving is its OnDied, the death's collapse
(health_component.py). The base's OnHealthChanged event, a client's alone (a
Blueprint Set of a native property calls no notify), is what makes the rest
of it right there:

    HitCount moved    a blow: LastDamageTime = this machine's clock, and
                      PrevHealth is left behind Health, so the Tick flinches
    it did not        a drain, a heal, a wanderer's maximum: PrevHealth =
                      Health, as the drain itself keeps it on the server

LastDamageTime is each machine's own clock, so it is not replicated. HitCount
rises only with Health (a blow on a body already at 0 changes no Health and
tells no change, and would be answered at the next drain instead).

Not through TakeHit: the drain and the world-floor net (the component's own
Tick, behind the same switch: nobody struck those), a heal, a wanderer's
maximum at possession and a loaded profile, which are written on the server.
"""

from combat import health_vars as HV
from combat.game_state import LAST_DAMAGE_VAR, NPC_ID_VAR
from combat.hit_reaction import LAST_HIT_FROM_VAR, PREV_HEALTH_VAR
from uebp import net
from uebp.g import _G
from uebp.graph import _connect, _node, _palette, _pin, _set, out, then
from uebp.nodes.actor import FN_GET_INSTIGATOR_CONTROLLER, FN_GET_OWNER
from uebp.nodes.health import FN_TAKE_HIT, NODE_EVENT_HEALTH_CHANGED
from uebp.nodes.math import FN_NEQ_II
from uebp.nodes.palette import MACRO_SWITCH_AUTHORITY_COMP
from uebp.nodes.system import FN_TIME_SECONDS

# The base's functions and events, by name.
TAKE_HIT, DIE = "TakeHit", "Die"
ON_HEALTH_CHANGED, ON_DIED = "OnHealthChanged", "OnDied"
AMOUNT, FROM, INSTIGATOR, CAUSE = "Amount", "From", "InstigatedBy", "Cause"
TAKE_HIT_PARAMS = (AMOUNT, FROM, INSTIGATOR, CAUSE)
# What a client is sent of the Blueprint's own variables, and to whom:
# everyone (the bar over a wanderer is drawn on every machine).
REPLICATED = (HV.MaxHealth, NPC_ID_VAR)
# ...and of the base's (C++: GetLifetimeReplicatedProps), {name: its notify}.
NATIVE_REPLICATED = {HV.Health: "OnRep_Health", HV.Dead: "OnRep_Dead",
                     HV.HitCount: "None", LAST_HIT_FROM_VAR: "None"}


def hit(ed, as_health, amount, came_from, instigator, cause, execs):
    """Call TakeHit on ``as_health`` (the cast's pin). ``amount`` is a float
    pin or a literal, ``came_from`` a vector pin, ``instigator`` a controller
    pin and ``cause`` an actor pin. Returns the call's then pin, and the node."""
    call = _node(ed, FN_TAKE_HIT)
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


def author_health_changed(ed):
    """OnHealthChanged, in BP_HealthComponent's event graph: what a client
    does about a Health that arrived. The base tells it on a client alone;
    the switch's Remote arm says so here too."""
    g = _G(ed)
    event = g.keep(_palette(ed, NODE_EVENT_HEALTH_CHANGED))
    server = g.keep(ed.add_macro_node(MACRO_SWITCH_AUTHORITY_COMP))
    _connect(then(event), _pin(server, "execute"))
    moved = g.call(FN_NEQ_II, A=g.get(HV.HitCount), B=g.get(HV.SeenHits))
    blow, other = g.branch(out(moved), [out(server, "Remote")])
    seen = g.put(HV.SeenHits, g.get(HV.HitCount), [blow])
    g.put(LAST_DAMAGE_VAR, out(g.call(FN_TIME_SECONDS)), [seen])
    g.put(PREV_HEALTH_VAR, g.get(HV.Health), [other])
    ed.add_comment_to_nodes(
        "A client's copy, told a new Health. HitCount moved with it: a blow, stamped with "
        "this machine's own clock (the bar, the grunt), and the Tick flinches at the drop. "
        "It did not: a drain or a heal, and PrevHealth follows so nothing flinches.", g.made)
    return g.made


def replicate_health(bp):
    """Mark what of the Blueprint's own variables travels. After every
    declare (a re-declared variable loses its replication) and before the
    compile."""
    for var in REPLICATED:
        net.replicate(bp, var)
