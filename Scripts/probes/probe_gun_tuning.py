"""Gun tuning: the M panel's gun tuning tab changes a carried gun at once, and saves
gun_tuning.csv.

The keys are raised by writing the HUD's TuneRow / TuneWeapon / TuneNudge /
TuneSaveRequested (a probe has no keyboard); the keys themselves are the
verifier's. With the shotgun issued:

  - one nudge up on its damage row lands on the carried shotgun's Damage;
  - pellets nudged down ten times stop at the minimum, 1, and land rounded;
  - one nudge up on its throw arc row lands on its ThrowArcDegrees, which the
    throw's launch reads (probe_throw.py shows the arc following it);
  - with the knife shown, a nudge up on its throw damage row lands on the
    carried knife's ThrowDamage, and one on its damage row, which is not a
    melee weapon's, moves nothing; nor does one on the shotgun's throw damage
    row, which is not a gun's;
  - Left on the gun row wraps from the first gun to the last weapon;
  - the pistol's numbers are untouched;
  - the save writes those numbers, and only those, into gun_tuning.csv, the
    knife's row holding its throw alone;
  - the panel, drawn by hand, shows the gun and the value on the caret's row,
    and a dash on a row that is not the shown weapon's.

gun_tuning.csv and any saved profile are set aside first and put back.
"""

import os
import shutil

import unreal

from combat.gun_tuning import CSV_PATH, MELEE_COLUMNS, TUNE_STATS, read_table
from combat.knife import KNIFE_DISPLAY
from combat.paths import WEAPON_COMP_CLASS_PATH
from combat.throw_tuning import (
    THROW_DAMAGE_COLUMN, THROW_DAMAGE_VAR, THROW_PITCH_COLUMN, THROW_PITCH_VAR,
)
from graphics_menu import tune_consts as TC
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR, PROFILE_SLOT
from graphics_menu.umg_consts import ROW_CARET, ROW_VALUE

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HUD_BP_PATH, v) for v in (TC.TUNE_OPEN_VAR, TC.TUNE_ROW_VAR,
                                       TC.TUNE_WEAPON_VAR, TC.TUNE_NUDGE_VAR,
                                       TC.TUNE_SAVE_VAR, "MenuOpen")]
COLS = [s[0] for s in TUNE_STATS]
N = len(TUNE_STATS)


def _profile():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{PROFILE_SLOT}.sav")


def _live_hud(p):
    try:
        hud = p.hud()
    except Exception:
        return None
    return hud if hud is not None and p.get(hud, PROFILE_CHECKED_VAR) else None


def probe(p):
    kept = [(f, f + ".probe-backup") for f in (_profile(), CSV_PATH)]
    for f, b in kept:
        if os.path.exists(f):
            shutil.copy2(f, b) if f == CSV_PATH else shutil.move(f, b)
    try:
        yield from _run(p)
    finally:
        for f, b in kept:
            if os.path.exists(b):
                shutil.move(b, f)


def _nudge(p, hud, row, step, times=1):
    p.set(hud, TC.TUNE_ROW_VAR, row)
    for _ in range(times):
        p.set(hud, TC.TUNE_NUDGE_VAR, step)
        yield lambda: p.get(hud, TC.TUNE_NUDGE_VAR) == 0
    yield 0.1           # the next Tick's apply


def _gun(p, wc, name):
    return next((i for i in p.get(wc, "Inventory") if p.get(i, "DisplayName") == name), None)


def _run(p):
    yield lambda: _live_hud(p) is not None
    hud = _live_hud(p)
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    guns = [str(g) for g in p.get(hud, TC.TUNE_WEAPONS_VAR)]
    shotgun, pistol = _gun(p, wc, "Shotgun"), _gun(p, wc, "Pistol")
    p.check("the shotgun and pistol are carried, and the table lists them first",
            shotgun is not None and pistol is not None and guns[:2] == ["Shotgun", "Pistol"],
            str(guns))
    before = float(p.get(shotgun, "Damage"))
    pistol_before = [float(p.get(pistol, s[1])) for s in TUNE_STATS]

    p.set(hud, TC.TUNE_WEAPON_VAR, 0)
    yield from _nudge(p, hud, 1 + COLS.index("damage"), 1)
    p.check("one nudge up raises the carried shotgun's damage by its step",
            abs(float(p.get(shotgun, "Damage")) - (before + TUNE_STATS[0][3])) < 1e-6,
            f"{before} -> {p.get(shotgun, 'Damage')}")

    yield from _nudge(p, hud, 1 + COLS.index("pellets"), -1, times=10)
    p.check("pellets nudged down stop at the minimum and land as a whole number",
            p.get(shotgun, "PelletCount") == 1, str(p.get(shotgun, "PelletCount")))
    arc_stat = TUNE_STATS[COLS.index(THROW_PITCH_COLUMN)]
    arc = float(p.get(shotgun, THROW_PITCH_VAR))
    yield from _nudge(p, hud, 1 + COLS.index(THROW_PITCH_COLUMN), 1)
    p.check("one nudge up on the throw arc row tips the carried shotgun's throw "
            "up by its step",
            arc_stat[1] == THROW_PITCH_VAR
            and abs(float(p.get(shotgun, THROW_PITCH_VAR)) - (arc + arc_stat[3])) < 1e-6,
            f"{arc} -> {p.get(shotgun, THROW_PITCH_VAR)} deg")
    p.check("the pistol is untouched",
            [float(p.get(pistol, s[1])) for s in TUNE_STATS] == pistol_before)

    # The melee rows: only the throw is the knife's, and its damage no gun's.
    knife = _gun(p, wc, KNIFE_DISPLAY)
    p.check("the knife is carried, and the table lists it after the guns",
            knife is not None and KNIFE_DISPLAY in guns[2:], str(guns))
    if knife is None or KNIFE_DISPLAY not in guns:
        return
    hit_row = 1 + COLS.index(THROW_DAMAGE_COLUMN)
    hit_stat = TUNE_STATS[COLS.index(THROW_DAMAGE_COLUMN)]
    yield from _nudge(p, hud, hit_row, 1)
    p.check("a nudge on the shotgun's throw damage row, which is no gun's, "
            "moves nothing: a thrown gun still takes nothing",
            float(p.get(shotgun, THROW_DAMAGE_VAR)) == 0.0
            and float(p.get(hud, TC.TUNE_VALUES_VAR)[COLS.index(THROW_DAMAGE_COLUMN)]) == 0.0,
            str(p.get(shotgun, THROW_DAMAGE_VAR)))
    k = guns.index(KNIFE_DISPLAY)
    p.set(hud, TC.TUNE_WEAPON_VAR, k)
    hit, slash = float(p.get(knife, THROW_DAMAGE_VAR)), float(p.get(knife, "Damage"))
    yield from _nudge(p, hud, hit_row, 1)
    p.check("with the knife shown, one nudge up on its throw damage row raises "
            "the carried knife's ThrowDamage by its step",
            hit_stat[1] == THROW_DAMAGE_VAR
            and abs(float(p.get(knife, THROW_DAMAGE_VAR)) - (hit + hit_stat[3])) < 1e-6,
            f"{hit} -> {p.get(knife, THROW_DAMAGE_VAR)}")
    cells = [float(v) for v in p.get(hud, TC.TUNE_VALUES_VAR)]
    yield from _nudge(p, hud, 1 + COLS.index("damage"), 1)
    p.check("...and one on its damage row, which is not a melee weapon's, moves nothing",
            float(p.get(knife, "Damage")) == slash
            and [float(v) for v in p.get(hud, TC.TUNE_VALUES_VAR)] == cells,
            f"{slash} -> {p.get(knife, 'Damage')}")
    p.check("the shotgun is as it was tuned, the knife's rows aside",
            abs(float(p.get(shotgun, "Damage")) - (before + TUNE_STATS[0][3])) < 1e-6
            and p.get(shotgun, "PelletCount") == 1)

    p.set(hud, TC.TUNE_WEAPON_VAR, 0)
    yield from _nudge(p, hud, 0, -1)
    p.check("Left on the gun row wraps to the last weapon",
            p.get(hud, TC.TUNE_WEAPON_VAR) == len(guns) - 1,
            str(p.get(hud, TC.TUNE_WEAPON_VAR)))

    old = read_table()
    p.set(hud, TC.TUNE_SAVE_VAR, True)
    yield lambda: not p.get(hud, TC.TUNE_SAVE_VAR)
    new = read_table()
    p.check("the save succeeds (TuneSaved)", p.get(hud, TC.TUNE_SAVED_VAR))
    want = dict(old.get("Shotgun", {}), damage=before + TUNE_STATS[0][3], pellets=1,
                **{THROW_PITCH_COLUMN: arc + arc_stat[3]})
    p.check("the CSV holds the tuned shotgun", new.get("Shotgun") == want,
            str(new.get("Shotgun")))
    p.check("...and the tuned knife, its row its throw alone",
            new.get(KNIFE_DISPLAY) == dict(old.get(KNIFE_DISPLAY, {}),
                                           **{THROW_DAMAGE_COLUMN: hit + hit_stat[3]})
            and set(new.get(KNIFE_DISPLAY, {})) == set(MELEE_COLUMNS),
            str(new.get(KNIFE_DISPLAY)))
    p.check("...and every other weapon as it was",
            all(new.get(g) == old.get(g) for g in guns
                if g not in ("Shotgun", KNIFE_DISPLAY)))

    ui = p.get(hud, "UiPause")
    panel, rows = (ui.get_editor_property(n) for n in (TC.TUNE_PANEL, TC.TUNE_ROWS_BOX))
    p.set(hud, "MenuOpen", True)
    p.set(hud, TC.TUNE_OPEN_VAR, True)
    p.set(hud, TC.TUNE_WEAPON_VAR, 0)
    p.set(hud, TC.TUNE_ROW_VAR, 1 + COLS.index("damage"))
    hud.call_method("ReceiveDrawHUD", (1920, 1080))
    gun_row = rows.get_child_at(0)
    row = rows.get_child_at(1 + COLS.index("damage"))
    shown = str(gun_row.get_editor_property(ROW_VALUE).get_text())
    value = str(row.get_editor_property(ROW_VALUE).get_text())
    p.check("drawn, the panel shows the gun and its damage on the caret's row",
            "COLLAPSED" not in str(panel.get_visibility()).upper() and shown == "Shotgun"
            and float(value) == before + TUNE_STATS[0][3]
            and row.get_editor_property(ROW_CARET).get_render_opacity() == 1.0,
            f"{panel.get_visibility()} {shown!r} {value!r}")
    p.set(hud, TC.TUNE_WEAPON_VAR, k)
    hud.call_method("ReceiveDrawHUD", (1920, 1080))
    shown = str(gun_row.get_editor_property(ROW_VALUE).get_text())
    value = str(row.get_editor_property(ROW_VALUE).get_text())
    thrown = str(rows.get_child_at(hit_row).get_editor_property(ROW_VALUE).get_text())
    p.check("with the knife shown, its damage row is a dash and its throw "
            "damage row its number",
            shown == KNIFE_DISPLAY and value == TC.TUNE_DASH
            and float(thrown) == hit + hit_stat[3], f"{shown!r} {value!r} {thrown!r}")
    p.set(hud, TC.TUNE_OPEN_VAR, False)
    hud.call_method("ReceiveDrawHUD", (1920, 1080))
    p.check("shut, the panel is collapsed",
            "COLLAPSED" in str(panel.get_visibility()).upper(), str(panel.get_visibility()))
    p.set(hud, "MenuOpen", False)
