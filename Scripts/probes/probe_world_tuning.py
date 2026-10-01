"""World tuning: a game starts at a random time of day, and the M panel's [O]
tab shows the clock as an hour, moves it, changes the day's length, and
saves world_tuning.csv.

The keys are raised by writing the HUD's WorldTuneRow / WorldTuneNudge /
WorldTuneSaveRequested (a probe has no keyboard); the keys themselves are the
verifier's.

  - the cycle has RandomStart and its clock is not where a fixed start would
    put it (a 1-in-100 chance of a false failure: a random clock can land
    there);
  - opened, the tab's hour is the cycle's clock on the dial;
  - one nudge up moves the clock half an hour, and 25 more cross into the
    other half of the cycle, where IsDay agrees with the hour;
  - a day length nudge lands on the cycle, and a night cold nudge;
  - the save writes the lengths and the night cold into world_tuning.csv;
  - the panel, drawn by hand, shows the hour on its row.

world_tuning.csv is set aside first and put back.
"""

import shutil

import unreal

from graphics_menu import world_tune_consts as WC
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR
from graphics_menu.umg_consts import ROW_VALUE
from world import world_config as cfg
from world.day_night_blueprint import NIGHT_COLD_VAR, RANDOM_START_VAR
from world.paths import DAY_NIGHT_CLASS_PATH
from world.world_tuning import CSV_PATH, WORLD_STATS, read_table

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
TAB = WC.WORLD_TAB
WRITABLE = [(HUD_BP_PATH, v) for v in (TAB.open_var, TAB.row_var, TAB.nudge_var,
                                       TAB.save_var, "MenuOpen")]
HOUR_STEP = WORLD_STATS[0][3]
DAY_STEP = WORLD_STATS[1][3]
COLD_STEP = WORLD_STATS[3][3]


def _live_hud(p):
    try:
        hud = p.hud()
    except Exception:
        return None
    return hud if hud is not None and p.get(hud, PROFILE_CHECKED_VAR) else None


def _dial(a, b):
    """How far apart two hours are, round the 24-hour dial."""
    d = abs(a - b) % 24.0
    return min(d, 24.0 - d)


def probe(p):
    backup = CSV_PATH + ".probe-backup"
    shutil.copy2(CSV_PATH, backup)
    try:
        yield from _run(p)
    finally:
        shutil.move(backup, CSV_PATH)


def _nudge(p, hud, row, step, times=1):
    p.set(hud, TAB.row_var, row)
    for _ in range(times):
        p.set(hud, TAB.nudge_var, step)
        yield lambda: p.get(hud, TAB.nudge_var) == 0
    yield 0.1           # the next Tick's apply and read-back


def _hour(p, cycle):
    return cfg.clock_to_hour(p.get(cycle, "Clock"), p.get(cycle, "DayLengthSeconds"),
                             p.get(cycle, "NightLengthSeconds"))


def _run(p):
    yield lambda: _live_hud(p) is not None
    hud, cycle = _live_hud(p), p.actor_of(DAY_NIGHT_CLASS_PATH)
    t = unreal.GameplayStatics.get_time_seconds(p.world())
    clock = p.get(cycle, "Clock")
    fixed = (cfg.START_CLOCK_S + t) % cfg.cycle_length()
    p.check("the game starts at a random time of day, not the fixed start",
            p.get(cycle, RANDOM_START_VAR) and 0.0 <= clock < cfg.cycle_length()
            and abs(clock - fixed) > 2.5,
            f"clock {clock:.1f} s, the fixed start would be {fixed:.1f} s")

    p.set(hud, "MenuOpen", True)
    p.set(hud, TAB.open_var, True)
    yield 0.1
    shown = float(list(p.get(hud, TAB.values_var))[0])
    p.check("opened, the tab's hour is the cycle's clock on the dial",
            _dial(shown, _hour(p, cycle)) < 0.02, f"{shown:.3f} vs {_hour(p, cycle):.3f}")

    before = _hour(p, cycle)
    yield from _nudge(p, hud, WC.HOUR_ROW, 1)
    after = _hour(p, cycle)
    p.check("one nudge up moves the clock half an hour",
            _dial(after, before + HOUR_STEP) < 0.03, f"{before:.3f} -> {after:.3f}")

    yield from _nudge(p, hud, WC.HOUR_ROW, 1, times=25)
    far = _hour(p, cycle)
    want = (after + 25 * HOUR_STEP) % 24.0
    day = cfg.SUNRISE_HOUR <= far < cfg.SUNRISE_HOUR + cfg.HALF_HOURS
    p.check("25 more cross into the other half, and IsDay agrees with the hour",
            _dial(far, want) < 0.1 and bool(p.get(cycle, "IsDay")) == day,
            f"{far:.3f} vs {want:.3f}, IsDay {p.get(cycle, 'IsDay')}")

    length = p.get(cycle, "DayLengthSeconds")
    yield from _nudge(p, hud, WC.HOUR_ROW + 1, 1)
    p.check("a day length nudge lands on the cycle",
            abs(p.get(cycle, "DayLengthSeconds") - (length + DAY_STEP)) < 1e-3,
            f"{length} -> {p.get(cycle, 'DayLengthSeconds')}")

    cold = p.get(cycle, NIGHT_COLD_VAR)
    yield from _nudge(p, hud, WC.HOUR_ROW + 3, 1)
    p.check("a night cold nudge lands on the cycle",
            abs(p.get(cycle, NIGHT_COLD_VAR) - (cold + COLD_STEP)) < 1e-6,
            f"{cold} -> {p.get(cycle, NIGHT_COLD_VAR)}")

    p.set(hud, TAB.save_var, True)
    yield lambda: not p.get(hud, TAB.save_var)
    saved = read_table()
    p.check("the save writes the lengths and the night cold into world_tuning.csv",
            p.get(hud, TAB.saved_var)
            and saved.get("day_length_s") == length + DAY_STEP
            and saved.get("night_length_s") == p.get(cycle, "NightLengthSeconds")
            and abs(saved.get("night_temperature_drop_per_s", -1.0)
                    - (cold + COLD_STEP)) < 1e-6,
            str(saved))

    ui = p.get(hud, "UiPause")
    panel, rows = (ui.get_editor_property(n) for n in (TAB.panel, TAB.rows_box))
    p.set(hud, TAB.row_var, WC.HOUR_ROW)
    hud.call_method("ReceiveDrawHUD", (1920, 1080))
    subject = str(rows.get_child_at(0).get_editor_property(ROW_VALUE).get_text())
    value = str(rows.get_child_at(WC.HOUR_ROW).get_editor_property(ROW_VALUE).get_text())
    p.check("drawn, the panel shows the hour on its row",
            "COLLAPSED" not in str(panel.get_visibility()).upper()
            and subject == WC.WORLD_SUBJECT and _dial(float(value), _hour(p, cycle)) < 0.05,
            f"{panel.get_visibility()} {subject!r} {value!r}")
    p.set(hud, TAB.open_var, False)
    p.set(hud, "MenuOpen", False)
