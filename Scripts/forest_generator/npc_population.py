"""How many wanderers a server keeps: the budget that follows the players
(task M29). Single player keeps the level's fixed count (NPC_COUNT) and the
dead wanderer's own replacement, and reads none of this.

Constants only -- no `unreal` import -- like npc_stalk.py and npc_ward.py.
They are defaults: the game reads the controller's TunePop* variables, which
npc/monster_tuning.csv and the M panel's MONSTER SETTINGS tab can change
(npc/monster_tuning.py). The rule itself is C++
(Source/Otherworld/Public/OtherworldPopulation.h); the controller hands it
these on possession (Scripts/npc/population.py).
"""

from forest_generator.npc_placement import NPC_COUNT, NPC_VARIANTS, NPC_WENDIGO_EVERY

# At most this many of a creature within NPC_POP_DESPAWN_CM of one player:
# the pack a level of NPC_COUNT places, so one player on a server meets what
# the single player does. The budget is the smaller of this and what the
# level in play placed (a level with two zombies stays a level of two).
_WENDIGOS = NPC_COUNT // NPC_WENDIGO_EVERY
NPC_POP_PER_PLAYER = {
    NPC_VARIANTS[0].key: float(NPC_COUNT - _WENDIGOS),
    NPC_VARIANTS[1].key: float(_WENDIGOS),
}
# ...and at most this many alive on the server, however many players: five
# full packs. Sixty-four players spread out do not each get a pack; the
# server's frame is what this protects (Scripts/net/CLAUDE.md, the load test).
NPC_POP_SERVER_CAP = {
    NPC_VARIANTS[0].key: 40.0,
    NPC_VARIANTS[1].key: 10.0,
}
# A living wanderer further than this from every player is removed, and a
# player's count is taken within it. Past the 150 m at which a wanderer stops
# being sent to a client (net/relevancy_consts.CHARACTER), so no one sees one
# go, and past the far edge of the band a new one appears in.
NPC_POP_DESPAWN_CM = 20000.0
