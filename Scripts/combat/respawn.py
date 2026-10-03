"""Where wanderers come from and where things fall out of the world: the
75-100 m respawn band and nav projection (authored by replacement.py), the
respawn delay, the world floor, and the two
BP_HealthComponent fragments built on them -- BeginPlay's spawn numbering
and log line, and Tick's world-floor safety net.
"""

from forest_generator.npc_placement import (
    NPC_CAPSULE_HALF_HEIGHT_CM, NPC_RESPAWN_DELAY_S, NPC_RESPAWN_NAV_SNAP_CM,
    NPC_SPAWN_MAX_DISTANCE_CM, NPC_SPAWN_MIN_DISTANCE_CM,
)
from combat.game_state import (
    FELL_LOG_PREFIX, NPC_ID_VAR, SPAWNED_AT_VAR, SPAWN_COUNT_VAR,
    SPAWN_LOG_PREFIX,
)
from combat.graph import BEL, _connect, _loose_pin, _node, _palette, _pin, _set
from combat.hit_reaction import HIT_REACT_PROBE, LAST_HIT_FROM_VAR
from combat.nodes import (
    FN_ACTOR_FORWARD, FN_ACTOR_LOC, FN_ADD_II, FN_AND, FN_BREAK_VECTOR,
    FN_CONCAT, FN_GET_GAME_MODE, FN_GET_OWNER, FN_GE_FF, FN_GREATER_FF,
    FN_INT_TO_STR, FN_LESS_FF, FN_OBJECT_CLASS, FN_PRINT, FN_SUB_FF,
    FN_TIME_SECONDS, FN_VEC_TO_STR, FN_WARN, NODE_CAST_GAME_MODE,
)
from combat.paths import GAME_MODE_CLASS_PATH


# NPC respawn: a replacement wanderer appears in the same 75-100 m band the
# level generator spawns the pack in -- but measured from wherever the PLAYER is
# standing at that moment, not from a fixed point. Anchoring it to the dead
# NPC's own spawn point (what this used to do) made the rule decay: the player
# walks 300 m, kills something, and its replacement appears 300 m behind them,
# or worse, right on top of them when they have walked toward the spawn.
#
# The band's far edge can fall outside the navigable island, and the point is
# built from the PLAYER's Z, which is not the ground height at a spot 90 m away.
# So the point is a *request*, never a spawn location: it is projected onto the
# navmesh first, and only the projected result is ever spawned at. See
# _author_respawn_point for what happens when the projection fails.
RESPAWN_BAND = (NPC_SPAWN_MIN_DISTANCE_CM, NPC_SPAWN_MAX_DISTANCE_CM)
RESPAWN_NAV_SNAP = NPC_RESPAWN_NAV_SNAP_CM
# How long the pack stays one short after a death. A variable on the component
# (RespawnDelay) rather than a pin literal, so a probe can shorten the wait.
RESPAWN_DELAY = NPC_RESPAWN_DELAY_S
RESPAWN_DELAY_VAR = "RespawnDelay"
# Search box for that projection, half-extents in cm. Deliberately wide in XY:
# a band point that overshoots the navigable island by 20 m snaps back onto its
# edge rather than failing, which is the common case on a map whose usable
# radius (80 m on a 200 m map) is narrower than the band. Deliberately tall in
# Z: the request carries the player's height, and the terrain it has to land on
# ranges from a -2 m hollow to a 40 m edge ramp.
RESPAWN_PROJECT_EXTENT = (3000.0, 3000.0, 10000.0)
# A navmesh point is the ground; a Character's origin is its capsule centre.
RESPAWN_LIFT = NPC_CAPSULE_HALF_HEIGHT_CM
# ...except a navmesh point is NOT reliably the ground. Recast voxelises the
# terrain (cell height, then polygon simplification), so on a slope its polygon
# can sit well below the mesh surface -- measured at up to 86 cm low over 1847
# respawns, with 3% of them landing a capsule less than half-seated and 0.2%
# more than half buried. A capsule that starts inside the terrain depenetrates,
# and a thin one-sided surface is exactly what it pops *through*: that is the
# "some still fall through" case. So the chosen point's XY is kept and its Z is
# re-derived by tracing onto the real collision geometry.
#
# The trace starts only 2 m up on purpose. A trace from far overhead would hit a
# tree canopy and seat the wanderer in the branches; 2 m clears the worst
# measured burial and stays under anything growing above.
RESPAWN_TRACE_UP = 200.0
RESPAWN_TRACE_DOWN = 500.0
# The floor of the world. The terrain bottoms out at about -185 cm and the nav
# volume at -385, so anything under -1000 cm is not standing on anything and
# never will be.
#
# This is now BOTH the NPC safety net and the player's death from walking off
# the map, which are the same measurement and deliberately the same number.
# The navigable island is a disc of radius 85 m inside a 200 m square of
# terrain, and the terrain itself simply ends: walk far enough and there is
# nothing under the capsule. Before this, the player fell for the rest of the
# session -- no floor, no KillZ, no bottom. A Character in freefall never
# stops, and the game has no way to notice, because "still falling" and
# "standing still" look identical to everything that is watching.
#
# Routing it into Health = 0 rather than into a teleport or a Destroy is what
# makes it cost nothing: the death path, the animation, the pause and the
# restart menu all already exist and all already run at 0 HP.
WORLD_FLOOR_Z = -1000.0
# How many independent bearings to try before giving up on the band. One is
# enough whenever the navmesh has settled -- measured at runtime, 215 of 220
# band points projected, and the five failures were all in the first frame,
# before any tile existed. A second draw exists for exactly that window, and for
# the tile churn that follows a burst of deaths: it costs nothing when the first
# attempt succeeds, and it keeps a respawn in the band instead of dropping it
# next to the player.
RESPAWN_ATTEMPTS = 2


def _author_health_begin_play(ed, begin):
    """BP_HealthComponent's BeginPlay: a wanderer respawns as its own class,
    takes the next number from the GameMode and logs where it appeared."""
    # --- BeginPlay: take the next number and say where this one appeared -----
    # Numbered in spawn order, wanderers only (the player carries the same
    # component and must not consume a number). Both the initially placed five
    # and every replacement come through here, so the log is a complete record
    # of every wanderer that has ever existed this session -- which is what
    # makes a fall-through reportable: read the number off the health bar, find
    # that number in the log, and its spawn location is right there.
    mine = ed.add_get_member_variable_node("DespawnOnDeath")
    is_wanderer = ed.add_branch_node()
    _connect(_pin(mine, "DespawnOnDeath", is_input=False), _pin(is_wanderer, "Condition"))
    _connect(BEL.find_then_pin(begin), _pin(is_wanderer, "execute"))

    # --- what this one respawns as: itself -----------------------------------
    # RespawnClass used to be a default written onto BP_ForestWanderer's own
    # component template, and every variant inherited it. So a wendigo's
    # replacement was a BP_ForestWanderer -- which wears the PARENT's mesh,
    # i.e. a zombie. Kill the two wendigos the level places and there are never
    # any more, which is exactly what it looked like. (The zombies had the same
    # bug and it was invisible: the thing they respawned as looked identical.)
    #
    # Asking the owner what class it is fixes it for every variant at once,
    # including ones that do not exist yet, and needs nothing per creature.
    # The template default stays as the fallback for a wanderer that somehow
    # has no owner class, and DespawnOnDeath -- already the "am I a wanderer"
    # test above -- stays the thing that decides whether any of this runs.
    me = _node(ed, FN_GET_OWNER)
    my_class = _node(ed, FN_OBJECT_CLASS)
    _connect(_pin(me, "ReturnValue", is_input=False), _pin(my_class, "Object"))
    same_again = ed.add_set_member_variable_node("RespawnClass")
    _connect(_pin(my_class, "ReturnValue", is_input=False),
             _pin(same_again, "RespawnClass"))
    _connect(BEL.find_then_pin(is_wanderer), _pin(same_again, "execute"))

    mode = _node(ed, FN_GET_GAME_MODE)
    as_mode = _palette(ed, NODE_CAST_GAME_MODE)
    _connect(_pin(mode, "ReturnValue", is_input=False), _pin(as_mode, "Object"))
    _connect(BEL.find_then_pin(same_again), _pin(as_mode, "execute"))
    mode_out = _loose_pin(as_mode, "AsBPThirdPersonGameMode", is_input=False)

    seen = ed.add_get_member_variable_node(SPAWN_COUNT_VAR, GAME_MODE_CLASS_PATH)
    _connect(mode_out, _pin(seen, "self"))
    next_id = _node(ed, FN_ADD_II)
    _connect(_pin(seen, SPAWN_COUNT_VAR, is_input=False), _pin(next_id, "A"))
    _set(next_id, "B", 1)
    # Take the number FIRST, then write the counter back from the stored value,
    # and read the stored value everywhere after that. The obvious order -- bump
    # the counter, then set NpcId from the same "+1" node -- numbers the first
    # wanderer 2: the add is pure, so reading it again after the counter has
    # moved re-evaluates it against the new count. Same trap as the navmesh
    # queries in the respawn path; a stored value is what makes it go away.
    take = ed.add_set_member_variable_node(NPC_ID_VAR)
    _connect(_pin(next_id, "ReturnValue", is_input=False), _pin(take, NPC_ID_VAR))
    _connect(BEL.find_then_pin(as_mode), _pin(take, "execute"))

    my_id = ed.add_get_member_variable_node(NPC_ID_VAR)
    my_id_out = _pin(my_id, NPC_ID_VAR, is_input=False)

    bump = ed.add_set_member_variable_node(SPAWN_COUNT_VAR, GAME_MODE_CLASS_PATH)
    _connect(mode_out, _pin(bump, "self"))
    _connect(my_id_out, _pin(bump, SPAWN_COUNT_VAR))
    _connect(BEL.find_then_pin(take), _pin(bump, "execute"))

    # "[NPC-SPAWN] #7 at X=... Y=... Z=..."
    id_str = _node(ed, FN_INT_TO_STR)
    _connect(my_id_out, _pin(id_str, "InInt"))
    head = _node(ed, FN_CONCAT)
    _set(head, "A", SPAWN_LOG_PREFIX)
    _connect(_pin(id_str, "ReturnValue", is_input=False), _pin(head, "B"))
    here_owner = _node(ed, FN_GET_OWNER)
    here = _node(ed, FN_ACTOR_LOC)
    _connect(_pin(here_owner, "ReturnValue", is_input=False), _pin(here, "self"))
    record = ed.add_set_member_variable_node(SPAWNED_AT_VAR)
    _connect(_pin(here, "ReturnValue", is_input=False), _pin(record, SPAWNED_AT_VAR))
    _connect(BEL.find_then_pin(bump), _pin(record, "execute"))
    # The log line reads the stored value rather than the actor again, so the
    # line and the variable the safety net quotes can never disagree.
    spawned_at = ed.add_get_member_variable_node(SPAWNED_AT_VAR)
    where_str = _node(ed, FN_VEC_TO_STR)
    _connect(_pin(spawned_at, SPAWNED_AT_VAR, is_input=False), _pin(where_str, "InVec"))
    at_str = _node(ed, FN_CONCAT)
    _set(at_str, "A", " at ")
    _connect(_pin(where_str, "ReturnValue", is_input=False), _pin(at_str, "B"))
    line = _node(ed, FN_CONCAT)
    _connect(_pin(head, "ReturnValue", is_input=False), _pin(line, "A"))
    _connect(_pin(at_str, "ReturnValue", is_input=False), _pin(line, "B"))

    say = _node(ed, FN_PRINT)
    _connect(_pin(line, "ReturnValue", is_input=False), _pin(say, "InString"))
    # Log only. On screen it would be five lines at level start and another
    # every time something dies, over the top of the HUD it is meant to explain.
    _set(say, "bPrintToScreen", "false")
    _set(say, "bPrintToLog", "true")
    _set(say, "Duration", 0.0)
    _connect(BEL.find_then_pin(record), _pin(say, "execute"))

    ed.add_comment_to_nodes(
        "Every wanderer takes the next number from the GameMode as it spawns "
        "and writes one log line saying where it appeared. The HUD draws the "
        "same number beside its health bar, so anything seen on screen can be "
        "looked up in the log. The player's copy of this component skips it -- "
        "DespawnOnDeath is what tells the two apart.",
        [mine, is_wanderer, mode, as_mode, seen, next_id, take, my_id, bump,
         record, spawned_at, id_str, head, here_owner, here, where_str, at_str,
         line, say])


def _author_world_floor_net(ed, tick):
    """BP_HealthComponent's Tick, first thing: below WORLD_FLOOR_Z is dead.

    Returns (lost, write_off): the net's branch, whose False arm is the normal
    frame, and the Health = 0 write both of its True arms end in. The caller
    joins both into the death check."""
    # --- Tick: the safety net -----------------------------------------------
    # Anything below the world is counted as dead. For a wanderer that routes
    # into the despawn-and-replace path, so one that ends up under the terrain
    # is gone within a frame and a correctly seated replacement takes its
    # place. For the player it routes into _author_player_death, and that is
    # the answer to walking off the edge of the map.
    #
    # IT USED TO BE GATED ON DespawnOnDeath, i.e. NPCs only, on the reasoning
    # that the player "has no replacement to be given". That was true when it
    # was written and stopped being true the day the player got a death path:
    # the player does not need a replacement, they need the restart menu, and
    # the menu is what 0 HP already opens. So the gate moved inward. It now
    # guards only the log line, which is the part that really is
    # wanderer-specific -- it quotes an NpcId and a spawn location, and the
    # player has neither.
    #
    # For the NPCs this is a net, not the fix: the fix is tracing the respawn
    # onto real ground (see below). A net is worth having anyway, because "the
    # capsule ended up inside geometry" has more causes than the one that was
    # measured. For the player it is not a net at all -- it is the only thing
    # standing between "walked too far" and a fall with no bottom.
    net_owner = _node(ed, FN_GET_OWNER)
    net_loc = _node(ed, FN_ACTOR_LOC)
    _connect(_pin(net_owner, "ReturnValue", is_input=False), _pin(net_loc, "self"))
    net_brk = _node(ed, FN_BREAK_VECTOR)
    _connect(_pin(net_loc, "ReturnValue", is_input=False), _pin(net_brk, "InVec"))
    under = _node(ed, FN_LESS_FF)
    _connect(_pin(net_brk, "Z", is_input=False), _pin(under, "A"))
    _set(under, "B", WORLD_FLOOR_Z)
    lost = ed.add_branch_node()
    _connect(_pin(under, "ReturnValue", is_input=False), _pin(lost, "Condition"))
    tick_out = BEL.find_then_pin(tick)

    if HIT_REACT_PROBE:
        # TEMPORARY, and removed by re-running with HIT_REACT_PROBE False.
        #
        # Nothing shoots a wanderer in a headless run, so the NPC half of the
        # reaction is a gate the -game session never opens -- and an unopened
        # gate and a broken one leave the same (empty) log. This shoots one for
        # it: at t > 6 s, any wanderer still at full health takes 20 damage from
        # a direction along its OWN FORWARD, which is the Front bucket and
        # therefore the random-of-three arm the player's own punches never
        # reach. It needs no extra variable to fire once -- after the hit,
        # Health < MaxHealth is false forever.
        probe_npc = ed.add_get_member_variable_node("DespawnOnDeath")
        probe_now = _node(ed, FN_TIME_SECONDS)
        probe_late = _node(ed, FN_GREATER_FF)
        _connect(_pin(probe_now, "ReturnValue", is_input=False), _pin(probe_late, "A"))
        _set(probe_late, "B", 6.0)
        probe_hp = ed.add_get_member_variable_node("Health")
        probe_max = ed.add_get_member_variable_node("MaxHealth")
        probe_full = _node(ed, FN_GE_FF)
        _connect(_pin(probe_hp, "Health", is_input=False), _pin(probe_full, "A"))
        _connect(_pin(probe_max, "MaxHealth", is_input=False), _pin(probe_full, "B"))
        probe_and = _node(ed, FN_AND)
        _connect(_pin(probe_npc, "DespawnOnDeath", is_input=False), _pin(probe_and, "A"))
        _connect(_pin(probe_late, "ReturnValue", is_input=False), _pin(probe_and, "B"))
        probe_and2 = _node(ed, FN_AND)
        _connect(_pin(probe_and, "ReturnValue", is_input=False), _pin(probe_and2, "A"))
        _connect(_pin(probe_full, "ReturnValue", is_input=False), _pin(probe_and2, "B"))
        probe_br = ed.add_branch_node()
        _connect(_pin(probe_and2, "ReturnValue", is_input=False), _pin(probe_br, "Condition"))
        _connect(tick_out, _pin(probe_br, "execute"))

        probe_owner = _node(ed, FN_GET_OWNER)
        probe_fwd = _node(ed, FN_ACTOR_FORWARD)
        _connect(_pin(probe_owner, "ReturnValue", is_input=False), _pin(probe_fwd, "self"))
        probe_dir = ed.add_set_member_variable_node(LAST_HIT_FROM_VAR)
        _connect(_pin(probe_fwd, "ReturnValue", is_input=False),
                 _pin(probe_dir, LAST_HIT_FROM_VAR))
        _connect(BEL.find_then_pin(probe_br), _pin(probe_dir, "execute"))
        probe_hurt = _node(ed, FN_SUB_FF)
        _connect(_pin(probe_hp, "Health", is_input=False), _pin(probe_hurt, "A"))
        _set(probe_hurt, "B", 20.0)
        probe_set = ed.add_set_member_variable_node("Health")
        _connect(_pin(probe_hurt, "ReturnValue", is_input=False), _pin(probe_set, "Health"))
        _connect(BEL.find_then_pin(probe_dir), _pin(probe_set, "execute"))

        probe_join = ed.add_branch_node()
        _set(probe_join, "Condition", "true")
        _connect(BEL.find_then_pin(probe_set), _pin(probe_join, "execute"))
        _connect(BEL.find_else_pin(probe_br), _pin(probe_join, "execute"))
        tick_out = BEL.find_then_pin(probe_join)

    _connect(tick_out, _pin(lost, "execute"))
    # ...and only then, is this one worth a log line? A wanderer under the map
    # is a bug worth reporting with its number and its spawn point. A player
    # under the map walked there.
    net_is_npc = ed.add_get_member_variable_node("DespawnOnDeath")
    reportable = ed.add_branch_node()
    _connect(_pin(net_is_npc, "DespawnOnDeath", is_input=False),
             _pin(reportable, "Condition"))
    _connect(BEL.find_then_pin(lost), _pin(reportable, "execute"))
    # Say which one, by its number, before removing it: the net recovers the
    # game within a frame, which would otherwise erase the evidence of the very
    # thing worth diagnosing. Grep [NPC-FELL] for the number, then [NPC-SPAWN]
    # for the same number to see exactly where it was put.
    net_id = ed.add_get_member_variable_node(NPC_ID_VAR)
    net_id_str = _node(ed, FN_INT_TO_STR)
    _connect(_pin(net_id, NPC_ID_VAR, is_input=False), _pin(net_id_str, "InInt"))
    net_head = _node(ed, FN_CONCAT)
    _set(net_head, "A", FELL_LOG_PREFIX)
    _connect(_pin(net_id_str, "ReturnValue", is_input=False), _pin(net_head, "B"))
    net_where = _node(ed, FN_VEC_TO_STR)
    _connect(_pin(net_loc, "ReturnValue", is_input=False), _pin(net_where, "InVec"))
    net_at = _node(ed, FN_CONCAT)
    _set(net_at, "A", " fell to ")
    _connect(_pin(net_where, "ReturnValue", is_input=False), _pin(net_at, "B"))
    net_line = _node(ed, FN_CONCAT)
    _connect(_pin(net_head, "ReturnValue", is_input=False), _pin(net_line, "A"))
    _connect(_pin(net_at, "ReturnValue", is_input=False), _pin(net_line, "B"))

    # ...and where it was spawned, which is the half worth having: the fall
    # position is always "somewhere under the map", while the spawn position is
    # the thing that has to be explained. Quoting the stored SpawnedAt means the
    # two lines for one wanderer agree by construction.
    net_origin = ed.add_get_member_variable_node(SPAWNED_AT_VAR)
    net_origin_str = _node(ed, FN_VEC_TO_STR)
    _connect(_pin(net_origin, SPAWNED_AT_VAR, is_input=False),
             _pin(net_origin_str, "InVec"))
    net_from = _node(ed, FN_CONCAT)
    _set(net_from, "A", " — spawned at ")
    _connect(_pin(net_origin_str, "ReturnValue", is_input=False), _pin(net_from, "B"))
    net_full = _node(ed, FN_CONCAT)
    _connect(_pin(net_line, "ReturnValue", is_input=False), _pin(net_full, "A"))
    _connect(_pin(net_from, "ReturnValue", is_input=False), _pin(net_full, "B"))

    # PrintWarning, not PrintString: Warning is the highest severity Blueprint
    # can emit, so this is as close to an error as the graph can get, and it is
    # what makes the line stand out in the Output Log.
    net_say = _node(ed, FN_WARN)
    _connect(_pin(net_full, "ReturnValue", is_input=False), _pin(net_say, "InString"))
    _connect(BEL.find_then_pin(reportable), _pin(net_say, "execute"))

    # Both arms write the zero -- the reported wanderer after its line, the
    # player straight away. Missing the second connection would be the exact
    # bug this block exists to fix, silently: the player would fall past the
    # threshold, take the unreported branch, and carry on falling.
    write_off = ed.add_set_member_variable_node("Health")
    _set(write_off, "Health", 0.0)
    for tail in (BEL.find_then_pin(net_say), BEL.find_else_pin(reportable)):
        _connect(tail, _pin(write_off, "execute"))

    ed.add_comment_to_nodes(
        f"Below {WORLD_FLOOR_Z / 100:.0f} m there is nothing under the capsule "
        "and never will be, so whatever is down there is written off as dead "
        "and takes the death path it already has: a wanderer is replaced, and "
        "the player -- who walked off the edge of a 200 m square of terrain -- "
        "gets the restart menu instead of falling for the rest of the session. "
        "Only the log line is wanderer-specific; it quotes a number and a spawn "
        "point, and the player has neither.",
        [net_owner, net_loc, net_brk, under, net_is_npc, lost, reportable,
         net_id, net_id_str, net_head, net_where, net_at, net_line, net_origin,
         net_origin_str, net_from, net_full, net_say, write_off])
    return lost, write_off
