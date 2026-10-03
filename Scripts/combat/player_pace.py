"""The player's jog: the character's own MaxWalkSpeed, set when the
components are installed (install.install_on_character).

The weapon component's BeginPlay caches that speed into BaseSpeed, and the
sprint, the aim's slowdown and the low stances all work from BaseSpeed, so
this one default is the jog everywhere. The number is COMBAT.jog_speed_cms,
which is player_tuning.csv's.
"""

import unreal

from combat.log import _log
from uebp.graph import _component_object, _handles
from combat.tuning import COMBAT


def movement_of(bp):
    """The Blueprint's CharacterMovementComponent template."""
    movement = next((o for o in (_component_object(h) for h, _n in _handles(bp))
                     if isinstance(o, unreal.CharacterMovementComponent)), None)
    if movement is None:
        raise RuntimeError(f"{bp.get_name()} has no CharacterMovementComponent")
    return movement


def set_jog_speed(bp):
    movement = movement_of(bp)
    movement.set_editor_property("max_walk_speed", COMBAT.jog_speed_cms)
    got = movement.get_editor_property("max_walk_speed")
    if abs(got - COMBAT.jog_speed_cms) > 1e-3:
        raise RuntimeError(f"MaxWalkSpeed stayed at {got}, wanted {COMBAT.jog_speed_cms}")
    _log(f"player: jogs at {COMBAT.jog_speed_cms:.0f} cm/s, sprints at "
         f"{COMBAT.sprint_speed_cms:.0f}")
