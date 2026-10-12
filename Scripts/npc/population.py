"""The controller's one word to the population budget (task M29): on
possession it registers its wanderer, with this creature's TunePop* numbers
(npc/monster_tuning.py), the band a new one appears in and the wait before
one does (the single-player replacement's own: combat/respawn.py).

The budget itself is C++ (Source/Otherworld/Public/OtherworldPopulation.h)
and runs on a server alone: in single player the node does nothing, the
level's count stands and a dead wanderer is replaced by its own health
component (combat/replacement.py, behind IsStandalone).
"""

from forest_generator.npc_placement import (
    NPC_RESPAWN_DELAY_S, NPC_SPAWN_MAX_DISTANCE_CM, NPC_SPAWN_MIN_DISTANCE_CM)
from npc.tuned import tuned
from uebp.graph import _connect, _node, _pin, _set, then
from uebp.nodes.population import FN_REGISTER_WANDERER

# The node's pin for each of the table's columns.
BUDGET_PINS = (("PerPlayer", "pop_per_player"), ("ServerCap", "pop_server_cap"),
               ("Range", "pop_despawn_cm"))
# ...and for each literal.
BAND_PINS = (("SpawnMin", NPC_SPAWN_MIN_DISTANCE_CM), ("SpawnMax", NPC_SPAWN_MAX_DISTANCE_CM),
             ("Delay", NPC_RESPAWN_DELAY_S))


def author_population(ed, exec_in, pawn_pin):
    """exec in --> RegisterWanderer(the possessed pawn, the budget). Returns
    the node's then pin."""
    register = _node(ed, FN_REGISTER_WANDERER)
    _connect(pawn_pin, _pin(register, "Wanderer"))
    made = [register]
    for pin, column in BUDGET_PINS:
        node, value = tuned(ed, column)
        _connect(value, _pin(register, pin))
        made.append(node)
    for pin, literal in BAND_PINS:
        _set(register, pin, literal)
    _connect(exec_in, _pin(register, "execute"))
    ed.add_comment_to_nodes(
        "On a server the wanderers are a budget that follows the players "
        "(C++, OtherworldPopulation.h): this one is counted, with its "
        "creature's caps. In single player the node does nothing.", made)
    return then(register)
