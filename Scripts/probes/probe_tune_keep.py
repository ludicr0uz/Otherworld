"""What a tuning tab keeps between sessions (graphics_menu/tune_keep.py), on
the PLAYER SETTINGS tab: a nudge is saved to the tab's slot, the next level's
HUD loads it over the built table and applies it, and a save made over
another built table is left alone.

  - a fresh game has the built table and no save (boot.py set any aside);
  - a jog nudge writes the tab's slot;
  - the level opened again: the HUD's table holds the nudge, the tab is
    touched, and the new player's component jogs at it;
  - the save rewritten as if made over another CSV: the level opened again
    starts from the built table, untouched.

The slot is boot.py's to clear and put back (probes/kept_slots.py).
"""

SYSTEMS = ('menu',)

import os

import unreal

from combat.paths import WEAPON_COMP_CLASS_PATH
from combat.player_tuning import JOG_SPEED, PLAYER_STATS, cms, table
from combat.sprint_tuning import BASE_SPEED_VAR
from graphics_menu import hud_vars as MV
from graphics_menu import player_tune_consts as PC
from graphics_menu import tune_keep_consts as KC
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
TAB = PC.PLAYER_TAB
WRITABLE = [(HUD_BP_PATH, v) for v in (TAB.open_var, TAB.row_var, TAB.nudge_var, MV.MenuOpen)]
WRITABLE += [(KC.TUNE_SAVE_BP_PATH, KC.TUNE_SAVE_BUILT_FIELD)]
COLUMNS = [s[0] for s in PLAYER_STATS]
JOG = COLUMNS.index(JOG_SPEED)
STEP = PLAYER_STATS[JOG][2]


def _live_hud(p, not_this=None):
    try:
        hud = p.hud()
    except Exception:
        return None
    if hud is None or (not_this is not None and hud == not_this):
        return None
    return hud if p.get(hud, PROFILE_CHECKED_VAR) else None


def _slot_file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{TAB.keep_slot}.sav")


def _reopened(p, hud):
    """Open the level again; wait for its new HUD and player. Returns the HUD."""
    unreal.GameplayStatics.open_level(p.world(), p.map_path, True, "")
    yield lambda: _live_hud(p, not_this=hud) is not None and p.pawn() is not None
    yield 0.3           # the first Ticks' apply
    return p.hud()


def _cells(p, hud):
    return [float(v) for v in p.get(hud, TAB.values_var)]


def _base_speed(p):
    return float(p.get(p.component(p.pawn(), WEAPON_COMP_CLASS_PATH), BASE_SPEED_VAR))


def probe(p):
    yield lambda: _live_hud(p) is not None
    hud = _live_hud(p)
    built = [float(table()[c]) for c in COLUMNS]
    yield 0.2
    p.check("a fresh game has the built table, untouched, and no save of the tab's",
            _cells(p, hud) == built and not p.get(hud, TAB.touched_var)
            and not os.path.exists(_slot_file()),
            f"{_cells(p, hud)}, touched {p.get(hud, TAB.touched_var)}, "
            f"file {os.path.exists(_slot_file())}")

    p.set(hud, "MenuOpen", True)
    p.set(hud, TAB.open_var, True)
    yield 0.1
    p.set(hud, TAB.row_var, 1 + JOG)
    p.set(hud, TAB.nudge_var, 1)
    yield lambda: p.get(hud, TAB.nudge_var) == 0
    yield 0.1
    want = list(built)
    want[JOG] += STEP
    kept = unreal.GameplayStatics.load_game_from_slot(TAB.keep_slot, KC.TUNE_SAVE_USER_INDEX)
    p.check(f"a jog nudge writes slot {TAB.keep_slot!r}: the table, and the built one "
            "it was made over",
            kept is not None
            and [float(v) for v in p.get(kept, KC.TUNE_SAVE_TABLE_FIELD)] == want
            and [float(v) for v in p.get(kept, KC.TUNE_SAVE_BUILT_FIELD)] == built,
            f"file {os.path.exists(_slot_file())}, save {kept}")

    hud = yield from _reopened(p, hud)
    p.check("the level opened again: the HUD's table holds the nudge, the tab is "
            "touched, and the new player's component jogs at it",
            _cells(p, hud) == want and p.get(hud, TAB.touched_var)
            and abs(_base_speed(p) - cms(want[JOG])) < 0.5,
            f"{_cells(p, hud)}, touched {p.get(hud, TAB.touched_var)}, "
            f"BaseSpeed {_base_speed(p):.1f}, want {cms(want[JOG]):.1f}")

    # As if the CSV had changed since the save: another built table under it.
    other = list(built)
    other[JOG] += 10 * STEP
    p.set(kept, KC.TUNE_SAVE_BUILT_FIELD, other)
    unreal.GameplayStatics.save_game_to_slot(kept, TAB.keep_slot, KC.TUNE_SAVE_USER_INDEX)
    hud = yield from _reopened(p, hud)
    p.check("a save made over another built table is left alone: the built table, "
            "untouched, at the built jog",
            _cells(p, hud) == built and not p.get(hud, TAB.touched_var)
            and abs(_base_speed(p) - cms(built[JOG])) < 0.5,
            f"{_cells(p, hud)}, touched {p.get(hud, TAB.touched_var)}, "
            f"BaseSpeed {_base_speed(p):.1f}")
