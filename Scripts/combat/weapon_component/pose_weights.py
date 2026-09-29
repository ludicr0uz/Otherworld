"""The body poses' weights: writes the player's anim BP PoseCrouch, PoseProne,
GuardArms and GuardGun every frame, eased towards what the stance and the guard
say (body_pose.py owns the bones those weights turn).

    PoseCrouch -> Stance == CROUCH
    PoseProne  -> Stance == PRONE
    GuardGun   -> Blocking AND HeldTwoHanded
    GuardArms  -> Blocking AND NOT HeldTwoHanded     (fists, pistol, food)

Each weight is FInterpTo(its current value on the anim instance, target), so
the anim instance holds the state and the component needs none of its own.

HeldTwoHanded is copied off Held behind an IsValid Branch first: the weights'
expressions run every frame, empty-handed frames included, and a Held.X read
inside them would log an Accessed None on each of those frames.
"""

import unreal

from combat.body_pose import (
    GUARD_ARMS, GUARD_GUN, POSE_BLEND_SPEED, POSE_CROUCH, POSE_PRONE,
)
from combat.graph import BEL, _at, _connect, _node, _palette, _pin, _set
from combat.nodes import (
    FN_AND, FN_ANIM_INSTANCE, FN_BOOL_TO_FLOAT, FN_EQ_II, FN_INTERP_FF, FN_NOT,
)
from combat.paths import ITEM_CLASS_PATH
from combat.skin import player_skin
from combat.weapon_component.sight_pitch import _anim_class_path
from combat.weapon_component.stance import CROUCH, PRONE, STANCE_VAR

HELD_TWO_HANDED = "HeldTwoHanded"


def _author_held_two_handed(ed, held, armed_out, exec_ins, x0, y0):
    """HeldTwoHanded = IsValid(Held) ? Held.TwoHanded : false."""
    gate = _at(ed.add_branch_node(), x0, y0)
    _connect(armed_out, _pin(gate, "Condition"))
    for e in exec_ins:
        _connect(e, _pin(gate, "execute"))
    flag = _at(ed.add_get_member_variable_node("TwoHanded", ITEM_CLASS_PATH),
               x0 + 240, y0 + 200)
    _connect(held, _pin(flag, "self"))
    copy = _at(ed.add_set_member_variable_node(HELD_TWO_HANDED), x0 + 500, y0)
    _connect(_pin(flag, "TwoHanded", is_input=False), _pin(copy, HELD_TWO_HANDED))
    _connect(BEL.find_then_pin(gate), _pin(copy, "execute"))
    clear = _at(ed.add_set_member_variable_node(HELD_TWO_HANDED), x0 + 500, y0 + 300)
    _set(clear, HELD_TWO_HANDED, "false")
    _connect(BEL.find_else_pin(gate), _pin(clear, "execute"))
    return (BEL.find_then_pin(copy), BEL.find_then_pin(clear))


def _targets(ed, x0, y0):
    """{weight: bool pin} -- what each weight is easing towards."""
    stance = _at(ed.add_get_member_variable_node(STANCE_VAR), x0, y0)
    stance_out = _pin(stance, STANCE_VAR, is_input=False)
    out = {}
    for weight, value, dy in ((POSE_CROUCH, CROUCH, 0), (POSE_PRONE, PRONE, 120)):
        eq = _at(_node(ed, FN_EQ_II), x0 + 240, y0 + dy)
        _connect(stance_out, _pin(eq, "A"))
        _set(eq, "B", value)
        out[weight] = _pin(eq, "ReturnValue", is_input=False)

    blocking = _at(ed.add_get_member_variable_node("Blocking"), x0, y0 + 300)
    two = _at(ed.add_get_member_variable_node(HELD_TWO_HANDED), x0, y0 + 420)
    two_out = _pin(two, HELD_TWO_HANDED, is_input=False)
    one = _at(_node(ed, FN_NOT), x0 + 240, y0 + 480)
    _connect(two_out, _pin(one, "A"))
    for weight, hands, dy in ((GUARD_GUN, two_out, 300),
                              (GUARD_ARMS, _pin(one, "ReturnValue", is_input=False), 420)):
        both = _at(_node(ed, FN_AND), x0 + 480, y0 + dy)
        _connect(_pin(blocking, "Blocking", is_input=False), _pin(both, "A"))
        _connect(hands, _pin(both, "B"))
        out[weight] = _pin(both, "ReturnValue", is_input=False)
    return out


def _author_pose_weights(ed, tick, held, armed_out, exec_ins, x0, y0):
    """Ease the four weights on the player's anim instance. Returns the exec
    pins to carry on from. After the stance and the guard, which it reads."""
    before = {n.get_name() for n in ed.list_all_nodes()}
    anim_class = _anim_class_path(player_skin())
    if not unreal.load_class(None, anim_class):
        raise RuntimeError(f"{anim_class} did not load -- nothing to cast to")

    copied = _author_held_two_handed(ed, held, armed_out, exec_ins, x0, y0)

    mesh = _at(ed.add_get_member_variable_node("OwnerMesh"), x0 + 800, y0 + 160)
    anim = _at(_node(ed, FN_ANIM_INSTANCE), x0 + 1040, y0 + 160)
    _connect(_pin(mesh, "OwnerMesh", is_input=False), _pin(anim, "self"))
    cast = _at(_palette(ed, "Utilities|Casting|CastTo"
                            + anim_class.rsplit(".", 1)[1][:-2]), x0 + 1300, y0)
    _connect(_pin(anim, "ReturnValue", is_input=False), _pin(cast, "Object"))
    for e in copied:
        _connect(e, _pin(cast, "execute"))
    as_anim = next(p for p in BEL.list_output_pins(cast)
                   if str(unreal.BlueprintGraphPinLibrary.get_pin_name(p))
                   .startswith("As"))

    targets = _targets(ed, x0 + 1300, y0 + 500)
    tail, x = BEL.find_then_pin(cast), x0 + 2100
    for weight in (POSE_CROUCH, POSE_PRONE, GUARD_ARMS, GUARD_GUN):
        target = _at(_node(ed, FN_BOOL_TO_FLOAT), x - 500, y0 + 300)
        _connect(targets[weight], _pin(target, "InBool"))
        now = _at(ed.add_get_member_variable_node(weight, anim_class), x - 500, y0 + 440)
        _connect(as_anim, _pin(now, "self"))
        step = _at(_node(ed, FN_INTERP_FF), x - 250, y0 + 300)
        _connect(_pin(now, weight, is_input=False), _pin(step, "Current"))
        _connect(_pin(target, "ReturnValue", is_input=False), _pin(step, "Target"))
        _connect(_pin(tick, "DeltaSeconds", is_input=False), _pin(step, "DeltaTime"))
        _set(step, "InterpSpeed", POSE_BLEND_SPEED)
        put = _at(ed.add_set_member_variable_node(weight, anim_class), x, y0)
        _connect(as_anim, _pin(put, "self"))
        _connect(_pin(step, "ReturnValue", is_input=False), _pin(put, weight))
        _connect(tail, _pin(put, "execute"))
        tail, x = BEL.find_then_pin(put), x + 800

    ed.add_comment_to_nodes(
        f"The body poses: {POSE_CROUCH} / {POSE_PRONE} from the Stance, "
        f"{GUARD_GUN} / {GUARD_ARMS} from Blocking and whether Held is two-handed, "
        f"each eased (speed {POSE_BLEND_SPEED:g}) on the player's anim instance, "
        "whose ModifyBones they weight (Scripts/combat/body_pose.py).",
        [n for n in ed.list_all_nodes() if n.get_name() not in before])
    return (tail, _pin(cast, "CastFailed", is_input=False))
