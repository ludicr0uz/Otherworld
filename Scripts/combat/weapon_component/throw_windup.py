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
from combat.graph import BEL, _at, _connect, _node, _pin, _set
from uebp.graph import out
from combat.nodes import (
    FN_ANIM_INSTANCE, FN_GE_FF, FN_IS_VALID, FN_PLAY_SLOT, FN_TIME_SECONDS,
)
from combat.throw_tuning import (
    THROW_ANIM_BLEND_S, THROW_READY_S, THROW_RELEASE_S, THROW_WINDUP_S,
)
from combat.weapon_component.punch import _and, _get, _stamp

THROW_ANIM_VAR = "ThrowAnim"          # the skin's throw clip, or None
THROW_WINDING_VAR = "ThrowWinding"    # the item being thrown, until it leaves
THROW_DUE_VAR = "ThrowDueTime"        # world time the hand lets go

FN_SAME_OBJECT = "/Script/Engine.KismetMathLibrary.EqualEqual_ObjectObject"


def _winding(ed, x, y):
    """A throw is winding up: a plain read, safe in any condition."""
    valid = _at(_node(ed, FN_IS_VALID), x + 240, y)
    _connect(_get(ed, THROW_WINDING_VAR, x, y), _pin(valid, "Object"))
    return out(valid)


def _author_throw_windup(ed, held, started, exec_ins, x0, y0):
    """(let_go, called_off, waiting): ``started`` is the exec of the click
    that throws, and ``exec_ins`` every other way into the due gate. let_go
    runs on the frame the hand lets go of what it wound up with, for the
    release; called_off when the hand holds something else by then; waiting on
    every other frame."""
    keep = _at(ed.add_set_member_variable_node(THROW_WINDING_VAR), x0, y0)
    _connect(held, _pin(keep, THROW_WINDING_VAR))
    _connect(started, _pin(keep, "execute"))
    has = _at(_node(ed, FN_IS_VALID), x0, y0 + 300)
    _connect(_get(ed, THROW_ANIM_VAR, x0 - 240, y0 + 300), _pin(has, "Object"))
    clip = _at(ed.add_branch_node(), x0 + 260, y0)
    _connect(out(has), _pin(clip, "Condition"))
    _connect(BEL.find_then_pin(keep), _pin(clip, "execute"))
    step = _stamp(ed, THROW_DUE_VAR, THROW_WINDUP_S, BEL.find_then_pin(clip),
                  x0 + 520, y0)
    anim = _at(_node(ed, FN_ANIM_INSTANCE), x0 + 1000, y0 + 300)
    _connect(_get(ed, "OwnerMesh", x0 + 760, y0 + 300), _pin(anim, "self"))
    play = _at(_node(ed, FN_PLAY_SLOT), x0 + 1260, y0)
    _connect(out(anim), _pin(play, "self"))
    _connect(_get(ed, THROW_ANIM_VAR, x0 + 1000, y0 + 440), _pin(play, "Asset"))
    _set(play, "SlotNodeName", AIM_SLOT)
    _set(play, "BlendInTime", THROW_ANIM_BLEND_S)
    _set(play, "BlendOutTime", THROW_ANIM_BLEND_S)
    _set(play, "InPlayRate", 1.0)
    _set(play, "LoopCount", 1)
    # On from the ready pose's moment (throw_ready.py held the arm there).
    _set(play, "InTimeToStartMontageAt", THROW_READY_S)
    _connect(step, _pin(play, "execute"))

    # --- due: the hand lets go ----------------------------------------------
    now = _at(_node(ed, FN_TIME_SECONDS), x0 + 1560, y0 + 460)
    due = _at(_node(ed, FN_GE_FF), x0 + 1800, y0 + 460)
    _connect(out(now), _pin(due, "A"))
    _connect(_get(ed, THROW_DUE_VAR, x0 + 1560, y0 + 580), _pin(due, "B"))
    gate = _at(ed.add_branch_node(), x0 + 2280, y0)
    _connect(_and(ed, _winding(ed, x0 + 1560, y0 + 300), out(due),
                  x0 + 2040, y0 + 300), _pin(gate, "Condition"))
    for pin in tuple(exec_ins) + (BEL.find_then_pin(play), BEL.find_else_pin(clip)):
        _connect(pin, _pin(gate, "execute"))
    # Nested, not folded into the gate: it is asked only of a winding throw.
    same = _at(_node(ed, FN_SAME_OBJECT), x0 + 2280, y0 + 300)
    _connect(_get(ed, THROW_WINDING_VAR, x0 + 2040, y0 + 440), _pin(same, "A"))
    _connect(held, _pin(same, "B"))
    still = _at(ed.add_branch_node(), x0 + 2540, y0)
    _connect(out(same), _pin(still, "Condition"))
    _connect(BEL.find_then_pin(gate), _pin(still, "execute"))

    ed.add_comment_to_nodes(
        f"The throw's wind-up: the click plays the clip into {AIM_SLOT}, on "
        f"from the ready pose's {THROW_READY_S:.3f} s, and the item leaves "
        f"the hand {THROW_RELEASE_S:g} s into it, {THROW_WINDUP_S:.3f} s "
        "later, if the hand still holds it. A skin with no clip lets go at "
        "once.",
        [keep, clip, play, gate, still])
    return BEL.find_then_pin(still), BEL.find_else_pin(still), BEL.find_else_pin(gate)


def _author_wound_down(ed, exec_ins, x, y):
    """The wind-up is over, thrown or called off: ThrowWinding set with
    nothing connected clears it. Returns the exec pin after it."""
    clear = _at(ed.add_set_member_variable_node(THROW_WINDING_VAR), x, y)
    for pin in exec_ins:
        _connect(pin, _pin(clear, "execute"))
    return BEL.find_then_pin(clear)
