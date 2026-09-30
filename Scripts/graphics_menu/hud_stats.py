"""DrawHUD: the player's HP and the kill counter, written into WBP_HUD.

Health is read off BP_HealthComponent rather than off the character class, so
the HUD does not care which pawn is possessed -- anything carrying the
component shows. The kill count lives on the GameMode: it has to outlast the
wanderers that earn it and the player's own components.
"""

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set
from graphics_menu.hud_flash import author_flash
from graphics_menu.ui_graph import part, set_percent, set_text
from graphics_menu.umg_consts import HP_BAR, HP_GROUP, HP_NUM, KILLS, WBP_HUD

HEALTH_CLASS_PATH = "/Game/Weapons/BP_HealthComponent.BP_HealthComponent_C"
GAME_MODE_CLASS_PATH = ("/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode"
                        ".BP_ThirdPersonGameMode_C")
KILL_COUNT_VAR = "NpcKillCount"
KILLS_PREFIX = "KILLS  "
NODE_CAST_HEALTH = "Utilities|Casting|CastToBP_HealthComponent"
NODE_CAST_GAME_MODE = "Utilities|Casting|CastToBP_ThirdPersonGameMode"

FN_GET_PLAYER_PAWN = "/Script/Engine.GameplayStatics.GetPlayerPawn"
FN_GET_COMP = "/Script/Engine.Actor.GetComponentByClass"
FN_GET_GAME_MODE = "/Script/Engine.GameplayStatics.GetGameMode"
FN_DIV = "/Script/Engine.KismetMathLibrary.Divide_DoubleDouble"
FN_ROUND = "/Script/Engine.KismetMathLibrary.Round"
FN_INT_TO_STR = "/Script/Engine.KismetStringLibrary.Conv_IntToString"
FN_CONCAT = "/Script/Engine.KismetStringLibrary.Concat_StrStr"


def author_hp(ed, x0, y0, in_execs):
    """HpBar = Health / MaxHealth, HpNum = round(Health), and the group
    blinks under a quarter (hud_flash.py). Returns the exec pins
    to go on from -- the cast-failed one too, so a pawn with no health
    component still reaches the rest of the HUD."""
    pawn = _at(_node(ed, FN_GET_PLAYER_PAWN), x0, y0 + 240)
    _set(pawn, "PlayerIndex", 0)
    comp = _at(_node(ed, FN_GET_COMP), x0 + 240, y0 + 240)
    _connect(_pin(pawn, "ReturnValue", is_input=False), _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)
    cast = _at(_palette(ed, NODE_CAST_HEALTH), x0 + 500, y0)
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(cast, "Object"))
    for e in in_execs:
        _connect(e, _pin(cast, "execute"))
    as_health = _loose_pin(cast, "AsBPHealthComponent", is_input=False)

    health = _at(ed.add_get_member_variable_node("Health", HEALTH_CLASS_PATH),
                 x0 + 760, y0 + 260)
    _connect(as_health, _pin(health, "self"))
    top = _at(ed.add_get_member_variable_node("MaxHealth", HEALTH_CLASS_PATH),
              x0 + 760, y0 + 400)
    _connect(as_health, _pin(top, "self"))
    health_out = _pin(health, "Health", is_input=False)
    frac = _at(_node(ed, FN_DIV), x0 + 1000, y0 + 320)
    _connect(health_out, _pin(frac, "A"))
    _connect(_pin(top, "MaxHealth", is_input=False), _pin(frac, "B"))
    filled = set_percent(ed, part(ed, WBP_HUD, HP_BAR, x0 + 1000, y0 + 500),
                         _pin(frac, "ReturnValue", is_input=False),
                         [BEL.find_then_pin(cast)], x0 + 1500, y0)

    # Rounded for display only: the bar reads the unrounded value, so chip
    # damage still moves it.
    rounded = _at(_node(ed, FN_ROUND), x0 + 1500, y0 + 320)
    _connect(health_out, _pin(rounded, "A"))
    as_text = _at(_node(ed, FN_INT_TO_STR), x0 + 1740, y0 + 320)
    _connect(_pin(rounded, "ReturnValue", is_input=False), _pin(as_text, "InInt"))
    shown = set_text(ed, part(ed, WBP_HUD, HP_NUM, x0 + 1740, y0 + 500),
                     _pin(as_text, "ReturnValue", is_input=False), [filled],
                     x0 + 2240, y0)
    flashed = author_flash(ed, part(ed, WBP_HUD, HP_GROUP, x0 + 2240, y0 + 800),
                           _pin(frac, "ReturnValue", is_input=False), [shown],
                           x0 + 2500, y0)
    return (flashed, _pin(cast, "CastFailed", is_input=False))


def author_kills(ed, x0, y0, in_execs):
    """Kills = "KILLS  " + GameMode.NpcKillCount. Only read here; the combat
    death path is the one writer, and only for a wanderer the player killed."""
    mode = _at(_node(ed, FN_GET_GAME_MODE), x0, y0 + 260)
    cast = _at(_palette(ed, NODE_CAST_GAME_MODE), x0 + 260, y0)
    _connect(_pin(mode, "ReturnValue", is_input=False), _pin(cast, "Object"))
    for e in in_execs:
        _connect(e, _pin(cast, "execute"))
    kills = _at(ed.add_get_member_variable_node(KILL_COUNT_VAR, GAME_MODE_CLASS_PATH),
                x0 + 520, y0 + 260)
    _connect(_loose_pin(cast, "AsBPThirdPersonGameMode", is_input=False),
             _pin(kills, "self"))
    as_text = _at(_node(ed, FN_INT_TO_STR), x0 + 760, y0 + 260)
    _connect(_pin(kills, KILL_COUNT_VAR, is_input=False), _pin(as_text, "InInt"))
    line = _at(_node(ed, FN_CONCAT), x0 + 1000, y0 + 260)
    _set(line, "A", KILLS_PREFIX)
    _connect(_pin(as_text, "ReturnValue", is_input=False), _pin(line, "B"))
    shown = set_text(ed, part(ed, WBP_HUD, KILLS, x0 + 1000, y0 + 460),
                     _pin(line, "ReturnValue", is_input=False),
                     [BEL.find_then_pin(cast)], x0 + 1500, y0)
    return (shown, _pin(cast, "CastFailed", is_input=False))
