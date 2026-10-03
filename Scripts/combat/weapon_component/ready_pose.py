"""Keeps the ready pose playing: restarts it after a flinch or anything else
that stopped the montage group; and re-equips on the frames Lowered changes,
which is what starts and stops it (carry.py writes Lowered).
"""

from combat.anim_blueprint import AIM_SLOT, HIT_SLOT
from combat.carry_tuning import LOWERED_VAR, POSE_LOWERED_VAR
from uebp.graph import _connect, _node, _pin, _set, else_, out, then
from combat.hit_reaction import HIT_REACT_PROBE, POSE_BACK_PROBE_PREFIX
from combat.weapon_component.common import AIM_BLEND, AIM_LOOPS, _prop
from uebp.nodes.actor import FN_ANIM_INSTANCE, FN_IS_SLOT_ACTIVE, FN_PLAY_SLOT
from uebp.nodes.math import FN_AND, FN_NEQ_BB, FN_NOT
from uebp.nodes.system import FN_IS_VALID, FN_WARN
from combat import item_vars as IV
from combat.weapon_component import vars as WV


def _author_ready_pose_keepalive(ed, held, exec_ins):
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

        Held is valid AND not Lowered   (carry.py: sprinting, or a gun at rest)
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

    mesh = keep(ed.add_get_member_variable_node(WV.OwnerMesh))
    anim = keep(_node(ed, FN_ANIM_INSTANCE))
    _connect(out(mesh, WV.OwnerMesh), _pin(anim, "self"))
    anim_out = out(anim)

    armed = keep(_node(ed, FN_IS_VALID))
    _connect(held, _pin(armed, "Object"))
    running = keep(ed.add_get_member_variable_node(LOWERED_VAR))
    still = keep(_node(ed, FN_NOT))
    _connect(out(running, LOWERED_VAR), _pin(still, "A"))

    aiming = keep(_node(ed, FN_IS_SLOT_ACTIVE))
    _connect(anim_out, _pin(aiming, "self"))
    _set(aiming, "SlotNodeName", AIM_SLOT)
    no_pose = keep(_node(ed, FN_NOT))
    _connect(out(aiming), _pin(no_pose, "A"))

    flinching = keep(_node(ed, FN_IS_SLOT_ACTIVE))
    _connect(anim_out, _pin(flinching, "self"))
    _set(flinching, "SlotNodeName", HIT_SLOT)
    settled = keep(_node(ed, FN_NOT))
    _connect(out(flinching), _pin(settled, "A"))

    ready = keep(_node(ed, FN_AND))
    _connect(out(armed), _pin(ready, "A"))
    _connect(out(still), _pin(ready, "B"))
    quiet = keep(_node(ed, FN_AND))
    _connect(out(no_pose), _pin(quiet, "A"))
    _connect(out(settled), _pin(quiet, "B"))
    needed = keep(_node(ed, FN_AND))
    _connect(out(ready), _pin(needed, "A"))
    _connect(out(quiet), _pin(needed, "B"))

    gate = keep(ed.add_branch_node())
    _connect(out(needed), _pin(gate, "Condition"))
    for tail in exec_ins:
        _connect(tail, _pin(gate, "execute"))

    pose_pin, pose_n = _prop(ed, IV.AimPose, held)
    keep(pose_n)
    replay = keep(_node(ed, FN_PLAY_SLOT))
    _connect(anim_out, _pin(replay, "self"))
    _connect(pose_pin, _pin(replay, "Asset"))
    _set(replay, "SlotNodeName", AIM_SLOT)
    _set(replay, "BlendInTime", AIM_BLEND)
    _set(replay, "BlendOutTime", AIM_BLEND)
    _set(replay, "InPlayRate", 1.0)
    _set(replay, "LoopCount", AIM_LOOPS)
    _connect(then(gate), _pin(replay, "execute"))

    after_replay = then(replay)
    if HIT_REACT_PROBE:
        # Same temporary instrumentation as the reaction's own, and removed the
        # same way. Without it "the pose came back" is unobservable in a log:
        # the restart is silent and the only other evidence is a slot weight
        # sampled from outside, which cannot be caught in the 0.05 s gap
        # between two flinches when ten wanderers are hitting the player.
        say = keep(_node(ed, FN_WARN))
        _set(say, "InString", POSE_BACK_PROBE_PREFIX + "ready pose restarted")
        _connect(after_replay, _pin(say, "execute"))
        after_replay = then(say)

    join = keep(ed.add_branch_node())
    _set(join, "Condition", "true")
    _connect(after_replay, _pin(join, "execute"))
    _connect(else_(gate), _pin(join, "execute"))

    ed.add_comment_to_nodes(
        f"The ready pose puts itself back. A montage started in {HIT_SLOT} "
        f"stops the one in {AIM_SLOT}, because both slots are in the skeleton's "
        f"default montage GROUP and UE 5.8 gives Python no way to move one out "
        f"of it -- so the flinch costs the aim pose, and this is what buys it "
        f"back, on the first frame after the stagger has finished. The "
        f"{HIT_SLOT} term is what stops the two restarting each other forever.",
        made)
    return (then(join),)


def _author_lowered_pose_edge(ed, exec_ins):
    """Re-equip on the frames Lowered and PoseLowered disagree; returns the
    exits."""
    # Edge-triggered, not level-triggered, and that distinction is the whole
    # block. Re-equipping costs a detach, an attach and a montage restart; done
    # every frame the gun is up it would restart the ready pose sixty times a
    # second, which is a weapon that flickers. PoseLowered is what the pose
    # currently reflects, Lowered (carry.py) is what it should reflect,
    # and only the frames where those disagree do any work.
    now_sprint = ed.add_get_member_variable_node(LOWERED_VAR)
    now_sprint_out = out(now_sprint, LOWERED_VAR)
    posed = ed.add_get_member_variable_node(POSE_LOWERED_VAR)
    changed = _node(ed, FN_NEQ_BB)
    _connect(now_sprint_out, _pin(changed, "A"))
    _connect(out(posed, POSE_LOWERED_VAR), _pin(changed, "B"))
    pose_gate = ed.add_branch_node()
    _connect(out(changed), _pin(pose_gate, "Condition"))
    for exit_pin in exec_ins:
        _connect(exit_pin, _pin(pose_gate, "execute"))
    remember = ed.add_set_member_variable_node(POSE_LOWERED_VAR)
    _connect(now_sprint_out, _pin(remember, POSE_LOWERED_VAR))
    _connect(then(pose_gate), _pin(remember, "execute"))
    pose_dirty = ed.add_set_member_variable_node(WV.NeedsRefresh)
    _set(pose_dirty, WV.NeedsRefresh, "true")
    _connect(then(remember), _pin(pose_dirty, "execute"))

    ed.add_comment_to_nodes(
        "The gun was lowered or raised this frame (a sprint, an aim key, the "
        "guard, a shot) -- re-equip, which is what starts or stops the ready "
        "pose. Edge-triggered on PoseLowered: the level-triggered version "
        "restarts the montage every frame, and the weapon strobes.",
        [now_sprint, posed, changed, pose_gate, remember, pose_dirty])
    return (then(pose_dirty), else_(pose_gate))
