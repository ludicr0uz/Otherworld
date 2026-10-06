"""verify_graphics_menu.py's checks for the two modes (mode_consts.py,
wbp_modes.py, mode_draw.py, mode_tick.py, and menu_main's first row): the
title's Single Player and Multiplayer rows each open a page in the rows'
place, with BACK on top; Single Player's row starts the game as the first
row used to; Multiplayer's holds the address and joins; a client has no
title and leaves its server by the exit row, the profile untouched. The
graph and the widget trees only: a real join is probe_net_title.py's.
"""

import unreal

from graphics_menu import cursor_consts as CC
from graphics_menu import mode_consts as MC
from graphics_menu import umg_consts as UC
from graphics_menu.pause_checks import (
    _feeds, _gates, _is_row_test, _pins, _sets, _sources, _title, _value)
from graphics_menu.profile_consts import EXIT_ACTION, PROFILE_SLOT
from graphics_menu.settings_rows import BACK_LABEL, PAGE_TITLE, SETTINGS_SLOT
from graphics_menu.umg_checks import _labels, _tree
from net import session_consts as S
from net.session_checks import check_session
from net.input_checks import check_local_input
from net.owner_checks import check_no_player_zero_pawn
from net.random_checks import check_random_audit
from net.state_checks import check_no_client_game_mode

BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary
TICK_PIN, PAUSE_PIN = "bTickableWhenPaused", "bPaused"


def _int(n, pin):
    """An int literal; one equal to its default reads back empty once the
    asset is loaded from disk."""
    v = _value(n, pin)
    return int(v) if v.lstrip("-").isdigit() else (0 if v == "" else None)


def _over(widget, other):
    """``widget`` comes before ``other`` among the children of the stack
    they share."""
    stack = widget.get_parent()
    return bool(stack and other.get_parent() == stack
                and stack.get_child_index(widget) < stack.get_child_index(other))


def _bare(n):
    return _title(n).replace(" ", "")


def _deep(n, pin="Condition"):
    """Every node ``n``'s ``pin`` is computed from, through A / B / bPickA."""
    seen, todo = [], _sources(n, pin)
    while todo:
        c = todo.pop()
        if c in seen:
            continue
        seen.append(c)
        for p in ("A", "B", "InString", "S"):
            todo += _sources(c, p)
    return seen


def _upstream(n):
    """Every node whose exec leads to ``n``."""
    seen, todo = [], _sources(n, "execute")
    while todo:
        c = todo.pop()
        if c in seen:
            continue
        seen.append(c)
        for p in ("execute", "Exec"):
            todo += _sources(c, p)
    return seen


def _since(n, is_gate):
    """The nodes whose exec leads to ``n``, back to the Branch ``is_gate``
    picks, that Branch left out."""
    seen, todo = [], _sources(n, "execute")
    while todo:
        c = todo.pop()
        if c in seen or ("Condition" in _pins(c) and is_gate(c)):
            continue
        seen.append(c)
        todo += _sources(c, "execute")
    return seen


def _is_page_test(gate, page, row):
    """``gate``'s Condition holds MenuPage == ``page`` and PageClick == ``row``."""
    tests = [(f, _int(c, "B")) for c in _deep(gate) if _pins(c) == {"A", "B"}
             for f in _feeds(c, "A")]
    return (("Get MenuPage", page.page) in tests
            and (f"Get {CC.PAGE_CLICK_VAR}", row) in tests)


def _page_gated(n, page, row):
    return any(_is_page_test(g, page, row) for u in [n] + _upstream(n) for g in [u]
               if "Condition" in _pins(g))


def _standalone_gates(nodes):
    return [n for n in nodes if "Condition" in _pins(n)
            and [_bare(c) for c in _sources(n, "Condition")] == ["IsStandalone"]]


def _arm(gate, then):
    pin = BEL.find_then_pin(gate) if then else BEL.find_else_pin(gate)
    return [PIN.get_owning_node(q) for q in pin.list_connected_pins()] if pin else []


def _check_trees(check):
    tree = _tree(UC.WBP_PAUSE_MENU)
    for page in MC.PAGES:
        panel, back = tree.get(page.panel, (None, False)), tree.get(page.back, (None, False))
        box = tree.get(page.rows_box, (None, False))
        check(f"the {page.title} page is a panel of its own, starting collapsed, "
              f"with rows {list(page.labels)}",
              bool(panel[0]) and panel[1] and bool(box[0]) and box[1]
              and "COLLAPSED" in str(panel[0].get_editor_property("visibility")).upper()
              and _labels(tree, page.rows_box) == list(page.labels),
              f"{panel}, {_labels(tree, page.rows_box)}")
        check(f"...and {BACK_LABEL} is its top row, a row of its own over them",
              bool(back[0]) and back[1] and bool(box[0])
              and str(back[0].get_editor_property(UC.ROW_TEXT_VAR)) == BACK_LABEL
              and _over(back[0], box[0]), str(back))
    for name, what in ((MC.MULTI_STATUS, "the Multiplayer page has a status line"),
                       (UC.PAUSE_MODE, "the menu has a line for the mode, under its title")):
        w = tree.get(name, (None, False))
        check(f"{what}, written by the HUD",
              isinstance(w[0], unreal.TextBlock) and w[1], str(w))


def _check_first_rows(check, nodes):
    opens = {}
    for page, action in ((MC.SINGLE, UC.START_ACTION), (MC.MULTI, UC.MULTI_ACTION)):
        opens[page] = [n for n in _sets(nodes, "MenuPage") if _int(n, "MenuPage") == page.page
                       and any(_is_row_test(c, action) for u in [n] + _upstream(n)
                               if "Condition" in _pins(u) for c in _deep(u))]
    def on_title(n):
        return any("Get " + UC.GAME_STARTED_VAR in [_title(c) for c in _deep(g)]
                   for g in [n] + _upstream(n) if "Condition" in _pins(g))
    check("on the title the first row opens the Single Player page and the second "
          "the Multiplayer page (only off GameStarted's false side)",
          all(len(v) == 1 and on_title(v[0]) for v in opens.values()),
          str({p.title: len(v) for p, v in opens.items()}))
    resumes = [n for n in _sets(nodes, "MenuOpen") if _value(n, "MenuOpen") == "false"
               and any(_is_row_test(c, UC.START_ACTION) for u in _upstream(n)
                       if "Condition" in _pins(u) for c in _sources(u, "Condition"))
               and any(f"Get {UC.GAME_STARTED_VAR}" in _feeds(g, "Condition")
                       for g in _gates(n))]
    check("in play the first row shuts the menu (resume)", len(resumes) == 1,
          str(len(resumes)))
    tops = [m for v in opens.values() for n in v for m in _sets(nodes, "MenuRow")
            if n in _sources(m, "execute") and _int(m, "MenuRow") == 0]
    check("...each page opening with its caret on its first row", len(tops) == 2,
          str(len(tops)))


def _check_single(check, nodes):
    starts = [n for n in _sets(nodes, UC.GAME_STARTED_VAR)
              if _value(n, UC.GAME_STARTED_VAR) == "true"
              and _page_gated(n, MC.SINGLE, MC.SINGLE_START_ROW)]
    stops = [n for n in nodes if TICK_PIN in _pins(n)
             and (_value(n, TICK_PIN) or "false") == "false"]
    unpauses = [n for n in nodes if PAUSE_PIN in _pins(n)
                and (_value(n, PAUSE_PIN) or "false") == "false"
                and any(s in stops for s in _sources(n, "execute"))]
    before = [_title(u) for n in starts for u in _since(
        n, lambda g: _is_page_test(g, MC.SINGLE, MC.SINGLE_START_ROW))]
    check("the Single Player page's row starts the game as the first row did: "
          "the menu shut and back on its rows, GameStarted, the HUD no longer "
          "ticking while paused, then the unpause, last",
          len(starts) == len(stops) == len(unpauses) == 1
          and starts[0] in _sources(stops[0], "execute")
          and sorted(before) == ["Set MenuOpen", "Set MenuPage"],
          f"{len(starts)} start, {len(stops)} stop, {len(unpauses)} unpause, {before}")
    says = [n for n in nodes if {"self", "InText"} <= _pins(n)
            and UC.CONTINUE_ROW_LABEL in _value(n, "InText")]
    asked = [c for n in says for g in _gates(n) for c in _sources(g, "Condition")
             if "SlotName" in _pins(c) and _value(c, "SlotName") == PROFILE_SLOT]
    check("its row reads continue game while the saved profile exists "
          "(DoesSaveGameExist on its slot), and new game otherwise",
          len(says) == 1 and len(asked) == 1, f"{len(says)} says, {len(asked)} asked")


def _check_pages(check, nodes):
    lowered = [n for n in _sets(nodes, CC.PAGE_CLICK_VAR)
               if not _sources(n, CC.PAGE_CLICK_VAR) and _int(n, CC.PAGE_CLICK_VAR) == CC.NO_ROW]
    raised = sorted(t for n in _sets(nodes, CC.PAGE_CLICK_VAR)
                    for t in _feeds(n, CC.PAGE_CLICK_VAR))
    check("a page's row is taken with Enter on the caret's row or a click: "
          "PageClick, lowered at the top of every frame",
          len(lowered) == 1
          and raised == [f"Get {CC.CURSOR_ROW_VAR}"] * 2 + ["Get MenuRow"] * 2,
          f"{len(lowered)} lowered, raised from {raised}")
    backs = {page.title: [
        n for n in _sets(nodes, "MenuPage") if _int(n, "MenuPage") == PAGE_TITLE
        and any(_value(c, "Key") == CC.ESCAPE_KEY for g in _gates(n) for c in _deep(g)
                if "Key" in _pins(c))
        and any("Get MenuRow" in _feeds(c, "A") and _int(c, "B") == page.back_row
                and ">=" in _title(c) for g in _gates(n) for c in _deep(g))]
        for page in MC.PAGES}
    check("each page's BACK row, Enter on it (the caret on its number, the "
          "last), or Escape anywhere, returns to the menu's rows",
          all(len(v) == 1 for v in backs.values()),
          str({k: len(v) for k, v in backs.items()}))
    shows = {}
    for page in MC.PAGES:
        shows[page.title] = sorted(
            _value(n, "InVisibility") for n in nodes
            if "InVisibility" in _pins(n) and f"Get {page.panel}" in _feeds(n, "self"))
    check("a page shows while MenuPage names it and is collapsed otherwise, on "
          "the menu's rows too",
          all(v == [UC.HIDDEN, UC.HIDDEN, UC.SHOWN] for v in shows.values()), str(shows))


def _check_address(check, bp, nodes):
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    keys = [str(k.get_editor_property("key_name")) for k in cdo.get_editor_property(MC.AddressKeys)]
    chars = [str(c) for c in cdo.get_editor_property(MC.AddressChars)]
    typed = "".join(chars)
    check("the address row types letters, digits, the dot, the colon and the "
          "hyphen: a key and its character, in step",
          list(zip(keys, chars)) == [tuple(p) for p in MC.ADDRESS_KEYS]
          and all(c in typed for c in "az09.:-"), f"{len(keys)} keys, {typed!r}")
    polls = [n for n in nodes if "Key" in _pins(n) and _sources(n, "Key")
             and any(f"Get {MC.AddressKeys}" in _feeds(m, "Array") for m in _sources(n, "Key"))]
    writes = [n for n in nodes if _title(n) == f"Set {S.SERVER_ADDRESS_VAR}"]
    adds = [n for n in writes if "Append" in str(_feeds(n, S.SERVER_ADDRESS_VAR))
            or "Concat" in str([_bare(s) for s in _sources(n, S.SERVER_ADDRESS_VAR)])]
    roomy = [n for n in adds for g in _gates(n) for c in _sources(g, "Condition")
             if _int(c, "B") == MC.ADDRESS_MAX]
    on_row = [g for n in polls for loop in _sources(n, "Key") for g in _sources(loop, "Exec")
              if "Condition" in _pins(g)
              and any("Get MenuRow" in _feeds(c, "A") and _int(c, "B") == MC.MULTI_ADDRESS_ROW
                      for c in _sources(g, "Condition"))]
    erases = [n for n in nodes if "Key" in _pins(n) and _value(n, "Key") == MC.ADDRESS_ERASE_KEY]
    check("typing is one poll over AddressKeys, only with the caret on the "
          "address row: a key adds its character while there is room, "
          f"{MC.ADDRESS_ERASE_KEY} takes the last one off",
          len(polls) == 1 and len(writes) == 2 and len(adds) == 1 and len(roomy) == 1
          and bool(on_row) and len(erases) == 1,
          f"{len(polls)} polls, {len(writes)} writes, {len(adds)} adds, {len(roomy)} "
          f"bounded, {len(on_row)} on the row, {len(erases)} erase")
    status = [n for n in nodes if {"self", "InText"} <= _pins(n)
              and f"Get {MC.MULTI_STATUS}" in _feeds(n, "self")]
    gated = [g for n in status for g in _gates(n)
             if f"Get {S.Connecting}" in _feeds(g, "Condition")]
    check("the status line says a join is under way, or else the session's "
          "reason (the GameInstance's Connecting and NetReason)",
          len(status) == 2 and len(gated) == 2, f"{len(status)} writes, {len(gated)} gated")


def _check_join(check, nodes):
    opens = [n for n in nodes if "LevelName" in _pins(n) and "execute" in _pins(n)
             and any(f"Get {S.JoinAddress}" in _feeds(c, "InString")
                     for c in _sources(n, "LevelName"))]
    up = [_title(u) for n in opens for u in _upstream(n)]
    saved = [u for n in opens for u in _upstream(n)
             if "SaveGameObject" in _pins(u) and _value(u, "SlotName") == SETTINGS_SLOT]
    ready = [g for n in opens for g in _upstream(n) if "Condition" in _pins(g)
             and f"Get {S.Connecting}" in [_title(c) for d in _deep(g)
                                           for c in [d] + _sources(d, "A")]]
    check("Join Server opens the server at the typed address: behind the "
          "page's row and only with no join under way, the address saved to "
          "the settings first, the session noted (no reason, the address, "
          "Connecting)",
          len(opens) == 1 and _page_gated(opens[0], MC.MULTI, MC.MULTI_JOIN_ROW)
          and len(saved) == 1 and len(ready) == 1
          and all(f"Set {v}" in up for v in S.TABLE),
          f"{len(opens)} opens, {len(saved)} saved, {len(ready)} guarded")
    cancels = [n for n in nodes if "Command" in _pins(n)
               and _value(n, "Command") == S.CANCEL_COMMAND]
    away = [g for n in cancels for g in _gates(n)
            if {f"Get {S.Connecting}", "Get MenuPage"} <= {_title(c) for d in _deep(g)
                                                           for c in [d] + _sources(d, "A")}]
    check("a join under way is given up when the player leaves the page "
          f"(the engine's {S.CANCEL_COMMAND})", len(cancels) == 1 and len(away) == 1,
          f"{len(cancels)} cancel, {len(away)} gated")


def _check_begin(check, nodes):
    gates = _standalone_gates(nodes)
    skips = [n for n in _sets(nodes, UC.GAME_STARTED_VAR)
             if _value(n, UC.GAME_STARTED_VAR) == "true"
             and any(u in gates and n not in [d for t in _arm(u, True) for d in [t]]
                     for u in _upstream(n))
             and any(_title(u) == f"Set {S.Connecting}" for u in _sources(n, "execute"))]
    check("a client of a server has no title: BeginPlay, off IsStandalone's "
          "false arm, starts the game as -nomenu does (and no join is under way "
          "any more)", len(skips) == 1, str(len(skips)))
    ended = [n for n in _sets(nodes, "MenuPage") if _int(n, "MenuPage") == MC.PAGE_MULTI
             and any({f"Get {S.NetReason}", f"Get {S.JoinAddress}"}
                     <= {_title(c) for c in _deep(g)} for g in _gates(n))]
    closed = [n for n in nodes if _title(n) == f"Set {S.NetReason}"
              and _value(n, S.NetReason) == S.REASON_CLOSED]
    check("a title reached with the session not left (the GameInstance names a "
          "server, or holds a reason) opens on the Multiplayer page, with a "
          "reason to show", len(ended) == 1 and len(closed) == 1,
          f"{len(ended)} opens, {len(closed)} default reason")


def _check_in_play(check, nodes):
    leaves = [n for n in nodes if "Command" in _pins(n)
              and _value(n, "Command") == S.LEAVE_COMMAND]
    gates = [g for g in _standalone_gates(nodes)
             if leaves and any(g in _upstream(n) for n in leaves)]
    rowed = [n for n in leaves if any(_is_row_test(c, EXIT_ACTION) for u in _upstream(n)
                                      if "Condition" in _pins(u)
                                      for c in _sources(u, "Condition"))]
    cleared = [_title(u) for n in leaves for u in _upstream(n)
               if _title(u) in (f"Set {S.JoinAddress}", f"Set {S.NetReason}")]
    check("as a client the menu's exit row leaves the server: the session "
          f"cleared (no reason to show), then the engine's {S.LEAVE_COMMAND}",
          len(leaves) == 1 and len(gates) == 1 and len(rowed) == 1
          and sorted(set(cleared)) == [f"Set {S.JoinAddress}", f"Set {S.NetReason}"],
          f"{len(leaves)} leave, {len(gates)} gate, {len(rowed)} rowed, {cleared}")
    if len(gates) != 1:
        return
    gate = gates[0]
    single = _arm(gate, True)
    client = set(id(n) for n in _arm(gate, False))
    slot = [n for n in nodes if "SlotName" in _pins(n) and "execute" in _pins(n)
            and _value(n, "SlotName") == PROFILE_SLOT]
    behind = [n for n in slot if gate in _upstream(n)]
    through_client = [n for n in behind
                      if any(id(u) in client for u in _upstream(n))
                      and not any(u in single for u in _upstream(n))]
    check("the single-player profile is single player's: every load, save and "
          "delete of its slot in play runs off IsStandalone's true arm, whose "
          "one way in is that Branch",
          len(single) == 1 and _sources(single[0], "execute") == [gate]
          and len(behind) >= 3 and not through_client,
          f"{len(single)} entry, {len(behind)} of {len(slot)} behind, "
          f"{len(through_client)} by the client's arm")
    words = sorted(v for n in nodes if {"self", "InText"} <= _pins(n)
                   for v in [_value(n, "InText")]
                   if any(w in v for w in (MC.LEAVE_ROW_LABEL, UC.MODE_SINGLE_TEXT,
                                           UC.MODE_MULTI_TEXT))
                   and any("IsStandalone" in [_bare(c) for c in _sources(g, "Condition")]
                           for g in _gates(n)))
    check("the menu says which mode the game in play is, and its exit row reads "
          "leave server as a client (both off IsStandalone)", len(words) == 3, str(words))


def check_modes(check, bp, nodes):
    check_session(check)
    check_no_client_game_mode(check)
    check_no_player_zero_pawn(check)
    check_random_audit(check)
    check_local_input(check)
    _check_trees(check)
    _check_first_rows(check, nodes)
    _check_single(check, nodes)
    _check_pages(check, nodes)
    _check_address(check, bp, nodes)
    _check_join(check, nodes)
    _check_begin(check, nodes)
    _check_in_play(check, nodes)
