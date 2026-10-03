"""Getting ready to throw: while the throw key is held over an arc, the arm
is cocked back in A_ThrowReady (combat/throw_pose.py), the throw clip's own
pose where its hand is furthest back.

    every frame the arc is drawn (throw.py's aim):
        IsValid(ThrowReadyAnim) AND it is not what AIM_SLOT is playing
          AND HitSlot is quiet
            --> play it into AIM_SLOT, looping
            --> Held.ThrowGrip? move Held to its ThrowGripLocation/Rotation
                (the knife, held by the blade: knife.py)

    the frame the key is let go with nothing thrown:
        NeedsRefresh = true    the equip puts the item's own pose and grip
                               back, or stops the slot under a lowered gun

Level-triggered on what the slot is playing, not on the key's edge, so the
pose comes back by itself after anything that took the slot in the meantime:
a flinch, a re-equip (the carry raising or lowering a gun, a switch to
another item with the key still down). The HitSlot term is ready_pose.py's:
both slots are in one montage group, so restarting the pose under a flinch
would stop the flinch.

The click needs nothing here: throw_windup.py plays the clip into the same
slot, from the moment this pose was taken at, and the release re-equips.

A skin with no throw clip has no pose (ThrowReadyAnim stays None) and plays
nothing. The pose is upper body only, like everything in AIM_SLOT: the legs
keep walking, crouched or prone.
"""

from combat.anim_blueprint import AIM_SLOT, HIT_SLOT
from uebp.graph import _connect, _node, _pin, _set, else_, out, then
from combat.nodes import (
    FN_AND, FN_ANIM_INSTANCE, FN_IS_SLOT_ACTIVE, FN_IS_VALID, FN_NOT, FN_PLAY_SLOT,
    FN_SET_REL_LOC, FN_SET_REL_ROT,
)
from combat.throw_tuning import (
    THROW_GRIP_LOC_VAR, THROW_GRIP_ROT_VAR, THROW_GRIP_VAR, THROW_READY_BLEND_S,
)
from combat.weapon_component.common import AIM_LOOPS, _prop

THROW_READY_ANIM_VAR = "ThrowReadyAnim"   # A_ThrowReady, or None

FN_IS_PLAYING_SLOT = "/Script/Engine.AnimInstance.IsPlayingSlotAnimation"


def _author_throw_ready(ed, item, exec_in):
    """Hold the ready pose in the slot, and an item thrown by its blade in
    its throw grip; returns the exits. Run it on every frame of the aim, when
    ``item`` (Held) is valid."""
    made = []

    def keep(n):
        made.append(n)
        return n

    def get(name):
        return out(keep(ed.add_get_member_variable_node(name)), name)

    def both(a, b):
        n = keep(_node(ed, FN_AND))
        _connect(a, _pin(n, "A"))
        _connect(b, _pin(n, "B"))
        return out(n)

    def negate(a):
        n = keep(_node(ed, FN_NOT))
        _connect(a, _pin(n, "A"))
        return out(n)

    anim = keep(_node(ed, FN_ANIM_INSTANCE))
    _connect(get("OwnerMesh"), _pin(anim, "self"))
    pose = get(THROW_READY_ANIM_VAR)
    has = keep(_node(ed, FN_IS_VALID))
    _connect(pose, _pin(has, "Object"))
    held = keep(_node(ed, FN_IS_PLAYING_SLOT))
    _connect(out(anim), _pin(held, "self"))
    _connect(pose, _pin(held, "Asset"))
    _set(held, "SlotNodeName", AIM_SLOT)
    flinching = keep(_node(ed, FN_IS_SLOT_ACTIVE))
    _connect(out(anim), _pin(flinching, "self"))
    _set(flinching, "SlotNodeName", HIT_SLOT)
    free = both(negate(out(held)), negate(out(flinching)))
    gate = keep(ed.add_branch_node())
    _connect(both(out(has), free), _pin(gate, "Condition"))
    _connect(exec_in, _pin(gate, "execute"))

    play = keep(_node(ed, FN_PLAY_SLOT))
    _connect(out(anim), _pin(play, "self"))
    _connect(pose, _pin(play, "Asset"))
    _set(play, "SlotNodeName", AIM_SLOT)
    _set(play, "BlendInTime", THROW_READY_BLEND_S)
    _set(play, "BlendOutTime", THROW_READY_BLEND_S)
    _set(play, "InPlayRate", 1.0)
    _set(play, "LoopCount", AIM_LOOPS)
    _connect(then(gate), _pin(play, "execute"))

    # Held by the blade? Moved on the frame the pose starts, the same frame
    # after any re-equip (which put the hand's own grip back).
    by_blade, n = _prop(ed, THROW_GRIP_VAR, item)
    keep(n)
    blade = keep(ed.add_branch_node())
    _connect(by_blade, _pin(blade, "Condition"))
    _connect(then(play), _pin(blade, "execute"))
    loc, n = _prop(ed, THROW_GRIP_LOC_VAR, item)
    keep(n)
    put = keep(_node(ed, FN_SET_REL_LOC))
    _connect(item, _pin(put, "self"))
    _connect(loc, _pin(put, "NewRelativeLocation"))
    _connect(then(blade), _pin(put, "execute"))
    rot, n = _prop(ed, THROW_GRIP_ROT_VAR, item)
    keep(n)
    turn = keep(_node(ed, FN_SET_REL_ROT))
    _connect(item, _pin(turn, "self"))
    _connect(rot, _pin(turn, "NewRelativeRotation"))
    _connect(then(put), _pin(turn, "execute"))

    ed.add_comment_to_nodes(
        "Getting ready to throw (throw_ready.py): while the arc is drawn the "
        f"arm is cocked, the ready pose held in {AIM_SLOT}. Asked every frame "
        "of what the slot is playing, so it comes back after a flinch or a "
        f"re-equip; never under a flinch ({HIT_SLOT}), which it would stop. "
        "An item thrown by its blade (ThrowGrip) is moved into its throw grip.",
        made)
    return (then(turn), else_(blade), else_(gate))


def _author_ready_down(ed, exec_in):
    """The aim was called off: re-equip, which puts the held item's own pose
    back in the slot (or stops it, under a lowered gun). Returns the exit."""
    dirty = ed.add_set_member_variable_node("NeedsRefresh")
    _set(dirty, "NeedsRefresh", "true")
    _connect(exec_in, _pin(dirty, "execute"))
    return then(dirty)
