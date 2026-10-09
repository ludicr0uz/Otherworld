"""The knife: the fire key, pressed with a Melee item held, slashes.

    press   inside the fire gate (Held valid, not sprinting, not blocking, not
            a spent press): Held.Melee --> tap AND now >= NextKnifeTime
            --> KnifeQueued. Not Melee goes on to the ready gate (the guns).
    swing   KnifeQueued --> Server_Slash, which (a Melee item in a living
            hand, not guarding, off cooldown) stamps NextKnifeTime and
            KnifeDueTime, sets KnifePending and plays the swing's clip into
            the upper-body slot: A_AxeSwing (AxeAnim) while the ready pose in
            hand (HandPose, which every machine's copy has) is the axe's
            (AxePose), else A_KnifeSlash (KnifeAnim)
    blow    KnifePending AND now >= KnifeDueTime --> a sphere in front of the
            chest; a body with BP_HealthComponent loses COMBAT.knife_damage,
            or twice that off a creature afraid of fire while the blade in
            hand is hot (hot_blow.py)

The swing and the blow are punch.py's, run on the KNIFE Strike, with one
addition: a blow that lands on something with no health goes on to chop.py,
where the axe (an item that Chops) cuts a tree for wood. Only the
press differs: the punch's gate needs empty hands and so must not read Held,
while the knife's needs Held.Melee, which is only safe to read behind the fire
gate's IsValid(Held) -- so it sits there, beside the Consumable branch, and
a Melee item never reaches the ammunition or cooldown tests of a gun.

The press only queues, so a probe can slash by writing KnifeQueued (no key
can be injected into a headless game). Tuning is COMBAT.knife_* in tuning.py;
the clips are melee_clips.py's, each cut so that it strikes
COMBAT.knife_impact_s in.
"""

from uebp.graph import _connect, _must_load, _node, _pin, else_, out, then
from combat.paths import AXE_ANIM_PATH, HOLD_AXE_ANIM_PATH
from combat.fx_vars import BLADE_HIT, SLASH
from combat.strike_vars import SERVER_SLASH
from combat.tuning import COMBAT
from combat.weapon_component.chop import _author_chop
from combat.weapon_component.common import _prop
from combat.weapon_component.hot_blow import author_hot_blow
from combat.weapon_component.punch import (
    Strike, _and, _author_blow, _author_swing, _get, _set_bool,
)
from uebp.nodes.math import FN_GE_FF
from uebp.nodes.system import FN_TIME_SECONDS
from combat import item_vars as IV
from combat.weapon_component import vars as WV

KNIFE_ANIM_VAR = "KnifeAnim"
KNIFE_QUEUED_VAR = "KnifeQueued"
KNIFE_PENDING_VAR = "KnifePending"
NEXT_KNIFE_VAR = "NextKnifeTime"
KNIFE_DUE_VAR = "KnifeDueTime"
MELEE_VAR = IV.Melee
# The axe's own clip, and the ready pose that says the axe is in hand.
AXE_ANIM_VAR = "AxeAnim"
AXE_POSE_VAR = "AxePose"
AXE_CLIP_VARS = (AXE_ANIM_VAR, AXE_POSE_VAR)

KNIFE = Strike("knife", KNIFE_ANIM_VAR, KNIFE_QUEUED_VAR, KNIFE_PENDING_VAR,
               NEXT_KNIFE_VAR, KNIFE_DUE_VAR, COMBAT.knife_interval_s,
               COMBAT.knife_impact_s, COMBAT.knife_damage, COMBAT.knife_reach_cm,
               COMBAT.knife_radius_cm, COMBAT.knife_chest_cm, WV.BladeHitSounds,
               SERVER_SLASH, True, SLASH, BLADE_HIT,
               by_pose=((AXE_POSE_VAR, AXE_ANIM_VAR),))


def axe_clip_defaults():
    """The component's defaults for AXE_CLIP_VARS."""
    return {AXE_ANIM_VAR: _must_load(AXE_ANIM_PATH),
            AXE_POSE_VAR: _must_load(HOLD_AXE_ANIM_PATH)}


def _author_knife_press(ed, held, tap, not_melee):
    """Branch a Melee item off the fire gate; a tap off cooldown queues a
    slash. Returns (the gate's exec input, its exits)."""
    melee, melee_n = _prop(ed, MELEE_VAR, held)
    gate = ed.add_branch_node()
    _connect(melee, _pin(gate, "Condition"))
    _connect(else_(gate), not_melee)

    now = _node(ed, FN_TIME_SECONDS)
    rested = _node(ed, FN_GE_FF)
    _connect(out(now), _pin(rested, "A"))
    _connect(_get(ed, NEXT_KNIFE_VAR), _pin(rested, "B"))
    press = ed.add_branch_node()
    _connect(_and(ed, tap, out(rested)), _pin(press, "Condition"))
    _connect(then(gate), _pin(press, "execute"))
    queued = _set_bool(ed, KNIFE_QUEUED_VAR, True, then(press))
    ed.add_comment_to_nodes(
        "A Melee item (the knife) is swung, not fired: a tap off cooldown queues "
        "a slash (KnifeQueued), which the knife's swing stage plays. Anything "
        "else goes on to the guns' ready gate.",
        [melee_n, gate, now, rested, press])
    return _pin(gate, "execute"), (queued, else_(press))


def _author_knife_swing(ed, exec_ins):
    """The slash's swing (punch.py's, on KNIFE): queued, it is asked of the
    server (Server_Slash). Returns its exits."""
    return _author_swing(ed, KNIFE, exec_ins)


def _author_knife_blow(ed, exec_ins):
    """The slash's blow (punch.py's stage on KNIFE), in the upkeep; returns
    its exits. A blow on something with no health goes to chop.py: with an
    item that Chops in hand, a tree gives wood. What it takes off a body is
    hot_blow.py's: more, with a hot blade, off a creature afraid of fire."""
    return _author_blow(ed, KNIFE, exec_ins, scenery=_author_chop,
                        damage=author_hot_blow(KNIFE))
