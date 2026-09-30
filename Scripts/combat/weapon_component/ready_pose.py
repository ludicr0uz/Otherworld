"""Keeps the ready pose playing: restarts it after a flinch or anything else
that stopped the montage group.
"""

from combat.anim_blueprint import AIM_SLOT, HIT_SLOT
from combat.graph import BEL, _at, _connect, _node, _pin, _set
from combat.hit_reaction import HIT_REACT_PROBE, POSE_BACK_PROBE_PREFIX
from combat.nodes import (
    FN_AND, FN_ANIM_INSTANCE, FN_IS_SLOT_ACTIVE, FN_IS_VALID, FN_NEQ_BB, FN_NOT,
    FN_PLAY_SLOT, FN_WARN,
)
from combat.weapon_component.common import AIM_BLEND, AIM_LOOPS, _prop


def _author_ready_pose_keepalive(ed, held, exec_ins, x0, y0):
    """Put the ready pose back after a hit reaction has taken it away.

    THIS IS NOT BELT AND BRACES, it is the price of the second slot.
    UAnimInstance plays montages per GROUP, and every slot on a skeleton
    belongs to the default group unless the SKELETON maps it elsewhere --
    USkeleton::SetSlotGroupName, which UE 5.8 does not expose to Python at all
    (measured: `slot_group_names`, `slot_to_group_name_map` and
    `slot_anim_tracks` all fail as editor properties on a USkeleton, and the
    class has no slot or group methods). So starting the flinch in HitSlot
    stops the ready pose in DefaultSlot even though the two slots are different
    nodes in different blends.

    Measured before this existed, in a -game run: DefaultSlot sat at weight
    1.000 until the first punch landed, and read active=False, weight 0.000 for
    the rest of the session -- the player fought on with the gun in the
    locomotion pose. The flinch itself was fine; what it cost was the aim.

    Re-asserting it from Tick is the fix, and it is a better fix than never
    interrupting would have been: the arms ARE meant to be yanked off the
    sights for the length of the stagger, and this puts them back on the first
    frame after it, with the montage's own blend.

        Held is valid AND not sprinting
          AND DefaultSlot is quiet      (nothing is holding the pose)
          AND HitSlot is quiet          (we are not mid-flinch)
            -> play AimPose into DefaultSlot again

    The HitSlot term is the one that stops it oscillating: without it, the
    frame the flinch starts DefaultSlot goes quiet, this restarts the ready
    pose, and the restart stops the flinch -- in the same group, for the same
    reason -- and the reaction is a single frame of twitch.

    Nothing inside the condition reads a property off Held: only IsValid does,
    and the AimPose getter sits behind the gate on the play node's own pin, so
    a player with empty hands does not cost an Accessed None per frame.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    mesh = keep(_at(ed.add_get_member_variable_node("OwnerMesh"), x0, y0 + 500))
    anim = keep(_at(_node(ed, FN_ANIM_INSTANCE), x0 + 240, y0 + 500))
    _connect(_pin(mesh, "OwnerMesh", is_input=False), _pin(anim, "self"))
    anim_out = _pin(anim, "ReturnValue", is_input=False)

    armed = keep(_at(_node(ed, FN_IS_VALID), x0 + 240, y0 + 160))
    _connect(held, _pin(armed, "Object"))
    running = keep(_at(ed.add_get_member_variable_node("Sprinting"), x0, y0 + 280))
    still = keep(_at(_node(ed, FN_NOT), x0 + 240, y0 + 280))
    _connect(_pin(running, "Sprinting", is_input=False), _pin(still, "A"))

    aiming = keep(_at(_node(ed, FN_IS_SLOT_ACTIVE), x0 + 480, y0 + 620))
    _connect(anim_out, _pin(aiming, "self"))
    _set(aiming, "SlotNodeName", AIM_SLOT)
    no_pose = keep(_at(_node(ed, FN_NOT), x0 + 720, y0 + 620))
    _connect(_pin(aiming, "ReturnValue", is_input=False), _pin(no_pose, "A"))

    flinching = keep(_at(_node(ed, FN_IS_SLOT_ACTIVE), x0 + 480, y0 + 760))
    _connect(anim_out, _pin(flinching, "self"))
    _set(flinching, "SlotNodeName", HIT_SLOT)
    settled = keep(_at(_node(ed, FN_NOT), x0 + 720, y0 + 760))
    _connect(_pin(flinching, "ReturnValue", is_input=False), _pin(settled, "A"))

    ready = keep(_at(_node(ed, FN_AND), x0 + 480, y0 + 220))
    _connect(_pin(armed, "ReturnValue", is_input=False), _pin(ready, "A"))
    _connect(_pin(still, "ReturnValue", is_input=False), _pin(ready, "B"))
    quiet = keep(_at(_node(ed, FN_AND), x0 + 960, y0 + 680))
    _connect(_pin(no_pose, "ReturnValue", is_input=False), _pin(quiet, "A"))
    _connect(_pin(settled, "ReturnValue", is_input=False), _pin(quiet, "B"))
    needed = keep(_at(_node(ed, FN_AND), x0 + 1200, y0 + 400))
    _connect(_pin(ready, "ReturnValue", is_input=False), _pin(needed, "A"))
    _connect(_pin(quiet, "ReturnValue", is_input=False), _pin(needed, "B"))

    gate = keep(_at(ed.add_branch_node(), x0 + 1440, y0))
    _connect(_pin(needed, "ReturnValue", is_input=False), _pin(gate, "Condition"))
    for tail in exec_ins:
        _connect(tail, _pin(gate, "execute"))

    pose_pin, pose_n = _prop(ed, "AimPose", held, x0 + 1440, y0 + 300)
    keep(pose_n)
    replay = keep(_at(_node(ed, FN_PLAY_SLOT), x0 + 1720, y0))
    _connect(anim_out, _pin(replay, "self"))
    _connect(pose_pin, _pin(replay, "Asset"))
    _set(replay, "SlotNodeName", AIM_SLOT)
    _set(replay, "BlendInTime", AIM_BLEND)
    _set(replay, "BlendOutTime", AIM_BLEND)
    _set(replay, "InPlayRate", 1.0)
    _set(replay, "LoopCount", AIM_LOOPS)
    _connect(BEL.find_then_pin(gate), _pin(replay, "execute"))

    after_replay = BEL.find_then_pin(replay)
    if HIT_REACT_PROBE:
        # Same temporary instrumentation as the reaction's own, and removed the
        # same way. Without it "the pose came back" is unobservable in a log:
        # the restart is silent and the only other evidence is a slot weight
        # sampled from outside, which cannot be caught in the 0.05 s gap
        # between two flinches when ten wanderers are hitting the player.
        say = keep(_at(_node(ed, FN_WARN), x0 + 1980, y0 + 300))
        _set(say, "InString", POSE_BACK_PROBE_PREFIX + "ready pose restarted")
        _connect(after_replay, _pin(say, "execute"))
        after_replay = BEL.find_then_pin(say)

    join = keep(_at(ed.add_branch_node(), x0 + 2240, y0))
    _set(join, "Condition", "true")
    _connect(after_replay, _pin(join, "execute"))
    _connect(BEL.find_else_pin(gate), _pin(join, "execute"))

    ed.add_comment_to_nodes(
        f"The ready pose puts itself back. A montage started in {HIT_SLOT} "
        f"stops the one in {AIM_SLOT}, because both slots are in the skeleton's "
        f"default montage GROUP and UE 5.8 gives Python no way to move one out "
        f"of it -- so the flinch costs the aim pose, and this is what buys it "
        f"back, on the first frame after the stagger has finished. The "
        f"{HIT_SLOT} term is what stops the two restarting each other forever.",
        made)
    return (BEL.find_then_pin(join),)


def _author_sprint_pose_edge(ed, exec_ins):
    """Re-equip on the frames Sprinting and PoseSprinting disagree; returns the
    exits. (Moved verbatim out of tick.py's Tick author.)"""
    # Edge-triggered, not level-triggered, and that distinction is the whole
    # block. Re-equipping costs a detach, an attach and a montage restart; done
    # every frame the player holds Shift it would restart the run's ready pose
    # sixty times a second, which is a weapon that flickers. PoseSprinting is
    # what the pose currently reflects, Sprinting is what it should reflect,
    # and only the frames where those disagree do any work.
    now_sprint = _at(ed.add_get_member_variable_node("Sprinting"), 240, 1020)
    now_sprint_out = _pin(now_sprint, "Sprinting", is_input=False)
    posed = _at(ed.add_get_member_variable_node("PoseSprinting"), 240, 1140)
    changed = _at(_node(ed, FN_NEQ_BB), 520, 1060)
    _connect(now_sprint_out, _pin(changed, "A"))
    _connect(_pin(posed, "PoseSprinting", is_input=False), _pin(changed, "B"))
    pose_gate = _at(ed.add_branch_node(), 780, 940)
    _connect(_pin(changed, "ReturnValue", is_input=False), _pin(pose_gate, "Condition"))
    for exit_pin in exec_ins:
        _connect(exit_pin, _pin(pose_gate, "execute"))
    remember = _at(ed.add_set_member_variable_node("PoseSprinting"), 1040, 940)
    _connect(now_sprint_out, _pin(remember, "PoseSprinting"))
    _connect(BEL.find_then_pin(pose_gate), _pin(remember, "execute"))
    pose_dirty = _at(ed.add_set_member_variable_node("NeedsRefresh"), 1300, 940)
    _set(pose_dirty, "NeedsRefresh", "true")
    _connect(BEL.find_then_pin(remember), _pin(pose_dirty, "execute"))

    ed.add_comment_to_nodes(
        "Started or stopped sprinting this frame -- re-equip, which is what "
        "starts or stops the ready pose. Edge-triggered on PoseSprinting: the "
        "level-triggered version restarts the montage every frame Shift is "
        "held, and the weapon strobes.",
        [now_sprint, posed, changed, pose_gate, remember, pose_dirty])
    return (BEL.find_then_pin(pose_dirty), BEL.find_else_pin(pose_gate))
