"""A fresh player starts in the pants: worn, not carried
(combat/weapon_component/starter_worn.py).

    python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_starter_pants.py

  at the start    Worn[pants] is a BP_Pants, hidden and not Dropped, and the
                  only thing worn; the bag is the issued loadout with no
                  garment in it; the jeans are drawn on Legs, and Torso and
                  Feet are bare
  taken off       through AskTakeOff, the I panel's ask: the same actor is in
                  the bag, the slot is empty and Legs is bare, so it is a
                  worn garment like any other

STARTER_WORN keeps the class for this launch: every other probe's player
starts bare (probes/starter_bare.py).
"""

SYSTEMS = ('clothing',)
STARTER_WORN = True

import unreal

from clothing.starter import starter_garment
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.record_vars import TakeOffForced, TakeOffForcedTo
from combat.wear_tuning import NOT_CLOTHING, WORN_VAR
from combat.weapon_component import vars as WV
from combat.weapon_component.inventory import STARTER_CLASS_VARS
from probes.dressed import drawn, part
from probes.probe_clothing_draw import dress

WRITABLE = [(WEAPON_COMP_BP_PATH, v) for v in (TakeOffForced, TakeOffForcedTo)]
OTHERS = ("Jacket", "Boots")


def _worn(p, wc):
    return [w if w and unreal.SystemLibrary.is_valid(w) else None for w in p.get(wc, WORN_VAR)]


def probe(p):
    spec = starter_garment()
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    yield lambda: len(p.get(wc, WV.Inventory)) >= len(STARTER_CLASS_VARS)
    yield 0.3
    worn, slot = _worn(p, wc), spec.slot_index
    mine = worn[slot] if slot < len(worn) else None
    p.check(f"a fresh player wears the {spec.slot}: Worn[{slot}] is a {spec.asset}, "
            "and nothing else is worn",
            mine is not None and mine.get_class().get_path_name() == spec.class_path
            and sum(1 for w in worn if w) == 1,
            str([w.get_class().get_name() if w else None for w in worn]))
    if mine is None:
        return
    p.check("...hidden and not Dropped, as a wear leaves a garment",
            mine.get_editor_property("hidden") and not mine.get_editor_property("Dropped"))
    bag = list(p.get(wc, WV.Inventory))
    p.check(f"...and not carried: the bag is the {len(STARTER_CLASS_VARS)} issued items, "
            "no garment among them",
            len(bag) == len(STARTER_CLASS_VARS) and mine not in bag
            and all(b.get_editor_property("ClothingSlot") == NOT_CLOTHING for b in bag),
            str([b.get_class().get_name() for b in bag]))
    p.check("...drawn on the body: the jeans on Legs, shown, Torso and Feet bare",
            drawn(part(player, spec.display), spec.display)
            and not any(drawn(part(player, d), d) for d in OTHERS), str(dress(player)))

    p.ask_take_off(wc, slot)
    yield lambda: mine in p.get(wc, WV.Inventory)
    yield 0.1
    p.check("taken off as any worn garment is: the same actor in the bag, the slot "
            "empty, Legs bare and hidden",
            mine in p.get(wc, WV.Inventory) and not any(_worn(p, wc))
            and not drawn(part(player, spec.display), spec.display), str(dress(player)))
