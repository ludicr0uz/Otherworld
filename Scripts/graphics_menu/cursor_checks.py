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
from graphics_menu.inv_consts import DRAG_FROM_VAR, INV_AREAS, INV_OVER_VAR, SLOT_BOXES
from graphics_menu.tune_scroll import hidden_rows, rows_per_window, thumb_half
from graphics_menu.profile_consts import EXIT_ACTION
from graphics_menu.mode_consts import PAGES
from graphics_menu.tune_tabs import TABS
from graphics_menu.umg_checks import _tree
from graphics_menu.wear_consts import WEAR_OPEN_VAR, WEAR_SEL_VAR

BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary
# The row stacks the cursor is tested against: the menu (the title's too), its
# settings page, the loot window, the I panel, the tuning tabs, and the
# inventory's three grids of slots (inv_drag.py), and the title's two mode
# pages (mode_draw.py).
ROW_LISTS = 4 + len(TABS) + len(SLOT_BOXES) + len(PAGES)
# ...and the single lines a click lands on: the death menu's hint, the loot
# window's and the I panel's close buttons, the settings page's BACK row, each
# tab's hint and each tab's BACK row, and each mode page's BACK row.
CLICK_LINES = 4 + 2 * len(TABS) + len(PAGES)
# A scrolling tab's rows count only inside its list's window: one more test.
# Its bar's drag reads the list's box twice more: the press on it, and how far
# down it the cursor is (tune_scroll.py).
WINDOWS = sum(1 for t in TABS if t.visible_rows)
# The inventory's drag: a release over no slot is tested against each of the
# inventory's areas, and the carried icon is placed by one read of the
# cursor in the Body's space (inv_drag.py, inv_carry.py).
DRAG_TESTS = len(INV_AREAS) + 1


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
    def ored(node):
        """The variables an OR tree over Gets reads."""
        out = set()
        for pin in ("A", "B"):
            for q in BEL.find_input_pin(node, pin).list_connected_pins():
                f = PIN.get_owning_node(q)
                out |= ored(f) if _title(f).startswith("OR") else {_title(f)}
        return out

    asked = set()
    for n in alive:
        for q in BEL.find_input_pin(n, CC.CURSOR_WANTED_VAR).list_connected_pins():
            asked |= ored(PIN.get_owning_node(q))
    check("the cursor is asked for on the death screen, and otherwise while the "
          "menu (held open on the title), the loot window or the I panel is open",
          len(always) == 1 and len(alive) == 1
          and asked == {"Get MenuOpen", f"Get {LC.LOOT_OPEN_VAR}",
                        f"Get {WEAR_OPEN_VAR}"},
          f"{len(always)} always, {len(alive)} alive from {sorted(asked)}")

    shows = [n for n in nodes if CC_SHOW in _pins(n) and "self" in _pins(n)]
    check("...and put on the controller as bShowMouseCursor, from that wish",
          len(shows) == len(wishes) and all(
              _feeders(n, CC_SHOW) == [f"Get {CC.CURSOR_WANTED_VAR}"] for n in shows),
          str([_feeders(n, CC_SHOW) for n in shows]))
    def reads(node, pin, depth=6):
        """The titles of the pure nodes behind ``pin``, a few links deep."""
        found = set()
        for q in BEL.find_input_pin(node, pin).list_connected_pins():
            f = PIN.get_owning_node(q)
            found.add(_title(f))
            if depth:
                for name in _pins(f) - {"self", "execute"}:
                    found |= reads(f, name, depth - 1)
        return found

    gates = [n for n in nodes if _pins(n) == {"execute", "Condition"}
             and any("XOR" in t.upper() for t in reads(n, "Condition", 1))]
    check("...only on a change (wanted XOR shown), not every frame of play",
          len(gates) == len(wishes), str(len(gates)))
    again = [reads(n, "Condition") for n in gates]
    check("...and on the title every frame the left button is up: a launched "
          "game's window takes the mouse after the first one",
          bool(again) and all(
              f"Get {UC.GAME_STARTED_VAR}" in r and f"Get {CC.CURSOR_WANTED_VAR}" in r
              and any("KeyDown" in t.replace(" ", "") for t in r) for r in again),
          str([sorted(r) for r in again]))
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
          f"{CLICK_LINES} hint (or save row) and BACK lines and {WINDOWS} scrolling list's "
          "window (and its bar: the press, and where the drag is), and the "
          f"inventory drag's {DRAG_TESTS} (its areas, and the carried icon's place), "
          "none hit-testable",
          len(tests) == ROW_LISTS + CLICK_LINES + 3 * WINDOWS + DRAG_TESTS and not wrong,
          f"{len(tests)} tests, {len(wrong)} not off CursorPos")

    rows = _sets(nodes, CC.CURSOR_ROW_VAR)
    cleared = [n for n in rows if not _feeders(n, CC.CURSOR_ROW_VAR)]
    check("each list starts from no row, then keeps the one under the cursor",
          len(cleared) == ROW_LISTS and len(rows) == 2 * ROW_LISTS
          and all(_value(n, CC.CURSOR_ROW_VAR) == str(CC.NO_ROW) for n in cleared),
          f"{len(cleared)} cleared of {len(rows)}")

    carets = sorted(_title(n)[4:] for n in nodes if _title(n).startswith("Set ")
                    and f"Get {CC.CURSOR_ROW_VAR}" in _feeders(n, _title(n)[4:]))
    clicks = [CC.PAUSE_CLICK_VAR] + [CC.PAGE_CLICK_VAR] * len(PAGES)
    want = sorted(["MenuRow"] * (1 + len(PAGES))
                  + [LC.LOOT_SEL_VAR, WEAR_SEL_VAR, UC.PAUSE_ROW_VAR]
                  + clicks + [t.row_var for t in TABS])
    check("the row under the cursor takes the caret (the menu, its settings "
          "page and mode pages, loot, the I panel, the tabs), and on the menu "
          "and a mode page a click takes that row",
          carets == want, str(carets))
    stirred = [n for n in nodes if _pins(n) == {"A", "B"}
               and f"Get {CC.CURSOR_MOVED_VAR}" in _feeders(n, "A")]
    # One per list (PauseClick and PageClick are clicks, not carets), one per
    # BACK row (the tabs', the settings page's, the mode pages') and one per
    # save row (the graphics tab's SAVE DEFAULT).
    buttons = len(TABS) + 1 + len(PAGES) + sum(1 for t in TABS if t.save_widget)
    check("...only once the mouse moves or clicks, so a resting cursor does "
          "not hold the caret against Up/Down",
          len(stirred) == len(want) - len(clicks) + buttons, str(len(stirred)))


def _gates(n):
    """The Branches whose exec runs ``n``."""
    return [g for g in (PIN.get_owning_node(q) for q in
                        BEL.find_input_pin(n, "execute").list_connected_pins())
            if "Condition" in _pins(g)]


def _row_served(nodes, action, var, value):
    """``action``'s menu row taken is the Branch that sets ``var`` to
    ``value``."""
    row = UC.PAUSE_ROW_ACTIONS.index(action)
    for n in _sets(nodes, var):
        if _value(n, var) != value:
            continue
        for gate in _gates(n):
            for c in BEL.find_input_pin(gate, "Condition").list_connected_pins():
                eq = PIN.get_owning_node(c)
                # A literal 0 reads back empty once loaded from disk (row 0's).
                # (A bool pin's reads "false": an AND or an OR is no row test.)
                if (_pins(eq) == {"A", "B"} and (_value(eq, "B") or "0").isdigit()
                        and int(_value(eq, "B") or 0) == row
                        and f"Get {CC.PAUSE_CLICK_VAR}" in _feeders(eq, "A")):
                    return True
    return False


def _key_toggles(nodes, key, var, only_while):
    """``key``'s poll is the Branch that flips ``var``, and it is polled only
    behind a Branch on ``only_while``."""
    for n in _sets(nodes, var):
        if not any("NOT" in t.upper() for t in _feeders(n, var)):
            continue
        for gate in _gates(n):
            keys = [_value(PIN.get_owning_node(c), "Key")
                    for c in BEL.find_input_pin(gate, "Condition").list_connected_pins()
                    if "Key" in _pins(PIN.get_owning_node(c))]
            outer = [t for g in _gates(gate) for t in _feeders(g, "Condition")]
            if keys == [key] and outer == [f"Get {only_while}"]:
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


def _on_slot(user):
    """``user`` (an AND) also tests the slot under the cursor or the drag:
    a node feeding it reads InvOver or InvDragFrom (inv_drag.py)."""
    for pin in ("A", "B"):
        for q in BEL.find_input_pin(user, pin).list_connected_pins():
            feeder = PIN.get_owning_node(q)
            for inner in ("A", "B"):
                if inner in _pins(feeder) and any(
                        t in (f"Get {INV_OVER_VAR}", f"Get {DRAG_FROM_VAR}")
                        for t in _feeders(feeder, inner)):
                    return True
    return False


def _users(n):
    return [PIN.get_owning_node(q)
            for q in BEL.find_output_pin(n, "ReturnValue").list_connected_pins()]


def _check_scroll_drag(check, nodes):
    """Each scrolling tab's bar: a press in the list's box off its rows grabs
    it, and while grabbed the list's offset and the caret come from ScrollAt."""
    wrong = []
    for t in TABS:
        moves = [n for n in nodes if "NewScrollOffset" in _pins(n)
                 and f"Get {t.rows_box}" in _feeders(n, "self")]
        if not t.visible_rows:
            if moves:
                wrong.append(f"{t.rows_box}: scrolled, though it is no scrolling list")
            continue
        # ScrollAt less half the thumb, times the rows a window's height is.
        pasts = [n for n in nodes if _pins(n) == {"A", "B"}
                 and _feeders(n, "A") == [f"Get {CC.SCROLL_AT_VAR}"]
                 and abs(float(_value(n, "B") or 0) - thumb_half(t)) < 1e-6]
        scaled = [u for n in pasts for u in _users(n) if _pins(u) == {"A", "B"}
                  and abs(float(_value(u, "B") or 0) - rows_per_window(t)) < 1e-6]
        if len(moves) != 1 or not scaled:
            wrong.append(f"{t.rows_box}: {len(moves)} offset writes, {len(scaled)} sums of "
                         f"{CC.SCROLL_AT_VAR} onto its {hidden_rows(t)} hidden rows")
    grabs = sorted(_value(n, CC.SCROLL_GRAB_VAR) for n in _sets(nodes, CC.SCROLL_GRAB_VAR))
    ats = _sets(nodes, CC.SCROLL_AT_VAR)
    check(f"a scrolling list's bar is dragged ({WINDOWS} tabs): {CC.SCROLL_GRAB_VAR} is "
          f"raised and lowered once per tab, {CC.SCROLL_AT_VAR} written once, and the "
          "list's offset is that mapped onto the rows its window hides",
          not wrong and WINDOWS > 0 and grabs == ["false"] * WINDOWS + ["true"] * WINDOWS
          and len(ats) == WINDOWS, f"{wrong}, grabs {grabs}, {len(ats)} writes")


def _title_wait(user):
    """``user`` is the cursor mode's "the left button is up", ANDed with "the
    game has not started": the title giving its input mode again."""
    if _pins(user) != {"A"}:
        return False
    return any(f"Get {UC.GAME_STARTED_VAR}" in _feeders(f, "A")
               for u in _users(user) for pin in ("A", "B") if pin in _pins(u)
               for q in BEL.find_input_pin(u, pin).list_connected_pins()
               for f in [PIN.get_owning_node(q)] if _pins(f) == {"A"})


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
            if not any(CC.CURSOR_MOVED_VAR in t or "Under" in t for t in others) \
                    and not _on_slot(user) and not _title_wait(user):
                loose.append(_title(user))
    check("the left button is only ever read with the cursor over a row or a line "
          "(or, in the I panel, a slot: InvOver, or a drag begun on one)",
          bool(by_key[CC.CLICK_KEY]) and not loose, str(loose))
    wheel = [_title(n) for n in polls if _value(n, "Key") in CC.WHEEL_KEYS]
    check("no menu reads the mouse wheel: nothing polls its keys", not wheel, str(wheel))
    _check_scroll_drag(check, nodes)

    accepts = [_value(n, CC.CURSOR_ACCEPT_VAR) for n in _sets(nodes, CC.CURSOR_ACCEPT_VAR)]
    check("a click on a settings row, on the page's BACK row or on the death "
          "menu's hint raises CursorAccept, and each accept lowers it as it serves it; "
          "the death menu of a client of a server lowers it unserved",
          sorted(accepts) == ["false"] * 3 + ["true"] * 3, str(accepts))

    lowered = [n for n in _sets(nodes, CC.PAUSE_CLICK_VAR)
               if not _feeders(n, CC.PAUSE_CLICK_VAR)]
    # A literal 0 reads back empty once the asset is loaded from disk (row 0's).
    served = sorted(int(_value(n, "B") or 0) for n in nodes if _pins(n) == {"A", "B"}
                    and f"Get {CC.PAUSE_CLICK_VAR}" in _feeders(n, "A"))
    check("the M panel's taken row is lowered every frame, and each row's "
          "action answers to its own row",
          len(lowered) == 1 and _value(lowered[0], CC.PAUSE_CLICK_VAR) == str(CC.NO_ROW)
          # (the exit row twice: save and exit, and a client's leave server)
          and served == sorted(list(range(len(UC.PAUSE_ROW_ACTIONS)))
                               + [UC.PAUSE_ROW_ACTIONS.index(EXIT_ACTION)]),
          f"{len(lowered)}, {served}")
    # The first row as the menu's close button in play (resume) is
    # mode_checks.py's: on the title the same row opens the Single Player page.
    check(f"[{UC.MENU_KEY}] flips MenuOpen, and is polled only in play: the title's "
          "menu cannot be shut",
          _key_toggles(nodes, UC.MENU_KEY, "MenuOpen", UC.GAME_STARTED_VAR))
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
    wanted = set(CC.CURSOR_BOOLS + CC.CURSOR_INTS + CC.CURSOR_REALS + (CC.CURSOR_POS_VAR,))
    check("the HUD has the cursor's variables", wanted <= names, str(sorted(wanted - names)))
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    wrong = {k: cdo.get_editor_property(k) for k, v in cursor_defaults().items()
             if cdo.get_editor_property(k) != v}
    check("the cursor starts hidden, over nothing, with nothing clicked or dragged", not wrong,
          str(wrong))
    _check_widgets(check)
    _check_show(check, nodes)
    _check_rows(check, nodes)
    _check_clicks(check, nodes)
