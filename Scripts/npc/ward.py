"""Fire holds a wendigo off: the tree's Ward step (BT_Ward), tried before the
attack (stalk, chase, swing) while the wanderer is aggro. The numbers are
forest_generator/npc_ward.py's.

    BT_Ward -> [now < WardFleeUntil?]                 it is running away: (run)
       -> [no player, or no weapon component on them?]             fail
       -> [FireWard AND within the range AND in front of the player?]
            no                                         fail: the attack runs
       -> [no hold under way, or the last held pass too long ago?]
            yes  WardSince = now, WardSide = +1 or -1,
                 WardTurnAt = now + 2-4.5 s
            no   [standing still, or WardTurnAt <= now?]
                 WardSide = -WardSide, WardTurnAt = now + 2-4.5 s
       -> WardLast = now
       -> [now - WardSince >= the hold?]
            yes  WardFleeUntil = now + the flight, WardSince = 0
                 (a stalker: its hunt starts over, roar and all)  -> (run)
            no   face the player -> SimpleMoveToLocation(a point on the ring,
                 further round them from where it stands) -> the prowl speed
                                                                   succeed
    (run)  face the way it goes -> WardFleeGoal = straight away from the
           player, snapped onto the navmesh -> SimpleMoveToLocation there
           (off the navmesh: no order) -> the run speed            succeed

A pass that succeeds has given its own move order, and the tree does not go
on to the attack, so nothing swings (npc/tree.py). "In front" is measured
from where the player's body faces to where the wendigo stands, so a wendigo
that gets further round than the half angle is past the fire: the step
fails, and the charge and the swing are the ordinary ones.

The fire is the player's: FireWard on BP_WeaponComponent (combat/paths.py),
read through a cast behind an IsValid Branch, as a condition is pulled even
when its object is null.

SimpleMoveToLocation, as the stroll, the strafe and the stalk are: the level
verifier counts the chase's MoveToActor and MoveToLocation, one of each.
"""

import math

import unreal

from combat.paths import FIRE_WARD_VAR, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from forest_generator.npc_ward import (
    NPC_WARD_ARC_DEG, NPC_WARD_FEARS, NPC_WARD_FLEE_NAV_EXTENT_CM,
    NPC_WARD_FLEE_S, NPC_WARD_FLEE_STEP_CM, NPC_WARD_GRACE_S,
    NPC_WARD_HALF_ANGLE_DEG, NPC_WARD_HOLD_S, NPC_WARD_RANGE_CM,
    NPC_WARD_RING_CM, NPC_WARD_SPEED_SCALE, NPC_WARD_STALLED_CMS,
    NPC_WARD_TURN_MAX_S, NPC_WARD_TURN_MIN_S,
)
from npc.graph import (
    BEL, _Graph, _asset_sub, _connect, _log, _loose_pin, _palette, _pin, out,
)
from npc.nodes import (
    FN_ACTOR_LOC, FN_ADD_FF, FN_ADD_VV, FN_AND, FN_DISTANCE_2D, FN_DOT_VV,
    FN_EQ_FF, FN_FORWARD, FN_GE_FF, FN_GET_COMP, FN_GET_CONTROLLER, FN_GET_PAWN,
    FN_GET_PLAYER_PAWN, FN_GT_FF, FN_IS_VALID, FN_LE_FF, FN_LT_FF,
    FN_MAKE_VECTOR, FN_MUL_FF, FN_MUL_VV, FN_NORMAL_2D, FN_OR, FN_PROJECT_NAV,
    FN_RANDOM_BOOL, FN_RANDOM_FLOAT, FN_ROTATE_AXIS, FN_SELECT_FLOAT, FN_SIMPLE_MOVE, FN_SUB_FF,
    FN_SUB_VV, FN_TIME_SECONDS, FN_VELOCITY, FN_VSIZE_XY, NODE_CAST_WEAPON,
)
from npc.paths import (
    STALK_CHARGING_VAR, STALK_LEG_UNTIL_VAR, STALK_ROAR_UNTIL_VAR,
    WARD_FLEE_GOAL_VAR, WARD_FLEE_UNTIL_VAR, WARD_LAST_VAR, WARD_SIDE_VAR,
    WARD_SINCE_VAR, WARD_TURN_AT_VAR,
)
from npc.patrol import _author_walk_speed
from npc.strafe import _author_facing

# Dot(the player's forward, the unit bearing to the wendigo) at the edge of
# "in front". Rounded: cos(90 deg) is not quite 0 in floating point.
WARD_MIN_DOT = round(math.cos(math.radians(NPC_WARD_HALF_ANGLE_DEG)), 4)


def wards(key):
    """Does creature ``key`` get the step? It has to fear fire, and the
    player's weapon component has to have a FireWard to read: a project whose
    weapons were built before the flag existed has a wendigo that fears
    nothing, and a log line saying why."""
    if key not in NPC_WARD_FEARS:
        return False
    eas = _asset_sub()
    bp = (eas.load_asset(WEAPON_COMP_BP_PATH)
          if eas.does_asset_exist(WEAPON_COMP_BP_PATH) else None)
    try:
        if bp:
            unreal.get_default_object(BEL.generated_class(bp)).get_editor_property(
                FIRE_WARD_VAR)
            return True
    except Exception:
        pass
    _log(f"note: {WEAPON_COMP_BP_PATH} has no {FIRE_WARD_VAR} -- run "
         f"build_weapons_and_combat.py first. {key} is not held off by fire.")
    return False


def declare_ward_vars(ed):
    """All zero by default: no hold, no side, not fleeing."""
    kinds = {name: BEL.get_basic_type_by_name("real")
             for name in (WARD_SINCE_VAR, WARD_LAST_VAR, WARD_SIDE_VAR,
                          WARD_TURN_AT_VAR, WARD_FLEE_UNTIL_VAR)}
    kinds[WARD_FLEE_GOAL_VAR] = BEL.get_struct_type(unreal.Vector.static_struct())
    for name, kind in kinds.items():
        ed.remove_member_variable(name)
        if not ed.add_member_variable(name, kind):
            raise RuntimeError(f"could not declare {name}")


def _thrice(g, value, x, y):
    """A vector of three of ``value``: vector x float is a wildcard node."""
    return out(g.call(FN_MAKE_VECTOR, x, y, X=value, Y=value, Z=value))


def _author_held(g, exec_in, pins, x0, y0):
    """Is the fire between them? Returns ``(held, refused)``: the exec pin of
    a pass that is held off, and those of one that is not."""
    there = g.call(FN_IS_VALID, x0, y0 + 300)
    _connect(pins["player"], _pin(there, "Object"))
    present = g.branch(out(there), exec_in, x0 + 240, y0)
    comp = g.call(FN_GET_COMP, x0 + 240, y0 + 300)
    _connect(pins["player"], _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    cast = g.keep(_palette(g.ed, NODE_CAST_WEAPON), x0 + 540, y0)
    _connect(out(comp), _pin(cast, "Object"))
    _connect(BEL.find_then_pin(present), _pin(cast, "execute"))
    fire = g.keep(g.ed.add_get_member_variable_node(FIRE_WARD_VAR,
                                                    WEAPON_COMP_CLASS_PATH),
                  x0 + 840, y0 + 240)
    _connect(_loose_pin(cast, "AsBPWeaponComponent", is_input=False),
             _pin(fire, "self"))

    near = g.op(FN_LE_FF, pins["gap"], NPC_WARD_RANGE_CM, x0 + 840, y0 + 400)
    facing = g.call(FN_FORWARD, x0 + 540, y0 + 560)
    _connect(pins["player"], _pin(facing, "self"))
    dot = g.op(FN_DOT_VV, out(facing), pins["bearing"], x0 + 840, y0 + 560)
    front = g.op(FN_GT_FF, dot, WARD_MIN_DOT, x0 + 1080, y0 + 560)
    lit = g.op(FN_AND, _pin(fire, FIRE_WARD_VAR, is_input=False), near,
               x0 + 1080, y0 + 300)
    held = g.branch(g.op(FN_AND, lit, front, x0 + 1320, y0 + 400),
                    BEL.find_then_pin(cast), x0 + 1560, y0)
    return BEL.find_then_pin(held), [
        BEL.find_else_pin(present), _pin(cast, "CastFailed", is_input=False),
        BEL.find_else_pin(held)]


def _author_turn_time(g, exec_in, pins, x0, y0):
    """WardTurnAt = now + one throw of the time between two turns. Returns
    the Set's then pin."""
    throw = g.call(FN_RANDOM_FLOAT, x0, y0 + 460, Min=NPC_WARD_TURN_MIN_S,
                   Max=NPC_WARD_TURN_MAX_S)
    due = g.op(FN_ADD_FF, pins["now"], out(throw), x0 + 240, y0 + 300)
    return g.put(WARD_TURN_AT_VAR, exec_in, x0 + 480, y0, pin=due)


def _author_hold(g, exec_in, pins, x0, y0):
    """The hold's own state, for a pass that is held off: when it began, which
    way round and until when, the stamp. Returns the Branch on "held off long
    enough"."""
    idle = g.op(FN_SUB_FF, pins["now"], g.get(WARD_LAST_VAR, x0 - 240, y0 + 440),
                x0, y0 + 300)
    lapsed = g.op(FN_GT_FF, idle, NPC_WARD_GRACE_S, x0 + 240, y0 + 300)
    # Exactly 0, which is what a flight leaves: any other time is a hold's.
    unstarted = g.op(FN_EQ_FF, g.get(WARD_SINCE_VAR, x0, y0 + 600), 0.0,
                     x0 + 240, y0 + 600)
    fresh = g.branch(g.op(FN_OR, lapsed, unstarted, x0 + 480, y0 + 440), exec_in,
                     x0 + 740, y0)
    # --- a new hold: one throw for the way round, as the stalk's is -----------
    began = g.put(WARD_SINCE_VAR, BEL.find_then_pin(fresh), x0 + 1040, y0,
                  pin=pins["now"])
    coin = g.call(FN_SELECT_FLOAT, x0 + 1100, y0 + 300, A=1.0, B=-1.0)
    _connect(out(g.call(FN_RANDOM_BOOL, x0 + 860, y0 + 300)), _pin(coin, "bPickA"))
    picked = g.put(WARD_SIDE_VAR, began, x0 + 1340, y0, pin=out(coin))
    picked = _author_turn_time(g, picked, pins, x0 + 1340, y0 - 800)
    # --- the same hold: stopped by something, or its time that way round is
    # up? Round the other way. ------------------------------------------------
    moving = g.call(FN_VELOCITY, x0 + 740, y0 + 900)
    _connect(pins["self_pawn"], _pin(moving, "self"))
    pace = g.call(FN_VSIZE_XY, x0 + 980, y0 + 900)
    _connect(out(moving), _pin(pace, "A"))
    up = g.op(FN_LE_FF, g.get(WARD_TURN_AT_VAR, x0 + 980, y0 + 1300), pins["now"],
              x0 + 1220, y0 + 1300)
    still = g.op(FN_LT_FF, out(pace), NPC_WARD_STALLED_CMS, x0 + 1220, y0 + 900)
    stalled = g.branch(g.op(FN_OR, still, up, x0 + 1460, y0 + 1100),
                       BEL.find_else_pin(fresh), x0 + 1040, y0 + 700)
    other = g.op(FN_MUL_FF, g.get(WARD_SIDE_VAR, x0 + 1100, y0 + 1100), -1.0,
                 x0 + 1340, y0 + 1000)
    turned = g.put(WARD_SIDE_VAR, BEL.find_then_pin(stalled), x0 + 1580, y0 + 700,
                   pin=other)
    turned = _author_turn_time(g, turned, pins, x0 + 1580, y0 + 1500)

    stamped = g.put(WARD_LAST_VAR, [picked, turned, BEL.find_else_pin(stalled)],
                    x0 + 1900, y0, pin=pins["now"])
    so_far = g.op(FN_SUB_FF, pins["now"], g.get(WARD_SINCE_VAR, x0 + 1900, y0 + 440),
                  x0 + 2140, y0 + 300)
    spent = g.op(FN_GE_FF, so_far, NPC_WARD_HOLD_S, x0 + 2380, y0 + 300)
    return g.branch(spent, stamped, x0 + 2640, y0)


def _author_circle(g, exec_in, pins, stock, x0, y0):
    """Round the player on the ring, eyes on them. Returns the exec pins it
    ends on."""
    watch, step = _author_facing(g.ed, [exec_in], pins["player"], x0, y0)
    g.made.extend(watch)
    angle = g.op(FN_MUL_FF, g.get(WARD_SIDE_VAR, x0 + 1700, y0 + 600),
                 NPC_WARD_ARC_DEG, x0 + 1940, y0 + 500)
    round_them = g.call(FN_ROTATE_AXIS, x0 + 2200, y0 + 400)
    _connect(pins["bearing"], _pin(round_them, "InVect"))
    _connect(angle, _pin(round_them, "AngleDeg"))
    _connect(out(g.call(FN_MAKE_VECTOR, x0 + 1940, y0 + 700, Z=1.0)),
             _pin(round_them, "Axis"))
    reach = g.op(FN_MUL_VV, out(round_them),
                 _thrice(g, NPC_WARD_RING_CM, x0 + 2200, y0 + 700), x0 + 2460, y0 + 400)
    spot = g.op(FN_ADD_VV, pins["player_loc"], reach, x0 + 2700, y0 + 400)
    me = g.call(FN_GET_CONTROLLER, x0 + 2700, y0 + 600)
    _connect(pins["self_pawn"], _pin(me, "self"))
    go = g.call(FN_SIMPLE_MOVE, x0 + 2960, y0)
    _connect(out(me), _pin(go, "Controller"))
    _connect(spot, _pin(go, "Goal"))
    _connect(step, _pin(go, "execute"))
    prowl, tails, _entry = _author_walk_speed(
        g.ed, [BEL.find_then_pin(go)], False, stock, x0 + 3260, y0,
        scale=NPC_WARD_SPEED_SCALE)
    g.made.extend(prowl)
    return tails


def _author_flight(g, exec_in, pins, stock, x0, y0):
    """Straight away from the player, as far as the navmesh goes. ``exec_in``
    is every exec pin that runs it. Returns the exec pins it ends on."""
    ahead, step = _author_facing(g.ed, exec_in, None, x0, y0)
    g.made.extend(ahead)
    stride = g.op(FN_MUL_VV, pins["bearing"],
                  _thrice(g, NPC_WARD_FLEE_STEP_CM, x0 + 1700, y0 + 600),
                  x0 + 1940, y0 + 400)
    aimed = g.put(WARD_FLEE_GOAL_VAR, step, x0 + 2200, y0,
                  pin=g.op(FN_ADD_VV, pins["self_loc"], stride, x0 + 1940, y0 + 240))
    # Pure: branched on its bool before its point is read, and the point it
    # is given is the stored one.
    on_nav = g.call(FN_PROJECT_NAV, x0 + 2500, y0 + 300)
    _connect(g.get(WARD_FLEE_GOAL_VAR, x0 + 2260, y0 + 300), _pin(on_nav, "Point"))
    _connect(out(g.call(FN_MAKE_VECTOR, x0 + 2260, y0 + 460,
                        **dict(zip("XYZ", NPC_WARD_FLEE_NAV_EXTENT_CM)))),
             _pin(on_nav, "QueryExtent"))
    walkable = g.branch(out(on_nav), aimed, x0 + 2800, y0)
    snapped = g.put(WARD_FLEE_GOAL_VAR, BEL.find_then_pin(walkable), x0 + 3100, y0,
                    pin=out(on_nav, "ProjectedLocation"))
    me = g.call(FN_GET_CONTROLLER, x0 + 3100, y0 + 460)
    _connect(pins["self_pawn"], _pin(me, "self"))
    go = g.call(FN_SIMPLE_MOVE, x0 + 3400, y0)
    _connect(out(me), _pin(go, "Controller"))
    _connect(g.get(WARD_FLEE_GOAL_VAR, x0 + 3100, y0 + 620), _pin(go, "Goal"))
    _connect(snapped, _pin(go, "execute"))
    ran, tails, _entry = _author_walk_speed(
        g.ed, [BEL.find_then_pin(go), BEL.find_else_pin(walkable)], False, stock,
        x0 + 3700, y0)
    g.made.extend(ran)
    return tails


def _author_ward(ed, exec_in, result, stock, restalks, x0, y0):
    """Author BT_Ward. ``exec_in`` is the step's exec pin (behind the alive
    gate), ``result(value, x, y)`` makes a StepResult write and returns its
    exec input, ``stock`` is the creature's built run speed
    (patrol._author_walk_speed), and ``restalks`` says it is a stalker, whose
    hunt a flight starts over. Returns the nodes made, for a comment box.
    """
    g = _Graph(ed)
    self_pawn = g.call(FN_GET_PAWN, x0, y0 + 300)
    self_loc = g.call(FN_ACTOR_LOC, x0 + 240, y0 + 300)
    _connect(out(self_pawn), _pin(self_loc, "self"))
    player = g.call(FN_GET_PLAYER_PAWN, x0, y0 + 460, PlayerIndex=0)
    player_loc = g.call(FN_ACTOR_LOC, x0 + 240, y0 + 460)
    _connect(out(player), _pin(player_loc, "self"))
    gap = g.call(FN_DISTANCE_2D, x0 + 480, y0 + 380)
    _connect(out(self_loc), _pin(gap, "V1"))
    _connect(out(player_loc), _pin(gap, "V2"))
    # From the player to the wendigo, flat: where it stands about them, and
    # the way it runs when it runs away.
    bearing = g.call(FN_NORMAL_2D, x0 + 720, y0 + 540)
    _connect(g.op(FN_SUB_VV, out(self_loc), out(player_loc), x0 + 480, y0 + 540),
             _pin(bearing, "A"))
    now = g.call(FN_TIME_SECONDS, x0 + 240, y0 + 700)
    pins = dict(self_pawn=out(self_pawn), self_loc=out(self_loc), player=out(player),
                player_loc=out(player_loc), gap=out(gap), bearing=out(bearing),
                now=out(now))

    running = g.op(FN_LT_FF, pins["now"], g.get(WARD_FLEE_UNTIL_VAR, x0 + 480, y0 + 160),
                   x0 + 720, y0 + 160)
    fleeing = g.branch(running, exec_in, x0 + 980, y0)
    held, refused = _author_held(g, BEL.find_else_pin(fleeing), pins, x0 + 1300, y0)
    for i, pin in enumerate(refused):
        _connect(pin, result(False, x0 + 1900 + 300 * i, y0 - 240))
    spent = _author_hold(g, held, pins, x0 + 3300, y0)

    # --- held off long enough: it gives up ------------------------------------
    gone = g.put(WARD_FLEE_UNTIL_VAR, BEL.find_then_pin(spent), x0 + 6300, y0 + 1600,
                 pin=g.op(FN_ADD_FF, pins["now"], NPC_WARD_FLEE_S, x0 + 6040, y0 + 1900))
    gone = g.put(WARD_SINCE_VAR, gone, x0 + 6600, y0 + 1600, literal=0.0)
    if restalks:
        # Back from its flight it hunts as it first did: the roar, then tree
        # to tree (npc/stalk.py), rather than a charge from where it stopped.
        gone = g.put(STALK_ROAR_UNTIL_VAR, gone, x0 + 6900, y0 + 1600, literal=0.0)
        gone = g.put(STALK_LEG_UNTIL_VAR, gone, x0 + 7200, y0 + 1600, literal=0.0)
        gone = g.put(STALK_CHARGING_VAR, gone, x0 + 7500, y0 + 1600, literal="false")
    for tail in _author_flight(g, [BEL.find_then_pin(fleeing), gone], pins, stock,
                               x0 + 7900, y0 + 1600):
        _connect(tail, result(True, x0 + 13200, y0 + 1600))

    # --- still held: round them ------------------------------------------------
    for tail in _author_circle(g, BEL.find_else_pin(spent), pins, stock,
                               x0 + 6300, y0):
        _connect(tail, result(True, x0 + 11200, y0))
    return g.made
