"""The body poses' weights: writes the player's anim BP PoseCrouch, PoseProne,
GuardArms, GuardGun and PoseKneel every frame, eased towards what the stance,
the guard and the search say (body_pose.py owns the bones those weights turn,
stance_clips.py the clips).

    PoseCrouch -> Stance == CROUCH
    PoseProne  -> Stance == PRONE
    GuardGun   -> Blocking AND HeldTwoHanded
    GuardArms  -> Blocking AND NOT HeldTwoHanded     (fists, pistol, food)
    PoseKneel  -> Searching AND NOT Stance == PRONE  (slower: KNEEL_BLEND_SPEED)
    KneelTime  =  KNEEL_FROM_S + |time mod 2 span - span|, span = KNEEL_TO_S - KNEEL_FROM_S

Searching is written by the HUD while its loot window is open
(graphics_menu/loot_kneel.py); this component only reads it. A prone player
searches lying down: the crawl's hip lift (body_pose.py) is weighted by
PoseProne and would lift a kneeling body too. KneelTime is where the kneel
clip is held: a triangle wave over the stretch in which the hands work, so it
neither stands up at the clip's end nor jumps at a loop's seam.

Each weight is FInterpTo(its current value on the anim instance, target), so
the anim instance holds the state and the component needs none of its own.

HeldTwoHanded is copied off Held behind an IsValid Branch first: the weights'
expressions run every frame, empty-handed frames included, and a Held.X read
inside them would log an Accessed None on each of those frames.
"""

import unreal

from combat.body_pose import (
    GUARD_ARMS, GUARD_GUN, KNEEL_BLEND_SPEED, KNEEL_FROM_S, KNEEL_TIME, KNEEL_TO_S,
    POSE_BLEND_SPEED, POSE_CROUCH, POSE_KNEEL, POSE_PRONE,
)
from uebp.graph import BEL, _connect, _node, _palette, _pin, _set, else_, out, then
from combat.paths import ITEM_CLASS_PATH
from combat.skin import player_skin
from combat.support_hand import SUPPORT_POINT_VAR
from combat.weapon_component.sight_pitch import _anim_class_path
from combat.weapon_component.stance import CROUCH, PRONE, STANCE_VAR
from uebp.nodes.actor import FN_ANIM_INSTANCE
from uebp.nodes.math import (
    FN_ABS, FN_ADD_FF, FN_AND, FN_BOOL_TO_FLOAT, FN_EQ_II, FN_FMOD, FN_INTERP_FF, FN_NOT,
    FN_SUB_FF)
from uebp.nodes.system import FN_TIME_SECONDS

HELD_TWO_HANDED = "HeldTwoHanded"
# Held.SupportPoint, copied beside it: where the held gun's ready pose has the
# left hand (support_hand.py). Kept with nothing held; nothing reads it then.
HELD_SUPPORT_POINT = "HeldSupportPoint"
# The loot window is open (the HUD writes it, graphics_menu/loot_kneel.py).
SEARCHING_VAR = "Searching"


def _author_held_two_handed(ed, held, armed_out, exec_ins):
    """HeldTwoHanded = IsValid(Held) ? Held.TwoHanded : false, and with a
    valid Held, HeldSupportPoint = Held.SupportPoint."""
    gate = ed.add_branch_node()
    _connect(armed_out, _pin(gate, "Condition"))
    for e in exec_ins:
        _connect(e, _pin(gate, "execute"))
    flag = ed.add_get_member_variable_node("TwoHanded", ITEM_CLASS_PATH)
    _connect(held, _pin(flag, "self"))
    copy = ed.add_set_member_variable_node(HELD_TWO_HANDED)
    _connect(out(flag, "TwoHanded"), _pin(copy, HELD_TWO_HANDED))
    _connect(then(gate), _pin(copy, "execute"))
    clear = ed.add_set_member_variable_node(HELD_TWO_HANDED)
    _set(clear, HELD_TWO_HANDED, "false")
    _connect(else_(gate), _pin(clear, "execute"))
    point = ed.add_get_member_variable_node(SUPPORT_POINT_VAR, ITEM_CLASS_PATH)
    _connect(held, _pin(point, "self"))
    keep = ed.add_set_member_variable_node(HELD_SUPPORT_POINT)
    _connect(out(point, SUPPORT_POINT_VAR), _pin(keep, HELD_SUPPORT_POINT))
    _connect(then(copy), _pin(keep, "execute"))
    return (then(keep), then(clear))


def _targets(ed):
    """{weight: bool pin} -- what each weight is easing towards."""
    stance = ed.add_get_member_variable_node(STANCE_VAR)
    stance_out = _pin(stance, STANCE_VAR, is_input=False)
    out = {}
    for weight, value in ((POSE_CROUCH, CROUCH), (POSE_PRONE, PRONE)):
        eq = _node(ed, FN_EQ_II)
        _connect(stance_out, _pin(eq, "A"))
        _set(eq, "B", value)
        out[weight] = _pin(eq, "ReturnValue", is_input=False)

    blocking = ed.add_get_member_variable_node("Blocking")
    two = ed.add_get_member_variable_node(HELD_TWO_HANDED)
    two_out = _pin(two, HELD_TWO_HANDED, is_input=False)
    one = _node(ed, FN_NOT)
    _connect(two_out, _pin(one, "A"))
    for weight, hands in ((GUARD_GUN, two_out),
                          (GUARD_ARMS, _pin(one, "ReturnValue", is_input=False))):
        both = _node(ed, FN_AND)
        _connect(_pin(blocking, "Blocking", is_input=False), _pin(both, "A"))
        _connect(hands, _pin(both, "B"))
        out[weight] = _pin(both, "ReturnValue", is_input=False)

    searching = ed.add_get_member_variable_node(SEARCHING_VAR)
    up = _node(ed, FN_NOT)
    _connect(out[POSE_PRONE], _pin(up, "A"))
    down = _node(ed, FN_AND)
    _connect(_pin(searching, SEARCHING_VAR, is_input=False), _pin(down, "A"))
    _connect(_pin(up, "ReturnValue", is_input=False), _pin(down, "B"))
    out[POSE_KNEEL] = _pin(down, "ReturnValue", is_input=False)
    return out


def _kneel_time(ed):
    """KNEEL_FROM_S + |time mod 2 span - span|, as a pin."""
    span = KNEEL_TO_S - KNEEL_FROM_S
    now = _node(ed, FN_TIME_SECONDS)
    lap = _node(ed, FN_FMOD)
    _connect(out(now), _pin(lap, "Dividend"))
    _set(lap, "Divisor", 2.0 * span)
    back = _node(ed, FN_SUB_FF)
    _connect(out(lap, "Remainder"), _pin(back, "A"))
    _set(back, "B", span)
    wave = _node(ed, FN_ABS)
    _connect(out(back), _pin(wave, "A"))
    at = _node(ed, FN_ADD_FF)
    _connect(out(wave), _pin(at, "A"))
    _set(at, "B", KNEEL_FROM_S)
    return out(at)


def _author_pose_weights(ed, tick, held, armed_out, exec_ins):
    """Ease the weights on the player's anim instance. Returns the exec
    pins to carry on from. After the stance and the guard, which it reads."""
    before = {n.get_name() for n in ed.list_all_nodes()}
    anim_class = _anim_class_path(player_skin())
    if not unreal.load_class(None, anim_class):
        raise RuntimeError(f"{anim_class} did not load -- nothing to cast to")

    copied = _author_held_two_handed(ed, held, armed_out, exec_ins)

    mesh = ed.add_get_member_variable_node("OwnerMesh")
    anim = _node(ed, FN_ANIM_INSTANCE)
    _connect(out(mesh, "OwnerMesh"), _pin(anim, "self"))
    cast = _palette(ed, "Utilities|Casting|CastTo" + anim_class.rsplit(".", 1)[1][:-2])
    _connect(out(anim), _pin(cast, "Object"))
    for e in copied:
        _connect(e, _pin(cast, "execute"))
    as_anim = next(p for p in BEL.list_output_pins(cast)
                   if str(unreal.BlueprintGraphPinLibrary.get_pin_name(p))
                   .startswith("As"))

    targets = _targets(ed)
    tail = then(cast)
    for weight, speed in ((POSE_CROUCH, POSE_BLEND_SPEED), (POSE_PRONE, POSE_BLEND_SPEED),
                          (GUARD_ARMS, POSE_BLEND_SPEED), (GUARD_GUN, POSE_BLEND_SPEED),
                          (POSE_KNEEL, KNEEL_BLEND_SPEED)):
        target = _node(ed, FN_BOOL_TO_FLOAT)
        _connect(targets[weight], _pin(target, "InBool"))
        now = ed.add_get_member_variable_node(weight, anim_class)
        _connect(as_anim, _pin(now, "self"))
        step = _node(ed, FN_INTERP_FF)
        _connect(out(now, weight), _pin(step, "Current"))
        _connect(out(target), _pin(step, "Target"))
        _connect(out(tick, "DeltaSeconds"), _pin(step, "DeltaTime"))
        _set(step, "InterpSpeed", speed)
        put = ed.add_set_member_variable_node(weight, anim_class)
        _connect(as_anim, _pin(put, "self"))
        _connect(out(step), _pin(put, weight))
        _connect(tail, _pin(put, "execute"))
        tail = then(put)
    held_at = ed.add_set_member_variable_node(KNEEL_TIME, anim_class)
    _connect(as_anim, _pin(held_at, "self"))
    _connect(_kneel_time(ed), _pin(held_at, KNEEL_TIME))
    _connect(tail, _pin(held_at, "execute"))
    tail = then(held_at)

    ed.add_comment_to_nodes(
        f"The body poses: {POSE_CROUCH} / {POSE_PRONE} from the Stance, "
        f"{GUARD_GUN} / {GUARD_ARMS} from Blocking and whether Held is two-handed, "
        f"each eased (speed {POSE_BLEND_SPEED:g}) on the player's anim instance, "
        f"whose ModifyBones they weight (Scripts/combat/body_pose.py); and "
        f"{POSE_KNEEL} from {SEARCHING_VAR} (speed {KNEEL_BLEND_SPEED:g}), with "
        f"{KNEEL_TIME} running up and down the kneel clip's working stretch.",
        [n for n in ed.list_all_nodes() if n.get_name() not in before])
    return (tail, out(cast, "CastFailed"))
