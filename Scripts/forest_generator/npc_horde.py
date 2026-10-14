"""The Horde Survival level's difficulty: how many monsters it holds, rising a
level every three minutes of play.

Constants only -- no `unreal` import -- like npc_drawn.py. The rule is held
by the native AOtherworldHordeDirector (Source/Otherworld), one placed in the
level by forest_import/fort.py with these numbers written onto it; the
functions below are the same rule in Python, for the unit test
(Scripts/dev/tests/test_npc_horde.py) and the probe
(Scripts/probes/probe_horde_difficulty.py).

  level     1 at the start, one more every HORDE_STEP_S of play (paused time
            does not count), at most HORDE_MAX_LEVEL
  monsters  HORDE_FIRST_COUNT at level 1, HORDE_PER_LEVEL more each level:
            4, 6, 8, 10 ...
  wendigos  one for every HORDE_WENDIGO_EVERY levels (none until level 4,
            one there, two at 8): the rest are zombies, so level 4 is nine
            zombies and a wendigo, level 8 sixteen and two
  kept      a kill leaves the level one short for HORDE_DELAY_S, then one
            more comes, in the band round the player and out of sight; the
            level's own placed cast is cut to level 1's at the start
"""

from forest_generator.npc_placement import (
    NPC_RESPAWN_DELAY_S, NPC_SPAWN_MAX_DISTANCE_CM, NPC_SPAWN_MIN_DISTANCE_CM)

HORDE_STEP_S = 180.0
HORDE_FIRST_COUNT = 4
HORDE_PER_LEVEL = 2
HORDE_WENDIGO_EVERY = 4
# An hour in and it stops: 42 monsters, 5 of them wendigos. The pack's
# melee is balanced for ten (npc_placement.NPC_MELEE_DAMAGE), and every
# wanderer is a behaviour tree and a skinned mesh, so the climb has a top.
HORDE_MAX_LEVEL = 20
# A new one comes as a single player's replacement does: 75-100 m off, 10 s
# after the kill.
HORDE_SPAWN_MIN_CM = NPC_SPAWN_MIN_DISTANCE_CM
HORDE_SPAWN_MAX_CM = NPC_SPAWN_MAX_DISTANCE_CM
HORDE_DELAY_S = NPC_RESPAWN_DELAY_S


def horde_level(seconds, step_s=HORDE_STEP_S, max_level=HORDE_MAX_LEVEL):
    """The level after ``seconds`` of play."""
    steps = int(max(seconds, 0.0) // step_s) if step_s > 0 else 0
    return max(1, min(1 + steps, max(max_level, 1)))


def horde_total(level):
    return max(HORDE_FIRST_COUNT + HORDE_PER_LEVEL * (level - 1), 0)


def horde_wendigos(level):
    return min(level // HORDE_WENDIGO_EVERY, horde_total(level))


def horde_zombies(level):
    return horde_total(level) - horde_wendigos(level)
