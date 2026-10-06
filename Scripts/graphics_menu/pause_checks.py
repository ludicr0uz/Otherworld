"""verify_graphics_menu.py's checks for the M panel as a menu: its rows are
taken with the caret and Enter or by a click (no row has a hotkey), an open
tuning tab stands in the panel's place and has a BACK row, and the open
panel holds the player still (menu_screens, menu_nav, menu_still, tune_draw,
cursor.author_back_row, wbp_tune).

row_serves() is also what profile_checks and dev_guns_checks ask of their
rows.
"""

import unreal

from graphics_menu import cursor_consts as CC
from graphics_menu import tune_consts as TC
from graphics_menu import umg_consts as UC
from graphics_menu.menu_nav import NAV_DOWN, NAV_UP
from graphics_menu.menu_still import MENU_STILL_VAR
from graphics_menu.settings_rows import BACK_LABEL
from graphics_menu.tune_tabs import TABS
from graphics_menu.umg_checks import _tree

BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _pins(n):
    return {str(PIN.get_pin_name(p)) for p in BEL.list_input_pins(n)}


def _value(n, pin):
    return str(BEL.find_input_pin(n, pin).get_pin_value())


def _sources(n, pin):
    p = BEL.find_input_pin(n, pin)
    return [PIN.get_owning_node(q) for q in p.list_connected_pins()] if p else []


def _feeds(n, pin):
    return [_title(s) for s in _sources(n, pin)]


def _sets(nodes, var):
    return [n for n in nodes if _title(n) == f"Set {var}"]


def _gates(n):
    """The Branches whose exec runs ``n``."""
    return [g for g in _sources(n, "execute") if "Condition" in _pins(g)]


def _logic(gate):
    """The two-input nodes (AND, OR, a comparison) ``gate``'s Condition is
    made of, however deep."""
    seen, todo = [], _sources(gate, "Condition")
    while todo:
        c = todo.pop()
        if c not in seen and _pins(c) == {"A", "B"}:
            seen.append(c)
            todo += _sources(c, "A") + _sources(c, "B")
    return seen


def _is_row_test(n, action):
    """PauseClick == ``action``'s row. A literal 0 reads back empty once the
    asset is loaded from disk (row 0's)."""
    return (_pins(n) == {"A", "B"} and f"Get {CC.PAUSE_CLICK_VAR}" in _feeds(n, "A")
            and not _sources(n, "B")
            and int(_value(n, "B") or 0) == UC.PAUSE_ROW_ACTIONS.index(action))


def row_gates(n, action):
    """``n`` runs off the Branch ``action``'s row being taken is: its
    Condition is the PauseClick test itself, or an AND / OR with it."""
    for gate in _gates(n):
        for c in _sources(gate, "Condition"):
            if _is_row_test(c, action) or any(
                    _is_row_test(x, action)
                    for x in _sources(c, "A") + _sources(c, "B")):
                return True
    return False


def row_serves(nodes, action, var):
    """``action``'s row being taken is the Branch that sets ``var``: its
    Condition is the PauseClick test itself, or an AND / OR with it."""
    for n in _sets(nodes, var):
        for gate in _gates(n):
            for c in _sources(gate, "Condition"):
                if _is_row_test(c, action) or any(
                        _is_row_test(x, action)
                        for x in _sources(c, "A") + _sources(c, "B")):
                    return True
    return False


def _check_rows(check, nodes):
    check("the menu has no quality-preset rows and no hotkey in any row's label: "
          "single player, multiplayer, settings, debug, save and exit, the cheat, "
          "the six tabs, exit game",
          len(UC.PAUSE_ROW_LABELS) == len(UC.PAUSE_ROW_ACTIONS) == 13
          and not any("[" in label for label in UC.PAUSE_ROW_LABELS),
          str(UC.PAUSE_ROW_LABELS))
    # Up / Down on PauseRow, kept in the rows.
    steps = [n for n in _sets(nodes, UC.PAUSE_ROW_VAR)
             if any(t in ("Min", "Max") or "MIN" in t.upper() or "MAX" in t.upper()
                    for t in _feeds(n, UC.PAUSE_ROW_VAR))]
    keys = sorted(_value(k, "Key") for n in steps for g in _gates(n)
                  for k in _sources(g, "Condition") if "Key" in _pins(k))
    check("Up / Down move the M panel's caret (PauseRow), held inside its rows",
          keys == sorted([NAV_DOWN, NAV_UP]), f"{len(steps)} steps, {keys}")
    takes = [n for n in _sets(nodes, CC.PAUSE_CLICK_VAR)
             if _feeds(n, CC.PAUSE_CLICK_VAR) == [f"Get {UC.PAUSE_ROW_VAR}"]]
    polled = [_value(k, "Key") for n in takes for g in _gates(n)
              for k in _sources(g, "Condition") if "Key" in _pins(k)]
    check(f"{UC.PAUSE_ACCEPT_KEY} takes the row the caret is on: PauseClick := PauseRow",
          polled == [UC.PAUSE_ACCEPT_KEY], f"{len(takes)} takes, {polled}")


def _check_one_menu(check, nodes):
    panel = _tree(UC.WBP_PAUSE_MENU).get(UC.PAUSE_PANEL)
    check("the M panel's own rows are a variable of WBP_PauseMenu, so the HUD can "
          "hide them", bool(panel and panel[1]), str(panel))
    opens = {f"Get {t.open_var}" for t in TABS}
    hides = []
    for n in nodes:
        if "InVisibility" not in _pins(n) or f"Get {UC.PAUSE_PANEL}" not in _feeds(n, "self"):
            continue
        for gate in _gates(n):
            seen, todo = set(), list(_sources(gate, "Condition"))
            while todo:
                c = todo.pop()
                seen.add(_title(c))
                if _pins(c) == {"A", "B"}:
                    todo += _sources(c, "A") + _sources(c, "B")
            if opens <= seen:
                hides.append(_value(n, "InVisibility"))
    check("with a tuning tab open the M panel's rows are collapsed, and shown "
          "otherwise: one menu on screen at a time",
          sorted(hides) == sorted([UC.HIDDEN, UC.SHOWN]), str(hides))

    tree = _tree(UC.WBP_PAUSE_MENU)
    missing = [t.back_widget for t in TABS
               if not tree.get(t.back_widget) or not tree[t.back_widget][1]
               or str(tree[t.back_widget][0].get_editor_property(UC.ROW_TEXT_VAR))
               != BACK_LABEL]
    check(f"every tuning tab has a {BACK_LABEL} row, a variable under its list",
          not missing, str(missing))
    wrong = []
    for t in TABS:
        backs = [n for n in _sets(nodes, t.open_var) if _value(n, t.open_var) == "false"
                 and any(f"Get {t.row_var}" in _feeds(x, "A")
                         and int(_value(x, "B") or 0) == t.back_row
                         for g in _gates(n) for x in _logic(g)
                         if not _sources(x, "B"))]
        carets = [n for n in _sets(nodes, t.row_var) if not _sources(n, t.row_var)
                  and int(_value(n, t.row_var) or 0) == t.back_row]
        if len(backs) != 1 or len(carets) != 1:
            wrong.append((t.back_widget, len(backs), len(carets)))
    check(f"...{BACK_LABEL} shuts its tab (a click on it, or {CC.BACK_KEY} with the "
          f"caret on it, or {CC.ESCAPE_KEY}), and the cursor over it takes the caret", not wrong, str(wrong))
    reset = [t.open_var for t in TABS
             if not any(int(_value(n, t.row_var) or 0) == 0 and not _sources(n, t.row_var)
                        and row_serves(nodes, t.action, t.open_var)
                        for n in _sets(nodes, t.row_var))]
    check("each tab opens from its own M panel row, with the caret on its first row",
          not reset, str(reset))


def _check_still(check, nodes, cdo):
    stops = [n for n in nodes if "bNewMoveInput" in _pins(n)
             and _feeds(n, "bNewMoveInput") == ["Get MenuOpen"]]
    edge = [_title(f) for n in stops for f in _sources(n, "execute")]
    differs = {t for n in stops for f in _sources(n, "execute") for g in _gates(f)
               for c in _sources(g, "Condition") for t in _feeds(c, "A") + _feeds(c, "B")}
    check("the open M panel holds the player still: the controller ignores move "
          "input while MenuOpen, told once per change (MenuOpen != MenuStill)",
          len(stops) == 1 and edge == [f"Set {MENU_STILL_VAR}"]
          and differs == {"Get MenuOpen", f"Get {MENU_STILL_VAR}"}
          and cdo.get_editor_property(MENU_STILL_VAR) is False,
          f"{len(stops)} calls after {edge}, gated on {sorted(differs)}")


def _check_scroll(check, nodes):
    tree = _tree(UC.WBP_PAUSE_MENU)
    wrong = []
    for t in TABS:
        box = tree.get(t.rows_box, (None, False))[0]
        window = tree.get(f"{t.rows_box}Window", (None, False))[0]
        seeks = [n for n in nodes if "WidgetToFind" in _pins(n)
                 and f"Get {t.rows_box}" in _feeds(n, "self")]
        if t.visible_rows:
            ok = (isinstance(box, unreal.ScrollBox) and window is not None
                  and abs(window.get_editor_property("height_override")
                          - t.visible_rows * TC.TUNE_ROW_H) < 1e-3
                  and bool(box.get_editor_property("always_show_scrollbar"))
                  and len(seeks) == 1 and _value(seeks[0], "AnimateScroll") == "false")
        else:
            ok = isinstance(box, unreal.VerticalBox) and window is None and not seeks
        if not ok:
            wrong.append(t.rows_box)
    scrolling = [t.rows_box for t in TABS if t.visible_rows]
    check(f"a scrolling tab's list ({', '.join(scrolling)}) is a ScrollBox behind a "
          "window its visible rows high, the bar always shown, and DrawHUD scrolls "
          "the caret's row into view; the other tabs' lists are plain stacks",
          not wrong and bool(scrolling), str(wrong))


def check_pause_menu(check, bp, nodes):
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    _check_rows(check, nodes)
    _check_one_menu(check, nodes)
    _check_still(check, nodes, cdo)
    _check_scroll(check, nodes)
