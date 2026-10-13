"""The crawl by direction (P2): the eight directions, the clip and the play
rate of each, the slide each leaves, and the weights the anim graph blends
them by. Numbers and plain Python, importable outside the editor.

WHERE THE DIRECTION COMES FROM
------------------------------
The pawn's velocity, turned into the body's own frame: how fast it goes
ahead and how fast across (crawl_direction.py, in the weapon layers' event
graph, beside GroundSpeed). Every machine has both: the owning client and the
server move the body, and another machine's copy is handed its velocity and
its rotation by the engine's replicated movement. So nothing new replicates
and no RPC says it.

The two speeds are eased (TURN_SPEED), and everything else is read off the
eased pair (alphas()):

    CrawlMove    clamp(its length / CRAWL_FULL_CMS): lying still to crawling
    CrawlDiag    clamp(2t),      t = atan2(|across|, |ahead|) / 90
    CrawlSide    clamp(2t - 1)   (t: 0 ahead or back, 0.5 a diagonal, 1 a side)
    CrawlBack    1 going back, else 0
    CrawlRight   1 going right, else 0

and stance_clips.py blends (weights() is the same sum, for the unit test):

    moving = Blend(Blend(axis, diagonal, CrawlDiag), side, CrawlSide)
    axis = Blend(fwd, back, CrawlBack)        side = Blend(left, right, CrawlRight)
    diagonal = Blend(Blend(fwd_left, fwd_right, CrawlRight),
                     Blend(back_left, back_right, CrawlRight), CrawlBack)

NO POP: each of CrawlBack and CrawlRight steps only where what it chooses
between weighs nothing (the axis pair and the diagonals at a pure side, the
side pair and the diagonals at pure ahead or back), and a reversal takes the
eased pair through zero, where CrawlMove is 0 and the body lies still.

THE SLIDE (cm/s the body is carried over ground its limbs do not cover, at
the crawl's 80 cm/s; SLIDE_CMS): forward and back 0, the diagonals 27.7, the
sides 46.2. The pack's side loop covers 16.9 cm/s and its diagonals 26.2, and
no clip plays faster than RATE_SCALE_RANGE allows (2x, past which a limb
scurries). The side crawl does not read right at this speed; slowing the
crawl by direction is the movement's, and not decided here.
"""

import dataclasses
import math

from asset_pipeline.fal_paths import (
    PRONE_DIAG_S, PRONE_DIAG_TRAVEL_CM, PRONE_FWD_TRAVEL_CM, PRONE_SIDE_S,
    PRONE_SIDE_TRAVEL_CM,
)
from asset_pipeline.mixamo_paths import RATE_SCALE_RANGE
from combat.tuning import COMBAT

# What the player crawls at: the movement's (jog x prone_speed_scale).
CRAWL_CMS = COMBAT.jog_speed_cms * COMBAT.prone_speed_scale
# The eased speed at which the crawl has fully taken over from lying still:
# body_pose.MOVE_FULL_CM_S's number (that module needs the editor).
CRAWL_FULL_CMS = 60.0
# How fast the eased velocity follows the real one (FInterpTo, 1/s): a
# reversal is through lying still in about a third of a second.
TURN_SPEED = 8.0
# CrawlBack and CrawlRight are clamp(speed x this): a step at zero.
STEP_GAIN = 1000.0


def _rate(travel_cm, seconds):
    return min(RATE_SCALE_RANGE[1], round(CRAWL_CMS / (travel_cm / seconds), 2))


# The forward loop covers 63 cm in its second and the player crawls at 80
# cm/s, so it plays at 80 / 63 = 1.27 and nothing is left to slide. The side
# and diagonal loops would need 4.7x and 3.1x: they play at the cap.
PRONE_LOOP_RATE = _rate(PRONE_FWD_TRAVEL_CM, 1.0)
PRONE_DIAG_RATE = _rate(PRONE_DIAG_TRAVEL_CM, PRONE_DIAG_S)
PRONE_SIDE_RATE = _rate(PRONE_SIDE_TRAVEL_CM, PRONE_SIDE_S)


@dataclasses.dataclass(frozen=True)
class Direction:
    name: str
    ahead: float      # the unit direction of travel in the body's frame
    right: float
    clip: str         # the PlayerSkin field of the clip it plays
    rate: float       # negative: played in reverse
    covers_cms: float  # what the clip's limbs cover at 1x


_FWD = PRONE_FWD_TRAVEL_CM / 1.0
_DIAG = PRONE_DIAG_TRAVEL_CM / PRONE_DIAG_S
_SIDE = PRONE_SIDE_TRAVEL_CM / PRONE_SIDE_S
_H = math.sqrt(0.5)
# Backwards is a forward clip in reverse, and the mirror of it: going back
# and left is the forward-right loop backwards.
DIRECTIONS = (
    Direction("forward", 1.0, 0.0, "prone_crawl", PRONE_LOOP_RATE, _FWD),
    Direction("forward right", _H, _H, "prone_fwd_right", PRONE_DIAG_RATE, _DIAG),
    Direction("right", 0.0, 1.0, "prone_right", PRONE_SIDE_RATE, _SIDE),
    Direction("back right", -_H, _H, "prone_fwd_left", -PRONE_DIAG_RATE, _DIAG),
    Direction("back", -1.0, 0.0, "prone_crawl", -PRONE_LOOP_RATE, _FWD),
    Direction("back left", -_H, -_H, "prone_fwd_right", -PRONE_DIAG_RATE, _DIAG),
    Direction("left", 0.0, -1.0, "prone_left", PRONE_SIDE_RATE, _SIDE),
    Direction("forward left", _H, -_H, "prone_fwd_left", PRONE_DIAG_RATE, _DIAG),
)
BY_NAME = {d.name: d for d in DIRECTIONS}
# The PlayerSkin fields a crawl by direction needs beside prone_crawl.
DIRECTION_FIELDS = ("prone_left", "prone_right", "prone_fwd_left", "prone_fwd_right")
SLIDE_CMS = {d.name: round(CRAWL_CMS - abs(d.rate) * d.covers_cms, 1) for d in DIRECTIONS}


def _clamp(x):
    return max(0.0, min(1.0, x))


def alphas(ahead, right):
    """(CrawlMove, CrawlDiag, CrawlSide, CrawlBack, CrawlRight) for an eased
    velocity of ``ahead`` and ``right`` cm/s: what crawl_direction.py authors."""
    t2 = math.degrees(math.atan2(abs(right), abs(ahead))) * (2.0 / 90.0)
    return (_clamp(math.hypot(ahead, right) / CRAWL_FULL_CMS), _clamp(t2), _clamp(t2 - 1.0),
            _clamp(ahead * -STEP_GAIN), _clamp(right * STEP_GAIN))


def weights(ahead, right):
    """{direction name: its share of the moving pose}: the anim graph's blend
    tree, summed."""
    _move, diag, side, back, rightward = alphas(ahead, right)
    axis, diagonal = (1.0 - diag) * (1.0 - side), diag * (1.0 - side)
    fore, aft = 1.0 - back, back
    port, star = 1.0 - rightward, rightward
    return {"forward": axis * fore, "back": axis * aft,
            "left": side * port, "right": side * star,
            "forward left": diagonal * fore * port, "forward right": diagonal * fore * star,
            "back left": diagonal * aft * port, "back right": diagonal * aft * star}
