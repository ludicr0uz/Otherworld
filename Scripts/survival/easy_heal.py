"""GA_ConsumeItem's heal: on the EASY difficulty, an item's HealthRestoreEasy
goes onto the avatar's health, clamped to MaxHealth.

A fragment of consume_ability's graph, after hunger and thirst:

    Cast GetGameMode() to BP_ThirdPersonGameMode
        --> Branch(GameMode.Difficulty == EASY)
        --> Cast Avatar.GetComponentByClass(Health) to BP_HealthComponent
        --> Health = clamp(Health + Item.HealthRestoreEasy, 0, MaxHealth)

The difficulty is read off the GameMode, where the HUD copies it from the
save every DrawHUD (graphics_menu/difficulty.py); the ability never loads the
save. A GameMode that is not BP_ThirdPersonGameMode cannot say, so its cast
failing means no heal. Every exit is handed back for EndAbility.
"""

from combat.difficulty import DIFFICULTY_VAR, EASY
from combat.graph import BEL, _connect, _loose_pin, _must_load, _node, _palette, _pin, _set
from combat.nodes import (
    FN_ADD_FF, FN_CLAMP, FN_EQ_II, FN_GET_COMP, FN_GET_GAME_MODE,
    NODE_CAST_GAME_MODE, NODE_CAST_HEALTH,
)
from combat.paths import (
    GAME_MODE_BP_PATH, GAME_MODE_CLASS_PATH, HEALTH_BP_PATH, HEALTH_CLASS_PATH,
)
from survival.paths import CONSUMABLE_CLASS_PATH

RESTORE_VAR = "HealthRestoreEasy"


def _author_easy_heal(ed, in_exec, item, avatar):
    """Returns (nodes made, the exec pins that must reach EndAbility)."""
    # Both casts exist in the palette only for loaded classes.
    for path in (GAME_MODE_BP_PATH, HEALTH_BP_PATH):
        _must_load(path)
    made = []

    def keep(n):
        made.append(n)
        return n

    mode = keep(_node(ed, FN_GET_GAME_MODE))
    # An ability supplies its own world context, so the pin is normally hidden;
    # where it is shown, the avatar's world is the one to ask.
    world = BEL.find_input_pin(mode, "WorldContextObject")
    if world and world.is_valid():
        _connect(avatar, world)
    as_mode = keep(_palette(ed, NODE_CAST_GAME_MODE))
    _connect(_pin(mode, "ReturnValue", is_input=False), _pin(as_mode, "Object"))
    _connect(in_exec, _pin(as_mode, "execute"))
    mode_out = _loose_pin(as_mode, "AsBPThirdPersonGameMode", is_input=False)

    level = keep(ed.add_get_member_variable_node(DIFFICULTY_VAR, GAME_MODE_CLASS_PATH))
    _connect(mode_out, _pin(level, "self"))
    easy = keep(_node(ed, FN_EQ_II))
    _connect(_pin(level, DIFFICULTY_VAR, is_input=False), _pin(easy, "A"))
    _set(easy, "B", EASY)
    on_easy = keep(ed.add_branch_node())
    _connect(_pin(easy, "ReturnValue", is_input=False), _pin(on_easy, "Condition"))
    _connect(BEL.find_then_pin(as_mode), _pin(on_easy, "execute"))

    comp = keep(_node(ed, FN_GET_COMP))
    _connect(avatar, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)
    as_health = keep(_palette(ed, NODE_CAST_HEALTH))
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(as_health, "Object"))
    _connect(BEL.find_then_pin(on_easy), _pin(as_health, "execute"))
    health = _loose_pin(as_health, "AsBPHealthComponent", is_input=False)

    now = keep(ed.add_get_member_variable_node("Health", HEALTH_CLASS_PATH))
    _connect(health, _pin(now, "self"))
    top = keep(ed.add_get_member_variable_node("MaxHealth", HEALTH_CLASS_PATH))
    _connect(health, _pin(top, "self"))
    gain = keep(ed.add_get_member_variable_node(RESTORE_VAR, CONSUMABLE_CLASS_PATH))
    _connect(item, _pin(gain, "self"))
    more = keep(_node(ed, FN_ADD_FF))
    _connect(_pin(now, "Health", is_input=False), _pin(more, "A"))
    _connect(_pin(gain, RESTORE_VAR, is_input=False), _pin(more, "B"))
    clamp = keep(_node(ed, FN_CLAMP))
    _connect(_pin(more, "ReturnValue", is_input=False), _pin(clamp, "Value"))
    _set(clamp, "Min", 0.0)
    _connect(_pin(top, "MaxHealth", is_input=False), _pin(clamp, "Max"))
    write = keep(ed.add_set_member_variable_node("Health", HEALTH_CLASS_PATH))
    _connect(health, _pin(write, "self"))
    _connect(_pin(clamp, "ReturnValue", is_input=False), _pin(write, "Health"))
    _connect(BEL.find_then_pin(as_health), _pin(write, "execute"))

    ed.add_comment_to_nodes(
        f"EASY only: the item's {RESTORE_VAR} onto the avatar's health, clamped "
        f"to MaxHealth. The difficulty is the GameMode's {DIFFICULTY_VAR}, which "
        "the HUD copies from the settings save.", made)
    return made, (BEL.find_then_pin(write),
                  _pin(as_mode, "CastFailed", is_input=False),
                  BEL.find_else_pin(on_easy),
                  _pin(as_health, "CastFailed", is_input=False))
