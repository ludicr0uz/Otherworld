"""Player tuning: the player jogs and sprints at player_tuning.csv's speeds,
the stamina bar refills at its rate, and the menu's player tab changes all
four on the live player and saves player_tuning.csv.

The keys are raised by writing the HUD's PlayerTuneRow / PlayerTuneNudge /
PlayerTuneSaveRequested (a probe has no keyboard); the keys themselves are
the verifier's. No key can be injected either, so the sprint itself never
runs here: its speed and drain are read off the component, and
verify/sprint.py checks that the graph reads them.

  - the player's walk speed is the built jog, and the component holds the
    built sprint speed and stamina rates;
  - an emptied bar refills at the regen rate, timed on the game's clock;
  - a nudge of each row lands on the component in its units, and the jog on
    the character's MaxWalkSpeed the next Tick;
  - the save writes all four into player_tuning.csv;
  - the panel, drawn by hand, shows the jog on its row.

player_tuning.csv is set aside first and put back.
"""

import shutil

import unreal

from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.player_tuning import (
    CSV_PATH, JOG_SPEED, PLAYER_STATS, SPRINT_DURATION, SPRINT_SPEED, STAMINA_RECHARGE,
    cms, per_second, read_table, table,
)
from combat.sprint_tuning import (
    BASE_SPEED_VAR, SPRINT_SPEED_VAR, STAMINA_DRAIN_VAR, STAMINA_REGEN_VAR,
)
from graphics_menu import player_tune_consts as PC
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR
from graphics_menu.umg_consts import ROW_VALUE

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
TAB = PC.PLAYER_TAB
WRITABLE = [(HUD_BP_PATH, v) for v in (TAB.open_var, TAB.row_var, TAB.nudge_var,
                                       TAB.save_var, "MenuOpen")]
WRITABLE += [(WEAPON_COMP_BP_PATH, "Stamina")]
COLUMNS = [s[0] for s in PLAYER_STATS]
STEPS = {s[0]: s[2] for s in PLAYER_STATS}


def _live_hud(p):
    try:
        hud = p.hud()
    except Exception:
        return None
    return hud if hud is not None and p.get(hud, PROFILE_CHECKED_VAR) else None


def probe(p):
    backup = CSV_PATH + ".probe-backup"
    shutil.copy2(CSV_PATH, backup)
    try:
        yield from _run(p)
    finally:
        shutil.move(backup, CSV_PATH)


def _nudge(p, hud, column, step):
    p.set(hud, TAB.row_var, 1 + COLUMNS.index(column))
    p.set(hud, TAB.nudge_var, step)
    yield lambda: p.get(hud, TAB.nudge_var) == 0
    yield 0.1           # the next Tick's apply, and the sprint's write after it


def _walk(p):
    return float(p.pawn().get_editor_property("character_movement")
                 .get_editor_property("max_walk_speed"))


def _run(p):
    yield lambda: _live_hud(p) is not None
    hud = _live_hud(p)
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    built = table()
    full = float(p.get(wc, "MaxStamina"))
    yield 0.1
    p.check(f"the player jogs at the built {built[JOG_SPEED]:g} m/s",
            abs(_walk(p) - cms(built[JOG_SPEED])) < 0.5
            and abs(p.get(wc, BASE_SPEED_VAR) - cms(built[JOG_SPEED])) < 0.5,
            f"MaxWalkSpeed {_walk(p):.1f}, BaseSpeed {p.get(wc, BASE_SPEED_VAR):.1f}")
    drain, regen = p.get(wc, STAMINA_DRAIN_VAR), p.get(wc, STAMINA_REGEN_VAR)
    p.check(f"...and would sprint at {built[SPRINT_SPEED]:g} m/s for "
            f"{built[SPRINT_DURATION]:g} s from a full bar",
            abs(p.get(wc, SPRINT_SPEED_VAR) - cms(built[SPRINT_SPEED])) < 0.5
            and abs(full / drain - built[SPRINT_DURATION]) < 1e-3,
            f"SprintSpeed {p.get(wc, SPRINT_SPEED_VAR):.1f}, drain {drain:.3f}/s of {full:g}")

    # The refill, timed on the game's own clock (a headless frame is a fixed
    # small step, so wall time says nothing).
    p.set(wc, "Stamina", 0.0)
    t0 = unreal.GameplayStatics.get_time_seconds(p.world())
    yield 0.5
    gained = float(p.get(wc, "Stamina"))
    took = unreal.GameplayStatics.get_time_seconds(p.world()) - t0
    rate = gained / took if took > 0 else 0.0
    p.check(f"an emptied bar refills at the rate that fills it in "
            f"{built[STAMINA_RECHARGE]:g} s",
            abs(regen - per_second(full, built[STAMINA_RECHARGE])) < 1e-3
            and abs(rate - regen) < 0.15 * regen,
            f"{gained:.2f} in {took:.3f} s = {rate:.2f}/s, regen {regen:.3f}/s")

    p.set(hud, "MenuOpen", True)
    p.set(hud, TAB.open_var, True)
    yield 0.1
    want = dict(built)
    yield from _nudge(p, hud, JOG_SPEED, 1)
    want[JOG_SPEED] += STEPS[JOG_SPEED]
    p.check("a jog nudge lands on BaseSpeed and on the character's walk speed",
            abs(p.get(wc, BASE_SPEED_VAR) - cms(want[JOG_SPEED])) < 0.5
            and abs(_walk(p) - cms(want[JOG_SPEED])) < 0.5,
            f"BaseSpeed {p.get(wc, BASE_SPEED_VAR):.1f}, MaxWalkSpeed {_walk(p):.1f}, "
            f"want {cms(want[JOG_SPEED]):.1f}")

    yield from _nudge(p, hud, SPRINT_SPEED, -1)
    want[SPRINT_SPEED] -= STEPS[SPRINT_SPEED]
    p.check("a sprint speed nudge lands on SprintSpeed",
            abs(p.get(wc, SPRINT_SPEED_VAR) - cms(want[SPRINT_SPEED])) < 0.5,
            f"{p.get(wc, SPRINT_SPEED_VAR):.1f}, want {cms(want[SPRINT_SPEED]):.1f}")

    yield from _nudge(p, hud, SPRINT_DURATION, 1)
    want[SPRINT_DURATION] += STEPS[SPRINT_DURATION]
    yield from _nudge(p, hud, STAMINA_RECHARGE, 1)
    want[STAMINA_RECHARGE] += STEPS[STAMINA_RECHARGE]
    drain, regen = p.get(wc, STAMINA_DRAIN_VAR), p.get(wc, STAMINA_REGEN_VAR)
    p.check("the two time nudges land as stamina rates: the bar over the seconds",
            abs(drain - per_second(full, want[SPRINT_DURATION])) < 1e-3
            and abs(regen - per_second(full, want[STAMINA_RECHARGE])) < 1e-3,
            f"drain {drain:.4f}, regen {regen:.4f}")

    p.set(hud, TAB.save_var, True)
    yield lambda: not p.get(hud, TAB.save_var)
    saved = read_table()
    p.check("the save writes all four into player_tuning.csv",
            p.get(hud, TAB.saved_var)
            and all(abs(saved.get(c, -1.0) - want[c]) < 1e-6 for c in COLUMNS),
            str(saved))

    ui = p.get(hud, "UiPause")
    panel, rows = (ui.get_editor_property(n) for n in (TAB.panel, TAB.rows_box))
    hud.call_method("ReceiveDrawHUD", (1920, 1080))
    subject = str(rows.get_child_at(0).get_editor_property(ROW_VALUE).get_text())
    value = str(rows.get_child_at(1).get_editor_property(ROW_VALUE).get_text())
    p.check("drawn, the panel shows the jog on its row",
            "COLLAPSED" not in str(panel.get_visibility()).upper()
            and subject == PC.PLAYER_SUBJECT and abs(float(value) - want[JOG_SPEED]) < 0.01,
            f"{panel.get_visibility()} {subject!r} {value!r}")
    p.set(hud, TAB.open_var, False)
    p.set(hud, "MenuOpen", False)
