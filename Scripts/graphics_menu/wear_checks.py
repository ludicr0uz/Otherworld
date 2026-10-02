"""verify_graphics_menu.py's checks for the I panel (wear_tick, wear_draw,
wbp_wear). Here rather than in the verifier, which is over its size budget.
The weapon component's side (the wear and the take-off) is
combat/verify/wear.py's.
"""

import unreal

from combat.wear_tuning import TAKE_OFF_VAR, WORN_VAR
from combat.weapon_component.dead import OWNER_DEAD_VAR
from graphics_menu import umg_consts as UC
from graphics_menu import wear_consts as WC
from graphics_menu.umg_checks import _tree
from graphics_menu.wear_tick import WEAR_STILL_VAR, wear_defaults

BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _pins(n):
    return {str(PIN.get_pin_name(p)) for p in BEL.list_input_pins(n)}


def _value(n, pin):
    return str(BEL.find_input_pin(n, pin).get_pin_value())


def _feeders(n, pin):
    p = BEL.find_input_pin(n, pin)
    return [PIN.get_owning_node(q) for q in (p.list_connected_pins() if p else [])]


def _check_widgets(check):
    widgets = {name: w for name, (w, _var) in _tree(UC.WBP_HUD).items()}
    rows = widgets.get(WC.WEAR_ROWS_BOX)
    kids = list(rows.get_all_children()) if rows else []
    labels = [str(k.get_editor_property(UC.ROW_TEXT_VAR)) for k in kids]
    check(f"WBP_HUD has the I panel: one row per slot, labelled {list(WC.WEAR_LABELS)}, "
          "and its close line",
          WC.WEAR_PANEL in widgets and WC.WEAR_CLOSE in widgets
          and tuple(labels) == WC.WEAR_LABELS
          and all(k.get_class().get_name() == "WBP_MenuRow_C" for k in kids), str(labels))
    panel = widgets.get(WC.WEAR_PANEL)
    check("...collapsed until the HUD shows it",
          panel is not None
          and "COLLAPSED" in str(panel.get_editor_property("visibility")).upper())


def _check_keys(check, nodes):
    polls = [n for n in nodes if {"Key", "self"} <= _pins(n)
             and _value(n, "Key") == WC.WEAR_KEY]
    flips = [n for n in nodes if _title(n) == f"Set {WC.WEAR_OPEN_VAR}"
             and _feeders(n, WC.WEAR_OPEN_VAR)]
    check(f"[{WC.WEAR_KEY}] is polled once, and flips {WC.WEAR_OPEN_VAR}",
          len(polls) == 1 and len(flips) == 1, f"{len(polls)} polls, {len(flips)} flips")
    dying = [n for n in nodes if "Condition" in _pins(n)
             and [_title(f) for f in _feeders(n, "Condition")] == [f"Get {OWNER_DEAD_VAR}"]
             and any(_title(PIN.get_owning_node(q)) == f"Set {WC.WEAR_OPEN_VAR}"
                     for q in BEL.find_then_pin(n).list_connected_pins())]
    shuts = [PIN.get_owning_node(q) for n in dying
             for q in BEL.find_then_pin(n).list_connected_pins()]
    check(f"a dead player wears nothing new: {OWNER_DEAD_VAR} shuts the panel",
          len(dying) == 1 and [_value(n, WC.WEAR_OPEN_VAR) for n in shuts] == ["false"],
          str([_title(n) for n in shuts]))
    asks = [n for n in nodes if _title(n) == f"Set {TAKE_OFF_VAR}"]
    check(f"a take-off is asked of the weapon component: its {TAKE_OFF_VAR} := "
          f"{WC.WEAR_SEL_VAR}, once",
          len(asks) == 1 and [_title(f) for f in _feeders(asks[0], TAKE_OFF_VAR)]
          == [f"Get {WC.WEAR_SEL_VAR}"]
          and any("Cast" in _title(f) for f in _feeders(asks[0], "self")),
          str([[_title(f) for f in _feeders(n, TAKE_OFF_VAR)] for n in asks]))
    takes = sorted(_value(n, WC.WEAR_TAKE_VAR) for n in nodes
                   if _title(n) == f"Set {WC.WEAR_TAKE_VAR}")
    check("Enter or a click on a row raises the take-off, and Tick lowers it (and "
          "death clears it)", takes == ["false", "false", "true", "true"], str(takes))
    stills = [n for n in nodes if "bNewMoveInput" in _pins(n)
              and [_title(f) for f in _feeders(n, "bNewMoveInput")]
              == [f"Get {WC.WEAR_OPEN_VAR}"]]
    edge = [_title(f) for n in stills for f in _feeders(n, "execute")]
    check("the open panel holds the walk, told on WearOpen's edges only",
          len(stills) == 1 and edge == [f"Set {WEAR_STILL_VAR}"], str(edge))


def _check_draw(check, nodes):
    worn = [n for n in nodes if _title(n) == f"Get {WORN_VAR}"]
    check(f"the panel lists the weapon component's {WORN_VAR}, off a cast",
          len(worn) == 1 and any("Cast" in _title(f) for f in _feeders(worn[0], "self")),
          str(len(worn)))
    names = [n for n in nodes if _title(n) == "Get DisplayName"
             and any(_title(a) == f"Get {WORN_VAR}"
                     for f in _feeders(n, "self") for a in _feeders(f, "TargetArray"))]
    check("...each slot's value the worn garment's own DisplayName, read off Worn[i]",
          len(names) == 1, str(len(names)))


def check_wear(check, bp, nodes):
    _check_widgets(check)
    _check_keys(check, nodes)
    _check_draw(check, nodes)
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    wrong = {k: v for k, v in wear_defaults().items() if cdo.get_editor_property(k) != v}
    check("the I panel's variables start shut, on the first slot", not wrong, str(wrong))
