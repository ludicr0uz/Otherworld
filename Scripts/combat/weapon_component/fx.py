"""The fight as everyone sees and hears it (combat/fx_vars.py has the
picture): the pair of events every cosmetic is, the three gates, and the
calls the owners make.

    pair(ed, name, params, body, gate)   Fx_<name> holding ``body``, and
                                         Multicast_<name>: gate -> FxPlayed
                                         + 1 -> Fx_<name>
    tell(g, name, execs, **params)       the server's call of Multicast_<name>
                                         (inside a Server event, or behind
                                         authority)
    predict(g, name, execs, **params)    the owning client's call of Fx_<name>
                                         (off the authority Branch's false arm)
    announce(g, name, execs, **params)   Branch HasAuthority: tell / predict,
                                         for a graph both machines run
                                         (ReloadNow)

The body of a point cosmetic (chips, blood, a sound where a blow landed) is
authored by the module that owns the blow, with ``point_transform`` for the
one transform the two bursts share. The chop's body is here because two
owners share it (the axe on a tree, a thrown blade in a trunk).
"""

from uebp import net
from uebp.g import _G
from uebp.graph import _connect, _node, _palette, _pin, _set, _vec, out, then
from combat.fx_vars import (
    CHOP, FxPlayed, LOCATION_PARAM, NORMAL_PARAM, OTHERS, POINT_PARAMS, SCREEN,
    UNPREDICTED, fx_event, multicast_event)
from combat.weapon_component.record import authority
from combat.weapon_component.slot_nodes import not_, op
from combat.weapon_component.surface_impact import _author_surface_impact
from combat.weapon_component import vars as WV
from Sound.play import _author_sound
from uebp.nodes.math import FN_ADD_II, FN_MAKE_TRANSFORM, FN_MUL_VF, FN_OR, FN_ROT_FROM_X
from uebp.nodes.palette import NODE_SPAWN
from uebp.nodes.system import FN_IS_DEDICATED_SERVER


# --- the gates ---------------------------------------------------------------

def _unpredicted(g):
    """This copy still owes the cosmetic: it has authority (the server, and
    single player), or it is not the owning client's (LocalInput is the
    local gate's answer, written on every copy each Tick: local.py)."""
    return op(g, FN_OR, authority(g), not_(g, g.get(WV.LocalInput)))


def _others(g):
    return not_(g, g.get(WV.LocalInput))


def _screen(g):
    return not_(g, out(g.call(FN_IS_DEDICATED_SERVER)))


GATES = {UNPREDICTED: _unpredicted, OTHERS: _others, SCREEN: _screen}


# --- the pair ------------------------------------------------------------------

def pair(ed, name, params, body, gate, item_class=None):
    """Author Fx_<name> and Multicast_<name>. ``body(g, exec_in, event)``
    authors the cosmetic off ``exec_in``, reading a parameter with
    ``out(event, param)``; ``item_class`` is what its ``g.iget`` reads. Before
    any call of either, which finds the event by name."""
    g = _G(ed, item_class)
    fx = g.keep(net.custom_event(ed, fx_event(name), params))
    body(g, then(fx), fx)
    ed.add_comment_to_nodes(
        f"{fx_event(name)} (fx.py): the cosmetic itself, once. Called by "
        f"{multicast_event(name)} where this copy owes it"
        + (", and by the owning client as its prediction." if gate == UNPREDICTED else "."),
        g.made)

    m = _G(ed)
    cast = m.keep(net.multicast_event(ed, multicast_event(name), params, reliable=False))
    plays, _owed_nothing = m.branch(GATES[gate](m), [then(cast)])
    flow = m.put(FxPlayed, op(m, FN_ADD_II, m.get(FxPlayed), 1), [plays])
    call = m.keep(_node(ed, fx_event(name)))
    for param, _type in params:
        _connect(out(cast, param), _pin(call, param))
    _connect(flow, _pin(call, "execute"))
    ed.add_comment_to_nodes(
        f"{multicast_event(name)} (fx.py): the server's word that it happened, to "
        f"every machine, unreliable (a lost one loses a sound, never state). Gate "
        f"'{gate}' (combat/fx_vars.py); what passes is counted in {FxPlayed} and "
        f"played by {fx_event(name)}.", m.made)
    return fx, cast


def _call(g, event, execs, params):
    call = g.keep(_node(g.ed, event))
    for param, value in params.items():
        if isinstance(value, (bool, int, float, str)):
            _set(call, param, value)
        else:
            _connect(value, _pin(call, param))
    for e in execs:
        _connect(e, _pin(call, "execute"))
    return then(call)


def tell(g, name, execs, **params):
    """The server's: Multicast_<name>. Returns the exec pin after it."""
    return _call(g, multicast_event(name), execs, params)


def predict(g, name, execs, **params):
    """The owning client's own, at once: Fx_<name>. Returns the exec pin after."""
    return _call(g, fx_event(name), execs, params)


def announce(g, name, execs, **params):
    """Branch HasAuthority: told to everyone, or predicted here. Returns the
    two exec pins after."""
    owns, mine = g.branch(authority(g), execs)
    return [tell(g, name, [owns], **params), predict(g, name, [mine], **params)]


# --- point cosmetics: shared pieces ---------------------------------------------

def point_transform(g, event, scale=None):
    """The one transform a burst is spawned at: the event's Location, +X
    turned onto its Normal (each burst throws its cone along its own
    forward), and ``scale`` (a float pin) on every axis, or 1."""
    facing = g.call(FN_ROT_FROM_X, X=out(event, NORMAL_PARAM))
    where = g.call(FN_MAKE_TRANSFORM, Location=out(event, LOCATION_PARAM),
                   Rotation=out(facing))
    if scale is not None:
        sized = g.call(FN_MUL_VF, A=_vec(g.ed, 1.0, 1.0, 1.0), B=scale)
        _connect(out(sized), _pin(where, "Scale"))
    return where


def spawn_blood(g, where, execs):
    """BloodClass at ``where``. Returns the spawn node."""
    splash = g.keep(_palette(g.ed, NODE_SPAWN))
    _connect(g.get(WV.BloodClass), _pin(splash, "Class"))
    _connect(out(where), _pin(splash, "SpawnTransform"))
    _set(splash, "CollisionHandlingOverride", "AlwaysSpawn")
    for e in execs:
        _connect(e, _pin(splash, "execute"))
    return splash


def body_chop(g, exec_in, event):
    """Chips off the cut and one of ChopSounds from it: the axe in the wood,
    whether swung (chop.py) or thrown (throw_strike.py)."""
    where = point_transform(g, event)
    _cls, chipped = _author_surface_impact(g.ed, where, exec_in)
    g.keep(_cls)
    g.keep(chipped)
    return _author_sound(g.ed, WV.ChopSounds, out(event, LOCATION_PARAM), then(chipped))


def pair_chop(ed, name=CHOP):
    """The chop's pair, under ``name``: CHOP for the swing's, LODGE for the
    thrown blade's, so each owner's chips stay its own."""
    return pair(ed, name, POINT_PARAMS, body_chop, SCREEN)
