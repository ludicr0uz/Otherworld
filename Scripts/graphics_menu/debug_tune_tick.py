"""The DEBUG SETTINGS tab's HUD Tick fragment: the tab's keys and nudge
(tune_tick._author_keys and _author_nudge, the other tabs'), the FULL STATS
cheat in place of a save, and the two switches onto the GameState.

    its menu row taken      DebugTuneOpen = NOT DebugTuneOpen; the other tabs shut
    Left / Right on a switch  it goes OFF (0) or ON (1): min 0, max 1, step 1;
                            kept in the tab's save slot (tune_keep.py)
    DebugTuneCheatRequested (Enter or a click on FULL STATS) -> lower it, then,
      where this machine owns the GameState and the pawn's parts cast
      (player_parts.py):
        Health := MaxHealth                    (BP_HealthComponent)
        Stamina := MaxStamina, SetStamina      (the weapon component's copy,
                                                and the movement's own)
        Hunger, Thirst, Temperature := their Max (BP_SurvivalComponent)
        DebugTuneCheated := true               ("... filled", until a nudge)
    DebugTuneTouched, where this machine owns the GameState:
        GameState.DebugMode  := DebugTuneValues[0] > 0.5   (monster vision, agro)
        GameState.DebugShots := DebugTuneValues[1] > 0.5   (shot trajectory)
        DebugTuneTouched := false

Applied once per change, not every Tick: nothing else writes the flags in
play, and a probe that writes one on the GameState keeps it. A client of a
server has the GameState only to read, so neither the switches nor the cheat
do anything there (the server's debug flags are the server's), and Touched
stays up: a GameState that is not there yet (a client's first frames) is
tried again next Tick.
"""

from uebp.graph import _connect, _pin, out, then
from combat import health_vars as HV
from combat.paths import HEALTH_CLASS_PATH, WEAPON_COMP_CLASS_PATH
from combat.weapon_component import vars as WV
from graphics_menu.debug_tune_consts import (
    DEBUG_SUBJECT, DEBUG_SWITCHES, DEBUG_TAB, SWITCH_ON_ABOVE)
from graphics_menu.dev_guns import _branch, _call, _get, _setter
from graphics_menu.player_parts import PAWN, author_player_parts
from graphics_menu.profile_write import copy_var
from graphics_menu.tune_tabs import other_open_vars
from graphics_menu.tune_tick import _author_keys, _author_nudge, declare_tab_vars, tab_defaults
from net.state_consts import GAME_STATE_CLASS_PATH
from net.state_graph import owned_game_state
from survival import component_vars as SC
from survival.paths import SURVIVAL_CLASS_PATH
from uebp.nodes.array import FN_ARR_GET
from uebp.nodes.math import FN_GREATER_FF
from uebp.nodes.move import FN_SET_STAMINA

# (the component, its stat, the stat's ceiling) the cheat fills.
FILLS = ((HEALTH_CLASS_PATH, HV.Health, HV.MaxHealth),
         (WEAPON_COMP_CLASS_PATH, WV.Stamina, WV.MaxStamina),
         (SURVIVAL_CLASS_PATH, SC.Hunger, SC.MaxHunger),
         (SURVIVAL_CLASS_PATH, SC.Thirst, SC.MaxThirst),
         (SURVIVAL_CLASS_PATH, SC.Temperature, SC.MaxTemperature))


def declare_debug_tune_vars(ed):
    declare_tab_vars(ed, DEBUG_TAB)


def debug_tune_defaults():
    """Both switches off; each moves 0..1 by 1."""
    n = len(DEBUG_SWITCHES)
    return {**tab_defaults(DEBUG_TAB, [DEBUG_SUBJECT], [0.0] * n, [1.0] * n, [0.0] * n),
            DEBUG_TAB.maxs_var: [1.0] * n}


def _author_cheat(ed, in_execs, made):
    """Serve the FULL STATS row (module docstring). Returns the exec tails."""
    serve, idle = _branch(ed, _get(ed, DEBUG_TAB.save_var, made), in_execs, made)
    flow = _setter(ed, DEBUG_TAB.save_var, "false", [serve], made)
    state = owned_game_state(ed, [flow])
    made += state.nodes
    flow, fails, parts = author_player_parts(ed, [state.then], made)
    for owner, stat, ceiling in FILLS:
        flow = copy_var(ed, parts[owner], owner, ceiling, parts[owner], owner, stat,
                        flow, made)
    # The stamina is the movement component's; the weapon component's is its copy.
    full = _get(ed, WV.MaxStamina, made, WEAPON_COMP_CLASS_PATH, parts[WEAPON_COMP_CLASS_PATH])
    hand = _call(ed, FN_SET_STAMINA, made, Character=parts[PAWN], NewStamina=full)
    _connect(flow, _pin(hand, "execute"))
    done = _setter(ed, DEBUG_TAB.saved_var, "true", [then(hand)], made)
    return [done, idle, *state.fails, *fails]


def _author_apply(ed, in_execs, made):
    """The switches onto the GameState, once per change. Returns the tails."""
    go, idle = _branch(ed, _get(ed, DEBUG_TAB.touched_var, made), in_execs, made)
    state = owned_game_state(ed, [go])
    made += state.nodes
    flow = state.then
    for s, (_label, flag) in enumerate(DEBUG_SWITCHES):
        cell = _call(ed, FN_ARR_GET, made, TargetArray=_get(ed, DEBUG_TAB.values_var, made),
                     Index=s)
        on = _call(ed, FN_GREATER_FF, made, A=out(cell, "Item"), B=SWITCH_ON_ABOVE)
        n = ed.add_set_member_variable_node(flag, GAME_STATE_CLASS_PATH)
        made.append(n)
        _connect(state.pin, _pin(n, "self"))
        _connect(out(on), _pin(n, flag))
        _connect(flow, _pin(n, "execute"))
        flow = then(n)
    done = _setter(ed, DEBUG_TAB.touched_var, "false", [flow], made)
    return [done, idle, *state.fails]


def author_debug_tune_tick(ed, pc_out, in_execs):
    """The whole fragment (see the module docstring). Returns the exec tails."""
    made = []
    flow = _author_keys(ed, pc_out, in_execs, made, DEBUG_TAB, other_open_vars(DEBUG_TAB))
    flow = _author_nudge(ed, flow, made, DEBUG_TAB, 1)
    flow = _author_cheat(ed, flow, made)
    tails = _author_apply(ed, flow, made)
    ed.add_comment_to_nodes(
        "Debug settings (its row in the menu): Up/Down pick a row, Left/Right "
        "switch monster vision and agro, or the shots' trajectory, OFF or ON; "
        "FULL STATS fills health, stamina, hunger, thirst and warmth. Where "
        "this machine owns the GameState: the switches go onto its DebugMode "
        "and DebugShots once per change.", made[:1])
    return tails
