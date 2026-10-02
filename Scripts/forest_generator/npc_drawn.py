"""A fire draws the zombies: one burning within reach, and a zombie that has
not noticed the player leaves its patrol and walks to it, slowly.

Constants only -- no `unreal` import -- like npc_ward.py and npc_stalk.py.
The builder is Scripts/npc/drawn.py, the checks Scripts/npc/verify_drawn.py
and, in the game, Scripts/probes/probe_zombie_drawn.py.

It is the tree's Drawn step, tried after the senses and before the stroll,
so only by a wanderer that is not aggro:

  drawn    a campfire burns within NPC_DRAWN_RANGE_CM (flat; the nearest, if
           there are several): the zombie walks to it at its patrol walk and
           stands NPC_DRAWN_ARRIVE_CM off. Its senses still run first on
           every pass, so one that meets the player on the way hunts them.
  let go   the fire burns out, or there is none that near: the step fails
           and it patrols again, about where it spawned.
"""

from forest_generator.npc_placement import NPC_MELEE_RANGE_CM

# Who a fire draws. A creature without a row takes no notice of one.
NPC_DRAWN_BY_FIRE = ("Zombie",)

# How far off a fire draws one, flat.
NPC_DRAWN_RANGE_CM = 20000.0
# Where it stops and stands: beside the fire, not in it.
NPC_DRAWN_ARRIVE_CM = 300.0

# It walks there at its patrol walk (TunePatrolSpeed, a share of its run):
# "slowly" has no number of its own.

assert NPC_MELEE_RANGE_CM < NPC_DRAWN_ARRIVE_CM < NPC_DRAWN_RANGE_CM
