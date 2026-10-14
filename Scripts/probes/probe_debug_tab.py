"""The DEBUG SETTINGS tab in single player: its two switches set the
GameState's two flags apart, and FULL STATS fills the player's stats.

    python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_debug_tab.py

  - a nudge up on the first switch (the HUD's DebugTuneRow / DebugTuneNudge
    written, a probe having no keyboard) turns DebugMode on and leaves
    DebugShots off; one on the second turns DebugShots on; both back down
    turn both off, and the panel's draw reads ON, then OFF;
  - with health, stamina, hunger, thirst and warmth lowered, raising
    DebugTuneCheatRequested (what Enter or a click on FULL STATS does) puts
    each at its maximum and DebugTuneCheated up.

The kept tables' slots are set aside by the launch (probes/kept_slots.py).
"""

SYSTEMS = ('menu',)

import time

from combat import health_vars as HV
from combat.paths import (HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_BP_PATH,
                          WEAPON_COMP_CLASS_PATH)
from combat.weapon_component import vars as WV
from graphics_menu import debug_tune_consts as DC
from graphics_menu import hud_vars as MV
from graphics_menu import umg_consts as UC
from survival import component_vars as SC
from survival.paths import SURVIVAL_BP_PATH, SURVIVAL_CLASS_PATH

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
TAB = DC.DEBUG_TAB
WRITABLE = [*((HUD_BP_PATH, v) for v in (
                MV.MenuOpen, TAB.open_var, TAB.row_var, TAB.nudge_var, TAB.save_var)),
            (HEALTH_BP_PATH, HV.Health), (WEAPON_COMP_BP_PATH, WV.Stamina),
            *((SURVIVAL_BP_PATH, v) for v in (SC.Hunger, SC.Thirst, SC.Temperature))]
FLAGS = [flag for _label, flag in DC.DEBUG_SWITCHES]
# (component class, stat, ceiling): what FULL STATS fills.
STATS = ((HEALTH_CLASS_PATH, HV.Health, HV.MaxHealth),
         (WEAPON_COMP_CLASS_PATH, WV.Stamina, WV.MaxStamina),
         (SURVIVAL_CLASS_PATH, SC.Hunger, SC.MaxHunger),
         (SURVIVAL_CLASS_PATH, SC.Thirst, SC.MaxThirst),
         (SURVIVAL_CLASS_PATH, SC.Temperature, SC.MaxTemperature))
# A stat drifts between the fill and the read (hunger falls, stamina comes back).
DRIFT = 1.0


def _await(cond, timeout=3.0):
    start = time.monotonic()
    while not cond() and time.monotonic() - start < timeout:
        yield 0.05


def _flags(p):
    return [bool(p.get(p.game_state(), f)) for f in FLAGS]


def _nudge(p, hud, switch, step):
    p.set(hud, TAB.row_var, 1 + switch)
    p.set(hud, TAB.nudge_var, step)
    yield from _await(lambda: p.get(hud, TAB.nudge_var) == 0)
    yield 0.2           # the next Tick's apply


def _words(p, hud):
    hud.call_method("ReceiveDrawHUD", (1920, 1080))
    box = p.get(hud, "UiPause").get_editor_property(TAB.rows_box)
    return [str(k.get_editor_property(UC.ROW_VALUE).get_text())
            for k in list(box.get_all_children())[1:]]


def _switches(p, hud):
    yield from _nudge(p, hud, 0, 1)
    p.check("Monster vision & agro ON turns DebugMode on, and not DebugShots",
            _flags(p) == [True, False], str(_flags(p)))
    yield from _nudge(p, hud, 1, 1)
    p.check("...Shot trajectory ON turns DebugShots on", _flags(p) == [True, True],
            str(_flags(p)))
    on = _words(p, hud)
    yield from _nudge(p, hud, 0, -1)
    p.check("...Monster vision & agro OFF leaves the shots on", _flags(p) == [False, True],
            str(_flags(p)))
    yield from _nudge(p, hud, 1, -1)
    off = _words(p, hud)
    p.check("...and both OFF turns both off, the panel reading ON, then OFF",
            _flags(p) == [False, False] and on == [DC.DEBUG_ON_WORD] * 2
            and off == [DC.DEBUG_OFF_WORD] * 2, f"{_flags(p)}, {on} -> {off}")


def _full_stats(p, hud):
    pawn = p.pawn()
    comps = {c: p.component(pawn, c) for c, _s, _m in STATS}
    for c, stat, ceiling in STATS:
        p.set(comps[c], stat, float(p.get(comps[c], ceiling)) * 0.25)
    low = {stat: float(p.get(comps[c], stat)) for c, stat, _m in STATS}
    p.set(hud, TAB.save_var, True)
    yield from _await(lambda: not p.get(hud, TAB.save_var))
    yield 0.1
    now = {stat: (float(p.get(comps[c], stat)), float(p.get(comps[c], ceiling)))
           for c, stat, ceiling in STATS}
    p.check("FULL STATS puts health, stamina, hunger, thirst and warmth at their "
            "maximums", all(abs(v - m) <= DRIFT for v, m in now.values()),
            f"{low} -> {now}")
    p.check("...and says so (DebugTuneCheated)", bool(p.get(hud, TAB.saved_var)))


def probe(p):
    yield from _await(lambda: p.hud() is not None and p.get(p.hud(), "UiHud") is not None,
                      10.0)
    hud = p.hud()
    p.set(hud, MV.MenuOpen, True)
    p.set(hud, TAB.open_var, True)
    yield 0.2
    p.check("the debug tab starts with both switches off", _flags(p) == [False, False],
            str(_flags(p)))
    yield from _switches(p, hud)
    yield from _full_stats(p, hud)
    p.set(hud, TAB.open_var, False)
    p.set(hud, MV.MenuOpen, False)
