"""What one change of the inventory costs the wire: the bytes a server sends
its owner per record written.

    python3 Scripts/dev/uepy.py --net --clients 1 --probe Scripts/probes/probe_net_record_cost.py

The load test (probe_net_load.py) cannot see the record: its clients stand
still, so what they carry changes only when they die. Here the server moves
client 1's axe between two bag slots, MOVES times, and reads the connection's
bytes out (UOtherworldLoadLibrary) over that window and over an idle one of
the same length before it:

    bytes per change = (the moving window's bytes - the idle window's) / the
                       record's writes in it

A slot move is the smallest change there is (one row's slot), so this is the
floor of what a change costs; the figure is in Scripts/net/CLAUDE.md ("The
inventory"). Only a window with no writes fails: the number is the result.
"""

SYSTEMS = ('net', 'inventory')

import time

import unreal

from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.record_vars import FORCED
from combat.slot_tuning import BAG_FIRST

RUNS_ON = ("server",)
WRITABLE = [(WEAPON_COMP_BP_PATH, str(v)) for v in FORCED]
LIB = unreal.OtherworldInventoryLibrary
SETTLE_S = 6.0
WINDOW_S = 20.0
MOVES = 80
AXE_HOME, AXE_AWAY = BAG_FIRST, BAG_FIRST + 5


def _wall(seconds):
    end = time.time() + seconds
    return lambda: time.time() > end


def _out_bytes(world):
    return sum(int(c.get_editor_property("OutBytes"))
               for c in unreal.OtherworldLoadLibrary.connection_stats(world))


def probe(p):
    world = p.world()
    body = p.players()[0].get_controlled_pawn()
    wc = p.component(body, WEAPON_COMP_CLASS_PATH)
    yield _wall(SETTLE_S)

    start, writes = _out_bytes(world), LIB.inventory_record_writes(body)
    yield _wall(WINDOW_S)
    idle = _out_bytes(world) - start
    idle_writes = LIB.inventory_record_writes(body) - writes

    start, writes = _out_bytes(world), LIB.inventory_record_writes(body)
    until = time.time() + WINDOW_S
    for move in range(MOVES):
        src, dst = (AXE_HOME, AXE_AWAY) if move % 2 == 0 else (AXE_AWAY, AXE_HOME)
        p.ask_move(wc, src, dst)
        yield _wall(WINDOW_S / MOVES)
    yield lambda: time.time() > until
    moving = _out_bytes(world) - start
    wrote = LIB.inventory_record_writes(body) - writes

    p.check("nothing wrote the record while nothing changed", idle_writes == 0,
            f"{idle_writes} write(s) in the idle window")
    p.check(f"the server moved client 1's axe {MOVES} times, each a write of the record",
            wrote >= MOVES * 0.9, f"{wrote} write(s)")
    if wrote:
        p.check("the bytes the owner is sent per change of what it carries",
                True, f"{(moving - idle) / wrote:.1f} bytes a change ({moving} bytes out in "
                f"{WINDOW_S:.0f} s of {wrote} changes, {idle} in an idle {WINDOW_S:.0f} s)")
