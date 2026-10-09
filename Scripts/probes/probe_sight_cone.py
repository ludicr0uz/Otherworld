"""Debug mode's sight cone: every live wanderer draws its cone each frame
while the GameMode's DebugMode is on, and none does while it is off.

A headless game has no renderer to look at, so the draw is read off what it
leaves behind: each controller stamps SightConeDrawnAt with the game time
straight after its DrawDebugCone (npc/sight_cone.py).

  - debug mode on: every controller with a pawn has a stamp from the last
    moment, and the stamp keeps moving;
  - what it draws is the sight sense's own: the controller's TuneSightRange
    and TuneSightHalfAngle are real, positive numbers;
  - debug mode off: the stamps stop.
"""

SYSTEMS = ('weapons',)

import unreal

from combat.game_state import DEBUG_MODE_VAR
from net.state_consts import GAME_STATE_BP_PATH
from npc.monster_tuning import TUNED_VAR
from npc.paths import SIGHT_CONE_STAMP_VAR

WRITABLE = [(GAME_STATE_BP_PATH, DEBUG_MODE_VAR)]
FRESH_S = 0.1          # a stamp this recent was written in the last few frames


def _controllers(p):
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController)
    return [c for c in ctrls if "ForestWandererAI" in c.get_class().get_name()
            and c.get_controlled_pawn() is not None]


def _stamps(p):
    return [float(p.get(c, SIGHT_CONE_STAMP_VAR)) for c in _controllers(p)]


def probe(p):
    yield lambda: len(_controllers(p)) > 0
    yield 0.5
    mode, world = p.game_state(), p.world()

    p.set(mode, DEBUG_MODE_VAR, False)
    yield 0.3
    idle = _stamps(p)
    yield 0.3
    p.check("debug mode off: no wanderer draws a cone",
            _stamps(p) == idle, f"{len(idle)} controllers")

    p.set(mode, DEBUG_MODE_VAR, True)
    yield 0.3
    now = unreal.GameplayStatics.get_time_seconds(world)
    first = _stamps(p)
    p.check("debug mode on: every live wanderer drew its cone in the last moment",
            len(first) > 0 and all(now - s <= FRESH_S for s in first),
            f"{len(first)} controllers, oldest {now - min(first):.3f} s ago at {now:.2f} s")
    yield 0.3
    later = _stamps(p)
    p.check("...and draws it again every frame",
            len(later) == len(first) and all(b > a for a, b in zip(first, later)),
            f"{min(first):.2f} -> {min(later):.2f}")
    shapes = [(float(p.get(c, TUNED_VAR["vision_range_cm"])),
               float(p.get(c, TUNED_VAR["vision_half_angle_deg"])))
              for c in _controllers(p)]
    p.check("...as long and as wide as its sight (TuneSightRange, TuneSightHalfAngle)",
            all(reach > 0 and 0 < half < 180 for reach, half in shapes),
            str(sorted(set(shapes))))

    p.set(mode, DEBUG_MODE_VAR, False)
    yield 0.2
    stopped = _stamps(p)
    yield 0.3
    p.check("debug mode off again: the cones stop",
            _stamps(p) == stopped, f"{len(stopped)} controllers")
