"""On a client the fire action is the owning player's, and its press is a
shot on the server (I1; the single-player half is probe_fire_action.py).

    client 1   has the game's mapping context on its local player; IA_Fire
               handed to its Enhanced Input subsystem stamps the press on
               its own weapon component and spends its predicted round.
    server     no component there was pressed or is held (it has no local
               player to add a context for), and client 1's gun is a round
               down: the press went the whole way, Server_Fire included.
"""

SYSTEMS = ('net', 'weapons')

import time

import unreal

from combat.input_consts import IA_FIRE, IMC_DEFAULT
from combat.paths import WEAPON_COMP_CLASS_PATH
from combat.weapon_component import vars as WV
from uebp.nodes.weapon import FIRE_HELD

WAIT_S = 20.0
DOWN = unreal.Vector(1.0, 0.0, 0.0)


def _await(cond, seconds=WAIT_S):
    end = time.time() + seconds
    return lambda: cond() or time.time() > end


def _comp(p, actor):
    return p.component(actor, WEAPON_COMP_CLASS_PATH)


def _loaded(p, comp):
    held = p.get(comp, "Held")
    return p.get(held, "Loaded") if held else None


def probe_server(p):
    yield 1.0
    comps = [_comp(p, pc.get_controlled_pawn()) for pc in p.players()
             if pc.get_controlled_pawn()]
    before = [_loaded(p, c) for c in comps]
    p.check("every player's character is here, a loaded gun in hand",
            len(comps) == p.clients and all(n for n in before), str(before))
    p.post("ready")
    yield _await(lambda: p.posted("client 1", "pressed"))
    yield 0.5
    after = [_loaded(p, c) for c in comps]
    p.check("client 1's press of the action spent one round on the server",
            sorted(b - a for b, a in zip(before, after)) == [0] * (len(comps) - 1) + [1],
            f"{before} -> {after}")
    p.check("...and no component on the server was pressed or is held",
            all(p.get(c, WV.FirePressedAt) < 0.0 and not p.get(c, FIRE_HELD) for c in comps),
            str([(p.get(c, WV.FirePressedAt), p.get(c, FIRE_HELD)) for c in comps]))


def probe_client(p):
    yield _await(lambda: p.pawn() is not None and p.posted("server", "ready"))
    yield 0.5
    if p.client != 1:
        return
    own = _comp(p, p.pawn())
    action, context = unreal.load_asset(IA_FIRE), unreal.load_asset(IMC_DEFAULT)
    found = [o for o in unreal.ObjectIterator(unreal.EnhancedInputLocalPlayerSubsystem)
             if not o.get_name().startswith("Default__")]
    p.check("the client's local player has the game's mapping context",
            len(found) == 1 and found[0].has_mapping_context(context) is not None,
            f"{len(found)} subsystem(s)")
    if len(found) != 1:
        return
    start = _loaded(p, own)
    found[0].inject_input_vector_for_action(action, DOWN, [], [])
    yield _await(lambda: _loaded(p, own) != start)
    p.check("the action pressed stamps the press and spends the predicted round",
            p.get(own, WV.FirePressedAt) > 0.0 and _loaded(p, own) == start - 1,
            f"{start} -> {_loaded(p, own)}")
    p.post("pressed")
    yield 1.0
    p.check("...and the server's answer leaves it one round down, not two",
            _loaded(p, own) == start - 1, f"{start} -> {_loaded(p, own)}")
