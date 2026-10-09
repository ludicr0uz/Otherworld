"""verify.shot_hits -- a shot's impacts are told once (task A4,
weapon_component/shot_hits.py): the fire graph notes each pellet's impact
onto three arrays, FlushShotHits tells them in one Multicast_ShotHits after
the last pellet, and that Multicast plays Fx_PelletHit once per entry on
every machine with a screen. No pellet has a Multicast of its own.

Proof in the running game is probes/probe_net_fx.py (client 2 counts the
impacts) and, in single player, probes/probe_headshot.py.
"""

from combat import fx_vars as FX
from combat.hit_zones import HIT_POINT_VAR
from combat.verify import fx as fxv
from combat.verify.common import BEL, PIN, check, in_pins, pellet_calls, pin_value
from combat.verify.fixtures import exec_reach, wc, wg
from combat.verify.record import _feeders, _title
from uebp import net

FX_EVENT = FX.fx_event(FX.PELLET_HIT)
CAST = FX.multicast_event(FX.SHOT_HITS)
ARRAYS = (FX.ShotHitLocations, FX.ShotHitNormals, FX.ShotHitBloods)


def _array_nodes(nodes, *extra):
    """The array-library calls among ``nodes`` whose inputs are TargetArray
    and ``extra`` exactly."""
    want = {"TargetArray", *extra}
    return [n for n in nodes if set(in_pins(n)) - {"execute", "self"} == want]


def _array_of(node):
    """The titles of what feeds an array call's TargetArray."""
    return {_title(n) for n in _feeders(node, "TargetArray")}


def _reach(event):
    return exec_reach([p for p in BEL.list_output_pins(event)
                       if str(PIN.get_pin_name(p)) == "then"])


def check_events():
    check(f"{FX_EVENT} is a plain event and {CAST} an unreliable Multicast: the "
          "cosmetic once, and the server's word of a whole shot's to everyone",
          fxv.event(FX_EVENT) is not None and fxv.event(CAST) is not None
          and net.compiled_rpc(wc, FX_EVENT) == (net.LOCAL, False)
          and net.compiled_rpc(wc, CAST) == (net.MULTICAST, False))
    check(f"...and no pellet has a Multicast of its own "
          f"({FX.multicast_event(FX.PELLET_HIT)} is gone)",
          fxv.event(FX.multicast_event(FX.PELLET_HIT)) is None)
    for var in (*ARRAYS, FX.ShotHitScale):
        check(f"{var} is the server's own: it does not replicate",
              net.variable_replication(wc, str(var))[0] == net.NONE)


def check_multicast():
    cast = fxv.event(CAST)
    if cast is None:
        return
    gates = [n for n in fxv._feeders_then(cast) if _title(n) == "Branch"]
    asked = set().union(*[{fxv._squash(t) for t in fxv._reads(n)} for n in gates]) if gates else set()
    check(f"{CAST} asks its gate first ('{FX.SCREEN}': IsDedicatedServer)",
          len(gates) == 1 and "IsDedicatedServer" in asked
          and not ({"HasAuthority", fxv._squash(f"Get {fxv.WV.LocalInput}")} & asked),
          str(sorted(asked)))
    if len(gates) != 1:
        return
    counted = fxv._feeders_then(gates[0])
    lengths = [n for n in _feeders(_feeders(counted[0], str(FX.FxPlayed))[0], "B")
               if set(in_pins(n)) == {"TargetArray"}] if len(counted) == 1 else []
    check(f"...and on its true arm counts {FX.FxPlayed} up by the number of impacts "
          "(the Locations' length): one per burst, as each pellet's own Multicast did",
          len(counted) == 1 and _title(counted[0]) == f"Set {FX.FxPlayed}"
          and len(lengths) == 1 and _feeders(lengths[0], "TargetArray") == [cast],
          f"{[_title(n) for n in counted]}, {len(lengths)} length(s)")
    body = _reach(cast)
    loops = [n for n in body if "ForLoop" in _title(n).replace(" ", "")]
    inner = [n for n in fxv._calls_named(FX_EVENT) if n in body]
    check(f"...then, in a loop over them, calls {FX_EVENT} once",
          len(loops) == 1 and len(inner) == 1
          and [str(PIN.get_pin_name(q)) for q in PIN.list_connected_pins(
              BEL.find_input_pin(inner[0], "execute"))] == ["LoopBody"],
          f"{len(loops)} loop(s), {len(inner)} call(s)")
    if len(inner) != 1:
        return
    for param, array in ((FX.LOCATION_PARAM, FX.LOCATIONS_PARAM),
                         (FX.NORMAL_PARAM, FX.NORMALS_PARAM), (FX.BLOOD_PARAM, FX.BLOODS_PARAM)):
        gets = _feeders(inner[0], param)
        src = [str(PIN.get_pin_name(q)) for g in gets
               for q in PIN.list_connected_pins(BEL.find_input_pin(g, "TargetArray"))]
        idx = {_title(n).replace(" ", "") for g in gets for n in _feeders(g, "Index")}
        check(f"...with {param} the entry of the event's {array} at the loop's index",
              len(gets) == 1 and src == [array] and idx == {"ForLoop"}, f"{src} at {idx}")
    check(f"...and {FX.SCALE_PARAM} the event's own, the same for every entry",
          _feeders(inner[0], FX.SCALE_PARAM) == [cast])
    callers = fxv._calls_named(FX_EVENT)
    check(f"nobody predicts a pellet's impact: {FX_EVENT} is called by {CAST} alone",
          len(callers) == 1, f"{len(callers)} call(s)")


def check_notes():
    adds = _array_nodes(wg, "NewItem")
    by_array = {str(var): [n for n in adds if _array_of(n) == {f"Get {var}"}] for var in ARRAYS}
    check("the fire graph notes an impact twice (the scenery's chips, a body's blood): "
          "an Add onto each of the three arrays per note, nothing else writes them",
          all(len(v) == 2 for v in by_array.values()), str({k: len(v) for k, v in by_array.items()}))
    if not all(len(v) == 2 for v in by_array.values()):
        return
    # A literal equal to its pin's default (false) is not saved: "" once
    # loaded from disk, "false" in the editor that authored it.
    bloods = sorted(str(pin_value(n, "NewItem")).lower() or "false"
                    for n in by_array[str(FX.ShotHitBloods)])
    check("...one with Blood false and one with Blood true",
          bloods == ["false", "true"], str(bloods))
    spots = {t for n in by_array[str(FX.ShotHitLocations)] for t in
             {_title(f) for f in _feeders(n, "NewItem")}}
    check(f"...each at {HIT_POINT_VAR}: the pellet's own hit, moved onto the body it struck",
          spots == {f"Get {HIT_POINT_VAR}"}, str(spots))
    # Each note starts at its Set ShotHitScale: the blood's off the Branch on
    # PelletFlew's bHurt, the chips' off the Branch on its bScenery, which
    # hangs off the first one's False (verify/hit_bodies.py).
    starts = [n for n in wg if _title(n) == f"Set {FX.ShotHitScale}"]

    def gate(n):
        """(the flag the Branch that runs ``n`` asks, the arm it runs it off)."""
        links = PIN.list_connected_pins(BEL.find_input_pin(n, "execute"))
        if len(links) != 1:
            return None
        branch = PIN.get_owning_node(links[0])
        asks = [str(PIN.get_pin_name(q)) for q in PIN.list_connected_pins(
            BEL.find_input_pin(branch, "Condition"))] if "Condition" in in_pins(branch) else []
        return (asks[0] if len(asks) == 1 else None, str(PIN.get_pin_name(links[0])))
    gates = sorted(str(gate(n)) for n in starts)
    check("...the blood where the pellet hurt a body (bHurt), the chips where it struck "
          "what has no health (bScenery): a pellet never notes both",
          gates == sorted([str(("bHurt", "then")), str(("bScenery", "then"))]), str(gates))


def check_flush():
    flush = fxv.event(FX.FLUSH_SHOT_HITS)
    check(f"{FX.FLUSH_SHOT_HITS} is a plain event", flush is not None
          and net.compiled_rpc(wc, FX.FLUSH_SHOT_HITS) == (net.LOCAL, False))
    if flush is None:
        return
    calls = fxv._calls_named(FX.FLUSH_SHOT_HITS)
    after = [str(PIN.get_pin_name(q)) for n in calls
             for q in PIN.list_connected_pins(BEL.find_input_pin(n, "execute"))]
    callers = [PIN.get_owning_node(q) for n in calls
               for q in PIN.list_connected_pins(BEL.find_input_pin(n, "execute"))]
    check("...called once, when the native FirePellets has flown its last pellet",
          len(calls) == 1 and after == ["then"] and callers == pellet_calls(wg),
          f"{len(calls)} call(s) off {after}")
    body = _reach(flush)
    gates = [n for n in fxv._feeders_then(flush) if _title(n) == "Branch"]
    tells = fxv._calls_named(CAST)
    check(f"...which tells {CAST} once, only with something noted (a Branch on the "
          "Locations' length), and nothing else tells it",
          len(gates) == 1 and len(tells) == 1 and tells[0] in body
          and [str(PIN.get_pin_name(q)) for q in PIN.list_connected_pins(
              BEL.find_input_pin(tells[0], "execute"))] == ["then"],
          f"{len(gates)} gate(s), {len(tells)} tell(s)")
    if len(tells) == 1:
        fed = {param: {_title(n) for n in _feeders(tells[0], param)}
               for param, _t in FX.SHOT_HITS_PARAMS}
        want = {FX.LOCATIONS_PARAM: {f"Get {FX.ShotHitLocations}"},
                FX.NORMALS_PARAM: {f"Get {FX.ShotHitNormals}"},
                FX.BLOODS_PARAM: {f"Get {FX.ShotHitBloods}"},
                FX.SCALE_PARAM: {f"Get {FX.ShotHitScale}"}}
        check("...with the three arrays and the shot's Scale", fed == want, str(fed))
    clears = [n for n in _array_nodes(body) if "execute" in in_pins(n)]
    cleared = sorted(t for n in clears for t in _array_of(n))
    first = clears and sorted(str(PIN.get_pin_name(q)) for q in PIN.list_connected_pins(
        BEL.find_input_pin(next(n for n in clears if _array_of(n) == {f"Get {ARRAYS[0]}"}),
                           "execute")))
    check("...and empties all three after, told or not: the next shot starts with none",
          cleared == sorted(f"Get {v}" for v in ARRAYS) and first == ["else", "then"],
          f"{cleared} off {first}")


def run():
    check_events()
    check_multicast()
    check_notes()
    check_flush()
