"""The sights' two timings are the player's (PLAYER SETTINGS): how long the
zoom eases in on the boom before the view cuts to the sights (SightZoomIn),
and how long the gun takes to rise into the view (SightRaise, the ready
pose's blend in through HandRaise). Both go down to 0.

The tab's keys are raised by writing the HUD's PlayerTuneRow / PlayerTuneNudge
(a probe has no keyboard), and SightsForced stands in for the sights key, so
the path is a player's: the tab's apply onto the weapon component, the aim
state, the carry and the seat.

  - a nudge of each row down to its 0 lands on the component (SightZoomIn,
    SightRaise), and is held there (the minimum);
  - with the zoom-in at 0, the frame the sights key goes down is already the
    cut: SightSnapped, SightSeat 1, the zoom the weapon's own, the gun no
    longer lowered: straight from the boom into the sights;
  - with the raise at 0, the equip that raises the gun blends in over 0 s
    (HandRaise 0), and the gun is seated sooner than with the built raise,
    both timed on the game's clock from the key;
  - nudged back up, the built numbers are on the component again.

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end.
"""

LEVEL = "/Game/Maps/Lvl_Forest_200m"  # probe_sight_raise's level: it fails on the 50 m one (T11)
SYSTEMS = ('weapons', 'menu')

import os
import shutil
import time

import unreal

from combat.carry_tuning import LOWERED_VAR
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.player_tuning import PLAYER_STATS, SIGHT_RAISE, SIGHT_ZOOM_IN, table
from combat.seat_tuning import SEAT_VAR, SEATED_VAR, SIGHTS_FORCED_VAR
from combat.weapon_component import vars as WV
from combat.weapon_component.look_vars import HandRaise
from graphics_menu import hud_vars as MV
from graphics_menu import player_tune_consts as PC
from graphics_menu.dev_consts import DEV_GUNS_REQUEST_VAR
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR, PROFILE_SLOT

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
TAB = PC.PLAYER_TAB
WRITABLE = [(HUD_BP_PATH, v) for v in (TAB.open_var, TAB.row_var, TAB.nudge_var,
                                       MV.MenuOpen, DEV_GUNS_REQUEST_VAR)]
WRITABLE += [(WEAPON_COMP_BP_PATH, v) for v in
             (WV.EquippedIndex, WV.NeedsRefresh, SIGHTS_FORCED_VAR)]
COLUMNS = [s[0] for s in PLAYER_STATS]
STEPS = {s[0]: s[2] for s in PLAYER_STATS}
GUN = "BP_Shotgun_C"
SETTLE_S = 0.6          # the equip, the gun coming down
WALL_WAIT_S = 25.0      # a headless game's clock is slow: bound waits by the wall
GS = unreal.GameplayStatics


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{PROFILE_SLOT}.sav")


def _live_hud(p):
    try:
        hud = p.hud()
    except Exception:
        return None
    return hud if hud is not None and p.get(hud, PROFILE_CHECKED_VAR) else None


def _until(cond):
    end = time.time() + WALL_WAIT_S
    return lambda: cond() or time.time() > end


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _tab(p, hud, column, steps, sign):
    """Nudge ``column`` ``steps`` times in ``sign``'s direction, the tab open."""
    p.set(hud, MV.MenuOpen, True)
    p.set(hud, TAB.open_var, True)
    yield 0.1
    for _ in range(steps):
        p.set(hud, TAB.row_var, 1 + COLUMNS.index(column))
        p.set(hud, TAB.nudge_var, sign)
        yield lambda: p.get(hud, TAB.nudge_var) == 0
    yield 0.1           # the next Tick's apply
    p.set(hud, TAB.open_var, False)
    p.set(hud, MV.MenuOpen, False)
    yield 0.1


def _press(p, wc):
    """Lowered and settled, the sights key down: the game-clock seconds to
    SightSeated, and what the first frame after the key showed."""
    yield _until(lambda: p.get(wc, LOWERED_VAR) and p.get(wc, SEAT_VAR) == 0.0)
    yield SETTLE_S
    t0 = GS.get_time_seconds(p.world())
    p.set(wc, SIGHTS_FORCED_VAR, True)
    yield       # one tick: the Tick has read the key once
    first = {"snapped": p.get(wc, "SightSnapped"), "seat": p.get(wc, SEAT_VAR),
             "lowered": p.get(wc, LOWERED_VAR), "zoom": p.get(wc, "CurrentFOV"),
             "want": p.get(wc, "TargetFOV")}
    yield _until(lambda: p.get(wc, SEATED_VAR))
    first["seated_s"] = (GS.get_time_seconds(p.world()) - t0
                         if p.get(wc, SEATED_VAR) else None)
    first["raise"] = p.get(wc, HandRaise)
    p.set(wc, SIGHTS_FORCED_VAR, False)
    yield _until(lambda: p.get(wc, LOWERED_VAR) and p.get(wc, SEAT_VAR) < 1e-4)
    return first


def _run(p):
    yield lambda: _live_hud(p) is not None
    hud = _live_hud(p)
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    built = table()
    p.set(hud, DEV_GUNS_REQUEST_VAR, True)
    yield lambda: not p.get(hud, DEV_GUNS_REQUEST_VAR)
    bag = [i.get_class().get_name() for i in p.get(wc, "Inventory")]
    p.check("the shotgun is in the bag", GUN in bag, str(bag))
    if GUN not in bag:
        return
    p.set(wc, "EquippedIndex", bag.index(GUN))
    p.set(wc, "NeedsRefresh", True)
    yield _until(lambda: p.get(wc, "Held") is not None
                 and p.get(wc, "Held").get_class().get_name() == GUN)

    p.check(f"the component starts on player_tuning.csv's sights zoom-in "
            f"({built[SIGHT_ZOOM_IN]:g} s) and raise ({built[SIGHT_RAISE]:g} s)",
            abs(p.get(wc, WV.SightZoomIn) - built[SIGHT_ZOOM_IN]) < 1e-6
            and abs(p.get(wc, WV.SightRaise) - built[SIGHT_RAISE]) < 1e-6,
            f"SightZoomIn {p.get(wc, WV.SightZoomIn):g}, "
            f"SightRaise {p.get(wc, WV.SightRaise):g}")
    slow = yield from _press(p, wc)
    p.note(f"built: seated {slow['seated_s']} s after the key, HandRaise {slow['raise']}")

    # Both rows down to 0, and one step past it, which the minimum holds.
    downs = {c: int(round(built[c] / STEPS[c])) + 1 for c in (SIGHT_ZOOM_IN, SIGHT_RAISE)}
    for col, n in downs.items():
        yield from _tab(p, hud, col, n, -1)
    p.check("the PLAYER SETTINGS tab's sights zoom-in and raise nudged down land on "
            "the weapon component at 0, held at the minimum",
            p.get(wc, WV.SightZoomIn) == 0.0 and p.get(wc, WV.SightRaise) == 0.0,
            f"SightZoomIn {p.get(wc, WV.SightZoomIn)}, "
            f"SightRaise {p.get(wc, WV.SightRaise)}")

    fast = yield from _press(p, wc)
    p.check("with the zoom-in at 0, the frame the sights key goes down is the cut: "
            "SightSnapped, SightSeat 1, the zoom the weapon's own and the gun "
            "raised, straight from the boom into the sights",
            fast["snapped"] and fast["seat"] > 0.9999 and not fast["lowered"]
            and abs(fast["zoom"] - fast["want"]) < 1e-3,
            f"SightSnapped {fast['snapped']}, {SEAT_VAR} {fast['seat']:.4f}, "
            f"{LOWERED_VAR} {fast['lowered']}, FOV {fast['zoom']:.3f} of "
            f"{fast['want']:.3f}")
    p.check("with the raise at 0, the gun's ready pose blends in over 0 s "
            "(HandRaise) and the gun is seated sooner than with the built raise",
            fast["raise"] == 0.0 and fast["seated_s"] is not None
            and slow["seated_s"] is not None and fast["seated_s"] < slow["seated_s"],
            f"seated {fast['seated_s']} s after the key, built {slow['seated_s']} s; "
            f"HandRaise {fast['raise']}")

    for col, n in downs.items():
        yield from _tab(p, hud, col, n - 1, 1)
    p.check("nudged back up, the component holds the built numbers again",
            abs(p.get(wc, WV.SightZoomIn) - built[SIGHT_ZOOM_IN]) < 1e-6
            and abs(p.get(wc, WV.SightRaise) - built[SIGHT_RAISE]) < 1e-6,
            f"SightZoomIn {p.get(wc, WV.SightZoomIn):g}, "
            f"SightRaise {p.get(wc, WV.SightRaise):g}")
