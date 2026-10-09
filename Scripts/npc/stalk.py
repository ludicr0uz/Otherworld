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
              StalkTurnAt = the roar's end + 4-9 s,
              StalkOrigin = where the player stands
              stop, face the player, play the roar clip and a voice    succeed
       -> [now < StalkRoarUntil?]  still roaring                       succeed
       -> [player further than TuneStalkFled from StalkOrigin?]  they
              have run off: StalkCharging = true, one
              of its voices                            fail: Chase runs
       -> [player further off than the catch-up range?]
              StalkLegUntil = 0 (no leg: a pick, once it is inside)
              face the way it runs -> SimpleMoveToLocation(the player's
              spot) -> the leg speed                                   succeed
       -> [player within the charge range?]
              StalkCharging = true, one of its voices  fail: Chase runs
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

A leg is run faster than the chase (TuneStalkSpeed of the run speed);
the Chase step writes the run speed back on its first pass, so the charge is
at the run. The charge range, the catch-up range, the leg speed, the wait
behind a trunk, how far the player may run and the time between two turns are the controller's
TuneStalk* variables (npc/tuned.py: the MONSTER SETTINGS tab's "hunt:" rows),
defaulted to npc_stalk.py's numbers. Enraged is its own latch, apart from StalkCharging, which a
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

from uebp.vars import declare
from npc import controller_vars as NV

from forest_generator.npc_stalk import (
    NPC_STALK_ARRIVE_CM, NPC_STALK_OPEN_ARRIVE_CM, NPC_STALK_ROAR_S,
    NPC_STALK_STALLED_CMS,
)
from npc.graph import _Graph
from net.players import nearest_living_player, player_pin
from uebp.graph import _connect, _pin, else_, out, then
from npc.paths import (
    ENRAGED_VAR, STALK_ARRIVED_VAR,
    STALK_CHARGING_VAR, STALK_COVER_VAR, STALK_HIDDEN_VAR, STALK_LEG_UNTIL_VAR,
    STALK_ORIGIN_VAR, STALK_ROAR_UNTIL_VAR, STALK_SIDE_VAR, STALK_TURN_AT_VAR, VOICES_VAR,
)
from npc.patrol import _author_walk_speed
from npc.roar import _author_bellow
from npc.senses import _author_hurt
from Sound.play import _author_random_sound
from npc.stalk_cover import _author_cover, declare_cover_vars
from npc.strafe import _author_facing
from npc.tuned import tuned_pin
from uebp.nodes.actor import FN_ACTOR_LOC, FN_GET_CONTROLLER, FN_GET_PAWN, FN_VELOCITY
from uebp.nodes.ai import FN_SIMPLE_MOVE
from uebp.nodes.math import (
    FN_ADD_FF, FN_DISTANCE_2D, FN_GREATER_FF, FN_LESS_FF, FN_LE_FF, FN_MUL_FF,
    FN_RANDOM_BOOL, FN_RANDOM_FLOAT, FN_SELECT_FF, FN_VSIZE_XY)
from uebp.nodes.system import FN_TIME_SECONDS


def declare_stalk_vars(ed):
    """All zero/false by default: not roared, no leg, not charging, not
    enraged."""
    declare(ed, NV.STALK)
    declare_cover_vars(ed)


def _author_rage(g, exec_in, pins, result):
    """The head of the step: a wendigo the player has hurt does not hunt.
    Returns the exec pins of one that is not enraged, for the hunt."""
    raged = g.branch(g.get(ENRAGED_VAR), exec_in)
    _connect(then(raged), result(False))
    # The hurt sense's own read (BP_HealthComponent.DamagedByPlayer): what
    # woke it is what enrages it, so a shot from any range does both.
    read, shot, unhurt = _author_hurt(g.ed, [else_(raged)])
    g.made.extend(read)
    step = g.put(ENRAGED_VAR, shot, literal="true")
    sound, step = _author_random_sound(g.ed, VOICES_VAR, pins["self_loc"], step)
    g.made.extend(sound)
    _connect(step, result(False))
    return unhurt


def _author_turn_time(g, exec_in, since):
    """StalkTurnAt = ``since`` (a game time pin) + one throw of the time
    between two turns. Returns the Set's then pin."""
    throw = g.call(FN_RANDOM_FLOAT)
    _connect(tuned_pin(g, "stalk_turn_min_s"), _pin(throw, "Min"))
    _connect(tuned_pin(g, "stalk_turn_max_s"), _pin(throw, "Max"))
    due = g.op(FN_ADD_FF, since, out(throw))
    return g.put(STALK_TURN_AT_VAR, exec_in, pin=due)


def _author_turn(g, exec_in, pins):
    """The head of a new leg: once the time is up, the other way round.
    Returns the exec pins the pick carries on from."""
    up = g.op(FN_LE_FF, g.get(STALK_TURN_AT_VAR), pins["now"])
    due = g.branch(up, exec_in)
    about = g.op(FN_MUL_FF, g.get(STALK_SIDE_VAR), -1.0)
    step = g.put(STALK_SIDE_VAR, then(due), pin=about)
    step = _author_turn_time(g, step, pins["now"])
    return [step, else_(due)]


def _author_roar(g, exec_in, pins, roar_anim):
    """The first pass of the hunt. Returns the exec pin it ends on."""
    ends = g.op(FN_ADD_FF, pins["now"], NPC_STALK_ROAR_S)
    step = g.put(STALK_ROAR_UNTIL_VAR, exec_in, pin=ends)
    # One throw for the whole hunt: a new leg turns it about, never throws again.
    side = g.call(FN_SELECT_FF, A=1.0, B=-1.0)
    _connect(out(g.call(FN_RANDOM_BOOL)), _pin(side, "bPickA"))
    step = g.put(STALK_SIDE_VAR, step, pin=out(side))
    step = _author_turn_time(g, step, ends)
    # Where the player is hunted from: one who runs far from it is charged.
    step = g.put(STALK_ORIGIN_VAR, step, pin=pins["player_loc"])

    return _author_bellow(g, step, pins, roar_anim)


def _author_fled(g, exec_in, pins):
    """The player has run off from where they stood at the roar: no more
    trees. Returns ``(fled, stayed)``: the exec pin of a pass that charges,
    for the caller, and that of one whose player is still there."""
    run = g.call(FN_DISTANCE_2D)
    _connect(pins["player_loc"], _pin(run, "V1"))
    _connect(g.get(STALK_ORIGIN_VAR), _pin(run, "V2"))
    off = g.op(FN_GREATER_FF, out(run), tuned_pin(g, "stalk_fled_cm"))
    fled = g.branch(off, exec_in)
    return then(fled), else_(fled)


def _author_catch_up(g, exec_in, pins, stock, result):
    """Too far off to stalk: straight at the player, at the speed of a leg.
    Returns the exec pin of a pass that is near enough to hunt."""
    beyond = g.op(FN_GREATER_FF, pins["gap"], tuned_pin(g, "stalk_catch_up_cm"))
    far = g.branch(beyond, exec_in)
    # No leg is under way: the first pass inside the range picks one.
    step = g.put(STALK_LEG_UNTIL_VAR, then(far), literal=0.0)
    ahead, step = _author_facing(g.ed, [step], None)
    g.made.extend(ahead)
    me = g.call(FN_GET_CONTROLLER)
    _connect(pins["self_pawn"], _pin(me, "self"))
    run = g.call(FN_SIMPLE_MOVE)
    _connect(out(me), _pin(run, "Controller"))
    _connect(pins["player_loc"], _pin(run, "Goal"))
    _connect(step, _pin(run, "execute"))
    ran, tails, _entry = _author_walk_speed(g.ed, [then(run)], False,
                                            stock,
                                            scale="stalk_run_scale")
    g.made.extend(ran)
    for tail in tails:
        _connect(tail, result(True))
    return else_(far)


def _author_leg(g, exec_in, pins, stock, result):
    """A leg under way: wait behind the trunk, arrive, or run on. Every arm
    ends on a StepResult write of its own, but the two returned,
    ``(stalled, onward)``: the exec pin of a wendigo that is not moving, for
    the caller to charge on, and that of one near the end of a leg in the
    open, for the caller to pick the next on -- it does not stop there."""
    hiding = g.branch(g.get(STALK_ARRIVED_VAR), exec_in)
    _connect(then(hiding), result(True))

    left = g.call(FN_DISTANCE_2D)
    _connect(pins["self_loc"], _pin(left, "V1"))
    _connect(g.get(STALK_COVER_VAR), _pin(left, "V2"))
    # A leg in the open is over a pass's run short of its spot: the next is
    # picked while it still runs.
    reach = g.call(FN_SELECT_FF, A=NPC_STALK_ARRIVE_CM, B=NPC_STALK_OPEN_ARRIVE_CM)
    _connect(g.get(STALK_HIDDEN_VAR), _pin(reach, "bPickA"))
    close = g.op(FN_LE_FF, out(left), out(reach))
    there = g.branch(close, else_(hiding))
    covered = g.branch(g.get(STALK_HIDDEN_VAR), then(there))

    # --- arrived: wait behind the trunk, watching the player -----------------
    step = g.put(STALK_ARRIVED_VAR, then(covered), literal="true")
    # One throw per leg.
    wait = g.call(FN_RANDOM_FLOAT)
    _connect(tuned_pin(g, "stalk_hide_min_s"), _pin(wait, "Min"))
    _connect(tuned_pin(g, "stalk_hide_max_s"), _pin(wait, "Max"))
    until = g.op(FN_ADD_FF, pins["now"], out(wait))
    step = g.put(STALK_LEG_UNTIL_VAR, step, pin=until)
    watch, step = _author_facing(g.ed, [step], pins["player"])
    g.made.extend(watch)
    _connect(step, result(True))

    # --- not there: stalled (no path to the spot), or still running. The pass
    # after a move order is half a second later, by when it is at speed. ------
    pace = g.call(FN_VSIZE_XY)
    moving = g.call(FN_VELOCITY)
    _connect(pins["self_pawn"], _pin(moving, "self"))
    _connect(out(moving), _pin(pace, "A"))
    slow = g.op(FN_LESS_FF, out(pace), NPC_STALK_STALLED_CMS)
    stalled = g.branch(slow, else_(there))
    ran, tails, _entry = _author_walk_speed(g.ed, [else_(stalled)], False,
                                            stock,
                                            scale="stalk_run_scale")
    g.made.extend(ran)
    for tail in tails:
        _connect(tail, result(True))
    return then(stalled), else_(covered)


def _author_stalk(ed, exec_in, result, roar_anim, stock):
    """Author BT_Stalk. ``exec_in`` is the step's exec pin (behind the alive
    gate), ``result(value)`` makes a StepResult write and returns its
    exec input, ``roar_anim`` is roar_object()'s answer and ``stock`` the
    creature's built run speed (patrol._author_walk_speed).

    Returns ``(step_nodes, cover_nodes)``, for two comment boxes.
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
    now = g.call(FN_TIME_SECONDS)
    pins = dict(self_pawn=out(self_pawn), self_loc=out(self_loc), player=player_pin(player),
                player_loc=out(player_loc), gap=out(gap), now=out(now))

    # --- hurt by the player: no hunt, now or ever -----------------------------
    calm = _author_rage(g, exec_in, pins, result)

    # --- the charge: this step is over, for good -----------------------------
    charging = g.branch(g.get(STALK_CHARGING_VAR), calm)
    _connect(then(charging), result(False))

    # --- the roar ------------------------------------------------------------
    unroared = g.op(FN_LE_FF, g.get(STALK_ROAR_UNTIL_VAR), 0.0)
    first = g.branch(unroared, else_(charging))
    _connect(_author_roar(g, then(first), pins, roar_anim), result(True))
    during = g.op(FN_LESS_FF, pins["now"], g.get(STALK_ROAR_UNTIL_VAR))
    roaring = g.branch(during, else_(first))
    _connect(then(roaring), result(True))

    # --- the player has run off: charge ---------------------------------------
    fled, stayed = _author_fled(g, else_(roaring), pins)

    # --- close enough: charge ------------------------------------------------
    near = _author_catch_up(g, stayed, pins, stock, result)
    inside = g.op(FN_LE_FF, pins["gap"], tuned_pin(g, "stalk_charge_cm"))
    close = g.branch(inside, near)
    charge = [fled, then(close)]

    # --- a leg under way, or a new one ---------------------------------------
    before = g.op(FN_LESS_FF, pins["now"], g.get(STALK_LEG_UNTIL_VAR))
    on_leg = g.branch(before, else_(close))
    stalled, onward = _author_leg(g, then(on_leg), pins, stock, result)
    charge.append(stalled)
    cover, picked, lost = _author_cover(ed, _author_turn(g, [else_(on_leg), onward], pins), pins)
    # The player gone, close enough, standing still on a leg, or nowhere to
    # go: all one charge.
    step = g.put(STALK_CHARGING_VAR, charge + [lost], literal="true")
    # It roars as it breaks into the charge: the voice alone, no clip and no
    # stand, so the pass still fails and Chase gives its order at once.
    sound, step = _author_random_sound(g.ed, VOICES_VAR, pins["self_loc"], step)
    g.made.extend(sound)
    _connect(step, result(False))
    ahead, step = _author_facing(ed, picked, None)
    me = g.call(FN_GET_CONTROLLER)
    _connect(pins["self_pawn"], _pin(me, "self"))
    run = g.call(FN_SIMPLE_MOVE)
    _connect(out(me), _pin(run, "Controller"))
    _connect(g.get(STALK_COVER_VAR), _pin(run, "Goal"))
    _connect(step, _pin(run, "execute"))
    ran, tails, _entry = _author_walk_speed(ed, [then(run)], False, stock, scale="stalk_run_scale")
    for tail in tails:
        _connect(tail, result(True))
    return g.made, cover + ahead + ran
