"""The chase: one move order at the player, pathfinding when both ends are on
the navmesh and a straight line when either is not. The tree's Chase step
(BT_Chase, npc/steps.py) runs it once per pass of the Hunt branch.

    BT_Chase -> [player AND pawn on the navmesh?]
                  yes -> MoveToActor(player)        (pathfinding)
                  no  -> MoveToLocation(player)     (no pathfinding)
                -> on (the step's result)
"""

from forest_generator.npc_placement import (
    NAV_REACHABLE_EXTENT_CM, NPC_ACCEPTANCE_RADIUS_CM,
)
from npc.nodes import (
    FN_ACTOR_LOC, FN_AND_B, FN_GET_PAWN, FN_GET_PLAYER_PAWN, FN_MAKE_VECTOR,
    FN_MOVE_TO_ACTOR, FN_MOVE_TO_LOCATION, FN_PROJECT_NAV,
)
from npc.graph import BEL, _connect, _node, _pin, _set


def _author_chase(ed, exec_in):
    """Returns ``(nodes, after_move)``: the nodes made, for the comment box,
    and the exec pins after either move order."""
    move_to = _node(ed, FN_MOVE_TO_ACTOR)
    get_pawn = _node(ed, FN_GET_PLAYER_PAWN)

    # Goal = the player pawn
    _set(get_pawn, "PlayerIndex", 0)
    _connect(_pin(get_pawn, "ReturnValue", is_input=False), _pin(move_to, "Goal"))

    # Pathfinding is what makes it run around the trees rather than into them.
    _set(move_to, "AcceptanceRadius", NPC_ACCEPTANCE_RADIUS_CM)
    _set(move_to, "bUsePathfinding", "true")
    _set(move_to, "bStopOnOverlap", "true")
    # Partial paths keep the NPC advancing as far as the navmesh allows instead
    # of refusing to move at all; the tree then re-paths on its next pass, so a
    # temporary dead end does not end the chase.
    _set(move_to, "bAllowPartialPath", "true")

    # --- can this chase be pathfound at all? ---------------------------------
    # See NAV_REACHABLE_EXTENT_CM. Both ends are tested, and both have to be
    # on the navmesh for pathfinding to be the right tool: a player who has
    # walked into the un-navigable ring cannot be pathed TO, and a wanderer
    # already standing in it cannot be pathed FROM. Either way the answer is
    # the same -- walk at them in a straight line.
    #
    # K2_ProjectPointToNavigation is pure and re-evaluates once per output pin
    # that is read. Only ReturnValue is read from each of these, so each
    # projects exactly once per pass, and the ProjectedLocation output is
    # deliberately left dangling: the destination is the player's real
    # position, not a snapped one. Snapping it back onto the navmesh is
    # precisely the behaviour that made the dead zone.
    reach = _node(ed, FN_MAKE_VECTOR)
    for axis, value in zip(("X", "Y", "Z"), NAV_REACHABLE_EXTENT_CM):
        _set(reach, axis, value)
    reach_out = _pin(reach, "ReturnValue", is_input=False)

    goal_loc = _node(ed, FN_ACTOR_LOC)
    _connect(_pin(get_pawn, "ReturnValue", is_input=False), _pin(goal_loc, "self"))
    goal_out = _pin(goal_loc, "ReturnValue", is_input=False)
    goal_on = _node(ed, FN_PROJECT_NAV)
    _connect(goal_out, _pin(goal_on, "Point"))
    _connect(reach_out, _pin(goal_on, "QueryExtent"))

    here_pawn = _node(ed, FN_GET_PAWN)
    here_loc = _node(ed, FN_ACTOR_LOC)
    _connect(_pin(here_pawn, "ReturnValue", is_input=False), _pin(here_loc, "self"))
    here_on = _node(ed, FN_PROJECT_NAV)
    _connect(_pin(here_loc, "ReturnValue", is_input=False), _pin(here_on, "Point"))
    _connect(reach_out, _pin(here_on, "QueryExtent"))

    both_on = _node(ed, FN_AND_B)
    _connect(_pin(goal_on, "ReturnValue", is_input=False), _pin(both_on, "A"))
    _connect(_pin(here_on, "ReturnValue", is_input=False), _pin(both_on, "B"))

    pathable = ed.add_branch_node()
    _connect(_pin(both_on, "ReturnValue", is_input=False), _pin(pathable, "Condition"))
    _connect(exec_in, _pin(pathable, "execute"))
    _connect(BEL.find_then_pin(pathable), BEL.find_execute_pin(move_to))

    # --- the straight line ---------------------------------------------------
    # Not a teleport, not AddMovementInput, and not a second Tick: this is the
    # SAME move request the pathfinding branch issues, with pathfinding off, so
    # the path-following component drives the character with the same
    # acceleration and the same stop condition and keeps doing it between the
    # tree's passes. AddMovementInput would move the NPC for exactly one frame
    # out of every thirty, because the tree re-paths twice a second.
    #
    # bProjectDestinationToNavigation must stay FALSE. True is the dead zone,
    # written a different way: it snaps the goal back onto the navmesh island
    # and the NPC walks to the edge and stops.
    direct = _node(ed, FN_MOVE_TO_LOCATION)
    _connect(goal_out, _pin(direct, "Dest"))
    _set(direct, "AcceptanceRadius", NPC_ACCEPTANCE_RADIUS_CM)
    _set(direct, "bUsePathfinding", "false")
    _set(direct, "bProjectDestinationToNavigation", "false")
    _set(direct, "bStopOnOverlap", "true")
    _set(direct, "bCanStrafe", "false")
    _connect(BEL.find_else_pin(pathable), BEL.find_execute_pin(direct))

    nodes = [move_to, get_pawn, reach, goal_loc, goal_on, here_pawn, here_loc,
             here_on, both_on, pathable, direct]
    return nodes, [BEL.find_then_pin(move_to), BEL.find_then_pin(direct)]
