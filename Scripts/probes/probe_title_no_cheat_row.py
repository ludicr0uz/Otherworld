"""The dev-all-guns cheat is a game's row: the title's menu does not offer it.

    python3 Scripts/dev/uepy.py --game --title --windowed --probe Scripts/probes/probe_title_no_cheat_row.py

Rendered: the rows are collapsed and shown by DrawHUD, and a -nullrhi run
draws no HUD (it says so and checks nothing).

  the title     the cheat's row collapsed, the rows either side of it shown;
                a caret put on it is moved on to the row below
  in play       (New Game, then the menu opened) the row shown, and the caret
                rests on it
"""

SYSTEMS = ('title', 'menu')
LEVEL = "/Game/Maps/Lvl_Title"
# The forest's load is in it.
TIMEOUT = 150.0

import unreal

from graphics_menu import hud_vars as MV
from graphics_menu import mode_consts as MC
from graphics_menu import umg_consts as C
from graphics_menu.dev_consts import DEV_GUNS_ACTION
from probes import title as T
from title import paths as P

WRITABLE = list(T.WRITABLE) + [(T.HUD_BP_PATH, C.PAUSE_ROW_VAR)]
ROW = C.PAUSE_ROW_ACTIONS.index(DEV_GUNS_ACTION)
LOAD_WAIT = 60.0
PLAY_LEVEL_NAME = P.PLAY_LEVEL.rsplit("/", 1)[1]
COLLAPSED = unreal.SlateVisibility.COLLAPSED
GS = unreal.GameplayStatics


def _shown(p, hud):
    """Which of the row above, the cheat's row and the row below are shown."""
    rows = p.get(hud, C.UI_VAR[C.WBP_PAUSE_MENU]).get_editor_property(C.PAUSE_ROWS)
    return [rows.get_child_at(i).get_visibility() != COLLAPSED for i in (ROW - 1, ROW, ROW + 1)]


def probe(p):
    yield from T.wait(lambda: T.on_title(p))
    if not T.on_title(p):
        p.check("the game opens on the title (run with uepy.py --game --title)", False,
                "no title: -nomenu is on the command line")
        return
    yield from T.wait(lambda: T.drawn(p), 5.0)
    if not T.drawn(p):
        p.note("not drawn here (run --windowed): the title's rows")
        return
    hud = p.hud()
    yield from T.wait(lambda: _shown(p, hud) == [True, False, True])
    p.check("on the title the dev-all-guns row is collapsed, the rows either side shown",
            _shown(p, hud) == [True, False, True], str(_shown(p, hud)))
    p.set(hud, C.PAUSE_ROW_VAR, ROW)
    yield from T.wait(lambda: p.get(hud, C.PAUSE_ROW_VAR) != ROW)
    p.check("...and a caret put on it is moved on to the row below",
            p.get(hud, C.PAUSE_ROW_VAR) == ROW + 1, f"caret {p.get(hud, C.PAUSE_ROW_VAR)}")

    # The play level is found by its own path: the probe's world is the title's.
    def play_hud():
        world = unreal.find_object(None, f"{P.PLAY_LEVEL}.{PLAY_LEVEL_NAME}")
        pc = GS.get_player_controller(world, 0) if world else None
        return pc.get_hud() if pc else None

    def playing():
        hud = play_hud()
        return bool(hud and p.get(hud, C.GAME_STARTED_VAR))
    yield from T.take_row(p, C.START_ACTION, lambda: p.get(hud, MV.MenuPage) == MC.PAGE_SINGLE)
    yield from T.take_page_row(p, MC.SINGLE_START_ROW, playing, LOAD_WAIT)
    if not playing():
        p.check("New Game opens the play level", False, "no HUD in play")
        return
    hud = play_hud()
    p.set(hud, MV.MenuOpen, True)
    p.set(hud, C.PAUSE_ROW_VAR, ROW)
    yield from T.wait(lambda: _shown(p, hud) == [True, True, True])
    # On the wall clock: the open menu pauses the game. Long enough for a
    # caret that was going to be moved off the row to have been.
    yield from T.wait(lambda: p.get(hud, C.PAUSE_ROW_VAR) != ROW, 1.0)
    p.check("in play the menu shows the row, and the caret rests on it",
            _shown(p, hud) == [True, True, True] and p.get(hud, C.PAUSE_ROW_VAR) == ROW,
            f"{_shown(p, hud)}, caret {p.get(hud, C.PAUSE_ROW_VAR)}")
