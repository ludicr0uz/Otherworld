"""The dev tabs in single player (M32): the gameplay tables are the player's
own, with no switch, as before a server could refuse them.

    python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_dev_tuning_single.py

The third case beside probe_net_dev_tuning.py's two (a server that refuses
tuning, one started with -AllowDevTuning):

  - GameState.DevTuning is true;
  - every tab's hint line, drawn by hand, is its own words, never READ_ONLY_HINT;
  - one nudge up on PLAYER SETTINGS' jog speed (the HUD's TuneRow / TuneNudge
    written, a probe having no keyboard) moves the cell by its step and the
    player's speed with it.

The kept tables' slots are set aside by the launch (probes/kept_slots.py).
"""

SYSTEMS = ('menu',)

import time

from combat.paths import WEAPON_COMP_CLASS_PATH
from combat.player_tuning import JOG_SPEED, PLAYER_STATS, cms
from combat.sprint_tuning import BASE_SPEED_VAR
from graphics_menu import hud_vars as MV
from graphics_menu.game_tuner_consts import GAMEPLAY_TABS
from graphics_menu.player_tune_consts import PLAYER_TAB
from graphics_menu.sound_tune_consts import SOUND_TAB
from net import state_consts as S

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
TABS = (*GAMEPLAY_TABS, SOUND_TAB)
WRITABLE = [(HUD_BP_PATH, v) for v in (
    MV.MenuOpen, *(t.open_var for t in TABS), PLAYER_TAB.row_var, PLAYER_TAB.nudge_var)]

WAIT = 30.0             # wall seconds any one step may take
JOG = [s[0] for s in PLAYER_STATS].index(JOG_SPEED)
JOG_STEP = PLAYER_STATS[JOG][2]


def _await(ready, seconds=WAIT):
    until = time.time() + seconds
    yield lambda: ready() or time.time() > until


def _live_hud(p):
    try:
        hud = p.hud()
    except Exception:
        return None
    return hud if hud is not None and p.get(hud, "UiPause") is not None else None


def _cells(hud):
    return [float(v) for v in hud.get_editor_property(PLAYER_TAB.values_var)]


def probe(p):
    yield from _await(lambda: _live_hud(p) is not None and p.pawn() is not None)
    hud = _live_hud(p)
    if hud is None:
        p.check("the player has a HUD", False)
        return
    yield from _await(lambda: bool(p.get(p.game_state(), S.DevTuning)), 5.0)
    p.check("single player: GameState.DevTuning is true with no switch",
            bool(p.get(p.game_state(), S.DevTuning)))
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)

    ui = p.get(hud, "UiPause")
    p.set(hud, MV.MenuOpen, True)
    for tab in TABS:
        for other in TABS:
            p.set(hud, other.open_var, other is tab)
        hud.call_method("ReceiveDrawHUD", (1920, 1080))
        words = str(ui.get_editor_property(tab.hint_widget).get_text())
        p.check(f"single player: {tab.title_text}: the hint line is its own",
                words == tab.hint_text, repr(words))
        p.set(hud, tab.open_var, False)
    p.set(hud, MV.MenuOpen, False)

    cells, speed = _cells(hud), float(p.get(wc, BASE_SPEED_VAR))
    p.set(hud, PLAYER_TAB.row_var, 1 + JOG)
    p.set(hud, PLAYER_TAB.nudge_var, 1)
    yield from _await(lambda: p.get(hud, PLAYER_TAB.nudge_var) == 0)
    yield 0.2           # the next Tick's apply
    after, now = _cells(hud), float(p.get(wc, BASE_SPEED_VAR))
    p.check("single player: one nudge up moves the jog speed's cell by its step",
            after == cells[:JOG] + [cells[JOG] + JOG_STEP] + cells[JOG + 1:],
            f"{cells} -> {after}")
    p.check("...and the player's jog speed with it",
            abs(now - cms(after[JOG])) < 0.01 and now != speed, f"{speed} -> {now}")
