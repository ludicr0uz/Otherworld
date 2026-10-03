"""The PLAYER SETTINGS tab's HUD Tick fragment: the tab's keys, nudge and save
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

from uebp.graph import BEL, _connect, _loose_pin, _palette, _pin, out, then
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.player_tuning import (
    CM_PER_M, JOG_SPEED, PLAYER_STATS, SPRINT_DURATION, SPRINT_SPEED, STAMINA_RECHARGE,
    table,
)
from combat.sprint_tuning import (
    BASE_SPEED_VAR, SPRINT_SPEED_VAR, STAMINA_DRAIN_VAR, STAMINA_REGEN_VAR,
)
from graphics_menu.dev_guns import _branch, _call, _get
from graphics_menu.player_tune_consts import PLAYER_SUBJECT, PLAYER_TAB
from graphics_menu.tune_tabs import other_open_vars
from graphics_menu.tune_tick import author_tab_flow, declare_tab_vars, tab_defaults
from uebp.nodes.actor import FN_GET_COMP
from uebp.nodes.array import FN_ARR_GET
from uebp.nodes.math import FN_DIV_FF, FN_MUL_FF
from uebp.nodes.palette import NODE_CAST_WEAPON
from uebp.nodes.system import FN_GET_PLAYER_PAWN
from combat.weapon_component import vars as WV

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


def _value(ed, s, made):
    """PlayerTuneValues[s], a literal index."""
    cell = _call(ed, FN_ARR_GET, made, TargetArray=_get(ed, PLAYER_TAB.values_var, made), Index=s)
    return out(cell, "Item")


def _author_apply(ed, in_execs, made):
    """The table onto the player's weapon component (module docstring).
    Returns the exec tails."""
    go, idle = _branch(ed, _get(ed, PLAYER_TAB.touched_var, made), in_execs, made)
    pawn = out(_call(ed, FN_GET_PLAYER_PAWN, made, PlayerIndex=0))
    comp = _call(ed, FN_GET_COMP, made, self=pawn)
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    unreal.load_asset(WEAPON_COMP_BP_PATH)   # the cast exists only for a loaded class
    cast = _palette(ed, NODE_CAST_WEAPON)
    if not BEL.list_input_pins(cast):
        raise RuntimeError("no cast node for BP_WeaponComponent")
    made.append(cast)
    _connect(out(comp), _pin(cast, "Object"))
    _connect(go, _pin(cast, "execute"))
    wc = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)

    flow = then(cast)
    for s, (col, *_rest) in enumerate(PLAYER_STATS):
        var, kind = APPLIES[col]
        cell = _value(ed, s, made)
        if kind == SPEED:
            value = out(_call(ed, FN_MUL_FF, made, A=cell, B=CM_PER_M))
        else:
            full = _get(ed, WV.MaxStamina, made, WEAPON_COMP_CLASS_PATH, wc)
            value = out(_call(ed, FN_DIV_FF, made, A=full, B=cell))
        n = ed.add_set_member_variable_node(var, WEAPON_COMP_CLASS_PATH)
        made.append(n)
        _connect(wc, _pin(n, "self"))
        _connect(value, _pin(n, var))
        _connect(flow, _pin(n, "execute"))
        flow = then(n)
    return [flow, idle, out(cast, "CastFailed")]


def author_player_tune_tick(ed, pc_out, in_execs):
    """The whole fragment (see the module docstring). Returns the exec tails."""
    made = []
    flow = author_tab_flow(ed, pc_out, in_execs, made, PLAYER_TAB, 1, other_open_vars(PLAYER_TAB))
    tails = _author_apply(ed, flow, made)
    ed.add_comment_to_nodes(
        "Player tuning (its row in the menu): Up/Down pick a row, Left/Right "
        "change the jog's or the sprint's speed, or how long the stamina bar "
        "lasts and refills, Enter saves player_tuning.csv. Once anything is "
        "tuned, the player's weapon component takes the table each Tick.", made[:1])
    return tails
