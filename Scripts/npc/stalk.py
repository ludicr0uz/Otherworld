"""A wendigo's hunt: the tree's Stalk step (BT_Stalk), tried before Chase
while the wanderer is aggro. It roars, comes in round the player from tree to
tree, and then stops answering, which hands the hunt to the Chase step: the
charge. The numbers are forest_generator/npc_stalk.py's.

    BT_Stalk -> [StalkCharging?]                       fail: Chase runs
       -> [StalkRoarUntil is 0?]  the first pass:
              StalkRoarUntil = now + the roar, StalkSide = +1 or -1
              stop, face the player, play the roar clip and a voice    succeed
       -> [now < StalkRoarUntil?]  still roaring                       succeed
       -> [player within the charge range?]
              StalkCharging = true                     fail: Chase runs
              (so do a leg it is standing still on, and a pick with nowhere
              to go: it charges rather than stand)
       -> [now < StalkLegUntil?]  a leg is under way
              [StalkArrived?]  waiting behind the trunk                succeed
              [within reach of StalkCover?]
                  StalkArrived = true, StalkLegUntil = now + the wait
                  (none in the open), face the player                  succeed
              [standing still?]  no path: charge, as above
              the run speed                                            succeed
       -> a new leg: the next tree (stalk_cover.py); none, and no open
          ground either: charge, as above
              face the way it runs -> SimpleMoveToLocation(StalkCover)
              -> the run speed                                         succeed

Only the creatures of NPC_STALK_ROAR get the step, its variables and its
node in their tree (npc/tree.py); the others chase as before.

A pass that succeeds has given its own move order, so the tree's selector
does not go on to Chase; the Swing step after it still runs, and still
checks its own range. Every value that could differ between two reads is
stored: the side is one throw per hunt, the wait one throw per leg.

SimpleMoveToLocation, as the stroll and the strafe are: the level verifier
counts the chase's MoveToActor and MoveToLocation, one of each.
"""

from forest_generator.npc_stalk import (
    NPC_STALK_ARRIVE_CM, NPC_STALK_CHARGE_CM, NPC_STALK_HIDE_MAX_S,
    NPC_STALK_HIDE_MIN_S, NPC_STALK_ROAR_BLEND_S, NPC_STALK_ROAR_S,
    NPC_STALK_STALLED_CMS,
)
from npc.graph import (
    BEL, _Graph, _asset_sub, _connect, _log, _loose_pin, _mesh_object, _palette,
    _pin, out,
)
from npc.nodes import (
    FN_ACTOR_LOC, FN_ADD_FF, FN_ANIM_INSTANCE, FN_DISTANCE_2D,
    FN_GET_CONTROLLER, FN_GET_PAWN, FN_GET_PLAYER_PAWN, FN_LE_FF, FN_LT_FF,
    FN_PLAY_SLOT, FN_RANDOM_BOOL, FN_RANDOM_FLOAT, FN_SELECT_FLOAT,
    FN_SIMPLE_MOVE, FN_STOP_MOVEMENT, FN_TIME_SECONDS, FN_VELOCITY, FN_VSIZE_XY,
    NODE_CAST_CHARACTER,
)
from npc.paths import (
    CHARACTER_CLASS_PATH, MELEE_SLOT, STALK_ARRIVED_VAR, STALK_CHARGING_VAR,
    STALK_COVER_VAR, STALK_HIDDEN_VAR, STALK_LEG_UNTIL_VAR,
    STALK_ROAR_UNTIL_VAR, STALK_SIDE_VAR, VOICES_VAR,
)
from npc.patrol import _author_walk_speed
from npc.sound import _author_random_sound
from npc.stalk_cover import _author_cover, declare_cover_vars
from npc.strafe import _author_facing


def declare_stalk_vars(ed):
    """All zero/false by default: not roared, no leg, not charging."""
    for name, kind in ((STALK_ROAR_UNTIL_VAR, "real"), (STALK_SIDE_VAR, "real"),
                       (STALK_CHARGING_VAR, "bool")):
        ed.remove_member_variable(name)
        if not ed.add_member_variable(name, BEL.get_basic_type_by_name(kind)):
            raise RuntimeError(f"could not declare {name}")
    declare_cover_vars(ed)


def roar_object(roar_anim):
    """The roar clip as an object path, or None when the asset pipeline has
    not produced it (asset_pipeline/import_mixamo.py): the wendigo then
    stands and roars with its voice alone."""
    if roar_anim and _asset_sub().does_asset_exist(roar_anim):
        return _mesh_object(roar_anim)
    _log(f"note: no roar clip at {roar_anim} -- run "
         f"Scripts/asset_pipeline/import_mixamo.py. The roar is sound only.")
    return None


def _author_roar(g, exec_in, pins, roar_anim, x0, y0):
    """The first pass of the hunt. Returns the exec pin it ends on."""
    ends = g.op(FN_ADD_FF, pins["now"], NPC_STALK_ROAR_S, x0, y0 + 300)
    step = g.put(STALK_ROAR_UNTIL_VAR, exec_in, x0 + 240, y0, pin=ends)
    # One throw for the whole hunt: every leg goes the same way round.
    side = g.call(FN_SELECT_FLOAT, x0 + 300, y0 + 460, A=1.0, B=-1.0)
    _connect(out(g.call(FN_RANDOM_BOOL, x0 + 60, y0 + 460)), _pin(side, "bPickA"))
    step = g.put(STALK_SIDE_VAR, step, x0 + 540, y0, pin=out(side))

    halt = g.call(FN_STOP_MOVEMENT, x0 + 840, y0)
    _connect(step, _pin(halt, "execute"))
    watch, step = _author_facing(g.ed, [BEL.find_then_pin(halt)], pins["player"],
                                 x0 + 1100, y0)
    g.made.extend(watch)

    # Through the pawn's own AnimInstance, as the swing is (npc/melee.py), and
    # into the same upper-body slot: the legs stand, the chest and arms roar.
    as_char = g.keep(_palette(g.ed, NODE_CAST_CHARACTER), x0 + 2800, y0)
    _connect(pins["self_pawn"], _pin(as_char, "Object"))
    _connect(step, _pin(as_char, "execute"))
    voiced = [_pin(as_char, "CastFailed", is_input=False)]
    if roar_anim:
        mesh = g.keep(g.ed.add_get_member_variable_node("Mesh", CHARACTER_CLASS_PATH),
                      x0 + 2800, y0 + 300)
        _connect(_loose_pin(as_char, "AsCharacter", is_input=False), _pin(mesh, "self"))
        anim = g.call(FN_ANIM_INSTANCE, x0 + 3040, y0 + 300)
        _connect(_pin(mesh, "Mesh", is_input=False), _pin(anim, "self"))
        roar = g.call(FN_PLAY_SLOT, x0 + 3300, y0, Asset=roar_anim,
                      SlotNodeName=MELEE_SLOT, BlendInTime=NPC_STALK_ROAR_BLEND_S,
                      BlendOutTime=NPC_STALK_ROAR_BLEND_S)
        _connect(out(anim), _pin(roar, "self"))
        _connect(BEL.find_then_pin(as_char), _pin(roar, "execute"))
        voiced.append(BEL.find_then_pin(roar))
    else:
        voiced.append(BEL.find_then_pin(as_char))
    join = g.branch(None, voiced, x0 + 3700, y0)
    sound, step = _author_random_sound(g.ed, VOICES_VAR, pins["self_loc"],
                                       BEL.find_then_pin(join), x0 + 3960, y0)
    g.made.extend(sound)
    return step


def _author_leg(g, exec_in, pins, stock, result, x0, y0):
    """A leg under way: wait behind the trunk, arrive, or run on. Every arm
    ends on a StepResult write of its own, but the one returned: the exec pin
    of a wendigo that is not moving, for the caller to charge on."""
    hiding = g.branch(g.get(STALK_ARRIVED_VAR, x0 - 240, y0 + 200), exec_in, x0, y0)
    _connect(BEL.find_then_pin(hiding), result(True, x0 + 300, y0 - 200))

    left = g.call(FN_DISTANCE_2D, x0 + 60, y0 + 400)
    _connect(pins["self_loc"], _pin(left, "V1"))
    _connect(g.get(STALK_COVER_VAR, x0 - 240, y0 + 460), _pin(left, "V2"))
    close = g.op(FN_LE_FF, out(left), NPC_STALK_ARRIVE_CM, x0 + 300, y0 + 400)
    there = g.branch(close, BEL.find_else_pin(hiding), x0 + 560, y0)

    # --- arrived: wait behind the trunk, watching the player -----------------
    step = g.put(STALK_ARRIVED_VAR, BEL.find_then_pin(there), x0 + 860, y0,
                 literal="true")
    # One throw per leg, and none for a spot in the open: it moves straight on.
    wait = g.call(FN_SELECT_FLOAT, x0 + 900, y0 + 460, B=0.0)
    _connect(out(g.call(FN_RANDOM_FLOAT, x0 + 640, y0 + 460, Min=NPC_STALK_HIDE_MIN_S,
                        Max=NPC_STALK_HIDE_MAX_S)), _pin(wait, "A"))
    _connect(g.get(STALK_HIDDEN_VAR, x0 + 640, y0 + 620), _pin(wait, "bPickA"))
    until = g.op(FN_ADD_FF, pins["now"], out(wait), x0 + 1140, y0 + 300)
    step = g.put(STALK_LEG_UNTIL_VAR, step, x0 + 1380, y0, pin=until)
    watch, step = _author_facing(g.ed, [step], pins["player"], x0 + 1700, y0)
    g.made.extend(watch)
    _connect(step, result(True, x0 + 3400, y0))

    # --- not there: stalled (no path to the spot), or still running. The pass
    # after a move order is half a second later, by when it is at speed. ------
    pace = g.call(FN_VSIZE_XY, x0 + 860, y0 + 1000)
    moving = g.call(FN_VELOCITY, x0 + 620, y0 + 1000)
    _connect(pins["self_pawn"], _pin(moving, "self"))
    _connect(out(moving), _pin(pace, "A"))
    slow = g.op(FN_LT_FF, out(pace), NPC_STALK_STALLED_CMS, x0 + 1100, y0 + 1000)
    stalled = g.branch(slow, BEL.find_else_pin(there), x0 + 1380, y0 + 800)
    ran, tails, _entry = _author_walk_speed(g.ed, [BEL.find_else_pin(stalled)], False,
                                            stock, x0 + 1700, y0 + 1300)
    g.made.extend(ran)
    for tail in tails:
        _connect(tail, result(True, x0 + 3200, y0 + 1300))
    return BEL.find_then_pin(stalled)


def _author_stalk(ed, exec_in, result, roar_anim, stock, x0, y0):
    """Author BT_Stalk. ``exec_in`` is the step's exec pin (behind the alive
    gate), ``result(value, x, y)`` makes a StepResult write and returns its
    exec input, ``roar_anim`` is roar_object()'s answer and ``stock`` the
    creature's built run speed (patrol._author_walk_speed).

    Returns ``(step_nodes, cover_nodes)``, for two comment boxes.
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
    now = g.call(FN_TIME_SECONDS, x0 + 240, y0 + 620)
    pins = dict(self_pawn=out(self_pawn), self_loc=out(self_loc), player=out(player),
                player_loc=out(player_loc), gap=out(gap), now=out(now))

    # --- the charge: this step is over, for good -----------------------------
    charging = g.branch(g.get(STALK_CHARGING_VAR, x0 + 480, y0 + 160), exec_in,
                        x0 + 760, y0)
    _connect(BEL.find_then_pin(charging), result(False, x0 + 1060, y0 - 200))

    # --- the roar ------------------------------------------------------------
    unroared = g.op(FN_LE_FF, g.get(STALK_ROAR_UNTIL_VAR, x0 + 760, y0 + 300), 0.0,
                    x0 + 1000, y0 + 300)
    first = g.branch(unroared, BEL.find_else_pin(charging), x0 + 1260, y0)
    _connect(_author_roar(g, BEL.find_then_pin(first), pins, roar_anim,
                          x0 + 1600, y0 - 1400),
             result(True, x0 + 7600, y0 - 1400))
    during = g.op(FN_LT_FF, pins["now"],
                  g.get(STALK_ROAR_UNTIL_VAR, x0 + 1260, y0 + 440), x0 + 1500, y0 + 300)
    roaring = g.branch(during, BEL.find_else_pin(first), x0 + 1760, y0)
    _connect(BEL.find_then_pin(roaring), result(True, x0 + 2060, y0 - 200))

    # --- close enough: charge ------------------------------------------------
    inside = g.op(FN_LE_FF, pins["gap"], NPC_STALK_CHARGE_CM, x0 + 2000, y0 + 300)
    close = g.branch(inside, BEL.find_else_pin(roaring), x0 + 2260, y0)
    charge = [BEL.find_then_pin(close)]

    # --- a leg under way, or a new one ---------------------------------------
    before = g.op(FN_LT_FF, pins["now"],
                  g.get(STALK_LEG_UNTIL_VAR, x0 + 2260, y0 + 440), x0 + 2500, y0 + 300)
    on_leg = g.branch(before, BEL.find_else_pin(close), x0 + 2760, y0)
    charge.append(_author_leg(g, BEL.find_then_pin(on_leg), pins, stock, result,
                              x0 + 3200, y0 + 1200))
    cover, picked, lost = _author_cover(ed, BEL.find_else_pin(on_leg), pins,
                                        x0 + 3200, y0 + 4200)
    # Close enough, standing still on a leg, or nowhere to go: all one charge.
    _connect(g.put(STALK_CHARGING_VAR, charge + [lost], x0 + 2560, y0 - 200,
                   literal="true"), result(False, x0 + 2860, y0 - 200))
    ahead, step = _author_facing(ed, picked, None, x0 + 9000, y0 + 4200)
    me = g.call(FN_GET_CONTROLLER, x0 + 10400, y0 + 4500)
    _connect(pins["self_pawn"], _pin(me, "self"))
    run = g.call(FN_SIMPLE_MOVE, x0 + 10700, y0 + 4200)
    _connect(out(me), _pin(run, "Controller"))
    _connect(g.get(STALK_COVER_VAR, x0 + 10400, y0 + 4660), _pin(run, "Goal"))
    _connect(step, _pin(run, "execute"))
    ran, tails, _entry = _author_walk_speed(ed, [BEL.find_then_pin(run)], False, stock,
                                            x0 + 11000, y0 + 4200)
    for tail in tails:
        _connect(tail, result(True, x0 + 12500, y0 + 4200))
    return g.made, cover + ahead + ran
