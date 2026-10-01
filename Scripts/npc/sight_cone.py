"""Debug mode's sight cone: each live wanderer draws what its sight tests.

    [Tick] --> [GameMode.DebugMode?] --> [pawn valid?] --> [not a corpse?]
           --> DrawDebugCone(pawn location, pawn forward,
                             TuneSightRange, TuneSightHalfAngle either side,
                             aggro colour : patrol colour)
           --> SightConeDrawnAt = now

The cone is the sight sense's own volume (senses._author_sight): the same
origin, the same forward vector, and the same two Tune variables, so the MONSTER
TUNING tab moves the drawn cone and the sense together. It is a full cone,
not a fan on the ground, because the test is a dot product in three
dimensions. What it cannot show is the third condition, line of sight: a
player inside the cone and behind a trunk is still unseen.

On the controller's Tick rather than in a tree step: the steps run on the
tree's half-second beat, and a cone drawn that seldom lags the body it is
attached to. Drawn for one frame (Duration 0) and redrawn the next.
"""

from combat.game_state import DEBUG_MODE_VAR
from combat.paths import GAME_MODE_CLASS_PATH
from npc.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set
from npc.nodes import (
    FN_ACTOR_LOC, FN_DRAW_CONE, FN_FORWARD, FN_GET_GAME_MODE, FN_GET_PAWN,
    FN_IS_VALID, FN_SELECT_COLOR, FN_TIME_SECONDS, NODE_CAST_GAME_MODE,
    NODE_EVENT_TICK,
)
from npc.paths import (
    AGGRO_VAR, CORPSE_VAR, SIGHT_CONE_AGGRO_COLOR, SIGHT_CONE_PATROL_COLOR,
    SIGHT_CONE_SIDES, SIGHT_CONE_STAMP_VAR, SIGHT_CONE_THICKNESS,
)
from npc.tuned import tuned


def _author_sight_cone(ed, x0, y0):
    """Author the Tick that draws this wanderer's sight cone in debug mode.

    Needs the Tune*, Aggro and Corpse variables declared (npc/steps.py).
    Returns the nodes it made.
    """
    ed.remove_member_variable(SIGHT_CONE_STAMP_VAR)
    if not ed.add_member_variable(SIGHT_CONE_STAMP_VAR,
                                  BEL.get_basic_type_by_name("real")):
        raise RuntimeError(f"could not declare {SIGHT_CONE_STAMP_VAR}")
    made = []

    def keep(n, x, y):
        made.append(_at(n, x, y))
        return n

    def out(n, name="ReturnValue"):
        return _pin(n, name, is_input=False)

    def branch(condition, exec_in, x, y):
        b = keep(ed.add_branch_node(), x, y)
        _connect(condition, _pin(b, "Condition"))
        _connect(exec_in, _pin(b, "execute"))
        return b

    def get(name, x, y):
        return out(keep(ed.add_get_member_variable_node(name), x, y), name)

    tick = keep(_palette(ed, NODE_EVENT_TICK), x0, y0)
    # The flag first: with debug mode off, which is how the game is played,
    # a wanderer's Tick costs one cast and one branch.
    mode = keep(_node(ed, FN_GET_GAME_MODE), x0, y0 + 300)
    as_mode = keep(_palette(ed, NODE_CAST_GAME_MODE), x0 + 260, y0)
    _connect(out(mode), _pin(as_mode, "Object"))
    _connect(BEL.find_then_pin(tick), _pin(as_mode, "execute"))
    flag = keep(ed.add_get_member_variable_node(DEBUG_MODE_VAR, GAME_MODE_CLASS_PATH),
                x0 + 520, y0 + 300)
    _connect(_loose_pin(as_mode, "AsBPThirdPersonGameMode", is_input=False),
             _pin(flag, "self"))
    debugging = branch(out(flag, DEBUG_MODE_VAR), BEL.find_then_pin(as_mode),
                       x0 + 780, y0)

    # Nested, not ANDed: a Branch pulls its whole condition, and the cone's
    # inputs read the pawn (see the root CLAUDE.md, "Evaluation order").
    pawn = keep(_node(ed, FN_GET_PAWN), x0 + 780, y0 + 300)
    valid = keep(_node(ed, FN_IS_VALID), x0 + 1020, y0 + 300)
    _connect(out(pawn), _pin(valid, "Object"))
    bodied = branch(out(valid), BEL.find_then_pin(debugging), x0 + 1260, y0)
    dead = branch(get(CORPSE_VAR, x0 + 1260, y0 + 300), BEL.find_then_pin(bodied),
                  x0 + 1500, y0)

    here = keep(_node(ed, FN_ACTOR_LOC), x0 + 1500, y0 + 300)
    _connect(out(pawn), _pin(here, "self"))
    facing = keep(_node(ed, FN_FORWARD), x0 + 1500, y0 + 440)
    _connect(out(pawn), _pin(facing, "self"))
    colour = keep(_node(ed, FN_SELECT_COLOR), x0 + 1500, y0 + 860)
    _set(colour, "A", SIGHT_CONE_AGGRO_COLOR)
    _set(colour, "B", SIGHT_CONE_PATROL_COLOR)
    _connect(get(AGGRO_VAR, x0 + 1260, y0 + 860), _pin(colour, "bPickA"))

    cone = keep(_node(ed, FN_DRAW_CONE), x0 + 1800, y0)
    _connect(out(here), _pin(cone, "Origin"))
    _connect(out(facing), _pin(cone, "Direction"))
    reach_n, reach = tuned(ed, "vision_range_cm", x0 + 1500, y0 + 580)
    half_n, half = tuned(ed, "vision_half_angle_deg", x0 + 1500, y0 + 700)
    made.extend((reach_n, half_n))
    _connect(reach, _pin(cone, "Length"))
    _connect(half, _pin(cone, "AngleWidth"))
    _connect(half, _pin(cone, "AngleHeight"))
    _set(cone, "NumSides", SIGHT_CONE_SIDES)
    _connect(out(colour), _pin(cone, "LineColor"))
    _set(cone, "Duration", 0.0)
    _set(cone, "Thickness", SIGHT_CONE_THICKNESS)
    _connect(BEL.find_else_pin(dead), _pin(cone, "execute"))

    now = keep(_node(ed, FN_TIME_SECONDS), x0 + 1800, y0 + 500)
    stamp = keep(ed.add_set_member_variable_node(SIGHT_CONE_STAMP_VAR), x0 + 2200, y0)
    _connect(out(now), _pin(stamp, SIGHT_CONE_STAMP_VAR))
    _connect(BEL.find_then_pin(cone), _pin(stamp, "execute"))

    ed.add_comment_to_nodes(
        "Debug mode only: this wanderer's sight cone, redrawn every frame from "
        "the numbers its sight sense reads (TuneSightRange long, TuneSightHalfAngle "
        "either side of the way it faces). Yellow while it patrols, red once "
        "it hunts. Line of sight is not shown: a trunk still hides the player.",
        made)
    return made
