"""The inventory's slots in a game: the issued items in their slots, a slot
key putting the gun away and bringing it back, a quick slot sending the gun
home, and the HUD's drags (refused into a slot the item does not fit,
swapped where both fit).

No key can be injected into a headless game, so the probe writes what the
keys and the HUD write: SlotRequest (a number key, or a bag slot picked in
the I panel), NextRequest (Q: the bag's next item) and MoveFrom/MoveTo (a
drag). Any profile on disk is set aside
first, so the game starts on the issued loadout, and put back at the end.
"""

SYSTEMS = ('inventory',)

import os
import shutil

import unreal

from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.slot_tuning import (
    BAG_FIRST, HAND, HAND_FROM_VAR, MELEE_SLOT, MOVE_FROM_VAR, MOVE_TO_VAR, NEXT_REQUEST_VAR,
    NO_REQUEST,
    PISTOL_SLOT, PRIMARY, SLOT_REQUEST_VAR, SLOT_VAR, STARTER_SLOTS,
)
from combat.weapon_component.inventory import STARTER_CLASS_VARS
from graphics_menu.profile_consts import PROFILE_SLOT

WRITABLE = [(WEAPON_COMP_BP_PATH, v) for v in (SLOT_REQUEST_VAR, MOVE_FROM_VAR, MOVE_TO_VAR,
                                                  NEXT_REQUEST_VAR)]
SETTLE = 0.1


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{PROFILE_SLOT}.sav")


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
    names = [_name(i) for i in inv]
    start = {n: s for n, s in _slots(wc).items()}
    p.check("the issued items start in their slots (the shotgun in hand, pistol, knife, "
            "the rest in the bag)",
            len(inv) == len(STARTER_CLASS_VARS)
            and [start[n] for n in names] == list(STARTER_SLOTS)
            and _name(p.get(wc, "Held")) == names[0], str(start))
    shotgun, pistol, knife, axe, matches, stick = inv[:6]

    yield from _ask(p, wc, SLOT_REQUEST_VAR, PRIMARY)
    p.check("1 with the primary's gun in hand puts it away: empty hands",
            p.get(wc, "Held") is None and shotgun.get_editor_property(SLOT_VAR) == PRIMARY
            and p.get(wc, "EquippedIndex") == -1, str(_slots(wc)))
    yield from _ask(p, wc, SLOT_REQUEST_VAR, PRIMARY)
    p.check("1 again takes it back out", p.get(wc, "Held") == shotgun
            and p.get(wc, HAND_FROM_VAR) == PRIMARY, str(_slots(wc)))

    yield from _ask(p, wc, SLOT_REQUEST_VAR, BAG_FIRST + 1)
    p.check("6 (the bag's second slot: the matches) sends the gun home to the primary "
            "and brings the matches to hand",
            p.get(wc, "Held") == matches and shotgun.get_editor_property(SLOT_VAR) == PRIMARY
            and p.get(wc, HAND_FROM_VAR) == BAG_FIRST + 1, str(_slots(wc)))
    yield from _ask(p, wc, SLOT_REQUEST_VAR, PISTOL_SLOT)
    p.check("3 brings the pistol up and the matches go back into the bag",
            p.get(wc, "Held") == pistol
            and matches.get_editor_property(SLOT_VAR) == BAG_FIRST + 1, str(_slots(wc)))

    yield from _move(p, wc, BAG_FIRST, PRIMARY)
    p.check("the axe dragged onto the primary slot is refused (only a long gun fits)",
            axe.get_editor_property(SLOT_VAR) == BAG_FIRST
            and shotgun.get_editor_property(SLOT_VAR) == PRIMARY, str(_slots(wc)))
    yield from _move(p, wc, BAG_FIRST, MELEE_SLOT)
    p.check("the axe dragged onto the melee slot swaps with the knife",
            axe.get_editor_property(SLOT_VAR) == MELEE_SLOT
            and knife.get_editor_property(SLOT_VAR) == BAG_FIRST, str(_slots(wc)))
    yield from _move(p, wc, BAG_FIRST + 1, HAND)
    p.check("the matches dragged onto the hand swap with the pistol, which goes to the bag",
            p.get(wc, "Held") == matches
            and pistol.get_editor_property(SLOT_VAR) == BAG_FIRST + 1, str(_slots(wc)))
    yield from _move(p, wc, BAG_FIRST + 1, MELEE_SLOT)
    p.check("the pistol dragged onto the melee slot is refused",
            pistol.get_editor_property(SLOT_VAR) == BAG_FIRST + 1, str(_slots(wc)))
    p.check("the bag has room for a pick-up", p.get(wc, "HasRoom") is True)

    # Q: the matches are in hand out of the bag's second slot, the knife in
    # its first, the pistol in its second, the stick in its third.
    yield from _ask(p, wc, NEXT_REQUEST_VAR, 1)
    p.check("Q brings the bag's next item to hand (the stick), the matches going back "
            "into the bag",
            p.get(wc, "Held") == stick and p.get(wc, HAND_FROM_VAR) == BAG_FIRST + 2
            and matches.get_editor_property(SLOT_VAR) >= BAG_FIRST, str(_slots(wc)))
    yield from _ask(p, wc, NEXT_REQUEST_VAR, 1)
    p.check("Q past the bag's last item goes round to its first (the knife), not to a "
            "weapon slot",
            p.get(wc, "Held") == knife and p.get(wc, HAND_FROM_VAR) == BAG_FIRST
            and shotgun.get_editor_property(SLOT_VAR) == PRIMARY
            and axe.get_editor_property(SLOT_VAR) == MELEE_SLOT, str(_slots(wc)))
    yield from _ask(p, wc, NEXT_REQUEST_VAR, 1)
    p.check("Q again: the next one (the pistol, lying in the bag)",
            p.get(wc, "Held") == pistol and p.get(wc, HAND_FROM_VAR) == BAG_FIRST + 1,
            str(_slots(wc)))
    yield from _ask(p, wc, SLOT_REQUEST_VAR, PRIMARY)
    yield from _ask(p, wc, NEXT_REQUEST_VAR, 1)
    p.check("Q with a weapon slot's gun in hand sends it home and brings the bag's first "
            "item up",
            p.get(wc, "Held") is not None and p.get(wc, HAND_FROM_VAR) == BAG_FIRST
            and shotgun.get_editor_property(SLOT_VAR) == PRIMARY
            and p.get(wc, "Held") not in (shotgun, axe), str(_slots(wc)))
