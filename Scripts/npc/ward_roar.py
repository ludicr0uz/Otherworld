"""The two roars of a wendigo held off by fire: fragments of the Ward step
(npc/ward.py). The numbers are forest_generator/npc_ward.py's.

    a hold begins     WardRoarAt = now + 13-17 s (one throw per hold)
    a held pass, short of the hold's end:
       -> [now < WardRoarUntil?]  still roaring: no order             succeed
       -> [WardRoarAt set, and up?]
            yes  WardRoarAt = 0 (once a hold) -> (roar)
            no   the caller's circle
    the hold's end (the caller has set the flight up) -> (roar)
    a pass of the flight:
       -> [now < WardRoarUntil?]  still roaring: no order             succeed
          no: the caller's run
    (roar)  WardRoarUntil = now + the roar -> stop, face the player, the
            roar clip and a voice (npc/roar.py)                       succeed

The first is tested behind the held check and the stamp of WardLast, so a
roar does not break the hold (it is longer than the grace), and a wendigo
whose fire goes down mid-roar attacks at once. The second is tested inside
the flight, which runs fire or no fire: it roars, then runs.

A blow that lands on the player writes WardSince back to 0 (npc/melee.py's
``clears``), so the next held pass begins a new hold: the count to the
flight starts over, and so does the throw for the first roar.
"""

from forest_generator.npc_ward import (
    NPC_WARD_ROAR_AT_S, NPC_WARD_ROAR_S, NPC_WARD_ROAR_VARY_S,
)
from uebp.graph import BEL, else_, out, then
from npc.paths import WARD_ROAR_AT_VAR, WARD_ROAR_UNTIL_VAR
from npc.roar import _author_bellow
from uebp.nodes.math import (
    FN_ADD_FF, FN_AND, FN_GREATER_FF, FN_LESS_FF, FN_LE_FF, FN_RANDOM_FLOAT)


def declare_ward_roar_vars(ed):
    """Both zero by default: no roar due, none under way."""
    for name in (WARD_ROAR_AT_VAR, WARD_ROAR_UNTIL_VAR):
        ed.remove_member_variable(name)
        if not ed.add_member_variable(name, BEL.get_basic_type_by_name("real")):
            raise RuntimeError(f"could not declare {name}")


def _author_roar_time(g, exec_in, pins):
    """WardRoarAt = now + one throw of the time to the hold's first roar.
    Returns the Set's then pin."""
    throw = g.call(FN_RANDOM_FLOAT,
                   Min=NPC_WARD_ROAR_AT_S - NPC_WARD_ROAR_VARY_S,
                   Max=NPC_WARD_ROAR_AT_S + NPC_WARD_ROAR_VARY_S)
    due = g.op(FN_ADD_FF, pins["now"], out(throw))
    return g.put(WARD_ROAR_AT_VAR, exec_in, pin=due)


def _author_roar_wait(g, exec_in, pins):
    """Is a roar still under way? Returns ``(standing, onward)``: the exec pin
    of a pass that is, and that of one that is not."""
    during = g.op(FN_LESS_FF, pins["now"], g.get(WARD_ROAR_UNTIL_VAR))
    roaring = g.branch(during, exec_in)
    return then(roaring), else_(roaring)


def _author_roars(g, held_on, gave_up, pins, roar_anim):
    """Both roars. ``held_on`` is the exec pin of a held pass short of the
    hold's end, ``gave_up`` that of the pass that ends it, and ``roar_anim``
    roar_object()'s answer. Returns ``(circling, done)``: the exec pin of a
    pass that goes on round the player, and those of the passes that stand."""
    standing, onward = _author_roar_wait(g, held_on, pins)
    # 0 is a hold whose roar has been given: any other time is one to come.
    armed = g.op(FN_GREATER_FF, g.get(WARD_ROAR_AT_VAR), 0.0)
    up = g.op(FN_LE_FF, g.get(WARD_ROAR_AT_VAR), pins["now"])
    due = g.branch(g.op(FN_AND, armed, up), onward)
    given = g.put(WARD_ROAR_AT_VAR, then(due), literal=0.0)
    ends = g.op(FN_ADD_FF, pins["now"], NPC_WARD_ROAR_S)
    step = g.put(WARD_ROAR_UNTIL_VAR, [given, gave_up], pin=ends)
    step = _author_bellow(g, step, pins, roar_anim)
    return else_(due), [standing, step]
