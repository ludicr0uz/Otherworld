"""The player's movement component: BP_ThirdPersonCharacter reparented onto
the native character that has it, and the numbers it moves by.

Sprint, prone and the aim-walk are movement states the owning client has to
predict and the server has to agree with, and the engine supports that only
through a C++ subclass of CharacterMovementComponent
(Source/Otherworld, OtherworldCharacterMovement; Source/CLAUDE.md). A
Character's movement component is a native subobject, so only a native class
can choose its class: OtherworldCharacter does, and the player's Blueprint
is reparented onto it here, by the weapons build (install.install_on_character).

The component decides the sprint (the stamina latch, the forward cone), the
speed of each state and the stamina. Its numbers are properties of the
character's template, written here from COMBAT and sprint_tuning, so the
server and every client read the same ones off the same asset. The jog is
its MaxWalkSpeed (player_pace.py). The graphs only hand it the keys
(weapon_component/sprint.py, stance.py, ads.py; uebp.nodes.move).
"""

import unreal

from combat.log import _log
from combat.paths import MOVE_CHARACTER_CLASS_PATH
from combat.player_pace import movement_of
from combat.sprint_tuning import SPRINT_CONE_MIN_DOT
from combat.tuning import COMBAT
from uebp.graph import BEL

# The movement template's property -> its number.
MOVE_NUMBERS = {
    "sprint_speed": COMBAT.sprint_speed_cms,
    "max_stamina": COMBAT.max_stamina,
    "stamina_drain_per_second": COMBAT.stamina_drain_per_s,
    "stamina_regen_per_second": COMBAT.stamina_regen_per_s,
    "sprint_cone_min_dot": SPRINT_CONE_MIN_DOT,
    "aim_walk_speed_scale": COMBAT.ads_move_speed_scale,
    # The walk slows along the zoom's own ease, as it did when it was read
    # off the camera's FOV.
    "aim_walk_interp_speed": COMBAT.ads_interp_speed,
    "crouch_speed_scale": COMBAT.crouch_speed_scale,
    "prone_speed_scale": COMBAT.prone_speed_scale,
    "crouch_half_height": COMBAT.crouch_half_height_cm,
    "prone_half_height": COMBAT.prone_half_height_cm,
}


def _settings(movement):
    """{property: value} of everything the stock component lets Python read."""
    kept = {}
    for name in dir(unreal.CharacterMovementComponent):
        if name.startswith("_"):
            continue
        try:
            value = movement.get_editor_property(name)
        except Exception:               # a method, or a property Python cannot read
            continue
        # Not the references to its own character's parts: the new component
        # has the new character's.
        if not isinstance(value, unreal.Object):
            kept[name] = value
    return kept


def reparent_player(bp):
    """Make ``bp`` a child of OtherworldCharacter, keeping the movement
    settings it had.

    The reparent swaps the movement subobject for one of another class. The
    engine copies the old one's properties across; this checks every one
    Python can read and writes back any that did not survive, so the stock
    template's jump, air control and braking cannot change silently.
    """
    parent = unreal.load_class(None, MOVE_CHARACTER_CLASS_PATH)
    if parent is None:
        raise RuntimeError(f"{MOVE_CHARACTER_CLASS_PATH} is not loaded: compile the "
                           f"Otherworld module (Source/CLAUDE.md)")
    if BEL.get_blueprint_parent_class(bp) == parent:
        return
    before = _settings(movement_of(bp))
    BEL.reparent_blueprint(bp, parent)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{bp.get_name()} failed to compile on its new parent")
    if BEL.get_blueprint_parent_class(bp) != parent:
        raise RuntimeError(f"{bp.get_name()} did not take {MOVE_CHARACTER_CLASS_PATH}")
    movement = movement_of(bp)
    if not isinstance(movement, unreal.OtherworldCharacterMovement):
        raise RuntimeError(f"the movement component is still a {type(movement).__name__}")
    restored = []
    for name, value in before.items():
        try:
            if movement.get_editor_property(name) == value:
                continue
            movement.set_editor_property(name, value)
        except Exception:
            continue
        restored.append(name)
    _log(f"player: reparented onto {parent.get_name()}; movement settings written "
         f"back: {restored or 'none needed'}")


def set_move_numbers(bp):
    movement = movement_of(bp)
    for name, value in MOVE_NUMBERS.items():
        movement.set_editor_property(name, value)
        got = movement.get_editor_property(name)
        if abs(got - value) > 1e-4:
            raise RuntimeError(f"{name} stayed at {got}, wanted {value}")
    _log(f"player: movement states are the movement component's "
         f"({len(MOVE_NUMBERS)} numbers written)")
