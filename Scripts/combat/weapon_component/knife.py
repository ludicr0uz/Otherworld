"""The knife: the fire key, pressed with a Melee item held, slashes.

    press   inside the fire gate (Held valid, not sprinting, not blocking, not
            a spent press): Held.Melee --> tap AND now >= NextKnifeTime
            --> KnifeQueued. Not Melee goes on to the ready gate (the guns).
    swing   KnifeQueued --> NextKnifeTime, KnifeDueTime, KnifePending,
            A_KnifeSlash (KnifeAnim) into the upper-body slot
    blow    KnifePending AND now >= KnifeDueTime --> a sphere in front of the
            chest; a body with BP_HealthComponent loses COMBAT.knife_damage

The swing and the blow are punch.py's, run on the KNIFE Strike. Only the
press differs: the punch's gate needs empty hands and so must not read Held,
while the knife's needs Held.Melee, which is only safe to read behind the fire
gate's IsValid(Held) -- so it sits there, beside the Consumable branch, and
a Melee item never reaches the ammunition or cooldown tests of a gun.

The press only queues, so a probe can slash by writing KnifeQueued (no key
can be injected into a headless game). Tuning is COMBAT.knife_* in tuning.py;
the clip is knife_anim.py's.
"""

from combat.graph import BEL, _at, _connect, _node, _pin
from combat.nodes import FN_GE_FF, FN_TIME_SECONDS
from combat.tuning import COMBAT
from combat.weapon_component.common import _prop
from combat.weapon_component.punch import (
    Strike, _and, _author_swing, _get, _set_bool,
)

KNIFE_ANIM_VAR = "KnifeAnim"
KNIFE_QUEUED_VAR = "KnifeQueued"
KNIFE_PENDING_VAR = "KnifePending"
NEXT_KNIFE_VAR = "NextKnifeTime"
KNIFE_DUE_VAR = "KnifeDueTime"
MELEE_VAR = "Melee"

KNIFE = Strike("knife", KNIFE_ANIM_VAR, KNIFE_QUEUED_VAR, KNIFE_PENDING_VAR,
               NEXT_KNIFE_VAR, KNIFE_DUE_VAR, COMBAT.knife_interval_s,
               COMBAT.knife_impact_s, COMBAT.knife_damage, COMBAT.knife_reach_cm,
               COMBAT.knife_radius_cm, COMBAT.knife_chest_cm)


def _author_knife_press(ed, held, tap, not_melee, x0, y0):
    """Branch a Melee item off the fire gate; a tap off cooldown queues a
    slash. Returns (the gate's exec input, its exits)."""
    melee, melee_n = _prop(ed, MELEE_VAR, held, x0, y0 + 160)
    gate = _at(ed.add_branch_node(), x0 + 240, y0)
    _connect(melee, _pin(gate, "Condition"))
    _connect(BEL.find_else_pin(gate), not_melee)

    now = _at(_node(ed, FN_TIME_SECONDS), x0 + 240, y0 + 300)
    rested = _at(_node(ed, FN_GE_FF), x0 + 480, y0 + 300)
    _connect(_pin(now, "ReturnValue", is_input=False), _pin(rested, "A"))
    _connect(_get(ed, NEXT_KNIFE_VAR, x0 + 240, y0 + 420), _pin(rested, "B"))
    press = _at(ed.add_branch_node(), x0 + 720, y0)
    _connect(_and(ed, tap, _pin(rested, "ReturnValue", is_input=False),
                  x0 + 720, y0 + 300), _pin(press, "Condition"))
    _connect(BEL.find_then_pin(gate), _pin(press, "execute"))
    queued = _set_bool(ed, KNIFE_QUEUED_VAR, True, BEL.find_then_pin(press),
                       x0 + 960, y0)
    ed.add_comment_to_nodes(
        "A Melee item (the knife) is swung, not fired: a tap off cooldown queues "
        "a slash (KnifeQueued), which the knife's swing stage plays. Anything "
        "else goes on to the guns' ready gate.",
        [melee_n, gate, now, rested, press])
    return _pin(gate, "execute"), (queued, BEL.find_else_pin(press))


def _author_knife_swing(ed, exec_ins, x0, y0):
    """The slash's swing and blow (punch.py's stages on KNIFE); returns the
    blow stage's exits."""
    return _author_swing(ed, KNIFE, exec_ins, x0, y0)
