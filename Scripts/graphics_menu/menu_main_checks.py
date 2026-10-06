"""verify_graphics_menu.py's checks for the one menu (menu_main.py, and
menu_screens.author_title): the title is the menu held open over a paused
world, with the HUD ticking under it; its settings row opens the settings
page in the rows' place, and its last row quits. Its first two rows, the
modes, are mode_checks.py's. The graph only: the rows served under a real pause are
probes/probe_main_menu.py's.
"""

from graphics_menu import umg_consts as UC
from graphics_menu.gfx_tune_consts import TUNER_COMPONENT
from graphics_menu.pause_checks import (
    _feeds, _gates, _is_row_test, _pins, _sets, _sources, _value)
from graphics_menu.settings_rows import PAGE_SETTINGS
from net.pause_checks import check_standalone_pause

TICK_PIN, PAUSE_PIN = "bTickableWhenPaused", "bPaused"


def _flag(n, pin):
    """A bool literal; one equal to its default reads back empty once the
    asset is loaded from disk."""
    return _value(n, pin) or "false"


def _taken(n, action):
    """``n`` runs behind the Branch on ``action``'s row being taken."""
    return any(_is_row_test(c, action) for g in _gates(n)
               for c in _sources(g, "Condition"))


def _check_title(check, nodes):
    held = [n for n in _sets(nodes, "MenuOpen")
            if not _sources(n, "MenuOpen") and _value(n, "MenuOpen") == "true"]
    behind = [t for n in held for e in _sources(n, "execute")
              for b in _sources(e, "execute") for g in [b] + _gates(b)
              if "Condition" in _pins(g) for t in _feeds(g, "Condition")]
    check("the title is the menu held open: DrawHUD raises MenuOpen while "
          "GameStarted is false, after hiding the HUD's Body and the death menu",
          len(held) == 1 and behind == [f"Get {UC.GAME_STARTED_VAR}"],
          f"{len(held)} held, behind {behind}")

    ticks = [n for n in nodes if TICK_PIN in _pins(n)]
    on = [n for n in ticks if _flag(n, TICK_PIN) == "true"]
    selves = sorted(str(_feeds(n, "self")) for n in on)
    check("BeginPlay makes the HUD and its tuner tick while paused, before the "
          "title's pause: the menu's rows are served on Tick",
          selves == sorted(["[]", str([f"Get {TUNER_COMPONENT}"])]), str(selves))
    check_standalone_pause(check, nodes, "the title")


def _check_rows(check, nodes):
    # The first row, and the Single Player page's that starts the game, are
    # mode_checks.py's.
    pages = [n for n in _sets(nodes, "MenuPage") if _taken(n, UC.SETTINGS_ACTION)]
    tops = [m for n in pages for m in _sets(nodes, "MenuRow")
            if n in _sources(m, "execute") and int(_value(m, "MenuRow") or 0) == 0]
    check("the settings row opens the settings page, its caret on the top row",
          len(pages) == 1 and _value(pages[0], "MenuPage") == str(PAGE_SETTINGS)
          and len(tops) == 1, f"{len(pages)} pages, {len(tops)} carets")

    quits = [n for n in nodes if "QuitPreference" in _pins(n)]
    check("the exit game row, and nothing else, quits the game for the owning player",
          len(quits) == 1 and _taken(quits[0], UC.QUIT_ACTION)
          and bool(_sources(quits[0], "SpecificPlayer"))
          and _value(quits[0], "QuitPreference").endswith("Quit"),
          f"{len(quits)} QuitGame")


def _check_page(check, nodes):
    def shows(widget):
        found = []
        for n in nodes:
            if "InVisibility" in _pins(n) and f"Get {widget}" in _feeds(n, "self"):
                paged = any("Get MenuPage" in _feeds(c, "A")
                            for e in [n] + _sources(n, "execute") for g in _gates(e)
                            for c in _sources(g, "Condition"))
                found.append((_value(n, "InVisibility"), paged))
        return sorted(found)
    page, panel = shows(UC.SETTINGS_PANEL), shows(UC.PAUSE_PANEL)
    check("the settings page stands in the menu's place: shown, with the rows "
          "collapsed, while MenuPage names it, and collapsed on the rows and "
          "on a mode page",
          page == [(UC.HIDDEN, True), (UC.HIDDEN, True), (UC.SHOWN, True)]
          and (UC.HIDDEN, True) in panel, f"page {page}, panel {panel}")


def check_main_menu(check, nodes):
    _check_title(check, nodes)
    _check_rows(check, nodes)
    _check_page(check, nodes)
