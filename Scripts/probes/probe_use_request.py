"""The I panel's right click in a game (use_request.py): a weapon in the
bag goes to its free weapon slot, one whose slot is taken swaps with what is
there, a weapon in hand goes into a slot, a weapon slot's item comes to
hand, a plain item comes to hand, and a garment is worn.

No mouse reaches a headless game, so the probe writes UseRequest, the
request AskUseSlot raises, served with authority (single player). The garment is
one of the test row on Lvl_Forest_200m, picked up with E. Any
profile on disk is set aside first, so the game starts on the issued loadout.
"""

SYSTEMS = ('inventory', 'clothing')
LEVEL = "/Game/Maps/Lvl_Forest_200m"     # the test garments lie there

import os
import shutil

import unreal

from combat.paths import ITEM_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.slot_tuning import (
    BAG_FIRST, HAND, HAND_FROM_VAR, MELEE_SLOT, MOVE_FROM_VAR, MOVE_TO_VAR, NO_REQUEST,
    PISTOL_SLOT, PRIMARY, SLOT_VAR, USE_REQUEST_VAR,
)
from combat.wear_tuning import NOT_CLOTHING, WORN_VAR
from graphics_menu.profile_consts import PROFILE_SLOT
from probes.dressed import WRITABLE as DRESSED_WRITABLE, pick_up

WRITABLE = ([(WEAPON_COMP_BP_PATH, v) for v in (USE_REQUEST_VAR, MOVE_FROM_VAR, MOVE_TO_VAR)]
            + DRESSED_WRITABLE)
SETTLE = 0.15


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames", f"{PROFILE_SLOT}.sav")


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _name(item):
    return item.get_editor_property("DisplayName") if item else "None"


def _slots(wc):
    return {_name(i): i.get_editor_property(SLOT_VAR) for i in wc.get_editor_property("Inventory")}


def _slot(item):
    return item.get_editor_property(SLOT_VAR)


def _ask(p, wc, var, value):
    p.set(wc, var, value)
    yield lambda: p.get(wc, var) == NO_REQUEST
    yield SETTLE


def _move(p, wc, src, dst):
    p.set(wc, MOVE_TO_VAR, dst)
    yield from _ask(p, wc, MOVE_FROM_VAR, src)


def _run(p):
    yield lambda: p.pawn() is not None
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    yield lambda: p.get(wc, "Held") is not None
    yield 0.3
    inv = list(wc.get_editor_property("Inventory"))
    shotgun, pistol, knife, axe, matches, stick = inv[:6]

    yield from _ask(p, wc, USE_REQUEST_VAR, HAND)
    p.check("use on the gun in hand puts it into its free weapon slot (the primary): "
            "empty hands",
            p.get(wc, "Held") is None and _slot(shotgun) == PRIMARY, str(_slots(wc)))
    yield from _ask(p, wc, USE_REQUEST_VAR, PRIMARY)
    p.check("use on a weapon slot's gun brings it to hand",
            p.get(wc, "Held") == shotgun and p.get(wc, HAND_FROM_VAR) == PRIMARY,
            str(_slots(wc)))

    yield from _ask(p, wc, USE_REQUEST_VAR, BAG_FIRST)
    p.check("use on the axe in the bag, the melee slot taken by the knife, swaps them: "
            "the axe in the melee slot, the knife in the bag slot it left",
            _slot(axe) == MELEE_SLOT and _slot(knife) == BAG_FIRST, str(_slots(wc)))

    yield from _move(p, wc, PISTOL_SLOT, BAG_FIRST + 3)
    p.check("(staging) the pistol dragged into the bag", _slot(pistol) == BAG_FIRST + 3,
            str(_slots(wc)))
    yield from _ask(p, wc, USE_REQUEST_VAR, BAG_FIRST + 3)
    p.check("use on the pistol in the bag puts it into its free pistol slot",
            _slot(pistol) == PISTOL_SLOT, str(_slots(wc)))

    yield from _ask(p, wc, USE_REQUEST_VAR, BAG_FIRST + 1)
    p.check("use on the matches (no slot to equip into) brings them to hand, the gun "
            "going home",
            p.get(wc, "Held") == matches and _slot(shotgun) == PRIMARY, str(_slots(wc)))

    # A garment: one of the test row, picked up with E (probes/dressed.py).
    player = p.pawn()
    every = unreal.GameplayStatics.get_all_actors_of_class(p.world(), p.load_class(ITEM_CLASS_PATH))
    hats = [a for a in every if a.get_editor_property("DisplayName") == "Hat"
            and a.get_editor_property("ClothingSlot") != NOT_CLOTHING
            and a.get_editor_property("Dropped")]
    p.check("the level has a hat to pick up", bool(hats), str(len(hats)))
    if not hats:
        return
    yaw = p.controller().get_control_rotation().yaw
    hat = yield from pick_up(p, player, wc, hats[0], yaw)
    p.check("(staging) E picks the hat up into the bag", hat is not None and _slot(hat) >= BAG_FIRST,
            str(_slots(wc)))
    if hat is None:
        return
    bag_slot = _slot(hat)
    yield from _ask(p, wc, USE_REQUEST_VAR, bag_slot)
    yield lambda: hat not in list(wc.get_editor_property("Inventory"))
    yield SETTLE
    worn = list(p.get(wc, WORN_VAR))
    slot = hat.get_editor_property("ClothingSlot")
    p.check("use on the hat in the bag wears it: out of the bag, in Worn[hat]",
            slot < len(worn) and worn[slot] == hat
            and hat not in list(wc.get_editor_property("Inventory")),
            f"{_slots(wc)}, worn {[_name(w) for w in worn]}")
