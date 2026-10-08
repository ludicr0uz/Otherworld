"""A shot's impacts, told once (task A4): the pellets' blood and chips used
to be a Multicast each, eight a shotgun blast; now the server notes each as
its pellet lands and tells the lot when the last pellet is traced.

    note()            impact.py, where Multicast_PelletHit was told: the
                      impact's point, normal and Blood onto three arrays, and
                      the shot's Scale beside them
    FlushShotHits     a plain event the fire graph calls after its pellet
                      loop: with anything noted, Multicast_ShotHits; then the
                      arrays are emptied for the next shot
    Multicast_ShotHits(Locations, Normals, Bloods, Scale)
                      unreliable, gate SCREEN (fx.py): each entry counted in
                      FxPlayed and played by Fx_PelletHit, the cosmetic
                      itself, which is unchanged (impact.py)

In single player the Multicast is a plain call, so the same graph plays the
bursts there. combat/fx_vars.py has the names; verify/shot_hits.py the checks.
"""

from combat.fx_vars import (
    BLOOD_PARAM, BLOODS_PARAM, FLUSH_SHOT_HITS, FxPlayed, LOCATION_PARAM, LOCATIONS_PARAM,
    NORMAL_PARAM, NORMALS_PARAM, PELLET_HIT, SCALE_PARAM, SCREEN, SHOT_HITS, SHOT_HITS_PARAMS,
    ShotHitBloods, ShotHitLocations, ShotHitNormals, ShotHitScale, fx_event, multicast_event,
)
from combat.weapon_component.slot_nodes import op
from combat.weapon_component.fx import GATES
from uebp import net
from uebp.g import _G
from uebp.graph import _connect, _loose_pin, _node, _pin, _set, out, then
from uebp.nodes.array import FN_ARR_ADD, FN_ARR_CLEAR, FN_ARR_GET, FN_ARR_LEN
from uebp.nodes.math import FN_ADD_II, FN_GREATER_II, FN_SUB_II
from uebp.nodes.palette import MACRO_FOR_LOOP

# The arrays, in the order of the Multicast's parameters.
NOTED = ((ShotHitLocations, LOCATIONS_PARAM), (ShotHitNormals, NORMALS_PARAM),
         (ShotHitBloods, BLOODS_PARAM))


def _array_call(g, fn, array, execs=()):
    n = g.keep(_node(g.ed, fn))
    _connect(array, _loose_pin(n, "TargetArray"))
    for e in execs:
        _connect(e, _pin(n, "execute"))
    return n


def note(g, execs, location, normal, scale, blood):
    """One impact onto the shot's batch. ``blood`` is a Python bool. Returns
    the exec pin after."""
    flow = g.put(ShotHitScale, scale, execs)
    for var, value in ((ShotHitLocations, location), (ShotHitNormals, normal)):
        add = _array_call(g, FN_ARR_ADD, g.get(var), [flow])
        _connect(value, _loose_pin(add, "NewItem"))
        flow = then(add)
    add = _array_call(g, FN_ARR_ADD, g.get(ShotHitBloods), [flow])
    _set(add, "NewItem", blood)
    return then(add)


def flush(g, execs):
    """After the pellet loop: tell what was noted. Returns the exec pin after."""
    call = g.keep(_node(g.ed, FLUSH_SHOT_HITS))
    for e in execs:
        _connect(e, _pin(call, "execute"))
    return then(call)


def _author_flush(ed):
    g = _G(ed)
    event = g.keep(net.custom_event(ed, FLUSH_SHOT_HITS))
    count = _array_call(g, FN_ARR_LEN, g.get(ShotHitLocations))
    some, none = g.branch(op(g, FN_GREATER_II, out(count), 0), [then(event)])
    tell = g.keep(_node(ed, multicast_event(SHOT_HITS)))
    for var, param in NOTED:
        _connect(g.get(var), _pin(tell, param))
    _connect(g.get(ShotHitScale), _pin(tell, SCALE_PARAM))
    _connect(some, _pin(tell, "execute"))
    flow = [then(tell), none]
    for var, _param in NOTED:
        flow = [then(_array_call(g, FN_ARR_CLEAR, g.get(var), flow))]
    ed.add_comment_to_nodes(
        f"{FLUSH_SHOT_HITS} (shot_hits.py): the fire graph's, after its last pellet. "
        f"Everything the shot's pellets struck goes to every machine in one "
        f"{multicast_event(SHOT_HITS)}, and the batch is emptied for the next shot.",
        g.made)


def _author_multicast(ed):
    g = _G(ed)
    cast = g.keep(net.multicast_event(ed, multicast_event(SHOT_HITS), SHOT_HITS_PARAMS,
                                      reliable=False))
    plays, _owed_nothing = g.branch(GATES[SCREEN](g), [then(cast)])
    count = _array_call(g, FN_ARR_LEN, out(cast, LOCATIONS_PARAM))
    flow = g.put(FxPlayed, op(g, FN_ADD_II, g.get(FxPlayed), out(count)), [plays])
    loop = g.keep(ed.add_macro_node(MACRO_FOR_LOOP))
    _set(loop, "FirstIndex", 0)
    _connect(op(g, FN_SUB_II, out(count), 1), _loose_pin(loop, "LastIndex"))
    _connect(flow, _loose_pin(loop, "execute"))
    index = _loose_pin(loop, "Index", is_input=False)
    call = g.keep(_node(ed, fx_event(PELLET_HIT)))
    for array, param in ((LOCATIONS_PARAM, LOCATION_PARAM), (NORMALS_PARAM, NORMAL_PARAM),
                         (BLOODS_PARAM, BLOOD_PARAM)):
        item = g.keep(_node(ed, FN_ARR_GET))
        _connect(out(cast, array), _loose_pin(item, "TargetArray"))
        _connect(index, _loose_pin(item, "Index"))
        _connect(_loose_pin(item, "Item", is_input=False), _pin(call, param))
    _connect(out(cast, SCALE_PARAM), _pin(call, SCALE_PARAM))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(call, "execute"))
    ed.add_comment_to_nodes(
        f"{multicast_event(SHOT_HITS)} (shot_hits.py): the server's word of everything "
        f"one shot struck, to every machine, unreliable. Gate '{SCREEN}' "
        f"(combat/fx_vars.py); each entry is counted in {FxPlayed} and played by "
        f"{fx_event(PELLET_HIT)}.", g.made)


def author_shot_hits(ed):
    """The batch's two events. After Fx_PelletHit (impact.py), which the
    Multicast calls, and before the fire graph, which calls the flush."""
    _author_multicast(ed)
    _author_flush(ed)
