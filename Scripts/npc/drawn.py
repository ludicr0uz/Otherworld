"""A fire draws a zombie: the Drawn step, the state between patrol and hunt.
The numbers are forest_generator/npc_drawn.py's; the step sits in the tree
after the senses and ahead of the stroll (npc/tree.py), so it runs only for
a wanderer that has not noticed the player.

    BT_Drawn (behind the alive gate)
      -> the campfires burning in the level (GetAllActorsOfClass)
      -> DrawnTo = the nearest of them to the pawn
      -> [DrawnTo is valid?]                     no: Drawn = false, fail
      -> [within NPC_DRAWN_RANGE_CM, flat?]      no: Drawn = false, fail
      -> Drawn = true
      -> [further than NPC_DRAWN_ARRIVE_CM?]
           yes: SimpleMoveToLocation(the fire) -> the patrol walk -> succeed
           no:  StopMovement -> succeed          (it stands by the fire)

A pass that succeeds has given its own order, so the Stroll is not reached;
a pass that fails falls through to it, and the zombie patrols as before.
The fire is looked for on every pass rather than told to the zombies when it
is lit: the controllers are separate Blueprints, so a campfire would need a
cast per creature, and a fire that burns out (its actor is destroyed) lets
go of them the same way, with nothing to clear.

FindNearestActor is pure, so its actor is read once, into DrawnTo, and the
Branches read the variable. The range Branch is nested behind the validity
one: its condition reads the fire's location.

The walk is patrol._author_walk_speed's stroll (RunSpeed x TuneRunSpeed /
stock x TunePatrolSpeed), written after the order on every pass, like the
Stroll step's: "slowly" is the patrol walk, and tuning that tunes this.
"""

import unreal

from forest_generator.npc_drawn import (
    NPC_DRAWN_ARRIVE_CM, NPC_DRAWN_BY_FIRE, NPC_DRAWN_RANGE_CM,
)
from npc.graph import BEL, _Graph, _asset_sub, _connect, _log, _pin, out
from npc.nodes import (
    FN_ACTOR_LOC, FN_ALL_ACTORS, FN_DISTANCE_2D, FN_GET_CONTROLLER, FN_GET_PAWN,
    FN_GT_FF, FN_IS_VALID, FN_LE_FF, FN_NEAREST_ACTOR, FN_SIMPLE_MOVE,
    FN_STOP_MOVEMENT,
)
from npc.patrol import _author_walk_speed
from npc.paths import DRAWN_TO_VAR, DRAWN_VAR
from survival.paths import CAMPFIRE_BP_PATH, CAMPFIRE_CLASS_PATH


def draws(key):
    """Does creature ``key`` get the step? A fire has to draw it, and there
    has to be a campfire to look for: a project whose survival assets were
    never built has zombies that take no notice, and a log line saying why."""
    if key not in NPC_DRAWN_BY_FIRE:
        return False
    if _asset_sub().does_asset_exist(CAMPFIRE_BP_PATH):
        return True
    _log(f"note: {CAMPFIRE_BP_PATH} does not exist -- run build_survival.py "
         f"first. {key} is not drawn to a fire.")
    return False


def declare_drawn_vars(ed):
    """False and none by default: nothing draws it yet."""
    kinds = {
        DRAWN_VAR: BEL.get_basic_type_by_name("bool"),
        DRAWN_TO_VAR: BEL.get_object_reference_type(unreal.Actor.static_class()),
    }
    for name, kind in kinds.items():
        ed.remove_member_variable(name)
        if not ed.add_member_variable(name, kind):
            raise RuntimeError(f"could not declare {name}")


def _author_drawn(ed, exec_in, result, stock, x0, y0):
    """The Drawn step, off ``exec_in`` (the event, behind its alive gate).
    ``result(value, x, y)`` makes a StepResult write and returns its exec
    input; ``stock`` is the creature's built run speed. Returns the nodes
    made, for the comment box."""
    g = _Graph(ed)
    pawn = out(g.call(FN_GET_PAWN, x0, y0 + 300))
    here = g.call(FN_ACTOR_LOC, x0 + 240, y0 + 300)
    _connect(pawn, _pin(here, "self"))

    fires = g.call(FN_ALL_ACTORS, x0 + 480, y0, ActorClass=CAMPFIRE_CLASS_PATH)
    _connect(exec_in, _pin(fires, "execute"))
    nearest = g.call(FN_NEAREST_ACTOR, x0 + 760, y0 + 300)
    _connect(out(here), _pin(nearest, "Origin"))
    _connect(out(fires, "OutActors"), _pin(nearest, "ActorsToCheck"))
    kept = g.put(DRAWN_TO_VAR, BEL.find_then_pin(fires), x0 + 1040, y0,
                 pin=out(nearest))

    fire = g.get(DRAWN_TO_VAR, x0 + 1040, y0 + 300)
    lit = g.call(FN_IS_VALID, x0 + 1280, y0 + 300)
    _connect(fire, _pin(lit, "Object"))
    burning = g.branch(out(lit), kept, x0 + 1520, y0)

    there = g.call(FN_ACTOR_LOC, x0 + 1520, y0 + 440)
    _connect(fire, _pin(there, "self"))
    gap = g.call(FN_DISTANCE_2D, x0 + 1760, y0 + 300)
    _connect(out(here), _pin(gap, "V1"))
    _connect(out(there), _pin(gap, "V2"))
    near = g.op(FN_LE_FF, out(gap), NPC_DRAWN_RANGE_CM, x0 + 2000, y0 + 300)
    reached = g.branch(near, BEL.find_then_pin(burning), x0 + 2240, y0)

    let_go = g.put(DRAWN_VAR,
                   [BEL.find_else_pin(burning), BEL.find_else_pin(reached)],
                   x0 + 2480, y0 + 700, literal="false")
    _connect(let_go, result(False, x0 + 2760, y0 + 700))

    drawn = g.put(DRAWN_VAR, BEL.find_then_pin(reached), x0 + 2480, y0,
                  literal="true")
    far = g.op(FN_GT_FF, out(gap), NPC_DRAWN_ARRIVE_CM, x0 + 2480, y0 + 300)
    walking = g.branch(far, drawn, x0 + 2760, y0)

    me = g.call(FN_GET_CONTROLLER, x0 + 2760, y0 + 440)
    _connect(pawn, _pin(me, "self"))
    go = g.call(FN_SIMPLE_MOVE, x0 + 3040, y0)
    _connect(out(me), _pin(go, "Controller"))
    _connect(out(there), _pin(go, "Goal"))
    _connect(BEL.find_then_pin(walking), _pin(go, "execute"))
    walked, tails, _entry = _author_walk_speed(
        ed, [BEL.find_then_pin(go)], True, stock, x0 + 3320, y0)

    stand = g.call(FN_STOP_MOVEMENT, x0 + 3040, y0 + 700)
    _connect(BEL.find_else_pin(walking), _pin(stand, "execute"))

    done = result(True, x0 + 4900, y0)
    for tail in tails + [BEL.find_then_pin(stand)]:
        _connect(tail, done)
    return g.made + walked
