"""verify_graphics_menu.py's checks for the mouse cursor in the menus
(cursor.py, and what menu_nav.py adds to the key polls). The graph only: where
a row is on screen, and the click itself, need a window
(probes/probe_menu_cursor.py raises the flags a click would).
"""

import unreal

from graphics_menu import cursor_consts as CC
from graphics_menu import loot_consts as LC
from graphics_menu import tune_tab as TT
from graphics_menu import umg_consts as UC
from graphics_menu.cursor import cursor_defaults
from graphics_menu.monster_tune_consts import MONSTER_TAB
from graphics_menu.gfx_tune_consts import GFX_TAB
from graphics_menu.tune_consts import GUN_TAB
from graphics_menu.umg_checks import _tree
from graphics_menu.world_tune_consts import WORLD_TAB

BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary
TABS = (GUN_TAB, MONSTER_TAB, WORLD_TAB, GFX_TAB)
# The row stacks the cursor is tested against: the title page, the settings
# page, the M panel, the loot window and the four tuning tabs.
ROW_LISTS = 4 + len(TABS)
# ...and the single lines a click lands on: the death menu's hint, the loot
# window's close button, each tab's hint and each tab's BACK row.
CLICK_LINES = 2 + 2 * len(TABS)
# A scrolling tab's rows count only inside its list's window: one more test.
WINDOWS = sum(1 for t in TABS if t.visible_rows)


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
    check(f"a row is under the cursor by its geometry: {ROW_LISTS} row lists, "
          f"{CLICK_LINES} hint and BACK lines and {WINDOWS} scrolling list's "
          "window, none hit-testable",
          len(tests) == ROW_LISTS + CLICK_LINES + WINDOWS and not wrong,
          f"{len(tests)} tests, {len(wrong)} not off CursorPos")

    rows = _sets(nodes, CC.CURSOR_ROW_VAR)
    cleared = [n for n in rows if not _feeders(n, CC.CURSOR_ROW_VAR)]
    check("each list starts from no row, then keeps the one under the cursor",
          len(cleared) == ROW_LISTS and len(rows) == 2 * ROW_LISTS
          and all(_value(n, CC.CURSOR_ROW_VAR) == str(CC.NO_ROW) for n in cleared),
          f"{len(cleared)} cleared of {len(rows)}")

    carets = sorted(_title(n)[4:] for n in nodes if _title(n).startswith("Set ")
                    and f"Get {CC.CURSOR_ROW_VAR}" in _feeders(n, _title(n)[4:]))
    want = sorted(["MenuRow", "MenuRow", LC.LOOT_SEL_VAR, UC.PAUSE_ROW_VAR,
                   CC.PAUSE_CLICK_VAR] + [t.row_var for t in TABS])
    check("the row under the cursor takes the caret (title, settings, the M "
          "panel, loot, the tabs), and on the M panel a click takes that row",
          carets == want, str(carets))
    stirred = [n for n in nodes if _pins(n) == {"A", "B"}
               and f"Get {CC.CURSOR_MOVED_VAR}" in _feeders(n, "A")]
    # One per list (PauseClick is a click, not a caret), and one per BACK row.
    check("...only once the mouse moves or clicks, so a resting cursor does "
          "not hold the caret against Up/Down",
          len(stirred) == len(want) - 1 + len(TABS), str(len(stirred)))


def _click_served(nodes, key, action, var):
    """``key``'s poll OR ``action``'s M-panel row taken is the Branch that
    sets ``var``."""
    row = UC.PAUSE_ROW_ACTIONS.index(action)
    for n in _sets(nodes, var):
        for q in BEL.find_input_pin(n, "execute").list_connected_pins():
            gate = PIN.get_owning_node(q)
            if "Condition" not in _pins(gate):
                continue
            for c in BEL.find_input_pin(gate, "Condition").list_connected_pins():
                either = PIN.get_owning_node(c)
                if _pins(either) != {"A", "B"}:
                    continue
                keys = [_value(PIN.get_owning_node(a), "Key")
                        for a in BEL.find_input_pin(either, "A").list_connected_pins()]
                rows = [int(_value(PIN.get_owning_node(b), "B") or 0)
                        for b in BEL.find_input_pin(either, "B").list_connected_pins()
                        if f"Get {CC.PAUSE_CLICK_VAR}"
                        in _feeders(PIN.get_owning_node(b), "A")]
                if keys == [key] and rows == [row]:
                    return True
    return False


def _on_line_click(n):
    """``n`` runs off a Branch on (left button pressed AND cursor over a widget)."""
    for q in BEL.find_input_pin(n, "execute").list_connected_pins():
        gate = PIN.get_owning_node(q)
        if "Condition" not in _pins(gate):
            continue
        for c in BEL.find_input_pin(gate, "Condition").list_connected_pins():
            both = PIN.get_owning_node(c)
            if _pins(both) != {"A", "B"}:
                continue
            polls = [_value(PIN.get_owning_node(a), "Key")
                     for a in BEL.find_input_pin(both, "A").list_connected_pins()
                     if "Key" in _pins(PIN.get_owning_node(a))]
            under = [PIN.get_owning_node(b)
                     for b in BEL.find_input_pin(both, "B").list_connected_pins()]
            if polls == [CC.CLICK_KEY] and any("Geometry" in _pins(u) for u in under):
                return True
    return False


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
    # Left/Right gain the wheel on the settings page and in each tuning tab;
    # in a scrolling tab it is Up/Down's instead, and the list follows.
    check("the wheel is Left/Right: the settings page and the four tabs",
          len(by_key[CC.WHEEL_MORE]) == 1 + len(TABS)
          and len(by_key[CC.WHEEL_LESS]) == 1 + len(TABS),
          f"{len(by_key[CC.WHEEL_MORE])} up, {len(by_key[CC.WHEEL_LESS])} down")
    # Each wheel poll is OR'd with a key poll: which key says what it moves.
    paired = {}
    for wheel in (CC.WHEEL_MORE, CC.WHEEL_LESS):
        for n in by_key[wheel]:
            for q in BEL.find_output_pin(n, "ReturnValue").list_connected_pins():
                either = PIN.get_owning_node(q)
                for a in BEL.find_input_pin(either, "A").list_connected_pins():
                    key = _value(PIN.get_owning_node(a), "Key")
                    paired[(wheel, key)] = paired.get((wheel, key), 0) + 1
    check(f"...except in a scrolling tab ({WINDOWS}), where it is Up/Down: the "
          "caret moves and the list follows it",
          paired == {(CC.WHEEL_MORE, TT.TUNE_MORE): 1 + len(TABS) - WINDOWS,
                     (CC.WHEEL_LESS, TT.TUNE_LESS): 1 + len(TABS) - WINDOWS,
                     (CC.WHEEL_MORE, TT.TUNE_UP): WINDOWS,
                     (CC.WHEEL_LESS, TT.TUNE_DOWN): WINDOWS} and WINDOWS > 0,
          str(paired))

    accepts = [_value(n, CC.CURSOR_ACCEPT_VAR) for n in _sets(nodes, CC.CURSOR_ACCEPT_VAR)]
    check("a click on a title or settings row, or on the death menu's hint, "
          "raises CursorAccept, and each accept lowers it as it serves it",
          sorted(accepts) == ["false"] * 3 + ["true"] * 3, str(accepts))

    lowered = [n for n in _sets(nodes, CC.PAUSE_CLICK_VAR)
               if not _feeders(n, CC.PAUSE_CLICK_VAR)]
    # A literal 0 reads back empty once the asset is loaded from disk (row 0's).
    served = sorted(int(_value(n, "B") or 0) for n in nodes if _pins(n) == {"A", "B"}
                    and f"Get {CC.PAUSE_CLICK_VAR}" in _feeders(n, "A"))
    check("the M panel's taken row is lowered every frame, and each row's "
          "action answers to its own row",
          len(lowered) == 1 and _value(lowered[0], CC.PAUSE_CLICK_VAR) == str(CC.NO_ROW)
          and served == list(range(len(UC.PAUSE_ROW_ACTIONS))), f"{len(lowered)}, {served}")
    check("the M panel's last row is its close button: taking it shuts the "
          f"panel, as [{UC.MENU_KEY}] does",
          UC.PAUSE_ROW_LABELS[-1] == UC.PAUSE_CLOSE_ROW_LABEL
          and UC.PAUSE_ROW_ACTIONS[-1] == UC.CLOSE_ACTION
          and _click_served(nodes, UC.MENU_KEY, UC.CLOSE_ACTION, "MenuOpen"),
          f"{UC.PAUSE_ROW_LABELS[-1]!r}, action {UC.PAUSE_ROW_ACTIONS[-1]}")
    shuts = [n for n in _sets(nodes, LC.LOOT_OPEN_VAR)
             if _value(n, LC.LOOT_OPEN_VAR) == "false" and _on_line_click(n)]
    check("a click on the loot window's close button lowers LootOpen, as "
          f"[{LC.LOOT_KEY}] does", len(shuts) == 1, str(len(shuts)))
    check("every M panel row has an action of its own, in row order",
          len(UC.PAUSE_ROW_ACTIONS) == len(UC.PAUSE_ROW_LABELS)
          == len(set(UC.PAUSE_ROW_ACTIONS)), str(UC.PAUSE_ROW_ACTIONS))

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
    lines[LC.LOOT_CLOSE] = _tree(UC.WBP_HUD).get(LC.LOOT_CLOSE)
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
