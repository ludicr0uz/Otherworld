"""The verifiers' check for net/pause.py, shared by every graph that pauses:
each SetGamePaused(true) runs only off the true arm of a Branch on
IsStandalone, and nothing else leads into it.
"""

import unreal

BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary


def _sources(n, pin):
    p = BEL.find_input_pin(n, pin)
    return [PIN.get_owning_node(q) for q in p.list_connected_pins()] if p else []


def _is_standalone_gate(n, pause):
    asks = ["".join(str(BEL.get_node_title(c)).split()) for c in _sources(n, "Condition")]
    then = BEL.find_then_pin(n)
    return (asks == ["IsStandalone"] and then is not None
            and pause in [PIN.get_owning_node(q) for q in then.list_connected_pins()])


def check_standalone_pause(check, nodes, what):
    """``nodes``: one graph's. ``what``: whose pause it is, for the label."""
    pauses = [n for n in nodes
              if BEL.find_input_pin(n, "bPaused") is not None
              and str(BEL.find_input_pin(n, "bPaused").get_pin_value()).lower() == "true"]
    gated = [n for n in pauses
             if _sources(n, "execute")
             and all(_is_standalone_gate(g, n) for g in _sources(n, "execute"))]
    check(f"{what} pauses in standalone only: SetGamePaused(true) runs off a "
          f"Branch on IsStandalone, and a client's world runs on",
          bool(pauses) and len(gated) == len(pauses),
          f"{len(gated)} of {len(pauses)} pause(s) behind the Branch")
