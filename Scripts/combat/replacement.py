"""The dead wanderer's replacement: BP_HealthComponent's fragment that waits
RESPAWN_DELAY seconds after a death, then picks a point in the respawn band
around the player, seats it on the ground and spawns the same creature there.
The band's numbers and why they are what they are live in respawn.py.
"""

from combat.graph import BEL, _connect, _loose_pin, _node, _palette, _pin, _set, _vec
from combat.nodes import (
    FN_ACTOR_LOC, FN_ADD_VV, FN_DELAY, FN_FORWARD, FN_GET_PLAYER_PAWN,
    FN_IS_VALID_CLASS, FN_MAKE_ROT, FN_MAKE_TRANSFORM, FN_MUL_VF,
    FN_PROJECT_NAV, FN_RANDOM_FLOAT, FN_RANDOM_NAV, FN_TRACE, NODE_BREAK_HIT,
    NODE_SPAWN,
)
from combat.respawn import (
    RESPAWN_ATTEMPTS, RESPAWN_BAND, RESPAWN_DELAY, RESPAWN_DELAY_VAR,
    RESPAWN_LIFT, RESPAWN_PROJECT_EXTENT, RESPAWN_TRACE_DOWN, RESPAWN_TRACE_UP,
)
from combat.weapon_component.common import _trace_defaults


def _author_replacement(ed, exec_in):
    """After RespawnDelay seconds, spawn RespawnClass in the band round the player.

    ``exec_in`` is the end of a wanderer's death: the kill is counted, the body
    is down and its brain retired before the wait starts, so nothing about
    dying waits on the replacement. Every path ends here; with no RespawnClass,
    or no navmesh to be found at all, the dead wanderer is NOT replaced. Losing
    one of ten is recoverable and visible; dropping a replacement through the
    floor is neither.
    """
    cls_get = ed.add_get_member_variable_node("RespawnClass")
    can_respawn = _node(ed, FN_IS_VALID_CLASS)
    _connect(_pin(cls_get, "RespawnClass", is_input=False), _pin(can_respawn, "Class"))
    respawns = ed.add_branch_node()
    _connect(_pin(can_respawn, "ReturnValue", is_input=False), _pin(respawns, "Condition"))
    _connect(exec_in, _pin(respawns, "execute"))

    # --- the wait -------------------------------------------------------------
    # A Delay is safe here, where it would not be for the corpse (see
    # _author_corpse): the body this component belongs to lies there for
    # CORPSE_SECONDS, six times the wait, so the latent action outlives it.
    # The duration is a variable, not a pin literal, so a probe can shorten it:
    # a headless game's clock is too slow to sit out ten seconds.
    pause = ed.add_get_member_variable_node(RESPAWN_DELAY_VAR)
    wait = _node(ed, FN_DELAY)
    _connect(_pin(pause, RESPAWN_DELAY_VAR, is_input=False), _pin(wait, "Duration"))
    _connect(BEL.find_then_pin(respawns), _pin(wait, "execute"))

    # --- where the replacement goes -----------------------------------------
    # Three steps, and the order matters:
    #
    #   1. build the REQUEST -- a random bearing and distance in the band,
    #      around the player -- and store it, so the random draw happens once;
    #   2. project it onto the navmesh, which is what supplies a real ground
    #      height (the request carries the *player's* Z, which is meaningless
    #      90 m away) and pulls a point that overshot the navigable island back
    #      onto it;
    #   3. only then spawn, lifted by the capsule's half height.
    #
    # Step 1 has to be a variable rather than wires straight into step 2.
    # K2_ProjectPointToNavigation is **pure** (a const BlueprintCallable, which
    # UHT promotes), so it is re-evaluated once per output pin read -- and if
    # its Point pin were driven by the RandomFloatInRange chain, the branch on
    # ReturnValue and the read of ProjectedLocation would each roll fresh
    # numbers and project two different points. Storing the request first makes
    # every re-evaluation deterministic.
    #
    # THIS IS THE BUG THIS SHAPE EXISTS TO FIX: the previous version read the
    # nav query's location output and never looked at its bool, so a failed
    # query -- routine here, because the band's far edge lies outside the
    # navigable island on a 200 m map -- spawned the replacement at the raw
    # request point, at the player's own Z. On any ground higher than the player
    # that is *inside* the terrain, and the capsule falls through the world.
    hero = _node(ed, FN_GET_PLAYER_PAWN)
    _set(hero, "PlayerIndex", 0)
    hero_loc = _node(ed, FN_ACTOR_LOC)
    _connect(_pin(hero, "ReturnValue", is_input=False), _pin(hero_loc, "self"))
    hero_out = _pin(hero_loc, "ReturnValue", is_input=False)

    # Everything below runs after the wait, so the player's location (a pure
    # read) is where they stand when the replacement appears, not where they
    # stood at the kill.
    made = [hero, hero_loc, pause, wait]
    flow = BEL.find_then_pin(wait)
    ready = []          # exec pins that have a good point and may spawn

    for attempt in range(RESPAWN_ATTEMPTS):
        bearing = _node(ed, FN_RANDOM_FLOAT)
        _set(bearing, "Min", 0.0)
        _set(bearing, "Max", 360.0)
        facing = _node(ed, FN_MAKE_ROT)
        _connect(_pin(bearing, "ReturnValue", is_input=False), _pin(facing, "Yaw"))
        _set(facing, "Pitch", 0.0)
        _set(facing, "Roll", 0.0)
        heading = _node(ed, FN_FORWARD)
        _connect(_pin(facing, "ReturnValue", is_input=False), _pin(heading, "InRot"))

        reach = _node(ed, FN_RANDOM_FLOAT)
        _set(reach, "Min", RESPAWN_BAND[0])
        _set(reach, "Max", RESPAWN_BAND[1])
        # Multiply_VectorFloat is a wildcard operator whose B pin defaults to a
        # *vector*, so a float literal on it silently does nothing -- but a
        # connected float is fine, and that is what this is.
        offset = _node(ed, FN_MUL_VF)
        _connect(_pin(heading, "ReturnValue", is_input=False), _pin(offset, "A"))
        _connect(_pin(reach, "ReturnValue", is_input=False), _pin(offset, "B"))

        request = _node(ed, FN_ADD_VV)
        _connect(hero_out, _pin(request, "A"))
        _connect(_pin(offset, "ReturnValue", is_input=False), _pin(request, "B"))

        ask = ed.add_set_member_variable_node("RespawnPoint")
        _connect(_pin(request, "ReturnValue", is_input=False), _pin(ask, "RespawnPoint"))
        _connect(flow, _pin(ask, "execute"))
        asked = ed.add_get_member_variable_node("RespawnPoint")

        proj = _node(ed, FN_PROJECT_NAV)
        _connect(_pin(asked, "RespawnPoint", is_input=False), _pin(proj, "Point"))
        # QueryExtent is a struct pin, and struct pins reject set_pin_value
        # outright -- an empty one compiles as the ZERO vector, i.e. a search box
        # with no volume, which finds nothing and fails every projection.
        _connect(_vec(ed, *RESPAWN_PROJECT_EXTENT), _pin(proj, "QueryExtent"))

        landed = ed.add_branch_node()
        _connect(_pin(proj, "ReturnValue", is_input=False), _pin(landed, "Condition"))
        _connect(BEL.find_then_pin(ask), _pin(landed, "execute"))

        use_proj = ed.add_set_member_variable_node("RespawnPoint")
        _connect(_pin(proj, "ProjectedLocation", is_input=False),
                 _pin(use_proj, "RespawnPoint"))
        _connect(BEL.find_then_pin(landed), _pin(use_proj, "execute"))

        ready.append(BEL.find_then_pin(use_proj))
        # A failed projection falls through to the next bearing; the draws are
        # independent, so a second one is a real second chance and not a repeat.
        flow = BEL.find_else_pin(landed)
        made += [bearing, facing, heading, reach, offset, request, ask, asked,
                 proj, landed, use_proj]

    # Last resort: no band point anywhere in the search box projected, which in
    # practice means the navmesh has not been generated yet (the first frame of
    # a level, or the tile churn after a burst of deaths). Take any navigable
    # point near the player rather than none -- a replacement standing too close
    # is a gameplay annoyance, one under the terrain is a bug. This call is the
    # *impure* nav function on purpose: it is random, so it must be evaluated
    # exactly once, and only a node with an exec pin can promise that.
    anywhere = _node(ed, FN_RANDOM_NAV)
    _connect(hero_out, _pin(anywhere, "Origin"))
    _set(anywhere, "Radius", RESPAWN_BAND[1])
    _connect(flow, _pin(anywhere, "execute"))

    salvaged = ed.add_branch_node()
    _connect(_pin(anywhere, "ReturnValue", is_input=False), _pin(salvaged, "Condition"))
    _connect(BEL.find_then_pin(anywhere), _pin(salvaged, "execute"))

    use_any = ed.add_set_member_variable_node("RespawnPoint")
    _connect(_pin(anywhere, "RandomLocation", is_input=False),
             _pin(use_any, "RespawnPoint"))
    _connect(BEL.find_then_pin(salvaged), _pin(use_any, "execute"))
    ready.append(BEL.find_then_pin(use_any))

    # 3. seat it on the real ground. The point is on the navmesh by now, but the
    # navmesh is a voxelised approximation of the terrain and its Z can be most
    # of a capsule too low -- so keep the XY, throw the Z away, and trace onto
    # the collision geometry the character will actually stand on.
    seat = ed.add_get_member_variable_node("RespawnPoint")
    seat_out = _pin(seat, "RespawnPoint", is_input=False)
    above = _node(ed, FN_ADD_VV)
    _connect(seat_out, _pin(above, "A"))
    _connect(_vec(ed, 0.0, 0.0, RESPAWN_TRACE_UP), _pin(above, "B"))
    below = _node(ed, FN_ADD_VV)
    _connect(seat_out, _pin(below, "A"))
    _connect(_vec(ed, 0.0, 0.0, -RESPAWN_TRACE_DOWN), _pin(below, "B"))

    drop = _node(ed, FN_TRACE)
    _connect(_pin(above, "ReturnValue", is_input=False), _pin(drop, "Start"))
    _connect(_pin(below, "ReturnValue", is_input=False), _pin(drop, "End"))
    _trace_defaults(drop)
    # The terrain is imported with complex collision, and its simple collision
    # is a box around the whole 200 m mesh -- tracing against that would seat
    # every respawn on an invisible lid.
    _set(drop, "bTraceComplex", "true")
    for tail in ready:
        _connect(tail, _pin(drop, "execute"))

    found = ed.add_branch_node()
    _connect(_pin(drop, "ReturnValue", is_input=False), _pin(found, "Condition"))
    _connect(BEL.find_then_pin(drop), _pin(found, "execute"))

    lift = _vec(ed, 0.0, 0.0, RESPAWN_LIFT)
    brk = _palette(ed, NODE_BREAK_HIT)
    _connect(_pin(drop, "OutHit", is_input=False), _pin(brk, "Hit"))
    ground = _node(ed, FN_ADD_VV)
    _connect(_loose_pin(brk, "Location", is_input=False), _pin(ground, "A"))
    _connect(lift, _pin(ground, "B"))
    stand = ed.add_set_member_variable_node("RespawnPoint")
    _connect(_pin(ground, "ReturnValue", is_input=False), _pin(stand, "RespawnPoint"))
    _connect(BEL.find_then_pin(found), _pin(stand, "execute"))

    # Nothing under the point at all (it hangs over a hole in the world). Keep
    # the navmesh height and lift off that instead -- worse, but still above
    # whatever the navmesh thinks the floor is.
    airborne = _node(ed, FN_ADD_VV)
    _connect(seat_out, _pin(airborne, "A"))
    _connect(lift, _pin(airborne, "B"))
    hover = ed.add_set_member_variable_node("RespawnPoint")
    _connect(_pin(airborne, "ReturnValue", is_input=False), _pin(hover, "RespawnPoint"))
    _connect(BEL.find_else_pin(found), _pin(hover, "execute"))

    made += [seat, above, below, drop, found, brk, ground, stand, airborne, hover]

    # 4. spawn, on ground the character can actually stand on.
    chosen = ed.add_get_member_variable_node("RespawnPoint")
    xform = _node(ed, FN_MAKE_TRANSFORM)
    _connect(_pin(chosen, "RespawnPoint", is_input=False), _pin(xform, "Location"))
    _connect(_vec(ed, 1.0, 1.0, 1.0), _pin(xform, "Scale"))

    spawn = _palette(ed, NODE_SPAWN)
    _connect(_pin(cls_get, "RespawnClass", is_input=False), _pin(spawn, "Class"))
    _connect(_pin(xform, "ReturnValue", is_input=False), _pin(spawn, "SpawnTransform"))
    # AlwaysSpawn: the nav point is inset from obstacles by the agent radius but
    # may still clip a trunk's collision, and a respawn that silently returns
    # null would empty the forest one death at a time.
    # AdjustIfPossibleButAlwaysSpawn, not AlwaysSpawn: the nav point is inset
    # from obstacles by the agent radius but can still clip a trunk, and a
    # capsule left interpenetrating gets depenetrated -- sometimes downwards,
    # through the terrain. Adjusting nudges it clear first; it still always
    # spawns, so a respawn cannot silently return null and empty the forest.
    _set(spawn, "CollisionHandlingOverride", "AdjustIfPossibleButAlwaysSpawn")
    for tail in (BEL.find_then_pin(stand), BEL.find_then_pin(hover)):
        _connect(tail, _pin(spawn, "execute"))

    ed.add_comment_to_nodes(
        f"A dead wanderer's replacement: wait RespawnDelay "
        f"({RESPAWN_DELAY:.0f} s), then ask for a point "
        f"{RESPAWN_BAND[0] / 100:.0f}-{RESPAWN_BAND[1] / 100:.0f} m from the "
        f"player on a random bearing, PROJECT it onto the navmesh (the request "
        f"carries the player's Z, which is not the ground height out there) "
        f"and spawn the replacement on that ground ({RESPAWN_ATTEMPTS} "
        f"bearings are tried before falling back to any navigable point near "
        f"the player). The replacement carries the same component, so the "
        f"cycle sustains itself with nothing tracking it.",
        [cls_get, can_respawn, respawns] + made +
        [anywhere, salvaged, use_any, chosen, xform, spawn])
