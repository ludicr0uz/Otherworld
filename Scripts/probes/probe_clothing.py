"""Clothing in a game: the test garments, picking one up, wearing it, taking
it off through the I panel, and a swap.

    python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_clothing.py

1. The 200 m map has one of each garment lying about 3 m in front of the
   player, Dropped, out of reach of the spawn.
2. The hat, the jacket and the shirt are laid one at a time 150 cm in front
   and picked up (InteractForced): each goes into the bag, not onto the
   player.
3. The hat in hand, the fire key (FireForced) wears it: out of the bag, into
   Worn[hat], hidden, out of the hand.
4. The I panel takes it off: the HUD's WearOpen / WearSel /
   WearTakeOffRequested, written as I and Enter would raise them. It comes
   back into the bag and the slot empties; while the panel is open the walk
   is held.
5. A swap: a garment already in the shirt's slot (the jacket, written there:
   there is only one of each) goes back into the bag when the shirt is worn.
6. The panel drawn (DrawHUD by hand): each slot reads what is worn there.

No key can be injected into a headless game, so every press is a variable
(CLAUDE.md, "Headless runs and probes"). Any profile on disk is set aside
first, so the game starts on the issued loadout, and put back at the end.
"""

SYSTEMS = ('clothing',)

import math
import os
import shutil

import unreal

from combat.paths import ITEM_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.tuning import INTERACT_RADIUS
from combat.wear_tuning import (
    NOT_CLOTHING, TAKE_OFF_TO_VAR, TAKE_OFF_VAR, WEAR_REQUEST_VAR, WEAR_SLOTS, WORN_VAR,
)
from combat.weapon_component.interact import INTERACT_FORCED_VAR
from combat.weapon_component.tick import FIRE_FORCED_VAR
from clothing.placement import AHEAD_CM
from clothing.specs import GARMENTS
from graphics_menu.inv_consts import BAG_PANEL
from graphics_menu.profile_consts import PROFILE_SLOT
from graphics_menu.umg_consts import SLOT_AMMO, SLOT_GHOST, SLOT_ICON
from graphics_menu.wear_consts import (
    WEAR_OPEN_VAR, WEAR_PANEL, WEAR_SEL_VAR, WEAR_SLOTS_BOX, WEAR_TAKE_VAR,
)
from probes.probe_clothing_drag import drag_checks
from combat.weapon_component import vars as WV

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = ([(WEAPON_COMP_BP_PATH, v) for v in
             (WV.EquippedIndex, WV.NeedsRefresh, INTERACT_FORCED_VAR, FIRE_FORCED_VAR,
              WORN_VAR, TAKE_OFF_VAR, TAKE_OFF_TO_VAR, WEAR_REQUEST_VAR)]
            + [(HUD_BP_PATH, v) for v in (WEAR_OPEN_VAR, WEAR_SEL_VAR, WEAR_TAKE_VAR)])

RING_CM = 150.0
DOWN_CM = 60.0
LOOK_DOWN_DEG = -35.0
SETTLE = 0.2


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


def _slot(name):
    return WEAR_SLOTS.index(next(g.slot for g in GARMENTS if g.display == name))


def _worn(p, wc):
    return list(p.get(wc, WORN_VAR))


def _worn_at(p, wc, slot):
    worn = _worn(p, wc)
    return worn[slot] if slot < len(worn) else None


def _bag(p, wc):
    return list(p.get(wc, "Inventory"))


def _pick_up(p, player, wc, item, yaw):
    """Lay ``item`` 150 cm ahead and press E. The take of a level actor destroys
    it and puts a fresh one of its class in the bag (task A2, pickup.py):
    returns that one, or None if nothing of its kind arrived."""
    a = math.radians(yaw)
    here = player.get_actor_location()
    before = list(_bag(p, wc))
    item.set_actor_location(
        here + unreal.Vector(RING_CM * math.cos(a), RING_CM * math.sin(a), -DOWN_CM),
        False, True)
    yield SETTLE
    p.set(wc, INTERACT_FORCED_VAR, True)
    yield lambda: not p.get(wc, INTERACT_FORCED_VAR)
    yield 0.05
    fresh = [b for b in _bag(p, wc) if b not in before and b.get_class() == item.get_class()]
    return fresh[0] if fresh and not unreal.SystemLibrary.is_valid(item) else None


def _hold(p, wc, item):
    p.set(wc, "EquippedIndex", _bag(p, wc).index(item))
    p.set(wc, "NeedsRefresh", True)
    yield lambda: p.get(wc, "Held") == item
    yield 0.05


def _fire(p, wc, item):
    """One press on ``item`` in hand. FireForced is a held key that counts as a
    press on every frame it is up, so it comes down on the first frame the
    item has left the bag: held longer, it wears what slides into the hand."""
    p.set(wc, FIRE_FORCED_VAR, True)
    yield lambda: item not in _bag(p, wc)
    p.set(wc, FIRE_FORCED_VAR, False)
    yield 0.1


def _check_row(p, player, mine):
    p.check("the level has one of each of the eight garments",
            sorted(mine) == sorted(g.display for g in GARMENTS), str(sorted(mine)))
    here = player.get_actor_location()
    yaw = math.radians(p.controller().get_control_rotation().yaw)
    ahead = [((a.get_actor_location() - here).x * math.cos(yaw)
              + (a.get_actor_location() - here).y * math.sin(yaw)) for a in mine.values()]
    p.check(f"...lying about {AHEAD_CM / 100:.0f} m in front of the player as the game starts",
            all(abs(d - AHEAD_CM) < 60.0 for d in ahead), str([round(d) for d in ahead]))
    p.check("...on the ground to be picked up (Dropped), out of the spawn's reach",
            all(a.get_editor_property("Dropped") for a in mine.values())
            and all((a.get_actor_location() - here).length() > INTERACT_RADIUS
                    for a in mine.values()))


def _run(p):
    yield lambda: p.pawn() is not None
    yield 0.5
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    hud = p.hud()
    yield lambda: p.get(wc, "Held") is not None
    every = unreal.GameplayStatics.get_all_actors_of_class(
        p.world(), p.load_class(ITEM_CLASS_PATH))
    mine = {a.get_editor_property("DisplayName"): a for a in every
            if a.get_editor_property("ClothingSlot") != NOT_CLOTHING}
    _check_row(p, player, mine)
    if not all(k in mine for k in ("Hat", "Jacket", "Shirt")):
        return
    here = player.get_actor_location()
    for a in every:   # forage lying at the spawn: out of the way
        if a not in mine.values() and a.get_editor_property("Dropped") \
                and (a.get_actor_location() - here).length() < INTERACT_RADIUS * 2:
            a.set_actor_location(here + unreal.Vector(0.0, 0.0, 5000.0), False, True)

    yaw = p.controller().get_control_rotation().yaw
    p.controller().set_control_rotation(
        unreal.Rotator(roll=0.0, pitch=LOOK_DOWN_DEG, yaw=yaw))
    yield SETTLE
    hat, jacket, shirt = mine["Hat"], mine["Jacket"], mine["Shirt"]
    took = []
    for item in (hat, jacket, shirt):
        took.append((yield from _pick_up(p, player, wc, item, yaw)))
    p.check("E picks a garment up into the bag, as any item (the level's actor gone, a "
            "fresh one of its kind carried)", all(took), str(took))
    p.check("...and wears nothing yet", not any(_worn(p, wc)), str(_worn(p, wc)))
    if not all(took):
        return
    hat, jacket, shirt = took

    # Wear the hat.
    yield from _hold(p, wc, hat)
    yield from _fire(p, wc, hat)
    p.check("the fire key on the hat in hand wears it, and only it: Worn[hat] is that hat",
            _worn_at(p, wc, _slot("Hat")) == hat and sum(1 for w in _worn(p, wc) if w) == 1,
            str([w.get_name() if w else None for w in _worn(p, wc)]))
    p.check("...out of the bag and out of the hand",
            hat not in _bag(p, wc) and p.get(wc, "Held") != hat)
    p.check("...and hidden (nothing is drawn worn yet)", hat.get_editor_property("hidden"))

    # Take it off through the I panel.
    p.set(hud, WEAR_OPEN_VAR, True)
    yield 0.1
    p.check("the open I panel holds the walk", p.controller().is_move_input_ignored())
    p.set(hud, WEAR_SEL_VAR, _slot("Hat"))
    p.set(hud, WEAR_TAKE_VAR, True)
    yield lambda: hat in _bag(p, wc)
    yield 0.05
    p.check("the I panel's take-off puts the hat back in the bag and empties its slot",
            hat in _bag(p, wc) and _worn_at(p, wc, _slot("Hat")) is None,
            str([w.get_name() if w else None for w in _worn(p, wc)]))
    p.check("...and both requests are lowered",
            p.get(hud, WEAR_TAKE_VAR) is False and p.get(wc, TAKE_OFF_VAR) == NOT_CLOTHING)
    p.check("...in the bag, not on the ground", hat.get_editor_property("Dropped") is False)
    p.set(hud, WEAR_OPEN_VAR, False)
    yield 0.1
    p.check("shut, the panel gives the walk back", not p.controller().is_move_input_ignored())

    # A swap: the shirt's slot already holds a garment.
    yield from _hold(p, wc, jacket)
    yield from _fire(p, wc, jacket)
    p.check("the jacket is worn in its own slot",
            _worn_at(p, wc, _slot("Jacket")) == jacket, str(_worn(p, wc)))
    worn = _worn(p, wc)
    worn[_slot("Shirt")], worn[_slot("Jacket")] = jacket, None
    p.set(wc, WORN_VAR, worn)
    yield from _hold(p, wc, shirt)
    yield from _fire(p, wc, shirt)
    p.check("wearing the shirt over a garment in its slot swaps them: the shirt is "
            "worn, the other is back in the bag",
            _worn_at(p, wc, _slot("Shirt")) == shirt and jacket in _bag(p, wc)
            and shirt not in _bag(p, wc), f"{_worn(p, wc)}, bag {len(_bag(p, wc))}")

    # What the panel shows: DrawHUD by hand (a -nullrhi run never draws).
    ui = p.get(hud, "UiHud")
    panel, grid = ui.get_editor_property(WEAR_PANEL), ui.get_editor_property(WEAR_SLOTS_BOX)
    shown = unreal.SlateVisibility.HIT_TEST_INVISIBLE
    p.set(hud, WEAR_OPEN_VAR, True)
    hud.call_method("ReceiveDrawHUD", (1920, 1080))
    cells = [grid.get_child_at(i) for i in range(len(WEAR_SLOTS))]

    def up(name):
        return [c.get_editor_property(name).get_visibility() == shown for c in cells]

    want = [i == _slot("Shirt") for i in range(len(WEAR_SLOTS))]
    drawn = cells[_slot("Shirt")].get_editor_property(SLOT_ICON).get_editor_property(
        "brush").get_editor_property("resource_object")
    p.check("the open I panel shows, each worn slot the icon of what is worn there, or "
            "the garment's silhouette, and no count",
            panel.get_visibility() != unreal.SlateVisibility.COLLAPSED
            and up(SLOT_ICON) == want and up(SLOT_GHOST) == [not w for w in want]
            and not any(up(SLOT_AMMO)) and drawn == p.get(shirt, "Icon"),
            f"icons {up(SLOT_ICON)}, ghosts {up(SLOT_GHOST)}, "
            f"{drawn.get_name() if drawn else None}")
    p.set(hud, WEAR_OPEN_VAR, False)
    hud.call_method("ReceiveDrawHUD", (1920, 1080))
    bag = ui.get_editor_property(BAG_PANEL)
    p.check("...and shut, the worn slots still show (bottom right) and so does the "
            "backpack under them",
            panel.get_visibility() != unreal.SlateVisibility.COLLAPSED
            and bag.get_visibility() != unreal.SlateVisibility.COLLAPSED)

    yield from drag_checks(p, wc, hat, jacket, shirt, _slot, _worn_at, _bag, _hold)
