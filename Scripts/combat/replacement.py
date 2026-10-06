"""The dead wanderer's replacement: BP_HealthComponent's fragment that waits
RESPAWN_DELAY seconds after a death, then picks a point in the respawn band
around the player, seats it on the ground and spawns the same creature there.
The band's numbers and why they are what they are live in respawn.py.
"""

from net.players import nearest_living_player, player_pin
from uebp.graph import (
    _connect, _loose_pin, _node, _palette, _pin, _set, _vec, else_, out, then)
from combat.respawn import (
    RESPAWN_ATTEMPTS, RESPAWN_BAND, RESPAWN_DELAY, RESPAWN_DELAY_VAR,
    RESPAWN_LIFT, RESPAWN_PROJECT_EXTENT, RESPAWN_TRACE_DOWN, RESPAWN_TRACE_UP,
)
from combat.weapon_component.common import _trace_defaults
from uebp.nodes.actor import FN_ACTOR_LOC, FN_GET_OWNER
from uebp.nodes.ai import FN_PROJECT_NAV, FN_RANDOM_NAV
from uebp.nodes.math import (
    FN_ADD_VV, FN_FORWARD, FN_MAKE_ROT, FN_MAKE_TRANSFORM, FN_MUL_VF, FN_RANDOM_FLOAT)
from uebp.nodes.palette import NODE_BREAK_HIT, NODE_SPAWN
from uebp.nodes.system import FN_DELAY, FN_IS_VALID, FN_IS_VALID_CLASS, FN_TRACE
from combat import health_vars as HV


def _author_replacement(ed, exec_in):
    """After RespawnDelay seconds, spawn RespawnClass in the band round the player.

    ``exec_in`` is the end of a wanderer's death: the kill is counted, the body
    is down and its brain retired before the wait starts, so nothing about
    dying waits on the replacement. Every path ends here; with no RespawnClass,
    or no navmesh to be found at all, the dead wanderer is NOT replaced. Losing
    one of ten is recoverable and visible; dropping a replacement through the
    floor is neither.
    """
    cls_get = ed.add_get_member_variable_node(HV.RespawnClass)
    can_respawn = _node(ed, FN_IS_VALID_CLASS)
    _connect(out(cls_get, HV.RespawnClass), _pin(can_respawn, "Class"))
    respawns = ed.add_branch_node()
    _connect(out(can_respawn), _pin(respawns, "Condition"))
    _connect(exec_in, _pin(respawns, "execute"))

    # --- the wait -------------------------------------------------------------
    # A Delay is safe here, where it would not be for the corpse (see
    # _author_corpse): the body this component belongs to lies there for
    # CORPSE_SECONDS, six times the wait, so the latent action outlives it.
    # The duration is a variable, not a pin literal, so a probe can shorten it:
    # a headless game's clock is too slow to sit out ten seconds.
    pause = ed.add_get_member_variable_node(RESPAWN_DELAY_VAR)
    wait = _node(ed, FN_DELAY)
    _connect(out(pause, RESPAWN_DELAY_VAR), _pin(wait, "Duration"))
    _connect(then(respawns), _pin(wait, "execute"))

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
    # Which player: the living one nearest the body (net/players.py), who in
    # single player is the player. With no one alive there is no band to
    # spawn in, and the wanderer is not replaced.
    body = _node(ed, FN_GET_OWNER)
    body_loc = _node(ed, FN_ACTOR_LOC)
    _connect(out(body), _pin(body_loc, "self"))
    hero = nearest_living_player(ed, out(body_loc))
    anyone = _node(ed, FN_IS_VALID)
    _connect(player_pin(hero), _pin(anyone, "Object"))
    someone = ed.add_branch_node()
    _connect(out(anyone), _pin(someone, "Condition"))
    _connect(then(wait), _pin(someone, "execute"))
    hero_loc = _node(ed, FN_ACTOR_LOC)
    _connect(player_pin(hero), _pin(hero_loc, "self"))
    hero_out = out(hero_loc)

    # Everything below runs after the wait, so the player's location (a pure
    # read) is where they stand when the replacement appears, not where they
    # stood at the kill.
    made = [body, body_loc, hero, anyone, someone, hero_loc, pause, wait]
    flow = then(someone)
    ready = []          # exec pins that have a good point and may spawn

    for attempt in range(RESPAWN_ATTEMPTS):
        bearing = _node(ed, FN_RANDOM_FLOAT)
        _set(bearing, "Min", 0.0)
        _set(bearing, "Max", 360.0)
        facing = _node(ed, FN_MAKE_ROT)
        _connect(out(bearing), _pin(facing, "Yaw"))
        _set(facing, "Pitch", 0.0)
        _set(facing, "Roll", 0.0)
        heading = _node(ed, FN_FORWARD)
        _connect(out(facing), _pin(heading, "InRot"))

        reach = _node(ed, FN_RANDOM_FLOAT)
        _set(reach, "Min", RESPAWN_BAND[0])
        _set(reach, "Max", RESPAWN_BAND[1])
        # Multiply_VectorFloat is a wildcard operator whose B pin defaults to a
        # *vector*, so a float literal on it silently does nothing -- but a
        # connected float is fine, and that is what this is.
        offset = _node(ed, FN_MUL_VF)
        _connect(out(heading), _pin(offset, "A"))
        _connect(out(reach), _pin(offset, "B"))

        request = _node(ed, FN_ADD_VV)
        _connect(hero_out, _pin(request, "A"))
        _connect(out(offset), _pin(request, "B"))

        ask = ed.add_set_member_variable_node(HV.RespawnPoint)
        _connect(out(request), _pin(ask, HV.RespawnPoint))
        _connect(flow, _pin(ask, "execute"))
        asked = ed.add_get_member_variable_node(HV.RespawnPoint)

        proj = _node(ed, FN_PROJECT_NAV)
        _connect(out(asked, HV.RespawnPoint), _pin(proj, "Point"))
        # QueryExtent is a struct pin, and struct pins reject set_pin_value
        # outright -- an empty one compiles as the ZERO vector, i.e. a search box
        # with no volume, which finds nothing and fails every projection.
        _connect(_vec(ed, *RESPAWN_PROJECT_EXTENT), _pin(proj, "QueryExtent"))

        landed = ed.add_branch_node()
        _connect(out(proj), _pin(landed, "Condition"))
        _connect(then(ask), _pin(landed, "execute"))

        use_proj = ed.add_set_member_variable_node(HV.RespawnPoint)
        _connect(out(proj, "ProjectedLocation"), _pin(use_proj, HV.RespawnPoint))
        _connect(then(landed), _pin(use_proj, "execute"))

        ready.append(then(use_proj))
        # A failed projection falls through to the next bearing; the draws are
        # independent, so a second one is a real second chance and not a repeat.
        flow = else_(landed)
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
    _connect(out(anywhere), _pin(salvaged, "Condition"))
    _connect(then(anywhere), _pin(salvaged, "execute"))

    use_any = ed.add_set_member_variable_node(HV.RespawnPoint)
    _connect(out(anywhere, "RandomLocation"), _pin(use_any, HV.RespawnPoint))
    _connect(then(salvaged), _pin(use_any, "execute"))
    ready.append(then(use_any))

    # 3. seat it on the real ground. The point is on the navmesh by now, but the
    # navmesh is a voxelised approximation of the terrain and its Z can be most
    # of a capsule too low -- so keep the XY, throw the Z away, and trace onto
    # the collision geometry the character will actually stand on.
    seat = ed.add_get_member_variable_node(HV.RespawnPoint)
    seat_out = out(seat, HV.RespawnPoint)
    above = _node(ed, FN_ADD_VV)
    _connect(seat_out, _pin(above, "A"))
    _connect(_vec(ed, 0.0, 0.0, RESPAWN_TRACE_UP), _pin(above, "B"))
    below = _node(ed, FN_ADD_VV)
    _connect(seat_out, _pin(below, "A"))
    _connect(_vec(ed, 0.0, 0.0, -RESPAWN_TRACE_DOWN), _pin(below, "B"))

    drop = _node(ed, FN_TRACE)
    _connect(out(above), _pin(drop, "Start"))
    _connect(out(below), _pin(drop, "End"))
    _trace_defaults(drop)
    # The terrain is imported with complex collision, and its simple collision
    # is a box around the whole 200 m mesh -- tracing against that would seat
    # every respawn on an invisible lid.
    _set(drop, "bTraceComplex", True)
    for tail in ready:
        _connect(tail, _pin(drop, "execute"))

    found = ed.add_branch_node()
    _connect(out(drop), _pin(found, "Condition"))
    _connect(then(drop), _pin(found, "execute"))

    lift = _vec(ed, 0.0, 0.0, RESPAWN_LIFT)
    brk = _palette(ed, NODE_BREAK_HIT)
    _connect(out(drop, "OutHit"), _pin(brk, "Hit"))
    ground = _node(ed, FN_ADD_VV)
    _connect(_loose_pin(brk, "Location", is_input=False), _pin(ground, "A"))
    _connect(lift, _pin(ground, "B"))
    stand = ed.add_set_member_variable_node(HV.RespawnPoint)
    _connect(out(ground), _pin(stand, HV.RespawnPoint))
    _connect(then(found), _pin(stand, "execute"))

    # Nothing under the point at all (it hangs over a hole in the world). Keep
    # the navmesh height and lift off that instead -- worse, but still above
    # whatever the navmesh thinks the floor is.
    airborne = _node(ed, FN_ADD_VV)
    _connect(seat_out, _pin(airborne, "A"))
    _connect(lift, _pin(airborne, "B"))
    hover = ed.add_set_member_variable_node(HV.RespawnPoint)
    _connect(out(airborne), _pin(hover, HV.RespawnPoint))
    _connect(else_(found), _pin(hover, "execute"))

    made += [seat, above, below, drop, found, brk, ground, stand, airborne, hover]

    # 4. spawn, on ground the character can actually stand on.
    chosen = ed.add_get_member_variable_node(HV.RespawnPoint)
    xform = _node(ed, FN_MAKE_TRANSFORM)
    _connect(out(chosen, HV.RespawnPoint), _pin(xform, "Location"))
    _connect(_vec(ed, 1.0, 1.0, 1.0), _pin(xform, "Scale"))

    spawn = _palette(ed, NODE_SPAWN)
    _connect(out(cls_get, HV.RespawnClass), _pin(spawn, "Class"))
    _connect(out(xform), _pin(spawn, "SpawnTransform"))
    # AlwaysSpawn: the nav point is inset from obstacles by the agent radius but
    # may still clip a trunk's collision, and a respawn that silently returns
    # null would empty the forest one death at a time.
    # AdjustIfPossibleButAlwaysSpawn, not AlwaysSpawn: the nav point is inset
    # from obstacles by the agent radius but can still clip a trunk, and a
    # capsule left interpenetrating gets depenetrated -- sometimes downwards,
    # through the terrain. Adjusting nudges it clear first; it still always
    # spawns, so a respawn cannot silently return null and empty the forest.
    _set(spawn, "CollisionHandlingOverride", "AdjustIfPossibleButAlwaysSpawn")
    for tail in (then(stand), then(hover)):
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
