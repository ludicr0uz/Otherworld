"""Only a gun is aimed down its sights: the knife, the axe and the matches are not.

Each issued item is taken in hand the way Q does (EquippedIndex + NeedsRefresh)
and the sights key is held (SightsForced: no key can be injected into a
headless game). With the knife, the axe or the matches the key must aim over
the shoulder: Aiming, but never SightAiming, and the camera never leaves the
boom (SightSeated false, SightSeat 0) on any frame. With the shotgun and the
pistol, the positive case, the same key must bring the camera onto the sights.

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end.
"""

import os
import shutil

import unreal

from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.seat_tuning import (
    HAS_SIGHTS_VAR, SEAT_VAR, SEATED_VAR, SIGHTS_FORCED_VAR,
)
from combat.tuning import COMBAT
from graphics_menu.profile_consts import PROFILE_SLOT

WRITABLE = [(WEAPON_COMP_BP_PATH, v)
            for v in ("EquippedIndex", "NeedsRefresh", SIGHTS_FORCED_VAR)]

ITEMS = (("BP_Knife_C", "the knife"), ("BP_Axe_C", "the axe"),
         ("BP_Matches_C", "the matches"))
GUNS = (("BP_Shotgun_C", "the shotgun"), ("BP_Pistol_C", "the pistol"))

HELD_S = 0.8            # longer than a gun takes to come up and seat the camera
ZOOM_TOL = 0.05


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{PROFILE_SLOT}.sav")


def _until(cond):
    return lambda: bool(cond())


def _equip(p, wc, bag, cls):
    p.set(wc, SIGHTS_FORCED_VAR, False)
    p.set(wc, "EquippedIndex", bag.index(cls))
    p.set(wc, "NeedsRefresh", True)
    held = lambda: p.get(wc, "Held")
    yield _until(lambda: held() is not None and held().get_class().get_name() == cls)
    yield _until(lambda: p.get(wc, SEAT_VAR) == 0.0 and not p.get(wc, "SightAiming"))
    yield 0.2


def _item(p, wc, bag, cls, label):
    yield from _equip(p, wc, bag, cls)
    held = p.get(wc, "Held")
    p.check(f"{label}: in hand, and it has no sights ({HAS_SIGHTS_VAR} False)",
            held.get_editor_property(HAS_SIGHTS_VAR) is False,
            str(held.get_editor_property(HAS_SIGHTS_VAR)))

    p.set(wc, SIGHTS_FORCED_VAR, True)
    seen = {"frames": 0, "sight": 0, "seated": 0, "seat": 0.0, "aiming": 0}
    t0 = unreal.GameplayStatics.get_time_seconds(p.world())

    def watch():
        seen["frames"] += 1
        seen["sight"] += bool(p.get(wc, "SightAiming"))
        seen["seated"] += bool(p.get(wc, SEATED_VAR))
        seen["seat"] = max(seen["seat"], p.get(wc, SEAT_VAR))
        seen["aiming"] += bool(p.get(wc, "Aiming"))
        return unreal.GameplayStatics.get_time_seconds(p.world()) - t0 > HELD_S
    yield _until(watch)

    p.check(f"{label}: the sights key held {HELD_S:g} s never aims down the sights "
            f"(SightAiming False on every frame)",
            seen["frames"] > 5 and seen["sight"] == 0,
            f"SightAiming on {seen['sight']} of {seen['frames']} frames")
    p.check(f"{label}: ...and the camera never leaves the boom "
            f"({SEATED_VAR} False, {SEAT_VAR} 0)",
            seen["seated"] == 0 and seen["seat"] == 0.0,
            f"{SEATED_VAR} on {seen['seated']} frames, {SEAT_VAR} up to {seen['seat']:.4f}")
    zoom = p.get(wc, "AimZoom")
    p.check(f"{label}: ...the key aims over the shoulder instead (Aiming, "
            f"{COMBAT.shoulder_zoom:g}x)",
            seen["aiming"] >= seen["frames"] - 1
            and abs(zoom - COMBAT.shoulder_zoom) < ZOOM_TOL,
            f"Aiming on {seen['aiming']} of {seen['frames']} frames, AimZoom {zoom:.2f}")
    p.set(wc, SIGHTS_FORCED_VAR, False)


def _gun(p, wc, bag, cls, label):
    yield from _equip(p, wc, bag, cls)
    held = p.get(wc, "Held")
    p.check(f"{label}: in hand, and it has sights ({HAS_SIGHTS_VAR})",
            held.get_editor_property(HAS_SIGHTS_VAR) is True,
            str(held.get_editor_property(HAS_SIGHTS_VAR)))
    p.set(wc, SIGHTS_FORCED_VAR, True)
    yield _until(lambda: p.get(wc, SEAT_VAR) > 0.9999)
    p.check(f"{label}: the sights key still brings the camera onto the gun "
            f"(SightAiming, {SEATED_VAR}, {SEAT_VAR} 1)",
            p.get(wc, "SightAiming") and p.get(wc, SEATED_VAR),
            f"{SEAT_VAR} {p.get(wc, SEAT_VAR):.4f}")
    p.set(wc, SIGHTS_FORCED_VAR, False)


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _run(p):
    yield lambda: p.pawn() is not None
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    yield _until(lambda: p.get(wc, "Held") is not None)
    bag = [i.get_class().get_name() for i in p.get(wc, "Inventory")]
    wanted = [c for c, _l in ITEMS + GUNS]
    p.check("the knife, the axe, the matches, the shotgun and the pistol are issued",
            set(wanted) <= set(bag), str(bag))
    for cls, label in ITEMS:
        if cls in bag:
            yield from _item(p, wc, bag, cls, label)
    for cls, label in GUNS:
        if cls in bag:
            yield from _gun(p, wc, bag, cls, label)
