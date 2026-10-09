"""Debug mode's sight cone: each live wanderer draws what its sight tests.

    [Tick] --> [GameMode.DebugMode?] --> [pawn valid?] --> [not a corpse?]
           --> DrawDebugCone(pawn location, pawn forward,
                             TuneSightRange, TuneSightHalfAngle either side,
                             aggro colour : patrol colour)
           --> SightConeDrawnAt = now

The cone is the sight sense's own volume (senses._author_sight): the same
origin, the same forward vector, and the same two Tune variables, so the MONSTER
SETTINGS tab moves the drawn cone and the sense together. It is a full cone,
not a fan on the ground, because the test is a dot product in three
dimensions. What it cannot show is the third condition, line of sight: a
player inside the cone and behind a trunk is still unseen.

On the controller's Tick rather than in a tree step: the steps run on the
tree's half-second beat, and a cone drawn that seldom lags the body it is
attached to. Drawn for one frame (Duration 0) and redrawn the next.
"""

from uebp.vars import declare
from npc import controller_vars as NV
from combat.game_state import DEBUG_MODE_VAR
from net.state_consts import GAME_STATE_CLASS_PATH
from net.state_graph import game_state
from uebp.graph import _connect, _node, _palette, _pin, _set, else_, then
from npc.paths import (
    AGGRO_VAR, CORPSE_VAR, SIGHT_CONE_AGGRO_COLOR, SIGHT_CONE_PATROL_COLOR,
    SIGHT_CONE_SIDES, SIGHT_CONE_STAMP_VAR, SIGHT_CONE_THICKNESS,
)
from npc.tuned import tuned
from uebp.nodes.actor import FN_ACTOR_FORWARD, FN_ACTOR_LOC, FN_GET_PAWN
from uebp.nodes.math import FN_SELECT_COLOR
from uebp.nodes.palette import NODE_TICK
from uebp.nodes.system import FN_DRAW_CONE, FN_IS_VALID, FN_TIME_SECONDS


def _author_sight_cone(ed):
    """Author the Tick that draws this wanderer's sight cone in debug mode.

    Needs the Tune*, Aggro and Corpse variables declared (npc/steps.py).
    Returns the nodes it made.
    """
    declare(ed, NV.SIGHT_CONE)
    made = []

    def keep(n):
        made.append(n)
        return n

    def out(n, name="ReturnValue"):
        return _pin(n, name, is_input=False)

    def branch(condition, exec_in):
        b = keep(ed.add_branch_node())
        _connect(condition, _pin(b, "Condition"))
        _connect(exec_in, _pin(b, "execute"))
        return b

    def get(name):
        return out(keep(ed.add_get_member_variable_node(name)), name)

    tick = keep(_palette(ed, NODE_TICK))
    # The flag first: with debug mode off, which is how the game is played,
    # a wanderer's Tick costs one cast and one branch.
    state = game_state(ed, [then(tick)])
    for n in state.nodes:
        keep(n)
    flag = keep(ed.add_get_member_variable_node(DEBUG_MODE_VAR, GAME_STATE_CLASS_PATH))
    _connect(state.pin, _pin(flag, "self"))
    debugging = branch(out(flag, DEBUG_MODE_VAR), state.then)

    # Nested, not ANDed: a Branch pulls its whole condition, and the cone's
    # inputs read the pawn (see the root CLAUDE.md, "Evaluation order").
    pawn = keep(_node(ed, FN_GET_PAWN))
    valid = keep(_node(ed, FN_IS_VALID))
    _connect(out(pawn), _pin(valid, "Object"))
    bodied = branch(out(valid), then(debugging))
    dead = branch(get(CORPSE_VAR), then(bodied))

    here = keep(_node(ed, FN_ACTOR_LOC))
    _connect(out(pawn), _pin(here, "self"))
    facing = keep(_node(ed, FN_ACTOR_FORWARD))
    _connect(out(pawn), _pin(facing, "self"))
    colour = keep(_node(ed, FN_SELECT_COLOR))
    _set(colour, "A", SIGHT_CONE_AGGRO_COLOR)
    _set(colour, "B", SIGHT_CONE_PATROL_COLOR)
    _connect(get(AGGRO_VAR), _pin(colour, "bPickA"))

    cone = keep(_node(ed, FN_DRAW_CONE))
    _connect(out(here), _pin(cone, "Origin"))
    _connect(out(facing), _pin(cone, "Direction"))
    reach_n, reach = tuned(ed, "vision_range_cm")
    half_n, half = tuned(ed, "vision_half_angle_deg")
    made.extend((reach_n, half_n))
    _connect(reach, _pin(cone, "Length"))
    _connect(half, _pin(cone, "AngleWidth"))
    _connect(half, _pin(cone, "AngleHeight"))
    _set(cone, "NumSides", SIGHT_CONE_SIDES)
    _connect(out(colour), _pin(cone, "LineColor"))
    _set(cone, "Duration", 0.0)
    _set(cone, "Thickness", SIGHT_CONE_THICKNESS)
    _connect(else_(dead), _pin(cone, "execute"))

    now = keep(_node(ed, FN_TIME_SECONDS))
    stamp = keep(ed.add_set_member_variable_node(SIGHT_CONE_STAMP_VAR))
    _connect(out(now), _pin(stamp, SIGHT_CONE_STAMP_VAR))
    _connect(then(cone), _pin(stamp, "execute"))

    ed.add_comment_to_nodes(
        "Debug mode only: this wanderer's sight cone, redrawn every frame from "
        "the numbers its sight sense reads (TuneSightRange long, TuneSightHalfAngle "
        "either side of the way it faces). Yellow while it patrols, red once "
        "it hunts. Line of sight is not shown: a trunk still hides the player.",
        made)
    return made
