"""uebp.nodes.population -- the wanderers' population budget (C++, the
Otherworld module: Source/Otherworld/Public/OtherworldPopulation.h). On a
server the count follows the players; single player keeps the level's count
and the dead wanderer's own replacement. Task M29.
"""

POPULATION_LIBRARY = "/Script/Otherworld.OtherworldPopulationLibrary"

# Wanderer, PerPlayer, ServerCap, Range, SpawnMin, SpawnMax, Delay: a wanderer
# has come into the world, with its creature's budget (npc/population.py).
# Does nothing in single player or on a client.
FN_REGISTER_WANDERER = POPULATION_LIBRARY + ".RegisterWanderer"
# For the probes: Class, PerPlayer, ServerCap, Range, SpawnMin, SpawnMax,
# Delay, as given whatever the level placed.
FN_SET_POPULATION_BUDGET = POPULATION_LIBRARY + ".SetPopulationBudget"
# -> ReturnValue: true on a server, where the count is a budget.
FN_POPULATION_IS_BUDGET = POPULATION_LIBRARY + ".PopulationIsBudget"
# For the probes: the living wanderers of a class, and what the budget did.
FN_POPULATION_COUNT = POPULATION_LIBRARY + ".PopulationCount"
FN_POPULATION_SPAWNED = POPULATION_LIBRARY + ".PopulationSpawned"
FN_POPULATION_REMOVED = POPULATION_LIBRARY + ".PopulationRemoved"
FN_POPULATION_NEAREST_SPAWN = POPULATION_LIBRARY + ".PopulationNearestSpawn"
