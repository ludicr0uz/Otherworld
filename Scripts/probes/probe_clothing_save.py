"""The profile saves what is worn: the jacket and the hat on, save and exit,
continue, and both are worn again, the jacket drawn, the bag as it was.

    python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_clothing_save.py

1. The jacket and the hat are picked up and worn (probes/dressed.py).
2. The countdown runs out (the weapon component's variables, written: a
   probe has no keyboard, probe_save_exit.py): the profile on disk holds the
   two classes at their slots of WornClasses and none elsewhere.
3. The reopened level loads it: Worn has a jacket and a hat at their slots,
   hidden, not Dropped and out of the bag, as a wear leaves them; Torso draws
   the jacket's mesh; the bag is what it was, class, rounds and slot.
4. Dying deletes the profile, the garments with the bag: the level opened
   again starts a game that wears nothing (and leaves a live player for the
   next probe of the launch).

Any profile already on disk is set aside first and put back at the end.
"""

SYSTEMS = ('clothing', 'menu')

import os
import shutil

import unreal

from clothing.specs import GARMENTS
from combat import health_vars as HV
from combat.ask_consts import EXIT_AT_VAR, EXIT_PENDING_VAR, EXIT_STARTED_VAR
from combat.paths import (
    HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH,
)
from combat.wear_tuning import WORN_VAR
from graphics_menu.profile_consts import (
    PROFILE_CHECKED_VAR, PROFILE_SLOT, PROFILE_USER_INDEX, WORN_CLASSES_FIELD,
)
from probes.dressed import WRITABLE as DRESSED, drawn, part, put_on, still

WRITABLE = DRESSED + [(WEAPON_COMP_BP_PATH, v) for v in
                      (EXIT_PENDING_VAR, EXIT_AT_VAR, EXIT_STARTED_VAR)] \
    + [(HEALTH_BP_PATH, HV.Health)]

WORN = ("Jacket", "Hat")
GS = unreal.GameplayStatics


def _spec(display):
    return next(g for g in GARMENTS if g.display == display)


def _saved():
    return GS.does_save_game_exist(PROFILE_SLOT, PROFILE_USER_INDEX)


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{PROFILE_SLOT}.sav")


def _live_hud(p, not_this=None):
    try:
        hud = p.hud()
    except Exception:
        return None
    if hud is None or (not_this is not None and hud == not_this):
        return None
    return hud if p.get(hud, PROFILE_CHECKED_VAR) else None


def _bag(p, wc):
    return [(i.get_class().get_name(), int(p.get(i, "Loaded")), int(p.get(i, "Reserve")),
             int(p.get(i, "Slot"))) for i in p.get(wc, "Inventory")]


def _names(classes):
    return [c.get_name() if c else None for c in classes]


def _want():
    """WornClasses as it should be saved: a class name at the two slots."""
    last = max(_spec(d).slot_index for d in WORN)
    want = [None] * (last + 1)
    for d in WORN:
        want[_spec(d).slot_index] = _spec(d).class_path.split(".")[-1]
    return want


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    held = []
    try:
        yield from _run(p, held)
    finally:
        still(p, held, False)
        if os.path.exists(_file()):
            os.remove(_file())
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _run(p, held):
    yield lambda: _live_hud(p) is not None
    hud = _live_hud(p)
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    still(p, held, True)

    # --- 1. dressed -----------------------------------------------------------
    on = []
    for display in WORN:
        item = yield from put_on(p, player, wc, display)
        on.append(item is not None)
    p.check("the jacket and the hat are picked up and worn", all(on), str(on))
    p.check("...the jacket drawn on the body", drawn(part(player, "Jacket"), "Jacket"))
    yield 0.2
    carried = _bag(p, wc)

    # --- 2. save and exit -------------------------------------------------------
    now = p.time()
    p.set(wc, EXIT_STARTED_VAR, now)
    p.set(wc, EXIT_AT_VAR, now + 0.3)
    p.set(wc, EXIT_PENDING_VAR, True)
    yield _saved
    save = GS.load_game_from_slot(PROFILE_SLOT, PROFILE_USER_INDEX)
    got = _names(p.get(save, WORN_CLASSES_FIELD)) if save else None
    # Worn is as long as the highest slot ever worn in; the save is as long.
    p.check("the saved profile holds what is worn, by slot, and none elsewhere",
            got is not None and got[:len(_want())] == _want()
            and not any(got[len(_want()):]), f"{got} vs {_want()}")
    p.check("...beside the bag, which holds neither garment",
            _names(p.get(save, "ItemClasses")) == [c for c, _l, _r, _s in carried]
            and not set(_want()) & set(_names(p.get(save, "ItemClasses"))),
            str(_names(p.get(save, "ItemClasses"))))

    # --- 3. continue ------------------------------------------------------------
    yield lambda: _live_hud(p, not_this=hud) is not None
    held.clear()
    still(p, held, True)
    yield 0.5
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    worn = list(p.get(wc, WORN_VAR))
    there = {d: worn[_spec(d).slot_index] if _spec(d).slot_index < len(worn) else None
             for d in WORN}
    p.check("the reopened game wears the jacket and the hat again, each in its slot",
            all(there[d] is not None
                and there[d].get_class().get_name() == _spec(d).class_path.split(".")[-1]
                for d in WORN)
            and sum(1 for w in worn if w is not None) == len(WORN),
            str([w.get_class().get_name() if w else None for w in worn]))
    items = [i for i in there.values() if i is not None]
    inventory = list(p.get(wc, "Inventory"))
    p.check("...hidden, not Dropped and out of the bag, as a wear leaves them",
            len(items) == len(WORN)
            and all(i.get_editor_property("hidden") for i in items)
            and all(not p.get(i, "Dropped") for i in items)
            and not any(i in inventory for i in items),
            str([(i.get_editor_property("hidden"), p.get(i, "Dropped")) for i in items]))
    p.check("...the jacket drawn on the body", drawn(part(player, "Jacket"), "Jacket"))
    p.check("...and the bag is as it was: class, rounds and slot",
            _bag(p, wc) == carried, f"{_bag(p, wc)} vs {carried}")

    # --- 4. the death wipe --------------------------------------------------------
    p.set(p.component(player, HEALTH_CLASS_PATH), HV.Health, 0.0)
    yield lambda: not _saved()
    p.check("dying deletes the profile, what was worn with the bag", not _saved())

    # A fresh game for whichever probe shares this launch next: this one's
    # player is dead.
    hud = p.hud()
    held.clear()        # the level's wanderers go with it
    GS.open_level(p.world(), p.map_path, True, "")
    yield lambda: _live_hud(p, not_this=hud) is not None
    worn = list(p.get(p.component(p.pawn(), WEAPON_COMP_CLASS_PATH), WORN_VAR))
    p.check("...and the next game wears nothing", not any(w is not None for w in worn),
            str(len(worn)))
