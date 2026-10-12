"""One world clock (M30): the head of BP_DayNightCycle's Tick, which decides
where this machine's Clock comes from, and the wind's shared time.

The cycle is placed in the level and does not replicate, so every machine has
one of its own; what makes them one sky is that only the server's keeps time.

    Tick --> Switch Has Authority
      Authority (a server, and single player):
          Clock := (Clock + dt) % (day + night)          as it always did
          the GameState, when what it holds is no longer true:
              WorldClockOffset := (Clock - time % cycle + cycle) % cycle
              WorldDayLength, WorldNightLength := the cycle's two lengths
      Remote (a client of a server), once the GameState has the lengths:
          DayLengthSeconds, NightLengthSeconds := the GameState's
          Clock := (WorldClockOffset + time) % (day + night)

``time`` is GameStateBase.GetServerWorldTimeSeconds: the world's own time on
the server, and on a client the engine's estimate of it, which it keeps in
step by itself. So the offset is a constant while the clock just runs, and the
server writes the GameState only when something moved the clock or a length
(the random start, the WORLD SETTINGS dial, a probe): nothing replicates per
frame, and a client's sky moves smoothly between the engine's corrections.
The server's Clock stays a plain variable anyone on that machine may write.
A client's is the server's every frame: a write to it there does nothing.

The wind: its only state is where in its sway it is, which the materials read
off their own machine's time. Both arms store ``time % WIND_WRAP_S`` less this
machine's world time in WindTimeOffset, and author_wind_time() puts it in
MPC_Wind.TimeOffset, which the materials add to their time
(forest_import/wind.py). It is 0 through single player's first hour; the wrap
keeps the sum small enough for a float, at the price of one skip an hour.
"""

import unreal

from forest_generator.wind import MPC_NAME, MPC_PATH, PARAM_TIME_OFFSET
from net import state_consts as S
from net.state_graph import game_state
from uebp.g import _G
from uebp.graph import BEL, _connect, _must_load, _pin, _set, out
from uebp.nodes.math import (
    FN_ABS, FN_ADD_FF, FN_GREATER_FF, FN_NEQ_FF, FN_OR, FN_PERCENT_FF, FN_SUB_FF)
from uebp.nodes.palette import MACRO_SWITCH_AUTHORITY
from uebp.nodes.system import FN_SERVER_WORLD_TIME, FN_SET_MPC_SCALAR, FN_TIME_SECONDS
from world import day_night_vars as DV

# How far the GameState's offset may be from the server's clock before the
# server writes it again: far above what two sums of the same frame times
# drift apart by, far below what anyone could see in the sky.
PUBLISH_SLACK_S = 0.05
# The wind's shared time wraps here (see the module docstring).
WIND_WRAP_S = 3600.0
PINS = unreal.BlueprintGraphPinLibrary
MPC_WIND_OBJECT_PATH = f"{MPC_PATH}.{MPC_NAME}"


def _f(g, fn, a, b):
    """fn(a, b) of two floats; ``b`` a pin, or a number (a literal stays on B)."""
    n = g.call(fn, A=a)
    if isinstance(b, (int, float)):
        _set(n, "B", float(b))
    else:
        _connect(b, _pin(n, "B"))
    return out(n)


def _server_time(g, state):
    """The server's world time, off a GameState pin known to be valid."""
    n = g.call(FN_SERVER_WORLD_TIME, self=state)
    names = [str(PINS.get_pin_name(q)) for q in BEL.list_input_pins(n)]
    if "execute" in names or "self" not in names:
        raise RuntimeError(f"GetServerWorldTimeSeconds: not the pure node expected: {names}")
    return out(n)


def _wind_offset(g, time, execs):
    """WindTimeOffset := time % WIND_WRAP_S - this machine's world time."""
    here = out(g.call(FN_TIME_SECONDS))
    shared = _f(g, FN_PERCENT_FF, time, WIND_WRAP_S)
    return g.put(DV.WindTimeOffset, _f(g, FN_SUB_FF, shared, here), execs)


def _author_server(g, tick, authority):
    """Advance Clock, then publish it where the GameState is out of date."""
    day, night = g.get(DV.DayLengthSeconds), g.get(DV.NightLengthSeconds)
    total = _f(g, FN_ADD_FF, day, night)
    ahead = _f(g, FN_ADD_FF, g.get(DV.Clock), out(tick, "DeltaSeconds"))
    flow = g.put(DV.Clock, _f(g, FN_PERCENT_FF, ahead, total), [authority])

    got = game_state(g.ed, [flow])
    g.made.extend(got.nodes)
    time = _server_time(g, got.pin)
    flow = _wind_offset(g, time, [got.then])
    # Clock less the time, wrapped: + total keeps the remainder positive.
    behind = _f(g, FN_SUB_FF, g.get(DV.Clock), _f(g, FN_PERCENT_FF, time, total))
    want = _f(g, FN_PERCENT_FF, _f(g, FN_ADD_FF, behind, total), total)
    held = g.iget(got.pin, S.WorldClockOffset, S.GAME_STATE_CLASS_PATH)
    gap = out(g.call(FN_ABS, A=_f(g, FN_SUB_FF, want, held)))
    stale = _f(g, FN_GREATER_FF, gap, PUBLISH_SLACK_S)
    for var, mine in ((S.WorldDayLength, day), (S.WorldNightLength, night)):
        theirs = g.iget(got.pin, var, S.GAME_STATE_CLASS_PATH)
        stale = out(g.call(FN_OR, A=stale, B=_f(g, FN_NEQ_FF, theirs, mine)))
    write, same = g.branch(stale, [flow])
    for var, value in ((S.WorldClockOffset, want), (S.WorldDayLength, day),
                       (S.WorldNightLength, night)):
        write = g.iput(got.pin, var, value, [write], S.GAME_STATE_CLASS_PATH)
    return [write, same] + got.fails


def _author_client(g, remote):
    """Take the lengths and the Clock from the GameState, once it has them."""
    got = game_state(g.ed, [remote])
    g.made.extend(got.nodes)
    time = _server_time(g, got.pin)
    flow = _wind_offset(g, time, [got.then])
    day = g.iget(got.pin, S.WorldDayLength, S.GAME_STATE_CLASS_PATH)
    night = g.iget(got.pin, S.WorldNightLength, S.GAME_STATE_CLASS_PATH)
    # 0 is "the server has not published yet": a cycle of no length has no
    # remainder to take.
    ready, early = g.branch(_f(g, FN_GREATER_FF, day, 0.0), [flow])
    flow = g.put(DV.DayLengthSeconds, day, [ready])
    flow = g.put(DV.NightLengthSeconds, night, [flow])
    offset = g.iget(got.pin, S.WorldClockOffset, S.GAME_STATE_CLASS_PATH)
    now = _f(g, FN_PERCENT_FF, _f(g, FN_ADD_FF, offset, time),
             _f(g, FN_ADD_FF, day, night))
    flow = g.put(DV.Clock, now, [flow])
    return [flow, early] + got.fails


def author_clock_source(ed, tick, exec_in):
    """The head of the Tick (see the module docstring). Returns the exec
    tails: every one goes on to the rest of the Tick, which reads Clock."""
    _must_load(S.GAME_STATE_BP_PATH)   # the cast exists only for a loaded class
    g = _G(ed)
    owns = g.keep(ed.add_macro_node(MACRO_SWITCH_AUTHORITY))
    _connect(exec_in, _pin(owns, "execute"))
    tails = _author_server(g, tick, out(owns, "Authority"))
    tails += _author_client(g, out(owns, "Remote"))
    ed.add_comment_to_nodes(
        "One world clock (M30). With authority (a server, single player): advance "
        "Clock, and write the GameState's WorldClockOffset and lengths when they are "
        "out of date. A client: take the lengths from the GameState and "
        "Clock = (WorldClockOffset + the server's world time) % the cycle.", g.made)
    return tails


def author_wind_time(ed, chain):
    """Extend the Tick chain: MPC_Wind.TimeOffset := WindTimeOffset."""
    _must_load(MPC_PATH)
    g = _G(ed)
    write = chain.step(g.call(FN_SET_MPC_SCALAR, ParameterName=PARAM_TIME_OFFSET,
                              ParameterValue=g.get(DV.WindTimeOffset)))
    pin = _pin(write, "Collection")
    pin.set_pin_value(MPC_WIND_OBJECT_PATH)
    got = str(pin.get_pin_value())
    if MPC_NAME not in got:
        raise RuntimeError(f"the Collection pin would not take {MPC_WIND_OBJECT_PATH!r}: {got!r}")
    ed.add_comment_to_nodes(
        f"The wind's time: {MPC_NAME}.{PARAM_TIME_OFFSET} := WindTimeOffset, the server's "
        "world time less this machine's, so every machine's grass sways as one.", [write])
