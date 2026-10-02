"""Getting ready to throw: while the throw key is held over an arc, the arm
is cocked back in A_ThrowReady (combat/throw_pose.py), the throw clip's own
pose where its hand is furthest back.

    every frame the arc is drawn (throw.py's aim):
        IsValid(ThrowReadyAnim) AND it is not what AIM_SLOT is playing
          AND HitSlot is quiet
            --> play it into AIM_SLOT, looping

    the frame the key is let go with nothing thrown:
        NeedsRefresh = true    the equip puts the item's own pose back, or
                               stops the slot under a lowered gun

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
from combat.graph import BEL, _at, _connect, _node, _pin, _set
from combat.nodes import (
    FN_AND, FN_ANIM_INSTANCE, FN_IS_SLOT_ACTIVE, FN_IS_VALID, FN_NOT, FN_PLAY_SLOT,
)
from combat.throw_tuning import THROW_READY_BLEND_S
from combat.weapon_component.common import AIM_LOOPS

THROW_READY_ANIM_VAR = "ThrowReadyAnim"   # A_ThrowReady, or None

FN_IS_PLAYING_SLOT = "/Script/Engine.AnimInstance.IsPlayingSlotAnimation"


def _out(n, name="ReturnValue"):
    return _pin(n, name, is_input=False)


def _author_throw_ready(ed, exec_in, x0, y0):
    """Hold the ready pose in the slot; returns the exits. Run it on every
    frame of the aim."""
    made = []

    def keep(n):
        made.append(n)
        return n

    def get(name, x, y):
        return _out(keep(_at(ed.add_get_member_variable_node(name), x, y)), name)

    def both(a, b, x, y):
        n = keep(_at(_node(ed, FN_AND), x, y))
        _connect(a, _pin(n, "A"))
        _connect(b, _pin(n, "B"))
        return _out(n)

    def negate(a, x, y):
        n = keep(_at(_node(ed, FN_NOT), x, y))
        _connect(a, _pin(n, "A"))
        return _out(n)

    anim = keep(_at(_node(ed, FN_ANIM_INSTANCE), x0 + 240, y0 + 300))
    _connect(get("OwnerMesh", x0, y0 + 300), _pin(anim, "self"))
    pose = get(THROW_READY_ANIM_VAR, x0, y0 + 440)
    has = keep(_at(_node(ed, FN_IS_VALID), x0 + 480, y0 + 440))
    _connect(pose, _pin(has, "Object"))
    held = keep(_at(_node(ed, FN_IS_PLAYING_SLOT), x0 + 480, y0 + 580))
    _connect(_out(anim), _pin(held, "self"))
    _connect(pose, _pin(held, "Asset"))
    _set(held, "SlotNodeName", AIM_SLOT)
    flinching = keep(_at(_node(ed, FN_IS_SLOT_ACTIVE), x0 + 480, y0 + 760))
    _connect(_out(anim), _pin(flinching, "self"))
    _set(flinching, "SlotNodeName", HIT_SLOT)
    free = both(negate(_out(held), x0 + 760, y0 + 580),
                negate(_out(flinching), x0 + 760, y0 + 760), x0 + 1000, y0 + 640)
    gate = keep(_at(ed.add_branch_node(), x0 + 1480, y0))
    _connect(both(_out(has), free, x0 + 1240, y0 + 440), _pin(gate, "Condition"))
    _connect(exec_in, _pin(gate, "execute"))

    play = keep(_at(_node(ed, FN_PLAY_SLOT), x0 + 1760, y0))
    _connect(_out(anim), _pin(play, "self"))
    _connect(pose, _pin(play, "Asset"))
    _set(play, "SlotNodeName", AIM_SLOT)
    _set(play, "BlendInTime", THROW_READY_BLEND_S)
    _set(play, "BlendOutTime", THROW_READY_BLEND_S)
    _set(play, "InPlayRate", 1.0)
    _set(play, "LoopCount", AIM_LOOPS)
    _connect(BEL.find_then_pin(gate), _pin(play, "execute"))

    ed.add_comment_to_nodes(
        "Getting ready to throw (throw_ready.py): while the arc is drawn the "
        f"arm is cocked, the ready pose held in {AIM_SLOT}. Asked every frame "
        "of what the slot is playing, so it comes back after a flinch or a "
        f"re-equip; never under a flinch ({HIT_SLOT}), which it would stop.",
        made)
    return (BEL.find_then_pin(play), BEL.find_else_pin(gate))


def _author_ready_down(ed, exec_in, x, y):
    """The aim was called off: re-equip, which puts the held item's own pose
    back in the slot (or stops it, under a lowered gun). Returns the exit."""
    dirty = _at(ed.add_set_member_variable_node("NeedsRefresh"), x, y)
    _set(dirty, "NeedsRefresh", "true")
    _connect(exec_in, _pin(dirty, "execute"))
    return BEL.find_then_pin(dirty)
