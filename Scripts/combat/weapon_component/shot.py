"""The shot and the reload as server requests (combat/shot_vars.py has the
picture): the two Server events, the reload both machines run, and the local
arm's asks, which are also the owning client's prediction.

    Server_Fire(AimPoint)   the server's: the guard's Allow (net/guard.py),
                            counted served whatever it said, then its
                            AimAllowed of the client's AimPoint; refused unless
                            Held is valid, the owner alive, the item a gun
                            (not Melee, Consumable or Lights), a round in it
                            and its cooldown over (within FIRE_GRACE_S); then
                            firing.py's shot from the server's own muzzle to
                            the client's AimPoint, and its noise
    Server_Reload           the guard's Allow, counted served, then ReloadNow
    ReloadNow               Held valid and the owner alive: ammo.py's reload

    _author_shot_ask        the trigger's gate passed, where the keys are:
                            without authority the shot's sound (Fx_Shot), a
                            round off Loaded, the cooldown and AsksSent;
                            Server_Fire
    _author_reload_ask      R: without authority ReloadNow and AsksSent;
                            Server_Reload

What everyone else sees and hears of it is fx.py's (task M21,
combat/fx_vars.py): Server_Fire tells Multicast_Shot before it traces, and
ReloadNow announces Multicast_Reload after a reload that moved rounds; each
plays Held's sound on every copy that did not predict it.

In single player the one machine has authority, so the asks predict nothing
and the Server events are plain calls: one shot, one reload, as before.

The server does not ask whether the player is sprinting or guarding. Both are
the local gate's: the guard is the owning client's alone until melee and
block are the server's, and a sprint's end and the shot behind it travel
separately, so the server would refuse honest shots.
"""

from net.guard import author_aim_guard, author_allow
from uebp import net
from uebp.g import _G
from uebp.graph import _connect, _loose_pin, _node, _palette, _pin, out, then
from combat import health_vars as HV
from combat import item_vars as IV
from combat.light_tuning import LIGHTS_VAR
from combat.paths import HEALTH_CLASS_PATH, ITEM_CLASS_PATH
from combat.shot_vars import (
    AIM_PARAM, FIRE_GRACE_S, FIRE_PARAMS, RELOAD_NOW, SERVER_FIRE, SERVER_RELOAD,
    AsksSent, AsksServed)
from combat.weapon_component import vars as WV
from combat.fx_vars import RELOAD, SHOT
from combat.weapon_component import fx
from combat.weapon_component.ammo import _author_reload
from combat.weapon_component.carry import _author_shot_origin
from combat.weapon_component.firing import _author_fire
from combat.weapon_component.record import authority, rep_dirty
from combat.weapon_component.shot_noise import _author_shot_noise
from combat.weapon_component.slot_nodes import not_, op, valid
from uebp.nodes.actor import FN_ACTOR_LOC, FN_GET_COMP, FN_GET_OWNER
from uebp.nodes.math import (
    FN_ADD_FF, FN_ADD_II, FN_AND, FN_GE_FF, FN_GREATER_II, FN_LE_FF, FN_OR, FN_SUB_II)
from uebp.nodes.palette import NODE_CAST_HEALTH
from uebp.nodes.system import FN_PLAY_SOUND, FN_TIME_SECONDS

import unreal


def replicate_shot(bp):
    """AsksServed travels to the owner, and its arrival makes the view look
    again (view.py). After every declare, before the compile."""
    rep_dirty(bp, AsksServed, unreal.LifetimeCondition.COND_OWNER_ONLY)


def _count(g, var, execs):
    """var += 1. Returns the exec pin after it."""
    return g.put(var, op(g, FN_ADD_II, g.get(var), 1), execs)


def _author_alive(g, execs):
    """The exec pins a living owner's ask carries on from. The Tick's dead
    gate stops a dead player's keys; a request can arrive after the blow that
    killed, so the events ask the health itself, as that gate does."""
    comp = g.call(FN_GET_COMP, self=out(g.call(FN_GET_OWNER)))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)
    cast = g.keep(_palette(g.ed, NODE_CAST_HEALTH))
    _connect(out(comp), _pin(cast, "Object"))
    for e in execs:
        _connect(e, _pin(cast, "execute"))
    health = _loose_pin(cast, "AsBPHealthComponent", is_input=False)
    gone = op(g, FN_OR, g.iget(health, HV.Dead, HEALTH_CLASS_PATH),
              out(g.call(FN_LE_FF, A=g.iget(health, HV.Health, HEALTH_CLASS_PATH))))
    _dead, alive = g.branch(gone, [then(cast)])
    return [alive, _pin(cast, "CastFailed", is_input=False)]


def _author_server_fire(ed):
    g = _G(ed, ITEM_CLASS_PATH)
    event = g.keep(net.server_event(ed, SERVER_FIRE, FIRE_PARAMS))
    # Asked first, and counted served either way: a refused shot's round is
    # handed back like any other the server did not fire.
    flow, allowed = author_allow(g, SERVER_FIRE, [then(event)])
    flow = _count(g, AsksServed, [flow])
    go, _refused = g.branch(allowed, [flow])
    aimed, _behind = author_aim_guard(g, out(event, AIM_PARAM), [go])
    held = g.get(WV.Held)
    armed, _empty = g.branch(valid(g, held), [aimed])
    alive = _author_alive(g, [armed])
    # Only a gun is fired: the knife, food and the matches have the fire key's
    # other arms, which are not this request.
    tool = op(g, FN_OR, op(g, FN_OR, g.iget(held, IV.Melee), g.iget(held, IV.Consumable)),
              g.iget(held, LIGHTS_VAR))
    _tool, gun = g.branch(tool, alive)
    has_ammo = op(g, FN_OR, not_(g, g.iget(held, IV.UsesAmmo)),
                  op(g, FN_GREATER_II, g.iget(held, IV.Loaded), 0))
    soon = op(g, FN_ADD_FF, out(g.call(FN_TIME_SECONDS)), str(FIRE_GRACE_S))
    cooled = op(g, FN_GE_FF, soon, g.iget(held, IV.NextFireTime))
    fire, _refused = g.branch(op(g, FN_AND, has_ammo, cooled), [gun])
    ed.add_comment_to_nodes(
        f"{SERVER_FIRE} (shot.py): the owning client's trigger. The guard is asked "
        "(net/guard.py: how often, and an AimPoint its view could rest on); counted "
        "served either way, then refused unless there is a gun in a living hand with a round in it and its "
        f"cooldown over (within {FIRE_GRACE_S:g} s: packets do not arrive evenly). The "
        "shot is traced from this machine's muzzle to the client's AimPoint.", g.made)
    # Heard by everyone who did not predict it, before the pellets fly.
    told = fx.tell(g, SHOT, [fire])
    # The server's own muzzle: where the gun is here, not where a client says.
    muzzle = _author_shot_origin(ed, held)
    fired, flew = _author_fire(ed, held, muzzle, out(event, AIM_PARAM), told)
    _author_shot_noise(ed, held, muzzle, flew, fired)


def _author_reload_now(ed):
    g = _G(ed, ITEM_CLASS_PATH)
    event = g.keep(net.custom_event(ed, RELOAD_NOW))
    held = g.get(WV.Held)
    armed, _empty = g.branch(valid(g, held), [then(event)])
    alive = _author_alive(g, [armed])
    ed.add_comment_to_nodes(
        f"{RELOAD_NOW} (shot.py): the reload, with a valid Held and a living owner. "
        f"The server's from {SERVER_RELOAD}; the owning client calls it too, as its "
        "prediction. A reload that moved rounds is heard: told to everyone with "
        "authority, played here without.", g.made)
    moved, _nothing = _author_reload(ed, held, alive)
    fx.announce(g, RELOAD, [moved])


def _author_heard_on_gun(ed, sound_var):
    """The body of Fx_Shot and Fx_Reload: Held's ``sound_var`` played where
    the gun is, behind IsValid(Held). A few centimetres from the muzzle, and
    no second copy of the muzzle sub-graph."""
    def body(g, exec_in, _event):
        held = g.get(WV.Held)
        armed, _empty = g.branch(valid(g, held), [exec_in])
        g.call(FN_PLAY_SOUND, [armed], Sound=g.iget(held, sound_var),
               Location=out(g.call(FN_ACTOR_LOC, self=held)))
    return body


def _author_server_reload(ed):
    g = _G(ed)
    event = g.keep(net.server_event(ed, SERVER_RELOAD))
    flow, allowed = author_allow(g, SERVER_RELOAD, [then(event)])
    flow = _count(g, AsksServed, [flow])
    go, _refused = g.branch(allowed, [flow])
    call = g.keep(_node(ed, RELOAD_NOW))
    _connect(go, _pin(call, "execute"))
    ed.add_comment_to_nodes(
        f"{SERVER_RELOAD} (shot.py): the owning client's R. Counted served, then the "
        "reload.", g.made)


def author_shot_events(ed):
    """The three events, and the shot's and the reload's cosmetics. Before
    the Tick, which calls them by name."""
    for name, sound in ((SHOT, IV.FireSound), (RELOAD, IV.ReloadSound)):
        fx.pair(ed, name, (), _author_heard_on_gun(ed, sound), fx.UNPREDICTED,
                item_class=ITEM_CLASS_PATH)
    _author_server_fire(ed)
    _author_reload_now(ed)
    _author_server_reload(ed)


def _author_shot_ask(ed, held, muzzle, exec_in):
    """The trigger's gate passed, on the machine with the keys. Returns the
    exec pin after the ask."""
    g = _G(ed, ITEM_CLASS_PATH)
    owns, predicts = g.branch(authority(g), [exec_in])
    # Heard by whoever fired, at once: its prediction (with authority the
    # event tells everyone, this machine included).
    heard = fx.predict(g, SHOT, [predicts])
    flow = g.iput(held, IV.Loaded, op(g, FN_SUB_II, g.iget(held, IV.Loaded), 1), [heard])
    again = op(g, FN_ADD_FF, out(g.call(FN_TIME_SECONDS)), g.iget(held, IV.FireInterval))
    flow = g.iput(held, IV.NextFireTime, again, [flow])
    flow = _count(g, AsksSent, [flow])
    ask = g.keep(_node(ed, SERVER_FIRE))
    _connect(g.get(WV.AimPoint), _pin(ask, AIM_PARAM))
    for e in (owns, flow):
        _connect(e, _pin(ask, "execute"))
    ed.add_comment_to_nodes(
        f"The shot is asked of the server ({SERVER_FIRE}, shot.py), with where the "
        "reticle rests. A client of a server plays its sound at once, spends the "
        "round and stamps the cooldown on its own copy, its prediction, and counts "
        "the ask: the view takes the server's rounds again once every ask is "
        "answered. With authority (single player) the event is the shot.",
        g.made)
    return then(ask)


def _author_reload_ask(ed, exec_in):
    """R, on the machine with the keys and a valid Held. Returns the exec pin
    after the ask."""
    g = _G(ed)
    owns, predicts = g.branch(authority(g), [exec_in])
    now = g.keep(_node(ed, RELOAD_NOW))
    _connect(predicts, _pin(now, "execute"))
    flow = _count(g, AsksSent, [then(now)])
    ask = g.keep(_node(ed, SERVER_RELOAD))
    for e in (owns, flow):
        _connect(e, _pin(ask, "execute"))
    ed.add_comment_to_nodes(
        f"The reload is asked of the server ({SERVER_RELOAD}, shot.py). A client of "
        "a server reloads its own copy first, its prediction, and counts the ask.",
        g.made)
    return then(ask)
