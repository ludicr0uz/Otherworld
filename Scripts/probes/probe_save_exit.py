"""Save and exit: the character stands still while it counts down, a hit
calls it off and frees it, running out saves the profile and
reopens the level, the reopened game loads it, a saved inventory unlike the
issued one replaces it, and dying deletes it.

The countdown is started by writing the HUD's variables rather than pressing
X (a probe has no keyboard), with ExitAt a fraction of a second away rather
than 15 s -- -nullrhi game time crawls. The key and the 15 s are the
verifier's to check. A hit is a write of LastDamageTime, which is what a
wanderer's swing stamps (npc/melee.py).

Any profile already on disk is set aside first and put back at the end.
"""

import os
import shutil

import unreal

from combat.game_state import KILL_COUNT_VAR
from combat.paths import (
    GAME_MODE_BP_PATH, HEALTH_BP_PATH, HEALTH_CLASS_PATH, PISTOL_BP_PATH,
    SHOTGUN_BP_PATH, SMG_BP_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH,
)
from graphics_menu.profile_consts import (
    EXIT_AT_VAR, EXIT_CALLED_OFF_VAR, EXIT_PENDING_VAR, EXIT_STARTED_VAR,
    PROFILE_BP_PATH, PROFILE_CHECKED_VAR, PROFILE_CLASS_PATH, PROFILE_SLOT, PROFILE_USER_INDEX,
)
from survival.paths import MUSHROOM_CLASS_PATH, SURVIVAL_BP_PATH, SURVIVAL_CLASS_PATH

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HUD_BP_PATH, EXIT_PENDING_VAR), (HUD_BP_PATH, EXIT_AT_VAR),
            (HUD_BP_PATH, EXIT_STARTED_VAR),
            (HEALTH_BP_PATH, "Health"), (HEALTH_BP_PATH, "LastDamageTime"),
            (SURVIVAL_BP_PATH, "Hunger"), (GAME_MODE_BP_PATH, KILL_COUNT_VAR),
            (WEAPON_COMP_BP_PATH, "EquippedIndex")]
# ...and every field of the crafted profile the load is tested with.
PROFILE_FIELDS = ("Health", "Stamina", "Hunger", "Thirst", "Temperature", "Kills",
                  "EquippedIndex", "ItemClasses", "ItemLoaded", "ItemReserve")
WRITABLE += [(PROFILE_BP_PATH, f) for f in PROFILE_FIELDS]

HEALTH, HUNGER, KILLS, EQUIPPED = 55.0, 40.0, 7, 1
# A profile nothing issues, for the load: a mushroom and a part-loaded SMG.
CRAFTED = ((MUSHROOM_CLASS_PATH, 0, 0), (f"{SMG_BP_PATH}.BP_SMG_C", 3, 11))
GS = unreal.GameplayStatics


def _saved():
    return GS.does_save_game_exist(PROFILE_SLOT, PROFILE_USER_INDEX)


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{PROFILE_SLOT}.sav")


def _inventory(p, wc):
    return [(i.get_class().get_name(), int(p.get(i, "Loaded")))
            for i in p.get(wc, "Inventory")]


def _live_hud(p, not_this=None):
    try:
        hud = p.hud()
    except Exception:
        return None
    if hud is None or (not_this is not None and hud == not_this):
        return None
    return hud if p.get(hud, PROFILE_CHECKED_VAR) else None


def _start_exit(p, hud, seconds):
    now = p.time()
    p.set(hud, EXIT_STARTED_VAR, now)
    p.set(hud, EXIT_AT_VAR, now + seconds)
    p.set(hud, EXIT_PENDING_VAR, True)


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(_file()):
            os.remove(_file())
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _run(p):
    yield lambda: _live_hud(p) is not None
    hud = _live_hud(p)
    pawn = p.pawn()
    health = p.component(pawn, HEALTH_CLASS_PATH)
    wc = p.component(pawn, WEAPON_COMP_CLASS_PATH)
    survival = p.component(pawn, SURVIVAL_CLASS_PATH)

    # --- the character stands still, and a hit calls the exit off -----------
    moves = pawn.get_editor_property("character_movement")
    _start_exit(p, hud, 100.0)
    yield 0.1
    p.check("the character can't move while the exit counts down",
            moves.movement_mode == unreal.MovementMode.MOVE_NONE,
            str(moves.movement_mode))
    p.set(health, "LastDamageTime", p.time())
    yield 0.2
    p.check("...and walks again once a hit calls it off",
            moves.movement_mode == unreal.MovementMode.MOVE_WALKING,
            str(moves.movement_mode))
    p.check("a hit during the countdown calls the exit off",
            not p.get(hud, EXIT_PENDING_VAR) and p.get(hud, EXIT_CALLED_OFF_VAR) > 0.0,
            f"pending {p.get(hud, EXIT_PENDING_VAR)}, "
            f"called off at {p.get(hud, EXIT_CALLED_OFF_VAR):.2f}")
    p.check("...and nothing is saved", not _saved())

    # --- running out saves and leaves ---------------------------------------
    p.set(health, "Health", HEALTH)
    p.set(survival, "Hunger", HUNGER)
    p.set(p.game_mode(), KILL_COUNT_VAR, KILLS)
    p.set(wc, "EquippedIndex", EQUIPPED)
    carried = _inventory(p, wc)
    _start_exit(p, hud, 0.3)
    yield _saved
    save = GS.load_game_from_slot(PROFILE_SLOT, PROFILE_USER_INDEX)
    p.check("the countdown running out saves the profile", save is not None)
    p.check("...with the stats",
            abs(p.get(save, "Health") - HEALTH) < 1e-3
            and abs(p.get(save, "Hunger") - HUNGER) < 1.0
            and p.get(save, "Kills") == KILLS,
            f"health {p.get(save, 'Health')}, hunger {p.get(save, 'Hunger'):.2f}, "
            f"kills {p.get(save, 'Kills')}")
    classes = [c.get_name() for c in p.get(save, "ItemClasses")]
    p.check("...and the inventory, slot by slot",
            classes == [c for c, _l in carried]
            and list(p.get(save, "ItemLoaded")) == [n for _c, n in carried]
            and p.get(save, "EquippedIndex") == EQUIPPED,
            f"{classes} {list(p.get(save, 'ItemLoaded'))} vs {carried}")

    # --- the reopened level loads it ------------------------------------------
    yield lambda: _live_hud(p, not_this=hud) is not None
    yield 0.3
    pawn = p.pawn()
    health = p.component(pawn, HEALTH_CLASS_PATH)
    wc = p.component(pawn, WEAPON_COMP_CLASS_PATH)
    p.check("the level reopened and the new game loaded the profile's stats",
            abs(p.get(health, "Health") - HEALTH) < 1e-3
            and p.get(p.game_mode(), KILL_COUNT_VAR) == KILLS,
            f"health {p.get(health, 'Health')}, "
            f"kills {p.get(p.game_mode(), KILL_COUNT_VAR)}")
    p.check("...its inventory, in place of the issued loadout",
            _inventory(p, wc) == carried and p.get(wc, "EquippedIndex") == EQUIPPED,
            f"{_inventory(p, wc)} vs {carried}, equipped {p.get(wc, 'EquippedIndex')}")
    held = p.get(wc, "Held")
    p.check("...and equips the saved slot",
            held is not None and held.get_class().get_name() == carried[EQUIPPED][0],
            held.get_class().get_name() if held else "nothing held")

    # --- a profile unlike the issued loadout replaces it ------------------------
    hud = _live_hud(p)
    crafted = GS.create_save_game_object(p.load_class(PROFILE_CLASS_PATH))
    for name, value in (("Health", 42.0), ("Stamina", 100.0), ("Hunger", 80.0),
                        ("Thirst", 70.0), ("Temperature", 50.0), ("Kills", 3),
                        ("EquippedIndex", 1)):
        p.set(crafted, name, value)
    p.set(crafted, "ItemClasses", [p.load_class(c) for c, _l, _r in CRAFTED])
    p.set(crafted, "ItemLoaded", [l for _c, l, _r in CRAFTED])
    p.set(crafted, "ItemReserve", [r for _c, _l, r in CRAFTED])
    GS.save_game_to_slot(crafted, PROFILE_SLOT, PROFILE_USER_INDEX)
    GS.open_level(p.world(), p.map_path, True, "")
    yield lambda: _live_hud(p, not_this=hud) is not None
    yield 0.3
    pawn = p.pawn()
    health = p.component(pawn, HEALTH_CLASS_PATH)
    wc = p.component(pawn, WEAPON_COMP_CLASS_PATH)
    items = list(p.get(wc, "Inventory"))
    got = [(i.get_class().get_path_name(), p.get(i, "Loaded"), p.get(i, "Reserve"))
           for i in items]
    p.check("a saved inventory unlike the issued one replaces it, ammo and all",
            got == list(CRAFTED), f"{got}")
    p.check("...carried, not lying about (Dropped false), and the saved slot held",
            all(not p.get(i, "Dropped") for i in items)
            and p.get(wc, "Held") is not None
            and p.get(wc, "Held").get_class().get_path_name() == CRAFTED[1][0],
            str([p.get(i, "Dropped") for i in items]))
    issued = [a for path in (f"{SHOTGUN_BP_PATH}.BP_Shotgun_C",
                             f"{PISTOL_BP_PATH}.BP_Pistol_C")
              for a in GS.get_all_actors_of_class(p.world(), p.load_class(path))]
    p.check("...and the issued shotgun and pistol are destroyed, not left behind",
            not issued, f"{len(issued)} still in the world")
    p.check("...with the saved health", abs(p.get(health, "Health") - 42.0) < 1e-3,
            str(p.get(health, "Health")))

    # --- dying deletes it ------------------------------------------------------
    p.set(health, "Health", 0.0)
    yield lambda: not _saved()
    p.check("dying deletes the saved profile", not _saved())
