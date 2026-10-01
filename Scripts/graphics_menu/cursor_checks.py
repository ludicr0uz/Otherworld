"""verify_graphics_menu.py's checks for the mouse cursor in the menus
(cursor.py, and what menu_nav.py adds to the key polls). The graph only: where
a row is on screen, and the click itself, need a window
(probes/probe_menu_cursor.py raises the flags a click would).
"""

import unreal

from graphics_menu import cursor_consts as CC
from graphics_menu import loot_consts as LC
from graphics_menu import umg_consts as UC
from graphics_menu.cursor import cursor_defaults
from graphics_menu.monster_tune_consts import MONSTER_TAB
from graphics_menu.tune_consts import GUN_TAB
from graphics_menu.umg_checks import _tree
from graphics_menu.world_tune_consts import WORLD_TAB

BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary
TABS = (GUN_TAB, MONSTER_TAB, WORLD_TAB)
# The row stacks the cursor is tested against: the title page, the settings
# page, the M panel, the loot window and the three tuning tabs.
ROW_LISTS = 4 + len(TABS)
# ...and the single lines a click lands on: the death menu's hint, each tab's.
CLICK_LINES = 1 + len(TABS)


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _pins(n):
    return {str(PIN.get_pin_name(p)) for p in BEL.list_input_pins(n)}


def _value(n, pin):
    return str(BEL.find_input_pin(n, pin).get_pin_value())


def _feeders(n, pin):
    return [_title(PIN.get_owning_node(q))
            for q in BEL.find_input_pin(n, pin).list_connected_pins()]


def _sets(nodes, var):
    return [n for n in nodes if _title(n) == f"Set {var}"]


def _check_show(check, nodes):
    wishes = _sets(nodes, CC.CURSOR_WANTED_VAR)
    always = [n for n in wishes if not _feeders(n, CC.CURSOR_WANTED_VAR)
              and _value(n, CC.CURSOR_WANTED_VAR) == "true"]
    alive = [n for n in wishes if _feeders(n, CC.CURSOR_WANTED_VAR)]
    asked = set()
    for n in alive:
        for q in BEL.find_input_pin(n, CC.CURSOR_WANTED_VAR).list_connected_pins():
            either = PIN.get_owning_node(q)
            asked |= set(_feeders(either, "A") + _feeders(either, "B"))
    check("the cursor is asked for on the title and death screens, and alive "
          "while the M panel or the loot window is open",
          len(always) == 2 and len(alive) == 1
          and asked == {"Get MenuOpen", f"Get {LC.LOOT_OPEN_VAR}"},
          f"{len(always)} always, {len(alive)} alive from {sorted(asked)}")

    shows = [n for n in nodes if CC_SHOW in _pins(n) and "self" in _pins(n)]
    check("...and put on the controller as bShowMouseCursor, from that wish",
          len(shows) == len(wishes) and all(
              _feeders(n, CC_SHOW) == [f"Get {CC.CURSOR_WANTED_VAR}"] for n in shows),
          str([_feeders(n, CC_SHOW) for n in shows]))
    gates = [n for n in nodes if _pins(n) == {"execute", "Condition"}
             and any("XOR" in t.upper() for t in _feeders(n, "Condition"))]
    check("...only on a change (wanted XOR shown), not every frame",
          len(gates) == len(wishes), str(len(gates)))
    free = [n for n in nodes if "InMouseLockMode" in _pins(n)]
    taken = [n for n in nodes if _pins(n) == {"execute", "PlayerController", "bFlushInput"}]
    check("shown is Game-and-UI with the cursor kept through a click; hidden "
          "is Game-only, which gives the mouse back to the camera",
          len(free) == len(wishes) == len(taken) and all(
              _value(n, "bHideCursorDuringCapture") == "false"
              and not _feeders(n, "InWidgetToFocus") for n in free),
          f"{len(free)} Game-and-UI, {len(taken)} Game-only")

    spent = [n for n in nodes if _title(n) == f"Set {CC.TRIGGER_SPENT_VAR}"]
    check("while it shows in a running game the weapon's fire press is kept "
          "spent, so a click on a row is not a shot",
          len(spent) == 1 and _value(spent[0], CC.TRIGGER_SPENT_VAR) == "true"
          and any("Cast" in t for t in _feeders(spent[0], "self")),
          str([_value(n, CC.TRIGGER_SPENT_VAR) for n in spent]))


def _check_rows(check, nodes):
    reads = [n for n in nodes if "MousePosition" in _title(n).replace(" ", "")]
    places = _sets(nodes, CC.CURSOR_POS_VAR)
    moved = _sets(nodes, CC.CURSOR_MOVED_VAR)
    check("DrawHUD reads the cursor once a frame, and whether it moved",
          len(reads) == 1 and len(places) == 1 and len(moved) == 1
          and bool(_feeders(moved[0], CC.CURSOR_MOVED_VAR)),
          f"{len(reads)} reads, {len(places)} CursorPos, {len(moved)} CursorMoved")

    tests = [n for n in nodes if {"Geometry", "AbsoluteCoordinate"} <= _pins(n)]
    wrong = [n for n in tests
             if _feeders(n, "AbsoluteCoordinate") != [f"Get {CC.CURSOR_POS_VAR}"]
             or not _feeders(n, "Geometry")]
    check(f"a row is under the cursor by its geometry: {ROW_LISTS} row lists "
          f"and {CLICK_LINES} hint lines, none hit-testable",
          len(tests) == ROW_LISTS + CLICK_LINES and not wrong,
          f"{len(tests)} tests, {len(wrong)} not off CursorPos")

    rows = _sets(nodes, CC.CURSOR_ROW_VAR)
    cleared = [n for n in rows if not _feeders(n, CC.CURSOR_ROW_VAR)]
    check("each list starts from no row, then keeps the one under the cursor",
          len(cleared) == ROW_LISTS and len(rows) == 2 * ROW_LISTS
          and all(_value(n, CC.CURSOR_ROW_VAR) == str(CC.NO_ROW) for n in cleared),
          f"{len(cleared)} cleared of {len(rows)}")

    carets = sorted(_title(n)[4:] for n in nodes if _title(n).startswith("Set ")
                    and f"Get {CC.CURSOR_ROW_VAR}" in _feeders(n, _title(n)[4:]))
    want = sorted(["MenuRow", "MenuRow", LC.LOOT_SEL_VAR, CC.PAUSE_CLICK_VAR]
                  + [t.row_var for t in TABS])
    check("the row under the cursor takes the caret (title, settings, loot, "
          "the tabs), and on the M panel a click is that row", carets == want,
          str(carets))
    stirred = [n for n in nodes if _pins(n) == {"A", "B"}
               and f"Get {CC.CURSOR_MOVED_VAR}" in _feeders(n, "A")]
    check("...only once the mouse moves or clicks, so a resting cursor does "
          "not hold the caret against Up/Down",
          len(stirred) == len(want) - 1, str(len(stirred)))


def _check_clicks(check, nodes):
    polls = [n for n in nodes if {"Key", "self"} <= _pins(n)]
    by_key = {k: [n for n in polls if _value(n, "Key") == k] for k in CC.CURSOR_KEYS}
    loose = []
    for n in by_key[CC.CLICK_KEY]:
        for q in BEL.find_output_pin(n, "ReturnValue").list_connected_pins():
            user = PIN.get_owning_node(q)
            if _pins(user) == {"execute", "Condition"}:
                continue        # the click Branch after the on-a-row Branch
            others = _feeders(user, "A") + _feeders(user, "B")
            if not any(CC.CURSOR_MOVED_VAR in t or "Under" in t for t in others):
                loose.append(_title(user))
    check("the left button is only ever read with the cursor over a row or a line",
          bool(by_key[CC.CLICK_KEY]) and not loose, str(loose))
    # Left/Right gain the wheel on the settings page and in each tuning tab.
    check("the wheel is Left/Right: the settings page and the three tabs",
          len(by_key[CC.WHEEL_MORE]) == 1 + len(TABS)
          and len(by_key[CC.WHEEL_LESS]) == 1 + len(TABS),
          f"{len(by_key[CC.WHEEL_MORE])} up, {len(by_key[CC.WHEEL_LESS])} down")

    accepts = [_value(n, CC.CURSOR_ACCEPT_VAR) for n in _sets(nodes, CC.CURSOR_ACCEPT_VAR)]
    check("a click on a title or settings row, or on the death menu's hint, "
          "raises CursorAccept, and each accept lowers it as it serves it",
          sorted(accepts) == ["false"] * 3 + ["true"] * 3, str(accepts))

    lowered = [n for n in _sets(nodes, CC.PAUSE_CLICK_VAR)
               if not _feeders(n, CC.PAUSE_CLICK_VAR)]
    served = sorted(int(_value(n, "B")) for n in nodes if _pins(n) == {"A", "B"}
                    and f"Get {CC.PAUSE_CLICK_VAR}" in _feeders(n, "A"))
    check("the M panel's clicked row is lowered every frame, and each row's "
          "key poll also answers to its own row",
          len(lowered) == 1 and _value(lowered[0], CC.PAUSE_CLICK_VAR) == str(CC.NO_ROW)
          and served == list(range(len(UC.PAUSE_ROW_KEYS))), f"{len(lowered)}, {served}")
    check("every M panel row has a key, in row order",
          len(UC.PAUSE_ROW_KEYS) == len(UC.PAUSE_ROW_LABELS)
          == len(set(UC.PAUSE_ROW_KEYS)), str(UC.PAUSE_ROW_KEYS))

    steps = [n for t in TABS for n in _sets(nodes, t.nudge_var)
             if _value(n, t.nudge_var) == "1"]
    saves = [n for t in TABS for n in _sets(nodes, t.save_var)
             if _value(n, t.save_var) == "true"]
    check("in a tuning tab a click on a row is one step up, and a click on "
          "the hint line saves: the flags Right and Enter raise",
          len(steps) == 2 * len(TABS) and len(saves) == 2 * len(TABS),
          f"{len(steps)} steps, {len(saves)} saves")


def _check_widgets(check):
    pause = _tree(UC.WBP_PAUSE_MENU)
    lines = {UC.DEATH_HINT_LINE: _tree(UC.WBP_DEATH_MENU).get(UC.DEATH_HINT_LINE)}
    lines.update({t.hint_widget: pause.get(t.hint_widget) for t in TABS})
    missing = [name for name, found in lines.items() if not found or not found[1]]
    check("the lines a click lands on are variables of their screens", not missing,
          str(missing))


CC_SHOW = "bShowMouseCursor"


def check_cursor(check, bp, nodes):
    names = {str(n) for n in BEL.list_member_variable_names(bp, False)}
    wanted = set(CC.CURSOR_BOOLS + CC.CURSOR_INTS + (CC.CURSOR_POS_VAR,))
    check("the HUD has the cursor's variables", wanted <= names, str(sorted(wanted - names)))
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    wrong = {k: cdo.get_editor_property(k) for k, v in cursor_defaults().items()
             if cdo.get_editor_property(k) != v}
    check("the cursor starts hidden, over nothing, with nothing clicked", not wrong,
          str(wrong))
    _check_widgets(check)
    _check_show(check, nodes)
    _check_rows(check, nodes)
    _check_clicks(check, nodes)
