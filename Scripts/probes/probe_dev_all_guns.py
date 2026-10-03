"""dev-all-guns: the M panel's cheat hands over every gun, once each.

The request is raised by writing the HUD's DevAllGunsRequested rather than
taking the cheat's row in the open panel (a probe has no keyboard or mouse);
the row raising it is the verifier's to check. From the issued shotgun and pistol,
with the issued knife taken away first, one request must add the SMG, rifle,
sniper and knife, carried and not switched to; a second must add nothing.

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end.
"""

import os
import shutil

import unreal

from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.slot_tuning import SLOT_COUNT
from graphics_menu.dev_consts import DEV_GUN_CLASS_PATHS, DEV_GUNS_REQUEST_VAR
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR, PROFILE_SLOT

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HUD_BP_PATH, DEV_GUNS_REQUEST_VAR), (WEAPON_COMP_BP_PATH, "Inventory")]
SETTLE = 0.3     # game seconds for the weapon component's re-equip
GUNS = [c.rsplit(".", 1)[1] for c in DEV_GUN_CLASS_PATHS]


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{PROFILE_SLOT}.sav")


def _live_hud(p):
    try:
        hud = p.hud()
    except Exception:
        return None
    return hud if hud is not None and p.get(hud, PROFILE_CHECKED_VAR) else None


def _classes(p, wc):
    return [i.get_class().get_name() for i in p.get(wc, "Inventory")]


def _request(p, hud):
    p.set(hud, DEV_GUNS_REQUEST_VAR, True)
    yield lambda: not p.get(hud, DEV_GUNS_REQUEST_VAR)
    yield SETTLE


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
    yield lambda: _live_hud(p) is not None
    hud = _live_hud(p)
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    # Lose the issued knife, so the request has to hand it back.
    items = list(p.get(wc, "Inventory"))
    knives = [i for i in items if i.get_class().get_name() == "BP_Knife_C"]
    p.set(wc, "Inventory", [i for i in items if i not in knives])
    for k in knives:
        k.destroy_actor()
    before = _classes(p, wc)
    p.check("the knife is gone before the request", "BP_Knife_C" not in before,
            str(before))
    held = p.get(wc, "Held")

    yield from _request(p, hud)
    after = _classes(p, wc)
    p.check("the request is served (the flag drops)",
            not p.get(hud, DEV_GUNS_REQUEST_VAR))
    p.check("every gun is in the inventory", all(g in after for g in GUNS),
            f"{before} -> {after}")
    p.check("...once each", all(after.count(g) == 1 for g in GUNS), str(after))
    p.check(f"...within the {SLOT_COUNT} slots", len(after) <= SLOT_COUNT,
            str(len(after)))
    items = list(p.get(wc, "Inventory"))
    p.check("the given guns are carried, not lying in the world",
            all(not p.get(i, "Dropped") for i in items),
            str([p.get(i, "Dropped") for i in items]))
    p.check("the held weapon stays held", p.get(wc, "Held") == held,
            f"{held.get_class().get_name() if held else None} -> "
            f"{p.get(wc, 'Held').get_class().get_name() if p.get(wc, 'Held') else None}")

    yield from _request(p, hud)
    again = _classes(p, wc)
    p.check("asking twice adds nothing", again == after, f"{after} -> {again}")
