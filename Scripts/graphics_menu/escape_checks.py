"""verify_graphics_menu.py's checks for Escape, which is BACK in every menu
(cursor_consts.ESCAPE_KEY): it shuts an open tuning tab and the controls
page (and calls an armed capture off) in DrawHUD, and in play, on the menu's
own rows, the menu itself, on Tick. The graph only: no probe can press a key.
"""

import unreal

from graphics_menu import cursor_consts as CC
from graphics_menu import hud_vars as MV
from graphics_menu.pause_checks import _gates, _pins, _sets, _sources, _title, _value
from graphics_menu.settings_rows import PAGE_TITLE
from graphics_menu.mode_consts import PAGES
from graphics_menu.tune_tabs import TABS

BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary


def upstream(n, pin):
    """Every node ``n``'s ``pin`` is computed from, through data pins."""
    seen, todo = [], _sources(n, pin)
    while todo:
        c = todo.pop()
        if c in seen:
            continue
        seen.append(c)
        for p in BEL.list_input_pins(c):
            name = str(PIN.get_pin_name(p))
            if name != "execute":
                todo += _sources(c, name)
    return seen


def _is_escape(n):
    return ({"Key", "self"} <= _pins(n) and not _sources(n, "Key")
            and _value(n, "Key") == CC.ESCAPE_KEY)


def _on_escape(gate):
    """``gate``'s Condition reads the Escape poll."""
    return any(_is_escape(c) for c in upstream(gate, "Condition"))


def _lowered(nodes, var):
    """The Sets that write a literal false to ``var`` (one equal to its
    default reads back empty once the asset is loaded from disk)."""
    return [n for n in _sets(nodes, var)
            if not _sources(n, var) and (_value(n, var) or "false") == "false"]


def check_escape(check, nodes):
    polls = [n for n in nodes if _is_escape(n)]
    check(f"{CC.ESCAPE_KEY} is polled once per tab and per mode page, twice on "
          "the controls page (the capture, the page) and once for the menu in play",
          len(polls) == len(TABS) + len(PAGES) + 3, f"{len(polls)} polls")

    deaf = [t.open_var for t in TABS
            if not any(_on_escape(g) for n in _lowered(nodes, t.open_var)
                       for g in _gates(n))]
    check(f"{CC.ESCAPE_KEY} shuts an open tuning tab, as its BACK row does",
          not deaf, str(deaf))

    pages = [n for n in _sets(nodes, MV.MenuPage) if not _sources(n, MV.MenuPage)
             and int(_value(n, MV.MenuPage) or 0) == PAGE_TITLE
             and any(_on_escape(g) for g in _gates(n))]
    # A mode page's BACK row and Escape share one gate (cursor.author_back_row,
    # mode_checks.py); the controls page's Set has its BACK's gate and Escape's.
    check(f"{CC.ESCAPE_KEY} on the controls page goes back to the menu's rows, "
          "through the same Set MenuPage as its BACK row, and on a mode page "
          "through that page's",
          sorted(len(_gates(n)) for n in pages) == [1] * len(PAGES) + [2],
          f"{len(pages)} pages, {[len(_gates(n)) for n in pages]} gates")

    disarms = [n for n in _lowered(nodes, MV.Capturing)
               if any(_on_escape(g) for g in _gates(n))]
    armed = [g for n in disarms for g in _gates(n) for b in _gates(g)
             if f"Get {MV.Capturing}" in [_title(s) for s in _sources(b, "Condition")]]
    check(f"{CC.ESCAPE_KEY} calls an armed capture off, before the key pool is walked",
          len(disarms) == 1 and len(armed) == 1,
          f"{len(disarms)} disarms, {len(armed)} behind Capturing")

    shuts = []
    for n in _lowered(nodes, MV.MenuOpen):
        for top in _gates(n):
            reads = {_title(c) for c in upstream(top, "Condition")}
            if (any(_on_escape(g) for g in _gates(top))
                    and {f"Get {MV.MenuOpen}", f"Get {MV.MenuPage}"} <= reads
                    and all(f"Get {t.open_var}" in reads for t in TABS)):
                shuts.append(n)
    check(f"{CC.ESCAPE_KEY} in play shuts the menu, only from its own rows: not "
          "with the controls page or a tab up, which take it themselves",
          len(shuts) == 1, f"{len(shuts)} shuts")
