"""The throw's wind-up: the click starts the overhand throw's clip, and the
item leaves the hand where the clip's hand lets go, THROW_RELEASE_S into it.

The clip is played on from THROW_READY_S, the moment the ready pose was taken
at (throw_ready.py holds the arm there while the key is down), so the arm
goes forward out of the pose it waited in and the hand lets go
THROW_WINDUP_S (the difference) after the click.

Two stages, each a Branch on the component's own variables (a component Tick
cannot hold a Delay), the way punch.py's swing and blow are:

  start   the click over the arc (throw.py's exec) --> ThrowWinding = Held;
          with a clip (ThrowAnim), ThrowDueTime = now + THROW_WINDUP_S and
          the clip into the upper-body slot, from THROW_READY_S
  due     IsValid(ThrowWinding) AND now >= ThrowDueTime --> if it is still
          what is held, throw.py's release; either way ThrowWinding is cleared

ThrowWinding is the item being thrown, not a flag, so a hand that changed in
the wind-up (a switch, a drop) throws nothing: the throw was of that item.

A skin with no clip (the mannequin: skin.throw is None) stamps nothing, so
ThrowDueTime is still in the past and the item leaves on the frame of the
click, as it did before there was a clip.

While it winds the throw is busy (_winding): throw.py draws no arc and keeps
Tick's fire gate shut, so a second click neither throws again nor fires.

The clip plays into DefaultSlot, upper body only (anim_blueprint.py), like
the punch and the slash: the legs keep walking.
"""

from combat.anim_blueprint import AIM_SLOT
from combat.fx_vars import THROW_CLIP, fx_event
from uebp.graph import _connect, _node, _pin, _set, else_, out, then
from combat.throw_tuning import (
    THROW_ANIM_BLEND_S, THROW_READY_S, THROW_RELEASE_S, THROW_WINDUP_S,
)
from combat.weapon_component.punch import _and, _get, _stamp
from uebp.nodes.actor import FN_ANIM_INSTANCE, FN_PLAY_SLOT
from uebp.nodes.math import FN_EQ_OO, FN_GE_FF
from uebp.nodes.system import FN_IS_VALID, FN_TIME_SECONDS
from combat.weapon_component import vars as WV

THROW_ANIM_VAR = "ThrowAnim"          # the skin's throw clip, or None
THROW_WINDING_VAR = "ThrowWinding"    # the item being thrown, until it leaves
THROW_DUE_VAR = "ThrowDueTime"        # world time the hand lets go


def _winding(ed):
    """A throw is winding up: a plain read, safe in any condition."""
    valid = _node(ed, FN_IS_VALID)
    _connect(_get(ed, THROW_WINDING_VAR), _pin(valid, "Object"))
    return out(valid)


def _author_throw_clip(ed, exec_in):
    """The skin's throw clip into the upper-body slot, on from the ready
    pose's moment (throw_ready.py held the arm there), behind IsValid of it.
    Returns (played, no clip): the exec pins after. Fx_ThrowClip's body too
    (throw.py): the other players' copies play it at the server's word."""
    has = _node(ed, FN_IS_VALID)
    _connect(_get(ed, THROW_ANIM_VAR), _pin(has, "Object"))
    clip = ed.add_branch_node()
    _connect(out(has), _pin(clip, "Condition"))
    _connect(exec_in, _pin(clip, "execute"))
    anim = _node(ed, FN_ANIM_INSTANCE)
    _connect(_get(ed, WV.OwnerMesh), _pin(anim, "self"))
    play = _node(ed, FN_PLAY_SLOT)
    _connect(out(anim), _pin(play, "self"))
    _connect(_get(ed, THROW_ANIM_VAR), _pin(play, "Asset"))
    _set(play, "SlotNodeName", AIM_SLOT)
    _set(play, "BlendInTime", THROW_ANIM_BLEND_S)
    _set(play, "BlendOutTime", THROW_ANIM_BLEND_S)
    _set(play, "InPlayRate", 1.0)
    _set(play, "LoopCount", 1)
    _set(play, "InTimeToStartMontageAt", THROW_READY_S)
    _connect(then(clip), _pin(play, "execute"))
    return then(play), else_(clip)


def _author_throw_windup(ed, held, started, exec_ins):
    """(let_go, called_off, waiting): ``started`` is the exec of the click
    that throws, and ``exec_ins`` every other way into the due gate. let_go
    runs on the frame the hand lets go of what it wound up with, for the
    release; called_off when the hand holds something else by then; waiting on
    every other frame."""
    keep = ed.add_set_member_variable_node(THROW_WINDING_VAR)
    _connect(held, _pin(keep, THROW_WINDING_VAR))
    _connect(started, _pin(keep, "execute"))
    has = _node(ed, FN_IS_VALID)
    _connect(_get(ed, THROW_ANIM_VAR), _pin(has, "Object"))
    clip = ed.add_branch_node()
    _connect(out(has), _pin(clip, "Condition"))
    _connect(then(keep), _pin(clip, "execute"))
    step = _stamp(ed, THROW_DUE_VAR, THROW_WINDUP_S, then(clip))
    # The clip itself is Fx_ThrowClip (throw.py), played here at once: the
    # owner's own, in both modes, before the server knows of the throw.
    play = _node(ed, fx_event(THROW_CLIP))
    _connect(step, _pin(play, "execute"))

    # --- due: the hand lets go ----------------------------------------------
    now = _node(ed, FN_TIME_SECONDS)
    due = _node(ed, FN_GE_FF)
    _connect(out(now), _pin(due, "A"))
    _connect(_get(ed, THROW_DUE_VAR), _pin(due, "B"))
    gate = ed.add_branch_node()
    _connect(_and(ed, _winding(ed), out(due)), _pin(gate, "Condition"))
    for pin in tuple(exec_ins) + (then(play), else_(clip)):
        _connect(pin, _pin(gate, "execute"))
    # Nested, not folded into the gate: it is asked only of a winding throw.
    same = _node(ed, FN_EQ_OO)
    _connect(_get(ed, THROW_WINDING_VAR), _pin(same, "A"))
    _connect(held, _pin(same, "B"))
    still = ed.add_branch_node()
    _connect(out(same), _pin(still, "Condition"))
    _connect(then(gate), _pin(still, "execute"))

    ed.add_comment_to_nodes(
        f"The throw's wind-up: the click plays the clip into {AIM_SLOT}, on "
        f"from the ready pose's {THROW_READY_S:.3f} s, and the item leaves "
        f"the hand {THROW_RELEASE_S:g} s into it, {THROW_WINDUP_S:.3f} s "
        "later, if the hand still holds it. A skin with no clip lets go at "
        "once.",
        [keep, clip, play, gate, still])
    return then(still), else_(still), else_(gate)


def _author_wound_down(ed, exec_ins):
    """The wind-up is over, thrown or called off: ThrowWinding set with
    nothing connected clears it. Returns the exec pin after it."""
    clear = ed.add_set_member_variable_node(THROW_WINDING_VAR)
    for pin in exec_ins:
        _connect(pin, _pin(clear, "execute"))
    return then(clear)
