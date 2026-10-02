"""A wendigo's hunt: the tree's Stalk step (BT_Stalk), tried before Chase
while the wanderer is aggro. It roars, comes in round the player from tree to
tree, and then stops answering, which hands the hunt to the Chase step: the
charge. The numbers are forest_generator/npc_stalk.py's.

    BT_Stalk -> [Enraged?]                             fail: Chase runs
       -> [the player has hurt it?]  (the hurt sense's own read)
              Enraged = true, one of its voices        fail: Chase runs
       -> [StalkCharging?]                             fail: Chase runs
       -> [StalkRoarUntil is 0?]  the first pass:
              StalkRoarUntil = now + the roar, StalkSide = +1 or -1,
              StalkTurnAt = the roar's end + 4-9 s
              stop, face the player, play the roar clip and a voice    succeed
       -> [now < StalkRoarUntil?]  still roaring                       succeed
       -> [player further off than the catch-up range?]
              StalkLegUntil = 0 (no leg: a pick, once it is inside)
              face the way it runs -> SimpleMoveToLocation(the player's
              spot) -> the leg speed                                   succeed
       -> [player within the charge range?]
              StalkCharging = true                     fail: Chase runs
              (so do a leg it is standing still on, and a pick with nowhere
              to go: it charges rather than stand)
       -> [now < StalkLegUntil?]  a leg is under way
              [StalkArrived?]  waiting behind the trunk                succeed
              [within reach of StalkCover? (in the open: a pass's run
               short of it)]
                  [StalkHidden?] no: a new leg, now -- it runs on
                  StalkArrived = true, StalkLegUntil = now + the wait,
                  face the player                                      succeed
              [standing still?]  no path: charge, as above
              the leg speed                                            succeed
       -> a new leg: [StalkTurnAt <= now?] StalkSide = -StalkSide,
                                           StalkTurnAt = now + 4-9 s
          the next tree (stalk_cover.py); none, and no open
          ground either: charge, as above
              face the way it runs -> SimpleMoveToLocation(StalkCover)
              -> the leg speed                                         succeed

A leg is run faster than the chase (NPC_STALK_RUN_SCALE of the run speed);
the Chase step writes the run speed back on its first pass, so the charge is
at the run. Enraged is its own latch, apart from StalkCharging, which a
flight from fire clears (npc/ward.py): a wendigo that has been shot comes
back from one charging, not hunting.

Only the creatures of NPC_STALK_ROAR get the step, its variables and its
node in their tree (npc/tree.py); the others chase as before.

A pass that succeeds has given its own move order, so the tree's selector
does not go on to Chase; the Swing step after it still runs, and still
checks its own range. Every value that could differ between two reads is
stored: the side is one throw per hunt (turned about, not thrown again), the
time to the next turn one throw per turn, the wait one throw per leg.

SimpleMoveToLocation, as the stroll and the strafe are: the level verifier
counts the chase's MoveToActor and MoveToLocation, one of each.
"""

from forest_generator.npc_stalk import (
    NPC_STALK_ARRIVE_CM, NPC_STALK_CATCH_UP_CM, NPC_STALK_CHARGE_CM,
    NPC_STALK_HIDE_MAX_S, NPC_STALK_HIDE_MIN_S, NPC_STALK_OPEN_ARRIVE_CM,
    NPC_STALK_ROAR_BLEND_S, NPC_STALK_ROAR_S,
    NPC_STALK_RUN_SCALE, NPC_STALK_STALLED_CMS, NPC_STALK_TURN_MAX_S,
    NPC_STALK_TURN_MIN_S,
)
from npc.graph import (
    BEL, _Graph, _asset_sub, _connect, _log, _loose_pin, _mesh_object, _palette,
    _pin, out,
)
from npc.nodes import (
    FN_ACTOR_LOC, FN_ADD_FF, FN_ANIM_INSTANCE, FN_DISTANCE_2D,
    FN_GET_CONTROLLER, FN_GET_PAWN, FN_GET_PLAYER_PAWN, FN_GT_FF, FN_LE_FF,
    FN_LT_FF,
    FN_MUL_FF, FN_PLAY_SLOT, FN_RANDOM_BOOL, FN_RANDOM_FLOAT, FN_SELECT_FLOAT,
    FN_SIMPLE_MOVE, FN_STOP_MOVEMENT, FN_TIME_SECONDS, FN_VELOCITY, FN_VSIZE_XY,
    NODE_CAST_CHARACTER,
)
from npc.paths import (
    CHARACTER_CLASS_PATH, ENRAGED_VAR, MELEE_SLOT, STALK_ARRIVED_VAR,
    STALK_CHARGING_VAR, STALK_COVER_VAR, STALK_HIDDEN_VAR, STALK_LEG_UNTIL_VAR,
    STALK_ROAR_UNTIL_VAR, STALK_SIDE_VAR, STALK_TURN_AT_VAR, VOICES_VAR,
)
from npc.patrol import _author_walk_speed
from npc.senses import _author_hurt
from npc.sound import _author_random_sound
from npc.stalk_cover import _author_cover, declare_cover_vars
from npc.strafe import _author_facing


def declare_stalk_vars(ed):
    """All zero/false by default: not roared, no leg, not charging, not
    enraged."""
    for name, kind in ((STALK_ROAR_UNTIL_VAR, "real"), (STALK_SIDE_VAR, "real"),
                       (STALK_TURN_AT_VAR, "real"), (STALK_CHARGING_VAR, "bool"),
                       (ENRAGED_VAR, "bool")):
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


def _author_rage(g, exec_in, pins, result, x0, y0):
    """The head of the step: a wendigo the player has hurt does not hunt.
    Returns the exec pins of one that is not enraged, for the hunt."""
    raged = g.branch(g.get(ENRAGED_VAR, x0 - 240, y0 + 200), exec_in, x0, y0)
    _connect(BEL.find_then_pin(raged), result(False, x0 + 300, y0 - 200))
    # The hurt sense's own read (BP_HealthComponent.DamagedByPlayer): what
    # woke it is what enrages it, so a shot from any range does both.
    read, shot, unhurt = _author_hurt(g.ed, [BEL.find_else_pin(raged)],
                                      x0 + 300, y0)
    g.made.extend(read)
    step = g.put(ENRAGED_VAR, shot, x0 + 1600, y0, literal="true")
    sound, step = _author_random_sound(g.ed, VOICES_VAR, pins["self_loc"], step,
                                       x0 + 1900, y0)
    g.made.extend(sound)
    _connect(step, result(False, x0 + 3900, y0))
    return unhurt


def _author_turn_time(g, exec_in, since, x0, y0):
    """StalkTurnAt = ``since`` (a game time pin) + one throw of the time
    between two turns. Returns the Set's then pin."""
    throw = g.call(FN_RANDOM_FLOAT, x0, y0 + 460, Min=NPC_STALK_TURN_MIN_S,
                   Max=NPC_STALK_TURN_MAX_S)
    due = g.op(FN_ADD_FF, since, out(throw), x0 + 240, y0 + 300)
    return g.put(STALK_TURN_AT_VAR, exec_in, x0 + 480, y0, pin=due)


def _author_turn(g, exec_in, pins, x0, y0):
    """The head of a new leg: once the time is up, the other way round.
    Returns the exec pins the pick carries on from."""
    up = g.op(FN_LE_FF, g.get(STALK_TURN_AT_VAR, x0 - 240, y0 + 300), pins["now"],
              x0, y0 + 300)
    due = g.branch(up, exec_in, x0 + 260, y0)
    about = g.op(FN_MUL_FF, g.get(STALK_SIDE_VAR, x0 + 300, y0 + 300), -1.0,
                 x0 + 540, y0 + 300)
    step = g.put(STALK_SIDE_VAR, BEL.find_then_pin(due), x0 + 780, y0, pin=about)
    step = _author_turn_time(g, step, pins["now"], x0 + 1080, y0)
    return [step, BEL.find_else_pin(due)]


def _author_roar(g, exec_in, pins, roar_anim, x0, y0):
    """The first pass of the hunt. Returns the exec pin it ends on."""
    ends = g.op(FN_ADD_FF, pins["now"], NPC_STALK_ROAR_S, x0, y0 + 300)
    step = g.put(STALK_ROAR_UNTIL_VAR, exec_in, x0 + 240, y0, pin=ends)
    # One throw for the whole hunt: a new leg turns it about, never throws again.
    side = g.call(FN_SELECT_FLOAT, x0 + 300, y0 + 460, A=1.0, B=-1.0)
    _connect(out(g.call(FN_RANDOM_BOOL, x0 + 60, y0 + 460)), _pin(side, "bPickA"))
    step = g.put(STALK_SIDE_VAR, step, x0 + 540, y0, pin=out(side))
    step = _author_turn_time(g, step, ends, x0 - 900, y0 - 700)

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


def _author_catch_up(g, exec_in, pins, stock, result, x0, y0):
    """Too far off to stalk: straight at the player, at the speed of a leg.
    Returns the exec pin of a pass that is near enough to hunt."""
    beyond = g.op(FN_GT_FF, pins["gap"], NPC_STALK_CATCH_UP_CM, x0, y0 + 300)
    far = g.branch(beyond, exec_in, x0 + 260, y0)
    # No leg is under way: the first pass inside the range picks one.
    step = g.put(STALK_LEG_UNTIL_VAR, BEL.find_then_pin(far), x0 + 560, y0 - 900,
                 literal=0.0)
    ahead, step = _author_facing(g.ed, [step], None, x0 + 860, y0 - 900)
    g.made.extend(ahead)
    me = g.call(FN_GET_CONTROLLER, x0 + 2300, y0 - 600)
    _connect(pins["self_pawn"], _pin(me, "self"))
    run = g.call(FN_SIMPLE_MOVE, x0 + 2600, y0 - 900)
    _connect(out(me), _pin(run, "Controller"))
    _connect(pins["player_loc"], _pin(run, "Goal"))
    _connect(step, _pin(run, "execute"))
    ran, tails, _entry = _author_walk_speed(g.ed, [BEL.find_then_pin(run)], False,
                                            stock, x0 + 2900, y0 - 900,
                                            scale=NPC_STALK_RUN_SCALE)
    g.made.extend(ran)
    for tail in tails:
        _connect(tail, result(True, x0 + 4400, y0 - 900))
    return BEL.find_else_pin(far)


def _author_leg(g, exec_in, pins, stock, result, x0, y0):
    """A leg under way: wait behind the trunk, arrive, or run on. Every arm
    ends on a StepResult write of its own, but the two returned,
    ``(stalled, onward)``: the exec pin of a wendigo that is not moving, for
    the caller to charge on, and that of one near the end of a leg in the
    open, for the caller to pick the next on -- it does not stop there."""
    hiding = g.branch(g.get(STALK_ARRIVED_VAR, x0 - 240, y0 + 200), exec_in, x0, y0)
    _connect(BEL.find_then_pin(hiding), result(True, x0 + 300, y0 - 200))

    left = g.call(FN_DISTANCE_2D, x0 + 60, y0 + 400)
    _connect(pins["self_loc"], _pin(left, "V1"))
    _connect(g.get(STALK_COVER_VAR, x0 - 240, y0 + 460), _pin(left, "V2"))
    # A leg in the open is over a pass's run short of its spot: the next is
    # picked while it still runs.
    reach = g.call(FN_SELECT_FLOAT, x0 + 60, y0 + 620, A=NPC_STALK_ARRIVE_CM,
                   B=NPC_STALK_OPEN_ARRIVE_CM)
    _connect(g.get(STALK_HIDDEN_VAR, x0 - 240, y0 + 620), _pin(reach, "bPickA"))
    close = g.op(FN_LE_FF, out(left), out(reach), x0 + 300, y0 + 400)
    there = g.branch(close, BEL.find_else_pin(hiding), x0 + 560, y0)
    covered = g.branch(g.get(STALK_HIDDEN_VAR, x0 + 560, y0 + 240),
                       BEL.find_then_pin(there), x0 + 700, y0)

    # --- arrived: wait behind the trunk, watching the player -----------------
    step = g.put(STALK_ARRIVED_VAR, BEL.find_then_pin(covered), x0 + 960, y0,
                 literal="true")
    # One throw per leg.
    wait = g.call(FN_RANDOM_FLOAT, x0 + 900, y0 + 460, Min=NPC_STALK_HIDE_MIN_S,
                  Max=NPC_STALK_HIDE_MAX_S)
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
                                            stock, x0 + 1700, y0 + 1300,
                                            scale=NPC_STALK_RUN_SCALE)
    g.made.extend(ran)
    for tail in tails:
        _connect(tail, result(True, x0 + 3200, y0 + 1300))
    return BEL.find_then_pin(stalled), BEL.find_else_pin(covered)


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

    # --- hurt by the player: no hunt, now or ever -----------------------------
    calm = _author_rage(g, exec_in, pins, result, x0 - 400, y0 - 3200)

    # --- the charge: this step is over, for good -----------------------------
    charging = g.branch(g.get(STALK_CHARGING_VAR, x0 + 480, y0 + 160), calm,
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
    near = _author_catch_up(g, BEL.find_else_pin(roaring), pins, stock, result,
                            x0 + 1900, y0 - 2400)
    inside = g.op(FN_LE_FF, pins["gap"], NPC_STALK_CHARGE_CM, x0 + 2000, y0 + 300)
    close = g.branch(inside, near, x0 + 2260, y0)
    charge = [BEL.find_then_pin(close)]

    # --- a leg under way, or a new one ---------------------------------------
    before = g.op(FN_LT_FF, pins["now"],
                  g.get(STALK_LEG_UNTIL_VAR, x0 + 2260, y0 + 440), x0 + 2500, y0 + 300)
    on_leg = g.branch(before, BEL.find_else_pin(close), x0 + 2760, y0)
    stalled, onward = _author_leg(g, BEL.find_then_pin(on_leg), pins, stock, result,
                                  x0 + 3200, y0 + 1200)
    charge.append(stalled)
    cover, picked, lost = _author_cover(
        ed, _author_turn(g, [BEL.find_else_pin(on_leg), onward], pins,
                         x0 + 1200, y0 + 4200),
        pins, x0 + 3200, y0 + 4200)
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
                                            x0 + 11000, y0 + 4200,
                                            scale=NPC_STALK_RUN_SCALE)
    for tail in tails:
        _connect(tail, result(True, x0 + 12500, y0 + 4200))
    return g.made, cover + ahead + ran
