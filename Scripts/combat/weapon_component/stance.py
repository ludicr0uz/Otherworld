"""Crouch and prone, authored into the weapon component's Tick, and the one
setting on the character's movement component that lets it crouch at all.

The stance is one integer, Stance (STAND/CROUCH/PRONE), toggled by two tapped
keys, and handed each frame to the character's movement component
(SetStance, uebp.nodes.move). Both low stances are UE's own crouch --
CharacterMovement shrinks the capsule, keeps the feet where they were and
moves the mesh so it does not sink, and the camera boom, which hangs off the
capsule, rides down with it. Prone is the same crouch to a lower height.
Nothing here moves a capsule by hand, which would have to redo all of that
and the floor checks.

How low and how fast are the movement component's (C++; the numbers are
written onto the character by combat/player_move.py): the crouch travels
with each move as the engine's own flag and "prone" as one of ours, so the
owning client predicts the capsule and the speed and the server makes the
same ones. The component resizes only as a crouch STARTS, so going from one
low stance to the other it stands and crouches again within the one step.

What a stance does to sound lives on the footstep component (StepVolume,
StepNoise), written from here every frame -- footsteps.py stays the same graph
for the player and every wanderer, and never learns what a stance is.
"""

import unreal

from combat.footsteps import FOOTSTEP_BP_PATH
from combat.log import _log
from uebp.graph import (
    _component_object, _connect, _handles, _loose_pin, _node, _palette, _pin, _set, out,
    then)
from combat.tuning import COMBAT, CROUCH_KEY, PRONE_KEY
from uebp.nodes.actor import FN_GET_COMP, FN_WAS_PRESSED
from uebp.nodes.math import FN_EQ_II, FN_SELECT_FF, FN_SELECT_II
from uebp.nodes.move import FN_SET_STANCE
from uebp.nodes.palette import NODE_CAST_FOOTSTEP
from combat.weapon_component import vars as WV

STANCE_VAR = "Stance"
STAND, CROUCH, PRONE = 0, 1, 2
FOOTSTEP_CLASS_PATH = f"{FOOTSTEP_BP_PATH}.BP_FootstepComponent_C"


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


def _author_stance_toggle(ed, pc_out, key_pins, exec_ins):
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
    _connect(out(ed.add_get_member_variable_node(WV.Sprinting), WV.Sprinting), _pin(stood, "bPickA"))

    mark = ed.add_set_member_variable_node(STANCE_VAR)
    _connect(out(stood), _pin(mark, STANCE_VAR))
    for e in exec_ins:
        _connect(e, _pin(mark, "execute"))
    return mark


def _author_stance(ed, pc_out, owner_out, key_pins, exec_ins):
    """Toggle the stance, hand it to the movement component, and tell the
    footsteps how loud it is. Runs after sprint, which it reads.

        Stance = toggled (see _author_stance_toggle)
          -> SetStance(owner, Stance)
          -> footstep component: StepVolume, StepNoise

    Returns the exec pins to carry on from.
    """
    before = {n.get_name() for n in ed.list_all_nodes()}
    mark = _author_stance_toggle(ed, pc_out, key_pins, exec_ins)
    stance = ed.add_get_member_variable_node(STANCE_VAR)
    stance_out = out(stance, STANCE_VAR)

    # --- stand, crouch or lie down -------------------------------------------
    # Every frame, not on a change: it is one write of two flags, and a
    # correction replayed on a client leaves them as the player has them.
    apply = _node(ed, FN_SET_STANCE)
    _connect(owner_out, _pin(apply, "Character"))
    _connect(stance_out, _pin(apply, "Stance"))
    _connect(then(mark), _pin(apply, "execute"))

    # --- and how loud the feet are -------------------------------------------
    comp = _node(ed, FN_GET_COMP)
    _connect(owner_out, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(FOOTSTEP_CLASS_PATH)
    as_feet = _palette(ed, NODE_CAST_FOOTSTEP)
    _connect(out(comp), _pin(as_feet, "Object"))
    _connect(then(apply), _pin(as_feet, "execute"))
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
    return (tail, out(as_feet, "CastFailed"))
