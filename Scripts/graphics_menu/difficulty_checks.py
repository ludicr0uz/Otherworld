"""verify_graphics_menu.py's checks for the DIFFICULTY row and its push onto
the GameMode (graphics_menu/difficulty.py). Here rather than in the verifier,
which is over its size budget.
"""

import unreal

from combat.difficulty import DIFFICULTY_VAR
from graphics_menu import settings_rows as S
from graphics_menu.difficulty import LABELS_VAR
from graphics_menu.umg_checks import row_labels
from graphics_menu.umg_consts import SETTINGS_ROWS_BOX, WBP_MAIN_MENU

BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary


def _pins(node):
    return {str(PIN.get_pin_name(p)) for p in BEL.list_input_pins(node)}


def _value(node, pin):
    return BEL.find_input_pin(node, pin).get_pin_value()


def _sources(node, pin):
    p = BEL.find_input_pin(node, pin)
    return [str(BEL.get_node_title(PIN.get_owning_node(q))).replace("\n", " ")
            for q in (p.list_connected_pins() if p and p.is_valid() else [])]


def check_difficulty(check, bp, nodes):
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    labels = [str(x) for x in cdo.get_editor_property(LABELS_VAR)]
    check("the difficulty row names EASY, MEDIUM and SURVIVOR, in the save's order",
          labels == list(S.DIFFICULTY_LABELS) == ["EASY", "MEDIUM", "SURVIVOR"],
          str(labels))
    check("the DIFFICULTY row sits under the sliders and above the binds, so "
          "Enter on it arms no capture",
          S.DIFFICULTY_ROW == len(S.SLIDERS) and S.FIRST_BIND_ROW == S.DIFFICULTY_ROW + 1
          and S.BACK_ROW == S.SETTINGS_ROWS - 1,
          f"row {S.DIFFICULTY_ROW}, binds from {S.FIRST_BIND_ROW}")
    rows = row_labels(WBP_MAIN_MENU, SETTINGS_ROWS_BOX)
    check("the page shows the DIFFICULTY label on its row",
          rows.count(S.DIFFICULTY_LABEL) == 1
          and rows.index(S.DIFFICULTY_LABEL) == S.DIFFICULTY_ROW, str(rows))

    # Left/Right on the row: + (1 or n-1), mod n. The wrap's B is the count.
    n = len(S.DIFFICULTY_LABELS)
    steps = [x for x in nodes if _pins(x) == {"A", "B", "bPickA"}
             and _value(x, "A") == "1" and _value(x, "B") == str(n - 1)]
    check("Left and Right step the difficulty one name either way",
          len(steps) == 1, str(len(steps)))
    wraps = [x for x in nodes if _pins(x) == {"A", "B"} and _value(x, "B") == str(n)
             and "%" in str(BEL.get_node_title(x))]
    check(f"...wrapping round all {n}", len(wraps) == 1,
          str([str(BEL.get_node_title(x)) for x in wraps]))
    rows = [x for x in nodes if _pins(x) == {"A", "B"}
            and _value(x, "B") == str(S.DIFFICULTY_ROW)
            and "Get MenuRow" in _sources(x, "A")]
    check("...only on the DIFFICULTY row", len(rows) >= 1, str(len(rows)))

    sets = [x for x in nodes
            if str(BEL.get_node_title(x)) == f"Set {DIFFICULTY_VAR}"]
    targets = sorted(src for x in sets for src in _sources(x, "self"))
    check(f"{DIFFICULTY_VAR} is stored by the nudge and pushed onto the GameMode",
          len(sets) == 2 and any("Settings" in t for t in targets)
          and any("ThirdPersonGameMode" in t for t in targets),
          str(targets))
