"""Sprint and stamina, authored into the weapon component's Tick.
"""

from combat.graph import (
    BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set,
)
from combat.nodes import (
    FN_ACTOR_FORWARD, FN_ADD_FF, FN_AND, FN_CLAMP, FN_DOT_VV, FN_GE_FF,
    FN_IS_KEY_DOWN, FN_LAST_MOVE_INPUT, FN_LE_FF, FN_MUL_FF, FN_NORMAL, FN_NOT,
    FN_OR, FN_SELECT_FF, MOVEMENT_CLASS_PATH, NODE_CAST_CHARACTER,
)
from combat.sprint_tuning import (
    SPRINT_AHEAD_VAR, SPRINT_CONE_HALF_ANGLE_DEG, SPRINT_CONE_MIN_DOT,
    SPRINT_SPEED_VAR, STAMINA_DRAIN_VAR, STAMINA_REGEN_VAR,
)
from combat.tuning import COMBAT, SPRINT_KEY

# Set when a held sprint runs Stamina out, cleared by letting the key go.
SPRINT_SPENT_VAR = "SprintSpent"


def _author_ahead(ed, char_out, exec_in, keep, x0, y0):
    """SprintAhead: is the player steering within the cone ahead of them?

        SprintAhead = Normal(last movement input) . actor forward >= cos(cone)

    The input, not the velocity: the velocity lags a change of direction, so a
    sprint would carry on sideways for as long as the character took to turn
    its momentum. No input at all normalises to zero, whose dot is 0: standing
    still is not sprinting. Stored, because the chain is pure and the probe
    (probes/probe_sprint_forward.py) reads it. Returns the write.
    """
    steer = keep(_at(_node(ed, FN_LAST_MOVE_INPUT), x0, y0))
    _connect(char_out, _pin(steer, "self"))
    unit = keep(_at(_node(ed, FN_NORMAL), x0 + 240, y0))
    _connect(_pin(steer, "ReturnValue", is_input=False), _pin(unit, "A"))
    facing = keep(_at(_node(ed, FN_ACTOR_FORWARD), x0, y0 + 140))
    _connect(char_out, _pin(facing, "self"))
    along = keep(_at(_node(ed, FN_DOT_VV), x0 + 480, y0))
    _connect(_pin(unit, "ReturnValue", is_input=False), _pin(along, "A"))
    _connect(_pin(facing, "ReturnValue", is_input=False), _pin(along, "B"))
    inside = keep(_at(_node(ed, FN_GE_FF), x0 + 720, y0))
    _connect(_pin(along, "ReturnValue", is_input=False), _pin(inside, "A"))
    _set(inside, "B", SPRINT_CONE_MIN_DOT)
    store = keep(_at(ed.add_set_member_variable_node(SPRINT_AHEAD_VAR),
                     x0 + 960, y0))
    _connect(_pin(inside, "ReturnValue", is_input=False),
             _pin(store, SPRINT_AHEAD_VAR))
    _connect(exec_in, _pin(store, "execute"))
    return store


def _author_sprint(ed, tick, pc_out, owner_out, key_pin, exec_ins, x0, y0):
    """Hold Shift to run, while there is stamina left to spend.

    Written without a single Branch, which is not cleverness for its own sake:
    the two arms would otherwise be the same two writes with different numbers,
    and the pair could drift. SelectFloat picks the number, one write applies it:

        SprintSpent = ShiftDown AND (SprintSpent OR Stamina <= 0)
        Sprinting = ShiftDown AND NOT SprintSpent AND SprintAhead
        MaxWalkSpeed = Sprinting ? SprintSpeed : BaseSpeed
        Stamina += (Sprinting ? -StaminaDrainPerSecond
                              : +StaminaRegenPerSecond) * DeltaSeconds,  clamped

    The three rates are variables (sprint_tuning.SPRINT_RATE_VARS), built from
    COMBAT, so the menu's PLAYER TUNING tab can write them in a running game.

    SprintSpent is a latch, and it is what keeps a held key from strobing. With
    only "ShiftDown AND Stamina > 0", a sprint that ran Stamina out stopped for
    one frame, that frame's regen put Stamina back above zero, and the next
    frame sprinted again: Sprinting flipped every frame for as long as the key
    was held. Everything gated on NOT Sprinting flipped with it -- the aim, so
    the zoom and the sights camera twitched with an aim key held, and the ready
    pose, which re-equipped every frame. Latched, a spent sprint stays off (and
    Stamina refills) until the key is let go and pressed again.

    SprintAhead (_author_ahead) keeps a sprint to the way the player faces:
    sideways and backwards the key does nothing. It gates Sprinting only, not
    the latch, so turning away and back with the key held resumes the sprint.

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
    out = keep(_at(_node(ed, FN_LE_FF), x0 + 480, y0 + 560))
    _connect(stamina_out, _pin(out, "A"))
    _set(out, "B", 0.0)

    # The latch, stored before Sprinting is: this frame's sprint reads it.
    was_spent = keep(_at(ed.add_get_member_variable_node(SPRINT_SPENT_VAR),
                         x0 + 240, y0 + 760))
    done = keep(_at(_node(ed, FN_OR), x0 + 480, y0 + 720))
    _connect(_pin(was_spent, SPRINT_SPENT_VAR, is_input=False), _pin(done, "A"))
    _connect(_pin(out, "ReturnValue", is_input=False), _pin(done, "B"))
    still_spent = keep(_at(_node(ed, FN_AND), x0 + 720, y0 + 640))
    _connect(_pin(down, "ReturnValue", is_input=False), _pin(still_spent, "A"))
    _connect(_pin(done, "ReturnValue", is_input=False), _pin(still_spent, "B"))
    latch = keep(_at(ed.add_set_member_variable_node(SPRINT_SPENT_VAR),
                     x0 + 480, y0))
    _connect(_pin(still_spent, "ReturnValue", is_input=False),
             _pin(latch, SPRINT_SPENT_VAR))
    ahead = _author_ahead(ed, char_out, BEL.find_then_pin(as_char), keep,
                          x0 + 240, y0 + 940)
    _connect(BEL.find_then_pin(ahead), _pin(latch, "execute"))

    fresh = keep(_at(_node(ed, FN_NOT), x0 + 720, y0 + 300))
    _connect(_loose_pin(latch, "Output_Get", is_input=False), _pin(fresh, "A"))
    running = keep(_at(_node(ed, FN_AND), x0 + 720, y0 + 460))
    _connect(_pin(down, "ReturnValue", is_input=False), _pin(running, "A"))
    _connect(_pin(fresh, "ReturnValue", is_input=False), _pin(running, "B"))
    forwards = keep(_at(_node(ed, FN_AND), x0 + 840, y0 + 300))
    _connect(_pin(running, "ReturnValue", is_input=False), _pin(forwards, "A"))
    _connect(_loose_pin(ahead, "Output_Get", is_input=False), _pin(forwards, "B"))
    mark = keep(_at(ed.add_set_member_variable_node("Sprinting"), x0 + 960, y0))
    _connect(_pin(forwards, "ReturnValue", is_input=False), _pin(mark, "Sprinting"))
    _connect(BEL.find_then_pin(latch), _pin(mark, "execute"))
    # Read the stored flag from here on, for the same reason the NPC id is read
    # back from its variable: the AND is pure and would be re-evaluated per read.
    is_running = keep(_at(ed.add_get_member_variable_node("Sprinting"),
                          x0 + 960, y0 + 460))
    running_out = _pin(is_running, "Sprinting", is_input=False)

    base = keep(_at(ed.add_get_member_variable_node("BaseSpeed"), x0 + 1200, y0 + 300))
    pick_speed = keep(_at(_node(ed, FN_SELECT_FF), x0 + 1440, y0 + 300))
    fast = keep(_at(ed.add_get_member_variable_node(SPRINT_SPEED_VAR), x0 + 1200, y0 + 160))
    _connect(_pin(fast, SPRINT_SPEED_VAR, is_input=False), _pin(pick_speed, "A"))
    _connect(_pin(base, "BaseSpeed", is_input=False), _pin(pick_speed, "B"))
    _connect(running_out, _pin(pick_speed, "bPickA"))
    apply_speed = keep(_at(ed.add_set_member_variable_node(
        "MaxWalkSpeed", MOVEMENT_CLASS_PATH), x0 + 1700, y0))
    _connect(movement_out, _pin(apply_speed, "self"))
    _connect(_pin(pick_speed, "ReturnValue", is_input=False),
             _pin(apply_speed, "MaxWalkSpeed"))
    _connect(BEL.find_then_pin(mark), _pin(apply_speed, "execute"))

    rate = keep(_at(_node(ed, FN_SELECT_FF), x0 + 1440, y0 + 620))
    # Variables, not literals: the PLAYER TUNING tab writes them in play.
    drain = keep(_at(ed.add_get_member_variable_node(STAMINA_DRAIN_VAR), x0 + 960, y0 + 620))
    spent = keep(_at(_node(ed, FN_MUL_FF), x0 + 1200, y0 + 620))
    _connect(_pin(drain, STAMINA_DRAIN_VAR, is_input=False), _pin(spent, "A"))
    _set(spent, "B", -1.0)
    regen = keep(_at(ed.add_get_member_variable_node(STAMINA_REGEN_VAR), x0 + 1200, y0 + 780))
    _connect(_pin(spent, "ReturnValue", is_input=False), _pin(rate, "A"))
    _connect(_pin(regen, STAMINA_REGEN_VAR, is_input=False), _pin(rate, "B"))
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
        f"{SPRINT_KEY}: {SPRINT_SPEED_VAR} ({COMBAT.sprint_speed_cms:.0f} cm/s as built) "
        f"while Stamina lasts "
        f"({COMBAT.max_stamina / COMBAT.stamina_drain_per_s:.0f} s from full), refilling at "
        f"{COMBAT.stamina_regen_per_s:.0f}/s the moment it stops. Forwards only: "
        f"{SPRINT_AHEAD_VAR} is the steering within "
        f"{SPRINT_CONE_HALF_ANGLE_DEG:.0f} deg of the way the character faces. "
        f"A sprint that runs "
        f"Stamina out latches {SPRINT_SPENT_VAR} until the key is let go, so a "
        f"held key cannot flip Sprinting (and the aim with it) every frame. No Branch: "
        f"SelectFloat picks the speed and the sign of the drain, so there is one "
        f"write of each and the two arms cannot drift apart. The fire gate below "
        f"reads Sprinting -- you cannot shoot while running.",
        made)
    return (BEL.find_then_pin(spend),
            _pin(as_char, "CastFailed", is_input=False))
