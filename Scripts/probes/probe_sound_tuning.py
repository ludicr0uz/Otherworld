"""Sound tuning: the HUD tells the game's sound mix each sound's volume from
sound_tuning.csv, and the SOUND SETTINGS tab changes one live and saves it.

The keys are raised by writing the HUD's SoundTuneRow / SoundTuneNudge /
SoundTuneSaveRequested (a probe has no keyboard); the keys themselves are
graph-checked by verify_graphics_menu.

What a class's volume is in the running game is asked of the audio device
itself: the console's ListSoundClassVolumes logs every class's current
volume, mixes applied, and the probe reads the game's log back (written a
few frames later, so it waits for the whole listing).

  - the HUD's first Ticks tell the mix (SoundTuneApplied) and lower the flag;
  - the audio device holds each class at its built volume: the footsteps
    under 1;
  - a nudge of the footsteps, and one of the wendigo's roar, reach the device;
  - a volume is held at its minimum, 0;
  - the save writes every volume into sound_tuning.csv;
  - drawn, the panel shows the footsteps' volume on its row.

sound_tuning.csv is set aside first and put back.
"""

SYSTEMS = ('menu', 'sound')

import re
import shutil

import unreal

from Sound.catalog import SOUND_STATS
from Sound.tuning import CSV_PATH, FOOTSTEPS, VOLUME_STEP, class_name, read_table, table
from graphics_menu import hud_vars as MV
from graphics_menu import sound_tune_consts as SC
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR
from graphics_menu.umg_consts import ROW_VALUE

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
TAB = SC.SOUND_TAB
WRITABLE = [(HUD_BP_PATH, v) for v in (TAB.open_var, TAB.row_var, TAB.nudge_var,
                                       TAB.save_var, MV.MenuOpen)]
COLUMNS = [s[0] for s in SOUND_STATS]
ROAR = "wendigo_roar"
LIST_COMMAND = "au.Debug.ListSoundClassVolumes"
LISTING = "SoundClass Volumes:"
LINE = re.compile(r"Cur \(\s*([-\d.]+),\s*[-\d.]+\) for SoundClass (\S+)")


def _live_hud(p):
    try:
        hud = p.hud()
    except Exception:
        return None
    return hud if hud is not None and p.get(hud, PROFILE_CHECKED_VAR) else None


def _log_path():
    found = re.search(r'-abslog="?([^"\s]+)', str(unreal.SystemLibrary.get_command_line()))
    return found.group(1) if found else ""


def _listings():
    """Every listing in the game's log so far: [{class name: volume}]."""
    with open(_log_path(), errors="replace") as f:
        parts = f.read().split(LISTING)[1:]
    return [{name: float(v) for v, name in LINE.findall(part)} for part in parts]


def _device_volumes(p):
    """{class name: volume} as the audio device holds them now. A generator:
    the log is written line by line over the next frames, so it waits for a
    new listing that names every class."""
    before = len(_listings())
    unreal.SystemLibrary.execute_console_command(p.world(), LIST_COMMAND)
    wanted = {class_name(c) for c in COLUMNS}
    yield lambda: len(_listings()) > before and wanted <= set(_listings()[-1])
    yield 0.1
    return _listings()[-1]


def _device_matches(got, want):
    return all(abs(got.get(class_name(c), -1.0) - want[c]) < 0.006 for c in COLUMNS)


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
    yield 0.2           # the same Tick's apply, then the device's own update


def _cell(p, hud, column):
    return float(list(p.get(hud, TAB.values_var))[COLUMNS.index(column)])


def _run(p):
    yield lambda: _live_hud(p) is not None
    hud = _live_hud(p)
    built = table()
    yield 0.3
    p.check("the HUD's first Ticks told the mix, and lowered the flag",
            p.get(hud, SC.SOUND_TUNE_APPLIED_VAR) and not p.get(hud, TAB.touched_var),
            f"applied {p.get(hud, SC.SOUND_TUNE_APPLIED_VAR)}, "
            f"touched {p.get(hud, TAB.touched_var)}")
    got = yield from _device_volumes(p)
    p.check(f"the audio device holds each of the {len(COLUMNS)} classes at its built "
            f"volume: the footsteps at {built[FOOTSTEPS]:g}",
            _device_matches(got, built) and built[FOOTSTEPS] < 1.0,
            str({k: v for k, v in got.items() if k.startswith("A_Class_")}))

    p.set(hud, "MenuOpen", True)
    p.set(hud, TAB.open_var, True)
    yield 0.1
    want = dict(built)
    yield from _nudge(p, hud, FOOTSTEPS, 1)
    want[FOOTSTEPS] += VOLUME_STEP
    yield from _nudge(p, hud, ROAR, -1)
    want[ROAR] -= VOLUME_STEP
    got = yield from _device_volumes(p)
    p.check("a nudge up of the footsteps and one down of the wendigo's roar reach "
            "the device, and no other class moves",
            abs(_cell(p, hud, FOOTSTEPS) - want[FOOTSTEPS]) < 1e-6
            and _device_matches(got, want) and not p.get(hud, TAB.touched_var),
            f"footsteps {got.get(class_name(FOOTSTEPS))}, roar {got.get(class_name(ROAR))}, "
            f"want {want[FOOTSTEPS]:g} and {want[ROAR]:g}")

    for _ in range(int(round(want[FOOTSTEPS] / VOLUME_STEP)) + 2):
        yield from _nudge(p, hud, FOOTSTEPS, -1)
    want[FOOTSTEPS] = 0.0
    got = yield from _device_volumes(p)
    p.check("nudged down past its end, a volume stops at 0: silent",
            abs(_cell(p, hud, FOOTSTEPS)) < 1e-6 and _device_matches(got, want),
            f"cell {_cell(p, hud, FOOTSTEPS)}, device {got.get(class_name(FOOTSTEPS))}")

    p.set(hud, TAB.save_var, True)
    yield lambda: not p.get(hud, TAB.save_var)
    saved = read_table()
    p.check(f"the save writes all {len(COLUMNS)} volumes into sound_tuning.csv",
            p.get(hud, TAB.saved_var)
            and all(abs(saved.get(c, -1.0) - want[c]) < 1e-6 for c in COLUMNS),
            str(saved))

    yield from _nudge(p, hud, FOOTSTEPS, 1)
    want[FOOTSTEPS] = VOLUME_STEP
    ui = p.get(hud, "UiPause")
    panel, rows = (ui.get_editor_property(n) for n in (TAB.panel, TAB.rows_box))
    hud.call_method("ReceiveDrawHUD", (1920, 1080))
    subject = str(rows.get_child_at(0).get_editor_property(ROW_VALUE).get_text())
    value = str(rows.get_child_at(1 + COLUMNS.index(FOOTSTEPS))
                .get_editor_property(ROW_VALUE).get_text())
    p.check("drawn, the panel shows the footsteps' volume on its row",
            "COLLAPSED" not in str(panel.get_visibility()).upper()
            and subject == SC.SOUND_SUBJECT and abs(float(value) - want[FOOTSTEPS]) < 0.006,
            f"{panel.get_visibility()} {subject!r} {value!r}")
    p.set(hud, TAB.open_var, False)
    p.set(hud, "MenuOpen", False)
