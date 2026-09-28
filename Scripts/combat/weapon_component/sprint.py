"""Sprint and stamina, authored into the weapon component's Tick.
"""

from combat.graph import (
    BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set,
)
from combat.nodes import (
    FN_ADD_FF, FN_AND, FN_CLAMP, FN_GREATER_FF, FN_IS_KEY_DOWN, FN_MUL_FF,
    FN_SELECT_FF, MOVEMENT_CLASS_PATH, NODE_CAST_CHARACTER,
)
from combat.tuning import COMBAT, SPRINT_KEY


def _author_sprint(ed, tick, pc_out, owner_out, key_pin, exec_ins, x0, y0):
    """Hold Shift to run, while there is stamina left to spend.

    Written without a single Branch, which is not cleverness for its own sake:
    the two arms would otherwise be the same two writes with different numbers,
    and the pair could drift. SelectFloat picks the number, one write applies it:

        Sprinting = ShiftDown AND Stamina > 0
        MaxWalkSpeed = Sprinting ? SPRINT_SPEED : BaseSpeed
        Stamina += (Sprinting ? -drain : +regen) * DeltaSeconds,  clamped

    BaseSpeed is whatever the character's own MaxWalkSpeed was at BeginPlay, so
    sprinting can never leave the player permanently faster or slower than the
    character asset says they are -- which is exactly what a hardcoded "walk
    speed" here would do the first time someone retuned the character.

    Stamina lives on the *weapon* component rather than on the health one
    because the HUD already casts to this component every frame for the
    inventory strip and the reticle, and because the thing sprinting interacts
    with is firing: the fire gate below reads Sprinting.

    Returns the exec pins to carry on from.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    # A cast, because MaxWalkSpeed lives on the CharacterMovementComponent and
    # GetOwner only promises an Actor. Its failure pin is a continuation: a
    # weapon component on something that is not a Character still has to fire.
    as_char = keep(_at(_palette(ed, NODE_CAST_CHARACTER), x0, y0))
    _connect(owner_out, _pin(as_char, "Object"))
    for e in exec_ins:
        _connect(e, _pin(as_char, "execute"))
    char_out = _loose_pin(as_char, "AsCharacter", is_input=False)

    movement = keep(_at(ed.add_get_member_variable_node(
        "CharacterMovement", "/Script/Engine.Character"), x0 + 240, y0 + 240))
    _connect(char_out, _pin(movement, "self"))
    movement_out = _pin(movement, "CharacterMovement", is_input=False)

    down = keep(_at(_node(ed, FN_IS_KEY_DOWN), x0 + 240, y0 + 420))
    _connect(pc_out, _pin(down, "self"))
    _connect(key_pin, _pin(down, "Key"))

    stamina = keep(_at(ed.add_get_member_variable_node("Stamina"), x0 + 240, y0 + 560))
    stamina_out = _pin(stamina, "Stamina", is_input=False)
    left = keep(_at(_node(ed, FN_GREATER_FF), x0 + 480, y0 + 560))
    _connect(stamina_out, _pin(left, "A"))
    _set(left, "B", 0.0)

    running = keep(_at(_node(ed, FN_AND), x0 + 720, y0 + 460))
    _connect(_pin(down, "ReturnValue", is_input=False), _pin(running, "A"))
    _connect(_pin(left, "ReturnValue", is_input=False), _pin(running, "B"))
    mark = keep(_at(ed.add_set_member_variable_node("Sprinting"), x0 + 960, y0))
    _connect(_pin(running, "ReturnValue", is_input=False), _pin(mark, "Sprinting"))
    _connect(BEL.find_then_pin(as_char), _pin(mark, "execute"))
    # Read the stored flag from here on, for the same reason the NPC id is read
    # back from its variable: the AND is pure and would be re-evaluated per read.
    is_running = keep(_at(ed.add_get_member_variable_node("Sprinting"),
                          x0 + 960, y0 + 460))
    running_out = _pin(is_running, "Sprinting", is_input=False)

    base = keep(_at(ed.add_get_member_variable_node("BaseSpeed"), x0 + 1200, y0 + 300))
    pick_speed = keep(_at(_node(ed, FN_SELECT_FF), x0 + 1440, y0 + 300))
    _set(pick_speed, "A", COMBAT.sprint_speed_cms)
    _connect(_pin(base, "BaseSpeed", is_input=False), _pin(pick_speed, "B"))
    _connect(running_out, _pin(pick_speed, "bPickA"))
    apply_speed = keep(_at(ed.add_set_member_variable_node(
        "MaxWalkSpeed", MOVEMENT_CLASS_PATH), x0 + 1700, y0))
    _connect(movement_out, _pin(apply_speed, "self"))
    _connect(_pin(pick_speed, "ReturnValue", is_input=False),
             _pin(apply_speed, "MaxWalkSpeed"))
    _connect(BEL.find_then_pin(mark), _pin(apply_speed, "execute"))

    rate = keep(_at(_node(ed, FN_SELECT_FF), x0 + 1440, y0 + 620))
    _set(rate, "A", -COMBAT.stamina_drain_per_s)
    _set(rate, "B", COMBAT.stamina_regen_per_s)
    _connect(running_out, _pin(rate, "bPickA"))
    step = keep(_at(_node(ed, FN_MUL_FF), x0 + 1700, y0 + 620))
    _connect(_pin(rate, "ReturnValue", is_input=False), _pin(step, "A"))
    _connect(_pin(tick, "DeltaSeconds", is_input=False), _pin(step, "B"))
    moved = keep(_at(_node(ed, FN_ADD_FF), x0 + 1940, y0 + 620))
    _connect(stamina_out, _pin(moved, "A"))
    _connect(_pin(step, "ReturnValue", is_input=False), _pin(moved, "B"))
    held_in = keep(_at(_node(ed, FN_CLAMP), x0 + 2180, y0 + 620))
    _connect(_pin(moved, "ReturnValue", is_input=False), _pin(held_in, "Value"))
    _set(held_in, "Min", 0.0)
    _set(held_in, "Max", COMBAT.max_stamina)
    spend = keep(_at(ed.add_set_member_variable_node("Stamina"), x0 + 2420, y0))
    _connect(_pin(held_in, "ReturnValue", is_input=False), _pin(spend, "Stamina"))
    _connect(BEL.find_then_pin(apply_speed), _pin(spend, "execute"))

    ed.add_comment_to_nodes(
        f"{SPRINT_KEY}: {COMBAT.sprint_speed_cms:.0f} cm/s while Stamina lasts "
        f"({COMBAT.max_stamina / COMBAT.stamina_drain_per_s:.0f} s from full), refilling at "
        f"{COMBAT.stamina_regen_per_s:.0f}/s the moment it is let go. No Branch: "
        f"SelectFloat picks the speed and the sign of the drain, so there is one "
        f"write of each and the two arms cannot drift apart. The fire gate below "
        f"reads Sprinting -- you cannot shoot while running.",
        made)
    return (BEL.find_then_pin(spend),
            _pin(as_char, "CastFailed", is_input=False))
