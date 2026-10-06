"""verify_graphics_menu.py's checks for the death menu by mode
(menu_screens.author_death_menu): in standalone the restart, as a client of a
server a hint that a respawn is coming and nothing to press. The graph only;
`probes/probe_net_death.py` is the behaviour, in both modes.
"""

import unreal

from graphics_menu import umg_consts as C
from graphics_menu.cursor_consts import CURSOR_ACCEPT_VAR
from graphics_menu.pause_checks import _gates, _pins, _sources, _title, _value
from graphics_menu.umg_checks import text_literal

BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary


def _reach(pin, limit=400):
    """Every node the exec leaving ``pin`` runs."""
    seen, todo = [], [PIN.get_owning_node(q) for q in pin.list_connected_pins()]
    while todo and len(seen) < limit:
        cur = todo.pop()
        if cur in seen:
            continue
        seen.append(cur)
        for p in BEL.list_output_pins(cur):
            if "exec" in str(PIN.get_pin_type_display_string(p)).lower():
                todo += [PIN.get_owning_node(q) for q in p.list_connected_pins()]
    return seen


def _restarts(nodes):
    return [n for n in nodes if "LevelName" in _pins(n)]


def _polls(nodes):
    return [n for n in nodes if "Key" in _pins(n) and not _sources(n, "Key")
            and _value(n, "Key") == C.RESTART_KEY]


def check_death_menu(check, nodes):
    hints = [n for n in nodes if {"self", "InText"} <= _pins(n)
             and text_literal(n) == C.DEATH_HINT_SERVER]
    gates = [g for n in hints for g in _gates(n)
             if any("Standalone" in _title(s) for s in _sources(g, "Condition"))]
    check("the death menu asks which mode this is: one Branch on IsStandalone, whose "
          "false arm writes the hint that a respawn is coming",
          len(hints) == 1 and len(gates) == 1, f"{len(hints)} hint(s), {len(gates)} gate(s)")
    if len(gates) != 1:
        return
    alone, shared = _reach(BEL.find_then_pin(gates[0])), _reach(BEL.find_else_pin(gates[0]))
    polled = [n for n in alone for s in _sources(n, "Condition") for a in _sources(s, "A")
              if a in _polls(nodes)]
    check(f"standalone keeps the restart: [{C.RESTART_KEY}] or a click, then OpenLevel",
          len(_restarts(alone)) == 1 and len(polled) == 1,
          f"{len(_restarts(alone))} OpenLevel, {len(polled)} poll(s)")
    lowered = [n for n in shared if _title(n) == f"Set {CURSOR_ACCEPT_VAR}"
               and _value(n, CURSOR_ACCEPT_VAR) == "false"]
    check("as a client of a server nothing restarts: no OpenLevel and no key poll on "
          "that arm, and a click on the hint is lowered unserved",
          not _restarts(shared) and len(lowered) == 1
          and not any(s in _polls(nodes) for n in shared for c in _sources(n, "Condition")
                      for s in _sources(c, "A")),
          f"{len(_restarts(shared))} OpenLevel, {len(lowered)} lowered")
