"""The combat trace's on/off switch: two custom events on BP_ThirdPersonGameMode
and the default of its CombatTrace flag.

The lines themselves are written by the wanderers (npc/combat_trace.py), which
read the flag once per landed swing. This module only owns the switch.

This module owns the GameMode's EventGraph and wipes it on every build. Nothing
else authors nodes there: the other GameMode edits are variables
(game_state.ensure_game_mode_vars) and HUDClass (build_graphics_menu.py).

Why console events rather than a menu key: the trace is for troubleshooting, so
the switch should cost nothing to reach in any session and should not take up
a key on the graphics menu players see. `ke * CombatTraceOn` calls the event on
every object in the world that has it, which is the one GameMode.
"""

from combat.game_state import (
    COMBAT_TRACE_OFF_EVENT, COMBAT_TRACE_ON_EVENT, COMBAT_TRACE_PREFIX,
    COMBAT_TRACE_VAR,
)
from combat.log import _log
from uebp.graph import BGE, _apply_defaults, _assets, _connect, _node, _pin, _set, then
from uebp.layout import arrange
from combat.nodes import FN_PRINT
from combat.paths import GAME_MODE_BP_PATH
from combat.tuning import COMBAT_TRACE_DEFAULT


def _author_switch(ed, event_name, value):
    """<event> -> CombatTrace = value -> print that it changed, screen and log."""
    event = ed.add_custom_event_node(event_name)
    flip = ed.add_set_member_variable_node(COMBAT_TRACE_VAR)
    _set(flip, COMBAT_TRACE_VAR, "true" if value else "false")
    _connect(then(event), _pin(flip, "execute"))

    say = _node(ed, FN_PRINT)
    _set(say, "InString", f"{COMBAT_TRACE_PREFIX}{'on' if value else 'off'}")
    _set(say, "bPrintToScreen", "true")
    _set(say, "bPrintToLog", "true")
    _set(say, "Duration", 3.0)
    _connect(then(flip), _pin(say, "execute"))
    return [event, flip, say]


def build_combat_trace_switch():
    """Author the two console events and write CombatTrace's default.

    Run after ensure_game_mode_vars(), which declares CombatTrace. Declaring it
    resets its default to false, so the default is written here, afterwards.
    """
    eas = _assets()
    bp = eas.load_asset(GAME_MODE_BP_PATH)
    if not bp:
        raise RuntimeError(f"could not load {GAME_MODE_BP_PATH}")
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    if not ed:
        raise RuntimeError(f"{GAME_MODE_BP_PATH} has no EventGraph")
    nodes = ed.list_all_nodes()
    if nodes:
        ed.remove_nodes(nodes)

    made = (_author_switch(ed, COMBAT_TRACE_ON_EVENT, True)
            + _author_switch(ed, COMBAT_TRACE_OFF_EVENT, False))
    ed.add_comment_to_nodes(
        f"Combat trace switch. In the console: `ke * {COMBAT_TRACE_ON_EVENT}` / "
        f"`ke * {COMBAT_TRACE_OFF_EVENT}`. While on, every landed wanderer swing "
        f"logs a {COMBAT_TRACE_PREFIX.strip()} line: attacker number, its "
        f"location, the target's location.",
        made)

    arrange(ed)
    # _apply_defaults compiles, saves and reads the default back.
    _apply_defaults(bp, {COMBAT_TRACE_VAR: COMBAT_TRACE_DEFAULT})
    _log(f"{GAME_MODE_BP_PATH}: {COMBAT_TRACE_ON_EVENT} / {COMBAT_TRACE_OFF_EVENT} "
         f"events, {COMBAT_TRACE_VAR} defaults to {COMBAT_TRACE_DEFAULT}")
    return bp
