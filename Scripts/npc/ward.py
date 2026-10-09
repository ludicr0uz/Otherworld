"""Fire holds a wendigo off: the tree's Ward step (BT_Ward), tried before the
attack (stalk, chase, swing) while the wanderer is aggro. The numbers are
forest_generator/npc_ward.py's.

    BT_Ward -> [now < WardFleeUntil?]  it is running away:
                 [now < WardRoarUntil?]  its last roar first       succeed
                 (run)
       -> [no player, or no weapon component on them?]             fail
       -> [FireWard AND within the range AND in front of the player?]
            no                                         fail: the attack runs
       -> [no hold under way, or the last held pass too long ago?]
            yes  WardSince = now, WardSide = +1 or -1,
                 WardTurnAt = now + 2-4.5 s, WardRoarAt = now + 13-17 s
            no   [standing still, or WardTurnAt <= now?]
                 WardSide = -WardSide, WardTurnAt = now + 2-4.5 s
       -> WardLast = now
       -> [now - WardSince >= the hold?]
            yes  WardFleeUntil = now + the roar + the flight, WardSince = 0
                 (a stalker: its hunt starts over, roar and all)
                 -> it roars (ward_roar.py), standing              succeed
            no   [roaring, or WardRoarAt up?]  it stands and roars, the
                 once a hold (ward_roar.py)                        succeed
                 face the player -> SimpleMoveToLocation(a point on the ring,
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

The range, the half angle (through DegCos), the ring, the prowl speed, the
time between two turns, the hold and the flight are the controller's
TuneWard* variables (npc/tuned.py: the MONSTER SETTINGS tab's "fire:" rows),
defaulted to npc_ward.py's numbers.

The fire is the player's: FireWard on BP_WeaponComponent (combat/paths.py),
read through a cast behind an IsValid Branch, as a condition is pulled even
when its object is null.

SimpleMoveToLocation, as the stroll, the strafe and the stalk are: the level
verifier counts the chase's MoveToActor and MoveToLocation, one of each.
"""

from uebp.vars import declare
from npc import controller_vars as NV
import unreal

from combat.paths import FIRE_WARD_VAR, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from forest_generator.npc_ward import (
    NPC_WARD_ARC_DEG, NPC_WARD_FEARS, NPC_WARD_FLEE_NAV_EXTENT_CM,
    NPC_WARD_FLEE_STEP_CM, NPC_WARD_GRACE_S, NPC_WARD_ROAR_S,
    NPC_WARD_STALLED_CMS,
)
from npc.graph import _Graph, _log
from net.players import nearest_living_player, player_pin
from uebp.graph import BEL, _assets, _connect, _loose_pin, _palette, _pin, else_, out, then
from npc.paths import (
    STALK_CHARGING_VAR, STALK_LEG_UNTIL_VAR, STALK_ROAR_UNTIL_VAR,
    WARD_FLEE_GOAL_VAR, WARD_FLEE_UNTIL_VAR, WARD_LAST_VAR, WARD_SIDE_VAR,
    WARD_SINCE_VAR, WARD_TURN_AT_VAR,
)
from npc.patrol import _author_walk_speed
from npc.strafe import _author_facing
from npc.tuned import tuned_pin
from npc.ward_roar import (
    _author_roar_time, _author_roar_wait, _author_roars, declare_ward_roar_vars,
)
from uebp.nodes.actor import (
    FN_ACTOR_FORWARD, FN_ACTOR_LOC, FN_GET_COMP, FN_GET_CONTROLLER, FN_GET_PAWN, FN_VELOCITY)
from uebp.nodes.ai import FN_PROJECT_NAV, FN_SIMPLE_MOVE
from uebp.nodes.math import (
    FN_ADD_FF, FN_ADD_VV, FN_AND, FN_DEG_COS, FN_DISTANCE_2D, FN_DOT_VV, FN_EQ_FF, FN_GE_FF,
    FN_GREATER_FF, FN_LESS_FF, FN_LE_FF, FN_MAKE_VECTOR, FN_MUL_FF, FN_MUL_VV, FN_NORMAL_2D,
    FN_OR, FN_RANDOM_BOOL, FN_RANDOM_FLOAT, FN_ROTATE_AXIS, FN_SELECT_FF, FN_SUB_FF,
    FN_SUB_VV, FN_VSIZE_XY)
from uebp.nodes.palette import NODE_CAST_WEAPON
from uebp.nodes.system import FN_IS_VALID, FN_TIME_SECONDS

def wards(key):
    """Does creature ``key`` get the step? It has to fear fire, and the
    player's weapon component has to have a FireWard to read: a project whose
    weapons were built before the flag existed has a wendigo that fears
    nothing, and a log line saying why."""
    if key not in NPC_WARD_FEARS:
        return False
    eas = _assets()
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
    declare(ed, NV.WARD)
    declare_ward_roar_vars(ed)


def _thrice(g, value):
    """A vector of three of ``value`` (a number or a pin): vector x float is
    a wildcard node."""
    if isinstance(value, (int, float)):
        return out(g.call(FN_MAKE_VECTOR, X=value, Y=value, Z=value))
    node = g.call(FN_MAKE_VECTOR)
    for axis in "XYZ":
        _connect(value, _pin(node, axis))
    return out(node)


def _author_held(g, exec_in, pins):
    """Is the fire between them? Returns ``(held, refused)``: the exec pin of
    a pass that is held off, and those of one that is not."""
    there = g.call(FN_IS_VALID)
    _connect(pins["player"], _pin(there, "Object"))
    present = g.branch(out(there), exec_in)
    comp = g.call(FN_GET_COMP)
    _connect(pins["player"], _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    cast = g.keep(_palette(g.ed, NODE_CAST_WEAPON))
    _connect(out(comp), _pin(cast, "Object"))
    _connect(then(present), _pin(cast, "execute"))
    fire = g.keep(g.ed.add_get_member_variable_node(FIRE_WARD_VAR, WEAPON_COMP_CLASS_PATH))
    _connect(_loose_pin(cast, "AsBPWeaponComponent", is_input=False),
             _pin(fire, "self"))

    near = g.op(FN_LE_FF, pins["gap"], tuned_pin(g, "ward_range_cm"))
    facing = g.call(FN_ACTOR_FORWARD)
    _connect(pins["player"], _pin(facing, "self"))
    dot = g.op(FN_DOT_VV, out(facing), pins["bearing"])
    edge = g.call(FN_DEG_COS)
    _connect(tuned_pin(g, "ward_half_angle_deg"), _pin(edge, "A"))
    front = g.op(FN_GREATER_FF, dot, out(edge))
    lit = g.op(FN_AND, out(fire, FIRE_WARD_VAR), near)
    held = g.branch(g.op(FN_AND, lit, front), then(cast))
    return then(held), [else_(present), out(cast, "CastFailed"), else_(held)]


def _author_turn_time(g, exec_in, pins):
    """WardTurnAt = now + one throw of the time between two turns. Returns
    the Set's then pin."""
    throw = g.call(FN_RANDOM_FLOAT)
    _connect(tuned_pin(g, "ward_turn_min_s"), _pin(throw, "Min"))
    _connect(tuned_pin(g, "ward_turn_max_s"), _pin(throw, "Max"))
    due = g.op(FN_ADD_FF, pins["now"], out(throw))
    return g.put(WARD_TURN_AT_VAR, exec_in, pin=due)


def _author_hold(g, exec_in, pins):
    """The hold's own state, for a pass that is held off: when it began, which
    way round and until when, when it first roars, the stamp. Returns the Branch on "held off long
    enough"."""
    idle = g.op(FN_SUB_FF, pins["now"], g.get(WARD_LAST_VAR))
    lapsed = g.op(FN_GREATER_FF, idle, NPC_WARD_GRACE_S)
    # Exactly 0, which is what a flight leaves: any other time is a hold's.
    unstarted = g.op(FN_EQ_FF, g.get(WARD_SINCE_VAR), 0.0)
    fresh = g.branch(g.op(FN_OR, lapsed, unstarted), exec_in)
    # --- a new hold: one throw for the way round, as the stalk's is -----------
    began = g.put(WARD_SINCE_VAR, then(fresh), pin=pins["now"])
    coin = g.call(FN_SELECT_FF, A=1.0, B=-1.0)
    _connect(out(g.call(FN_RANDOM_BOOL)), _pin(coin, "bPickA"))
    picked = g.put(WARD_SIDE_VAR, began, pin=out(coin))
    picked = _author_turn_time(g, picked, pins)
    picked = _author_roar_time(g, picked, pins)
    # --- the same hold: stopped by something, or its time that way round is
    # up? Round the other way. ------------------------------------------------
    moving = g.call(FN_VELOCITY)
    _connect(pins["self_pawn"], _pin(moving, "self"))
    pace = g.call(FN_VSIZE_XY)
    _connect(out(moving), _pin(pace, "A"))
    up = g.op(FN_LE_FF, g.get(WARD_TURN_AT_VAR), pins["now"])
    still = g.op(FN_LESS_FF, out(pace), NPC_WARD_STALLED_CMS)
    stalled = g.branch(g.op(FN_OR, still, up), else_(fresh))
    other = g.op(FN_MUL_FF, g.get(WARD_SIDE_VAR), -1.0)
    turned = g.put(WARD_SIDE_VAR, then(stalled), pin=other)
    turned = _author_turn_time(g, turned, pins)

    stamped = g.put(WARD_LAST_VAR, [picked, turned, else_(stalled)], pin=pins["now"])
    so_far = g.op(FN_SUB_FF, pins["now"], g.get(WARD_SINCE_VAR))
    spent = g.op(FN_GE_FF, so_far, tuned_pin(g, "ward_hold_s"))
    return g.branch(spent, stamped)


def _author_circle(g, exec_in, pins, stock):
    """Round the player on the ring, eyes on them. Returns the exec pins it
    ends on."""
    watch, step = _author_facing(g.ed, [exec_in], pins["player"])
    g.made.extend(watch)
    angle = g.op(FN_MUL_FF, g.get(WARD_SIDE_VAR), NPC_WARD_ARC_DEG)
    round_them = g.call(FN_ROTATE_AXIS)
    _connect(pins["bearing"], _pin(round_them, "InVect"))
    _connect(angle, _pin(round_them, "AngleDeg"))
    _connect(out(g.call(FN_MAKE_VECTOR, Z=1.0)), _pin(round_them, "Axis"))
    reach = g.op(FN_MUL_VV, out(round_them), _thrice(g, tuned_pin(g, "ward_ring_cm")))
    spot = g.op(FN_ADD_VV, pins["player_loc"], reach)
    me = g.call(FN_GET_CONTROLLER)
    _connect(pins["self_pawn"], _pin(me, "self"))
    go = g.call(FN_SIMPLE_MOVE)
    _connect(out(me), _pin(go, "Controller"))
    _connect(spot, _pin(go, "Goal"))
    _connect(step, _pin(go, "execute"))
    prowl, tails, _entry = _author_walk_speed(
        g.ed, [then(go)], False, stock,
        scale="ward_speed_scale")
    g.made.extend(prowl)
    return tails


def _author_flight(g, exec_in, pins, stock):
    """Straight away from the player, as far as the navmesh goes. ``exec_in``
    is every exec pin that runs it. Returns the exec pins it ends on."""
    ahead, step = _author_facing(g.ed, exec_in, None)
    g.made.extend(ahead)
    stride = g.op(FN_MUL_VV, pins["bearing"], _thrice(g, NPC_WARD_FLEE_STEP_CM))
    aimed = g.put(WARD_FLEE_GOAL_VAR, step, pin=g.op(FN_ADD_VV, pins["self_loc"], stride))
    # Pure: branched on its bool before its point is read, and the point it
    # is given is the stored one.
    on_nav = g.call(FN_PROJECT_NAV)
    _connect(g.get(WARD_FLEE_GOAL_VAR), _pin(on_nav, "Point"))
    _connect(out(g.call(FN_MAKE_VECTOR,
                        **dict(zip("XYZ", NPC_WARD_FLEE_NAV_EXTENT_CM)))),
             _pin(on_nav, "QueryExtent"))
    walkable = g.branch(out(on_nav), aimed)
    snapped = g.put(WARD_FLEE_GOAL_VAR, then(walkable), pin=out(on_nav, "ProjectedLocation"))
    me = g.call(FN_GET_CONTROLLER)
    _connect(pins["self_pawn"], _pin(me, "self"))
    go = g.call(FN_SIMPLE_MOVE)
    _connect(out(me), _pin(go, "Controller"))
    _connect(g.get(WARD_FLEE_GOAL_VAR), _pin(go, "Goal"))
    _connect(snapped, _pin(go, "execute"))
    ran, tails, _entry = _author_walk_speed(g.ed, [then(go), else_(walkable)], False, stock)
    g.made.extend(ran)
    return tails


def _author_ward(ed, exec_in, result, roar_anim, stock, restalks):
    """Author BT_Ward. ``exec_in`` is the step's exec pin (behind the alive
    gate), ``result(value)`` makes a StepResult write and returns its
    exec input, ``roar_anim`` is roar.roar_object()'s answer, ``stock`` is
    the creature's built run speed
    (patrol._author_walk_speed), and ``restalks`` says it is a stalker, whose
    hunt a flight starts over. Returns the nodes made, for a comment box.
    """
    g = _Graph(ed)
    self_pawn = g.call(FN_GET_PAWN)
    self_loc = g.call(FN_ACTOR_LOC)
    _connect(out(self_pawn), _pin(self_loc, "self"))
    player = g.keep(nearest_living_player(ed, out(self_loc)))
    player_loc = g.call(FN_ACTOR_LOC)
    _connect(player_pin(player), _pin(player_loc, "self"))
    gap = g.call(FN_DISTANCE_2D)
    _connect(out(self_loc), _pin(gap, "V1"))
    _connect(out(player_loc), _pin(gap, "V2"))
    # From the player to the wendigo, flat: where it stands about them, and
    # the way it runs when it runs away.
    bearing = g.call(FN_NORMAL_2D)
    _connect(g.op(FN_SUB_VV, out(self_loc), out(player_loc)), _pin(bearing, "A"))
    now = g.call(FN_TIME_SECONDS)
    pins = dict(self_pawn=out(self_pawn), self_loc=out(self_loc), player=player_pin(player),
                player_loc=out(player_loc), gap=out(gap), bearing=out(bearing),
                now=out(now))

    running = g.op(FN_LESS_FF, pins["now"], g.get(WARD_FLEE_UNTIL_VAR))
    fleeing = g.branch(running, exec_in)
    # It roars before it runs: the flight's first passes stand.
    standing, away = _author_roar_wait(g, then(fleeing), pins)
    _connect(standing, result(True))
    held, refused = _author_held(g, else_(fleeing), pins)
    for pin in refused:
        _connect(pin, result(False))
    spent = _author_hold(g, held, pins)

    # --- held off long enough: it gives up ------------------------------------
    gone = g.put(WARD_FLEE_UNTIL_VAR, then(spent),
                 pin=g.op(FN_ADD_FF,
                          g.op(FN_ADD_FF, pins["now"],
                               tuned_pin(g, "ward_flee_s")),
                          NPC_WARD_ROAR_S))
    gone = g.put(WARD_SINCE_VAR, gone, literal=0.0)
    if restalks:
        # Back from its flight it hunts as it first did: the roar, then tree
        # to tree (npc/stalk.py), rather than a charge from where it stopped.
        gone = g.put(STALK_ROAR_UNTIL_VAR, gone, literal=0.0)
        gone = g.put(STALK_LEG_UNTIL_VAR, gone, literal=0.0)
        gone = g.put(STALK_CHARGING_VAR, gone, literal="false")
    for tail in _author_flight(g, [away], pins, stock):
        _connect(tail, result(True))

    # --- its two roars: one part way through the hold, one at its end ----------
    circling, roared = _author_roars(g, else_(spent), gone, pins, roar_anim)
    for tail in roared:
        _connect(tail, result(True))

    # --- still held: round them ------------------------------------------------
    for tail in _author_circle(g, circling, pins, stock):
        _connect(tail, result(True))
    return g.made
