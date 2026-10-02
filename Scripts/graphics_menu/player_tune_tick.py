"""The PLAYER TUNING tab's HUD Tick fragment: the tab's keys, nudge and save
(tune_tick.author_tab_flow, shared with the other tabs), then the table onto
the player's weapon component, which owns the sprint.

    its menu row taken      PlayerTuneOpen = NOT PlayerTuneOpen; the other tabs shut
    PlayerTuneTouched, and the pawn has a BP_WeaponComponent (cast):
      BaseSpeed             := jog speed (m/s) x 100
      SprintSpeed           := sprint speed (m/s) x 100
      StaminaDrainPerSecond := MaxStamina / sprint from full (s)
      StaminaRegenPerSecond := MaxStamina / recharge to full (s)

The table is in a person's units and the component in its own; the sums are
combat/player_tuning.cms and per_second, which the build uses. Every Tick
once touched, as the guns' table: a respawned player is a new component, and
takes the tuning on its first frame. BaseSpeed is the jog everywhere: sprint
writes MaxWalkSpeed from it each frame, and the aim and the low stances
scale it. A row's minimum (PLAYER_STATS) keeps the two divisions off zero.
"""

import unreal

from combat.graph import BEL, _at, _connect, _loose_pin, _palette, _pin
from combat.nodes import FN_ARR_GET, FN_DIV_FF, FN_GET_COMP, FN_GET_PLAYER_PAWN, FN_MUL_FF
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.player_tuning import (
    CM_PER_M, JOG_SPEED, PLAYER_STATS, SPRINT_DURATION, SPRINT_SPEED, STAMINA_RECHARGE,
    table,
)
from combat.sprint_tuning import (
    BASE_SPEED_VAR, SPRINT_SPEED_VAR, STAMINA_DRAIN_VAR, STAMINA_REGEN_VAR,
)
from graphics_menu.dev_guns import _branch, _call, _get, _out
from graphics_menu.player_tune_consts import PLAYER_SUBJECT, PLAYER_TAB
from graphics_menu.tune_tabs import other_open_vars
from graphics_menu.tune_tick import (
    NODE_CAST_WEAPON, author_tab_flow, declare_tab_vars, tab_defaults,
)

# What each row writes on the component, and how: a speed is metres to
# centimetres, a time is the stamina rate that crosses the bar in it.
SPEED, TIME = "speed", "time"
APPLIES = {JOG_SPEED: (BASE_SPEED_VAR, SPEED), SPRINT_SPEED: (SPRINT_SPEED_VAR, SPEED),
           SPRINT_DURATION: (STAMINA_DRAIN_VAR, TIME),
           STAMINA_RECHARGE: (STAMINA_REGEN_VAR, TIME)}


def declare_player_tune_vars(ed):
    declare_tab_vars(ed, PLAYER_TAB)


def player_tune_defaults():
    """player_tuning.csv's numbers (else the defaults), as the build bakes them."""
    built = table()
    return tab_defaults(PLAYER_TAB, [PLAYER_SUBJECT],
                        [float(built[s[0]]) for s in PLAYER_STATS],
                        [float(s[2]) for s in PLAYER_STATS],
                        [float(s[3]) for s in PLAYER_STATS])


def _value(ed, s, x, y, made):
    """PlayerTuneValues[s], a literal index."""
    cell = _call(ed, FN_ARR_GET, x + 240, y, made,
                 TargetArray=_get(ed, PLAYER_TAB.values_var, x, y, made), Index=s)
    return _pin(cell, "Item", is_input=False)


def _author_apply(ed, in_execs, x0, y0, made):
    """The table onto the player's weapon component (module docstring).
    Returns the exec tails."""
    go, idle = _branch(ed, _get(ed, PLAYER_TAB.touched_var, x0 - 240, y0 + 300, made),
                       in_execs, x0, y0, made)
    pawn = _out(_call(ed, FN_GET_PLAYER_PAWN, x0, y0 + 440, made, PlayerIndex=0))
    comp = _call(ed, FN_GET_COMP, x0 + 260, y0 + 440, made, self=pawn)
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    unreal.load_asset(WEAPON_COMP_BP_PATH)   # the cast exists only for a loaded class
    cast = _at(_palette(ed, NODE_CAST_WEAPON), x0 + 520, y0)
    if not BEL.list_input_pins(cast):
        raise RuntimeError("no cast node for BP_WeaponComponent")
    made.append(cast)
    _connect(_out(comp), _pin(cast, "Object"))
    _connect(go, _pin(cast, "execute"))
    wc = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)

    flow, x = BEL.find_then_pin(cast), x0 + 900
    for s, (col, *_rest) in enumerate(PLAYER_STATS):
        var, kind = APPLIES[col]
        cell = _value(ed, s, x - 300, y0 + 440, made)
        if kind == SPEED:
            value = _out(_call(ed, FN_MUL_FF, x + 240, y0 + 440, made, A=cell, B=CM_PER_M))
        else:
            full = _get(ed, "MaxStamina", x - 60, y0 + 620, made, WEAPON_COMP_CLASS_PATH, wc)
            value = _out(_call(ed, FN_DIV_FF, x + 240, y0 + 440, made, A=full, B=cell))
        n = _at(ed.add_set_member_variable_node(var, WEAPON_COMP_CLASS_PATH), x + 500, y0)
        made.append(n)
        _connect(wc, _pin(n, "self"))
        _connect(value, _pin(n, var))
        _connect(flow, _pin(n, "execute"))
        flow = BEL.find_then_pin(n)
        x += 900
    return [flow, idle, _pin(cast, "CastFailed", is_input=False)]


def author_player_tune_tick(ed, pc_out, in_execs, x0, y0):
    """The whole fragment (see the module docstring). Returns the exec tails."""
    made = []
    flow = author_tab_flow(ed, pc_out, in_execs, x0, y0, made, PLAYER_TAB, 1,
                           other_open_vars(PLAYER_TAB))
    tails = _author_apply(ed, flow, x0 + 10400, y0, made)
    ed.add_comment_to_nodes(
        "Player tuning (its row in the menu): Up/Down pick a row, Left/Right "
        "change the jog's or the sprint's speed, or how long the stamina bar "
        "lasts and refills, Enter saves player_tuning.csv. Once anything is "
        "tuned, the player's weapon component takes the table each Tick.", made[:1])
    return tails
