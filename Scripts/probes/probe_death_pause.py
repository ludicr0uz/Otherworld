"""Single player still pauses: the player's death stops the world.

    python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_death_pause.py

The pause is behind a Branch on IsStandalone (net/pause.py), so that a client
of a server never pauses (`probe_net_menu_overlay.py`). This is the other
arm: in a single-player game the Branch is taken, and the world is paused once
the body has had its DEATH_PAUSE_SECONDS on the floor. Run it last in a game:
it leaves the player dead and the world paused.
"""

import time

import unreal

from combat import health_vars as HV
from combat.death import DEATH_PAUSE_SECONDS
from combat.paths import HEALTH_BP_PATH, HEALTH_CLASS_PATH

WRITABLE = [(HEALTH_BP_PATH, HV.Health)]

WAIT = 60.0     # wall seconds: a headless game's clock runs slower than the wall's


def probe(p):
    world = p.world()
    mine = p.component(p.pawn(), HEALTH_CLASS_PATH)
    p.check("this is a standalone game, alive and running",
            unreal.SystemLibrary.is_standalone(world) and p.get(mine, HV.Health) > 0.0
            and not unreal.GameplayStatics.is_game_paused(world))
    died = unreal.GameplayStatics.get_time_seconds(world)
    p.set(mine, HV.Health, 0.0)
    until = time.time() + WAIT
    yield lambda: unreal.GameplayStatics.is_game_paused(world) or time.time() > until
    waited = unreal.GameplayStatics.get_time_seconds(world) - died
    p.check("the player's death pauses a single-player world",
            unreal.GameplayStatics.is_game_paused(world), f"{waited:.2f} game s after the death")
    p.check(f"...after the body's {DEATH_PAUSE_SECONDS} s on the floor, not before",
            waited >= DEATH_PAUSE_SECONDS - 0.1, f"{waited:.2f} s")
