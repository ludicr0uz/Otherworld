"""The audit of every random draw a graph makes: which change the game
(state) and which only vary how it looks or sounds (cosmetic).

A state roll is made once, by the machine that owns the state, and its result
replicates; rolled on each machine, two players would see two worlds. A
cosmetic one is each machine's own. Constants only: `net/random_checks.py`
holds the verifiers' check that no builder draws outside this table, and
`net/CLAUDE.md` ("Random rolls") the rule.

A new draw gets a row here in the same commit, or the menu verifier fails.
"""

from collections import namedtuple

STATE = "state"
COSMETIC = "cosmetic"

# module   the builder that authors the draw, relative to Scripts/
# kind     STATE or COSMETIC
# what     what is drawn
# where    which machine draws it, and how the others learn the result;
#          "later" names the task that moves a draw still made per machine
Roll = namedtuple("Roll", "module kind what where later")

AUDIT = (
    # --- state, the server's already ---------------------------------------
    Roll("loot/roll.py", STATE,
         "what a killed wanderer carries: each loot-table entry against its chance",
         "the kill's arm of BP_HealthComponent, behind the Tick's authority "
         "switch; the body's Loot arrays replicate", ""),
    Roll("combat/gun_drop.py", STATE,
         "whether a kill leaves a gun, and which: two streams on the GameMode",
         "the same arm, and the streams are the GameMode's, which a client "
         "does not have; the gun is an actor the server spawns", "M23"),
    Roll("combat/replacement.py", STATE,
         "where a killed wanderer's replacement appears (bearing, distance, "
         "the navmesh's point)",
         "the same arm; the wanderer is spawned by the server and replicates", ""),
    Roll("combat/player_respawn.py", STATE,
         "which PlayerStart a respawn is given",
         "behind death's IsStandalone Branch and the authority switch; the "
         "new pawn replicates", ""),
    Roll("survival/on_hit_graph.py", STATE,
         "whether a blow leaves its on-hit effect (a wendigo's: bleeding, 33%)",
         "behind HasAuthority of the target, in the fragment itself; the "
         "effect is the target's ability system's", "M26"),
    Roll("npc/patrol.py", STATE,
         "a patrol's next point and how long the wanderer waits there",
         "the wanderer's AIController, which exists on the server alone; "
         "its movement replicates", ""),
    Roll("npc/stalk.py", STATE,
         "the wendigo's hunt: which way round, when it turns, the wait behind a tree",
         "the AIController, as the patrol", ""),
    Roll("npc/strafe.py", STATE,
         "between two swings: the sidestep's angle, side and distance",
         "the AIController, as the patrol", ""),
    Roll("npc/ward.py", STATE,
         "held off by fire: which way it circles and when it turns",
         "the AIController, as the patrol", ""),
    Roll("npc/ward_roar.py", STATE,
         "held off by fire: when the first roar comes (it stands for it)",
         "the AIController, as the patrol", ""),
    Roll("combat/weapon_component/firing.py", STATE,
         "where in the gun's cloud a round or a pellet goes",
         "inside Server_Fire, which only the server runs (single player: a "
         "plain call); the owning client draws nothing, and what the pellets "
         "did replicates as health", ""),
    # --- state, still drawn by the machine that acts ------------------------
    Roll("combat/weapon_component/chop.py", STATE,
         "where the wood lands beside the trunk, and how it lies",
         "the weapon component of whoever chops; the server's once the chop "
         "is a server action", "M25"),
    Roll("world/day_night_graph.py", STATE,
         "the time of day a level starts at",
         "every machine's own BP_DayNightCycle at BeginPlay; one clock, the "
         "server's, replicated", "M30"),
    # --- cosmetic: each machine's own ---------------------------------------
    Roll("Sound/play.py", COSMETIC,
         "which take of a sound plays (every sound with more than one)",
         "wherever the sound plays", ""),
    Roll("combat/hit_reaction.py", COSMETIC,
         "which of the three front flinches a blow from the front plays",
         "every machine's copy of the health component, off its own Tick", ""),
    Roll("combat/weapon_component/recoil.py", COSMETIC,
         "the kick's sideways drift, on the view of the player who fired",
         "the owning client: it turns its own controller, as the mouse does", ""),
    Roll("npc/stats.py", COSMETIC,
         "the gap before a wanderer's next growl",
         "the AIController (the server's); every client hears the growl "
         "once sounds are multicast", "M21"),
)

# The node catalog's names for a draw (uebp/nodes/math.py, ai.py). A builder
# naming one of these is a builder that draws.
CATALOG_NAMES = (
    "FN_RANDOM_BOOL", "FN_RANDOM_FLOAT", "FN_RANDOM_UNIT", "FN_RAND_CONE", "FN_RAND_INT",
    "FN_SEED_STREAM", "FN_SET_STREAM_SEED", "FN_STREAM_FLOAT", "FN_STREAM_INT",
    "FN_RANDOM_NAV", "FN_RANDOM_REACHABLE",
)

# The Blueprints those builders author into; a draw found in any other is one
# nobody audited. (A variable named Random... is not a draw: its node's title
# starts with Get or Set.)
BLUEPRINTS = (
    "BP_HealthComponent", "BP_WeaponComponent", "BP_FootstepComponent",
    "BP_DayNightCycle", "BP_ForestWandererAI",
)
