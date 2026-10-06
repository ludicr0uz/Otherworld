"""What the title probes share: working the real title menu (a run started
with ``uepy.py --title``, which leaves -nomenu off), its two mode pages and
the session behind them.

The level is reopened by a join, a failed join and a leave, and each brings a
new world and a new HUD: nothing here keeps one, every call asks ``p`` again.
Waits are on the wall clock (a paused title's game time stands still), and
each is bounded, so the check after it says what did not happen.

A row is taken as a click takes it: PauseClick (the menu's own rows) or
PageClick (a mode page's), which Tick serves. DrawHUD lowers both at the top
of a frame; a -nullrhi run draws none, so the taker lowers what it raised.
"""

import os
import time

import unreal

from combat.paths import SETTINGS_BP_PATH, SETTINGS_SLOT, SETTINGS_USER_INDEX
from graphics_menu import cursor_consts as CC
from graphics_menu import hud_vars as MV
from graphics_menu import umg_consts as C
from graphics_menu.profile_consts import PROFILE_SLOT
from net import session_consts as S

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
# What a title probe writes: the menu's taken rows, and the address field.
WRITABLE = [(HUD_BP_PATH, v) for v in (MV.MenuOpen, CC.PAUSE_CLICK_VAR, CC.PAGE_CLICK_VAR,
                                       MV.MenuPage, MV.MenuRow)]
WRITABLE += [(SETTINGS_BP_PATH, S.SERVER_ADDRESS_VAR)]
WAIT = 10.0


def wait(ready, seconds=WAIT):
    """Yield until ``ready()`` or ``seconds`` of wall time."""
    until = time.time() + seconds

    def done():
        try:
            return ready() or time.time() > until
        except Exception:       # a world or a HUD mid-travel
            return time.time() > until
    yield done


def session(p):
    """The GameInstance: the one object that outlives every travel here."""
    return unreal.GameplayStatics.get_game_instance(p.world())


def paused(p):
    return unreal.GameplayStatics.is_game_paused(p.world())


def alone(p):
    return unreal.SystemLibrary.is_standalone(p.world())


def on_title(p):
    """This process stands on the title: a standalone world, paused, its HUD's
    game not started."""
    hud = p.world() and p.hud()
    return bool(hud and p.get(hud, "UiHud") is not None and alone(p) and paused(p)
                and p.get(hud, C.GAME_STARTED_VAR) is False)


def in_play(p):
    hud = p.world() and p.pawn() and p.hud()
    return bool(hud and p.get(hud, "UiHud") is not None and p.get(hud, C.GAME_STARTED_VAR))


def take_row(p, action, served, seconds=WAIT):
    """Take the menu's row for ``action``; wait for ``served()``."""
    p.set(p.hud(), CC.PAUSE_CLICK_VAR, C.PAUSE_ROW_ACTIONS.index(action))
    yield from wait(served, seconds)
    _lower(p, CC.PAUSE_CLICK_VAR)


def take_page_row(p, row, served, seconds=WAIT):
    """Take row ``row`` of the open mode page; wait for ``served()``."""
    p.set(p.hud(), CC.PAGE_CLICK_VAR, row)
    yield from wait(served, seconds)
    _lower(p, CC.PAGE_CLICK_VAR)


def _lower(p, var):
    try:
        p.set(p.hud(), var, CC.NO_ROW)
    except Exception:           # the HUD that was asked is gone: so is its click
        pass


def address(p):
    return str(p.get(p.get(p.hud(), MV.Settings), S.SERVER_ADDRESS_VAR))


def type_address(p, text):
    """The Multiplayer page's address field := ``text`` (BP_Settings')."""
    p.set(p.get(p.hud(), MV.Settings), S.SERVER_ADDRESS_VAR, text)


def restore_address(p, text):
    """The player's own address back in the saved settings: a join saves what
    the probe typed."""
    settings = p.get(p.hud(), MV.Settings)
    p.set(settings, S.SERVER_ADDRESS_VAR, text)
    unreal.GameplayStatics.save_game_to_slot(settings, SETTINGS_SLOT, SETTINGS_USER_INDEX)


def profile_file():
    """The single-player profile on disk: (exists, size, mtime)."""
    path = os.path.join(unreal.Paths.project_saved_dir(), "SaveGames", f"{PROFILE_SLOT}.sav")
    try:
        stat = os.stat(path)
        return (True, stat.st_size, stat.st_mtime)
    except OSError:
        return (False, 0, 0.0)


# ─── What the menu shows (a rendered run: -nullrhi draws no HUD) ─────────────

def drawn(p):
    """The HUD is being drawn: DrawHUD holds the title's menu open."""
    return bool(p.get(p.hud(), MV.MenuOpen))


def _words(widget):
    return str(widget.get_text()) if widget else None


def menu_text(p, name):
    """A TextBlock of the menu (WBP_PauseMenu) by name."""
    return _words(p.get(p.hud(), C.UI_VAR[C.WBP_PAUSE_MENU]).get_editor_property(name))


def row_text(p, box, index, part=C.ROW_LABEL):
    """A row's label (or ``part``: its value) in the menu's list ``box``."""
    rows = p.get(p.hud(), C.UI_VAR[C.WBP_PAUSE_MENU]).get_editor_property(box)
    row = rows.get_child_at(index) if rows else None
    return _words(row.get_editor_property(part)) if row else None
