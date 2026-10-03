"""Crouch and prone, authored into the weapon component's Tick, and the one
setting on the character's movement component that lets it crouch at all.

The stance is one integer, Stance (STAND/CROUCH/PRONE), toggled by two tapped
keys. Both low stances are UE's own crouch -- CharacterMovement shrinks the
capsule, keeps the feet where they were and moves the mesh so it does not
sink, and the camera boom, which hangs off the capsule, rides down with it.
Prone is the same crouch to a lower CrouchedHalfHeight. Nothing here moves a
capsule by hand, which would have to redo all of that and the floor checks.

The movement component resizes only on the frame crouching STARTS, so going
from one low stance to the other stands up for one frame and crouches again
at the new height: the Branch below sees a crouched capsule of the wrong height
and uncrouches, and the next frame crouches afresh.

What a stance does to sound lives on the footstep component (StepVolume,
StepNoise), written from here every frame -- footsteps.py stays the same graph
for the player and every wanderer, and never learns what a stance is.
"""

import unreal

from combat.footsteps import FOOTSTEP_BP_PATH
from combat.log import _log
from uebp.graph import (
    _component_object, _connect, _handles, _loose_pin, _node, _palette, _pin, _set, else_,
    out, then)
from combat.nodes import MOVEMENT_CLASS_PATH
from combat.tuning import COMBAT, CROUCH_KEY, PRONE_KEY
from uebp.nodes.actor import (
    FN_CAPSULE_HALF_HEIGHT, FN_CROUCH, FN_GET_COMP, FN_IS_CROUCHING, FN_UNCROUCH,
    FN_WAS_PRESSED)
from uebp.nodes.math import (
    FN_ABS, FN_AND, FN_EQ_II, FN_GREATER_FF, FN_MUL_FF, FN_SELECT_FF, FN_SELECT_II,
    FN_SUB_FF)
from uebp.nodes.palette import NODE_CAST_CHARACTER, NODE_CAST_FOOTSTEP

STANCE_VAR = "Stance"
STAND, CROUCH, PRONE = 0, 1, 2
FOOTSTEP_CLASS_PATH = f"{FOOTSTEP_BP_PATH}.BP_FootstepComponent_C"
# A capsule that is within this of the stance's height is the stance's height.
# The engine writes the height it was asked for, so this is float slack only.
HEIGHT_SLACK_CM = 0.5


def allow_crouch(bp):
    """Let the character's movement component crouch.

    ACharacter::Crouch does nothing unless NavAgentProps.bCanCrouch is set, and
    the template ships it off. Walking off a ledge while low is allowed too:
    the engine's default keeps a crouched character on any edge, which on the
    forest's rocks and banks reads as an invisible wall.
    """
    movement = next((o for o in (_component_object(h) for h, _n in _handles(bp))
                     if isinstance(o, unreal.CharacterMovementComponent)), None)
    if movement is None:
        raise RuntimeError(f"{bp.get_name()} has no CharacterMovementComponent")
    props = movement.get_editor_property("nav_agent_props")
    props.set_editor_property("can_crouch", True)
    movement.set_editor_property("nav_agent_props", props)
    movement.set_editor_property("can_walk_off_ledges_when_crouching", True)
    if not movement.get_editor_property("nav_agent_props").get_editor_property("can_crouch"):
        raise RuntimeError("the character still cannot crouch")
    _log(f"player: can crouch ({CROUCH_KEY}) and go prone ({PRONE_KEY})")


def _by_stance(ed, stance_out, crouch, prone):
    """A float pin: 1.0 standing, ``crouch`` crouched, ``prone`` prone."""
    is_prone = _node(ed, FN_EQ_II)
    _connect(stance_out, _pin(is_prone, "A"))
    _set(is_prone, "B", PRONE)
    is_crouch = _node(ed, FN_EQ_II)
    _connect(stance_out, _pin(is_crouch, "A"))
    _set(is_crouch, "B", CROUCH)
    low = _node(ed, FN_SELECT_FF)
    _set(low, "A", crouch)
    _set(low, "B", 1.0)
    _connect(out(is_crouch), _pin(low, "bPickA"))
    pick = _node(ed, FN_SELECT_FF)
    _set(pick, "A", prone)
    _connect(out(low), _pin(pick, "B"))
    _connect(out(is_prone), _pin(pick, "bPickA"))
    return out(pick)


def _author_stance_toggle(ed, pc_out, key_pins, exec_in):
    """Stance = the toggled stance, or STAND while sprinting. No Branch:

        c = CrouchPressed ? (Stance == CROUCH ? STAND : CROUCH) : Stance
        p = PronePressed  ? (Stance == PRONE  ? STAND : PRONE)  : c
        Stance = Sprinting ? STAND : p

    Each WasInputKeyJustPressed is read exactly once. Sprint wins because it is
    the escape, the same reason it wins over the guard. Returns the Set node.
    """
    stance = ed.add_get_member_variable_node(STANCE_VAR)
    stance_out = out(stance, STANCE_VAR)

    def toggled(var, target):
        pressed = _node(ed, FN_WAS_PRESSED)
        _connect(pc_out, _pin(pressed, "self"))
        _connect(key_pins[var], _pin(pressed, "Key"))
        already = _node(ed, FN_EQ_II)
        _connect(stance_out, _pin(already, "A"))
        _set(already, "B", target)
        flip = _node(ed, FN_SELECT_II)
        _set(flip, "A", STAND)
        _set(flip, "B", target)
        _connect(out(already), _pin(flip, "bPickA"))
        return (out(pressed), out(flip))

    c_pressed, c_flip = toggled("KeyCrouch", CROUCH)
    p_pressed, p_flip = toggled("KeyProne", PRONE)
    after_c = _node(ed, FN_SELECT_II)
    _connect(c_flip, _pin(after_c, "A"))
    _connect(stance_out, _pin(after_c, "B"))
    _connect(c_pressed, _pin(after_c, "bPickA"))
    after_p = _node(ed, FN_SELECT_II)
    _connect(p_flip, _pin(after_p, "A"))
    _connect(out(after_c), _pin(after_p, "B"))
    _connect(p_pressed, _pin(after_p, "bPickA"))
    stood = _node(ed, FN_SELECT_II)
    _set(stood, "A", STAND)
    _connect(out(after_p), _pin(stood, "B"))
    _connect(out(ed.add_get_member_variable_node("Sprinting"), "Sprinting"), _pin(stood, "bPickA"))

    mark = ed.add_set_member_variable_node(STANCE_VAR)
    _connect(out(stood), _pin(mark, STANCE_VAR))
    _connect(exec_in, _pin(mark, "execute"))
    return mark


def _author_stance(ed, pc_out, owner_out, key_pins, exec_ins):
    """Toggle the stance, apply it to the movement component, and tell the
    footsteps how loud it is. Runs after sprint, which it reads.

        cast owner -> Stance = toggled (see _author_stance_toggle)
          -> MaxWalkSpeedCrouched = BaseSpeed * stance scale
          -> [Stance == STAND]            yes -> UnCrouch
          -> [crouched at another height] yes -> UnCrouch (re-crouch next frame)
                                          no  -> CrouchedHalfHeight, Crouch
          -> footstep component: StepVolume, StepNoise

    Returns the exec pins to carry on from.
    """
    before = {n.get_name() for n in ed.list_all_nodes()}
    as_char = _palette(ed, NODE_CAST_CHARACTER)
    _connect(owner_out, _pin(as_char, "Object"))
    for e in exec_ins:
        _connect(e, _pin(as_char, "execute"))
    char_out = _loose_pin(as_char, "AsCharacter", is_input=False)

    mark = _author_stance_toggle(ed, pc_out, key_pins, then(as_char))
    stance = ed.add_get_member_variable_node(STANCE_VAR)
    stance_out = out(stance, STANCE_VAR)

    movement = ed.add_get_member_variable_node("CharacterMovement", "/Script/Engine.Character")
    _connect(char_out, _pin(movement, "self"))
    movement_out = out(movement, "CharacterMovement")

    # --- how fast a low stance moves -----------------------------------------
    # The movement component reads MaxWalkSpeedCrouched instead of
    # MaxWalkSpeed while crouched, so sprint's and aiming's writes to the
    # latter simply do not apply down here.
    scale = _by_stance(ed, stance_out, COMBAT.crouch_speed_scale, COMBAT.prone_speed_scale)
    speed = _node(ed, FN_MUL_FF)
    _connect(out(ed.add_get_member_variable_node("BaseSpeed"), "BaseSpeed"), _pin(speed, "A"))
    _connect(scale, _pin(speed, "B"))
    pace = ed.add_set_member_variable_node("MaxWalkSpeedCrouched", MOVEMENT_CLASS_PATH)
    _connect(movement_out, _pin(pace, "self"))
    _connect(out(speed), _pin(pace, "MaxWalkSpeedCrouched"))
    _connect(then(mark), _pin(pace, "execute"))

    # --- stand, or crouch to the stance's height -----------------------------
    standing = _node(ed, FN_EQ_II)
    _connect(stance_out, _pin(standing, "A"))
    _set(standing, "B", STAND)
    up = ed.add_branch_node()
    _connect(out(standing), _pin(up, "Condition"))
    _connect(then(pace), _pin(up, "execute"))
    rise = _node(ed, FN_UNCROUCH)
    _connect(char_out, _pin(rise, "self"))
    _connect(then(up), _pin(rise, "execute"))

    height = _node(ed, FN_SELECT_FF)
    _set(height, "A", COMBAT.prone_half_height_cm)
    _set(height, "B", COMBAT.crouch_half_height_cm)
    is_prone = _node(ed, FN_EQ_II)
    _connect(stance_out, _pin(is_prone, "A"))
    _set(is_prone, "B", PRONE)
    _connect(out(is_prone), _pin(height, "bPickA"))
    height_out = out(height)

    capsule = ed.add_get_member_variable_node("CapsuleComponent", "/Script/Engine.Character")
    _connect(char_out, _pin(capsule, "self"))
    now_h = _node(ed, FN_CAPSULE_HALF_HEIGHT)
    _connect(out(capsule, "CapsuleComponent"), _pin(now_h, "self"))
    off = _node(ed, FN_SUB_FF)
    _connect(out(now_h), _pin(off, "A"))
    _connect(height_out, _pin(off, "B"))
    off_abs = _node(ed, FN_ABS)
    _connect(out(off), _pin(off_abs, "A"))
    wrong = _node(ed, FN_GREATER_FF)
    _connect(out(off_abs), _pin(wrong, "A"))
    _set(wrong, "B", HEIGHT_SLACK_CM)
    crouched = _node(ed, FN_IS_CROUCHING)
    _connect(movement_out, _pin(crouched, "self"))
    resize = _node(ed, FN_AND)
    _connect(out(crouched), _pin(resize, "A"))
    _connect(out(wrong), _pin(resize, "B"))

    restart = ed.add_branch_node()
    _connect(out(resize), _pin(restart, "Condition"))
    _connect(else_(up), _pin(restart, "execute"))
    _connect(then(restart), _pin(rise, "execute"))
    size = ed.add_set_member_variable_node("CrouchedHalfHeight", MOVEMENT_CLASS_PATH)
    _connect(movement_out, _pin(size, "self"))
    _connect(height_out, _pin(size, "CrouchedHalfHeight"))
    _connect(else_(restart), _pin(size, "execute"))
    duck = _node(ed, FN_CROUCH)
    _connect(char_out, _pin(duck, "self"))
    _connect(then(size), _pin(duck, "execute"))

    # --- and how loud the feet are -------------------------------------------
    comp = _node(ed, FN_GET_COMP)
    _connect(owner_out, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(FOOTSTEP_CLASS_PATH)
    as_feet = _palette(ed, NODE_CAST_FOOTSTEP)
    _connect(out(comp), _pin(as_feet, "Object"))
    for e in (then(rise), then(duck)):
        _connect(e, _pin(as_feet, "execute"))
    feet = _loose_pin(as_feet, "AsBPFootstepComponent", is_input=False)
    tail = then(as_feet)
    for var, crouch, prone in (
            ("StepVolume", COMBAT.crouch_step_volume, COMBAT.prone_step_volume),
            ("StepNoise", COMBAT.crouch_step_noise, COMBAT.prone_step_noise)):
        value = _by_stance(ed, stance_out, crouch, prone)
        write = ed.add_set_member_variable_node(var, FOOTSTEP_CLASS_PATH)
        _connect(feet, _pin(write, "self"))
        _connect(value, _pin(write, var))
        _connect(tail, _pin(write, "execute"))
        tail = then(write)

    ed.add_comment_to_nodes(
        f"{CROUCH_KEY} toggles crouch, {PRONE_KEY} toggles prone, sprinting "
        f"stands up. Both are UE's crouch: capsule half-height "
        f"{COMBAT.crouch_half_height_cm:.0f} / {COMBAT.prone_half_height_cm:.0f} cm "
        f"at {COMBAT.crouch_speed_scale:.0%} / {COMBAT.prone_speed_scale:.0%} of "
        f"BaseSpeed. Changing between the two low stances stands up for one "
        f"frame, because the movement component sizes the capsule only when a "
        f"crouch starts. Footsteps: volume x{COMBAT.crouch_step_volume} / "
        f"x{COMBAT.prone_step_volume}, noise reach x{COMBAT.crouch_step_noise} / "
        f"x{COMBAT.prone_step_noise}.",
        [n for n in ed.list_all_nodes() if n.get_name() not in before])
    return (tail, out(as_char, "CastFailed"), out(as_feet, "CastFailed"))
