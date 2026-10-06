"""DrawHUD: the player's HP and the kill counter, written into WBP_HUD.

Health is read off BP_HealthComponent rather than off the character class, so
the HUD does not care which pawn is possessed -- anything carrying the
component shows. The kill count is the player's own, on their PlayerState
(net/state_consts.py): it outlasts the wanderers that earn it and the
player's own components, and a client of a server can read it.
"""

from uebp.graph import _connect, _loose_pin, _node, _palette, _pin, _set, out, then
from graphics_menu.hud_flash import author_flash
from graphics_menu.ui_graph import part, set_percent, set_text
from graphics_menu.umg_consts import HP_BAR, HP_GROUP, HP_NUM, KILLS, WBP_HUD
from uebp.nodes.actor import FN_GET_COMP, FN_GET_OWNING_PAWN, FN_GET_OWNING_PC
from uebp.nodes.math import FN_DIV_FF, FN_ROUND
from uebp.nodes.palette import NODE_CAST_HEALTH
from uebp.nodes.system import FN_CONCAT, FN_INT_TO_STR
from net.state_consts import PLAYER_STATE_CLASS_PATH
from net.state_graph import CONTROLLER_CLASS_PATH, player_state_of
from combat import health_vars as HV

HEALTH_CLASS_PATH = "/Game/Weapons/BP_HealthComponent.BP_HealthComponent_C"
KILL_COUNT_VAR = "NpcKillCount"
KILLS_PREFIX = "KILLS  "


def author_hp(ed, in_execs):
    """HpBar = Health / MaxHealth, HpNum = round(Health), and the group
    blinks under a quarter (hud_flash.py). Returns the exec pins
    to go on from -- the cast-failed one too, so a pawn with no health
    component still reaches the rest of the HUD."""
    pawn = _node(ed, FN_GET_OWNING_PAWN)
    comp = _node(ed, FN_GET_COMP)
    _connect(out(pawn), _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)
    cast = _palette(ed, NODE_CAST_HEALTH)
    _connect(out(comp), _pin(cast, "Object"))
    for e in in_execs:
        _connect(e, _pin(cast, "execute"))
    as_health = _loose_pin(cast, "AsBPHealthComponent", is_input=False)

    health = ed.add_get_member_variable_node(HV.Health, HEALTH_CLASS_PATH)
    _connect(as_health, _pin(health, "self"))
    top = ed.add_get_member_variable_node(HV.MaxHealth, HEALTH_CLASS_PATH)
    _connect(as_health, _pin(top, "self"))
    health_out = out(health, HV.Health)
    frac = _node(ed, FN_DIV_FF)
    _connect(health_out, _pin(frac, "A"))
    _connect(out(top, HV.MaxHealth), _pin(frac, "B"))
    filled = set_percent(ed, part(ed, WBP_HUD, HP_BAR), out(frac), [then(cast)])

    # Rounded for display only: the bar reads the unrounded value, so chip
    # damage still moves it.
    rounded = _node(ed, FN_ROUND)
    _connect(health_out, _pin(rounded, "A"))
    as_text = _node(ed, FN_INT_TO_STR)
    _connect(out(rounded), _pin(as_text, "InInt"))
    shown = set_text(ed, part(ed, WBP_HUD, HP_NUM), out(as_text), [filled])
    flashed = author_flash(ed, part(ed, WBP_HUD, HP_GROUP), out(frac), [shown])
    return (flashed, out(cast, "CastFailed"))


def author_kills(ed, in_execs):
    """Kills = "KILLS  " + this player's NpcKillCount, off the owning
    controller's PlayerState. Only read here; the combat death path is the
    one writer, on the server, and only for a wanderer a player killed."""
    owner = _node(ed, FN_GET_OWNING_PC)
    mine = player_state_of(ed, out(owner), CONTROLLER_CLASS_PATH, in_execs)
    kills = ed.add_get_member_variable_node(KILL_COUNT_VAR, PLAYER_STATE_CLASS_PATH)
    _connect(mine.pin, _pin(kills, "self"))
    as_text = _node(ed, FN_INT_TO_STR)
    _connect(out(kills, KILL_COUNT_VAR), _pin(as_text, "InInt"))
    line = _node(ed, FN_CONCAT)
    _set(line, "A", KILLS_PREFIX)
    _connect(out(as_text), _pin(line, "B"))
    shown = set_text(ed, part(ed, WBP_HUD, KILLS), out(line), [mine.then])
    return (shown, *mine.fails)
