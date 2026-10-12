"""The I panel's portrait follows what is worn, and what is in hand can be
used with the panel open, in a rendered window (DrawHUD picks the portrait,
and a -nullrhi run never draws):

    python3 Scripts/dev/uepy.py --game --windowed --probe Scripts/probes/probe_inventory_use.py

  the portrait   bare, it is T_UI_Portrait; with the jacket on, the jacket's;
                 with the boots too, the picture of both; the jacket taken
                 off in the panel, the boots' alone (item_icons/portrait.py:
                 a bit per garment drawn on the body). `shot showui` saves
                 the screen with the dressed one up
  the use        a mushroom in hand, the panel open (the cursor up, so every
                 press is spent and the fire key eats nothing): the weapon
                 component's UseHeld, what the right click on the hand's slot
                 and the use key call (graphics_menu/inv_drag.py), eats it

No probe can click a cell or press a key: that the click and the key reach
UseHeld is the verifier's (graphics_menu/wear_checks.py).
"""

SYSTEMS = ('inventory', 'clothing')

import unreal

from clothing.specs import GARMENTS
from combat.ask_consts import USE_HELD
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.weapon_component import vars as WV
from graphics_menu.wear_consts import (
    WEAR_OPEN_VAR, WEAR_PORTRAIT_IMAGE, WEAR_SEL_VAR, WEAR_TAKE_VAR,
)
from item_icons.portrait import PORTRAITS, portrait_index
from probes import dressed
from survival import component_vars as UV
from survival.paths import MUSHROOM_CLASS_PATH, SURVIVAL_BP_PATH, SURVIVAL_CLASS_PATH

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = dressed.WRITABLE + [
    (HUD_BP_PATH, WEAR_OPEN_VAR), (HUD_BP_PATH, WEAR_SEL_VAR), (HUD_BP_PATH, WEAR_TAKE_VAR),
    (SURVIVAL_BP_PATH, UV.Hunger), (WEAPON_COMP_BP_PATH, WV.TriggerSpent)]
DRAW = 0.5                # a few frames of DrawHUD
START_HUNGER = 50.0


def _slot(display):
    return next(g.slot_index for g in GARMENTS if g.display == display)


def _picture(ui):
    brush = ui.get_editor_property(WEAR_PORTRAIT_IMAGE).get_editor_property("brush")
    drawn = brush.get_editor_property("resource_object")
    return drawn.get_name() if drawn else None


def _want(*worn):
    return PORTRAITS[portrait_index({_slot(d) for d in worn})].texture


def _open(p, hud, is_open):
    p.set(hud, WEAR_OPEN_VAR, is_open)
    yield DRAW


def _portrait(p, player, wc, hud, ui):
    yield from _open(p, hud, True)
    p.check("nothing worn, the portrait is the bare one", _picture(ui) == _want(),
            f"{_picture(ui)}, wanted {_want()}")
    for worn in (("Jacket",), ("Jacket", "Boots")):
        # Dressed with the panel shut: open, the fire key's press is spent.
        yield from _open(p, hud, False)
        got = yield from dressed.put_on(p, player, wc, worn[-1])
        p.check(f"the {worn[-1].lower()} is put on", got is not None)
        yield from _open(p, hud, True)
        p.check(f"wearing {' and '.join(worn)}, the portrait is the picture of that",
                _picture(ui) == _want(*worn), f"{_picture(ui)}, wanted {_want(*worn)}")
    unreal.SystemLibrary.execute_console_command(p.world(), "shot showui")
    p.note("shot showui: the I panel open, the portrait in the jacket and the boots")
    yield DRAW
    # The jacket off, as Enter on its slot takes it off.
    p.set(hud, WEAR_SEL_VAR, _slot("Jacket"))
    p.set(hud, WEAR_TAKE_VAR, True)
    yield DRAW
    p.check("the jacket taken off in the panel, the portrait is the boots' alone",
            _picture(ui) == _want("Boots"), f"{_picture(ui)}, wanted {_want('Boots')}")


def _use(p, player, wc, hud):
    survival = p.component(player, SURVIVAL_CLASS_PATH)
    yield from _open(p, hud, False)
    here = player.get_actor_location()
    food = unreal.OtherworldLoadLibrary.spawn_actor_at(
        p.world(), p.load_class(MUSHROOM_CLASS_PATH),
        unreal.Transform(here + unreal.Vector(0.0, 0.0, 300.0),
                         unreal.Rotator(0.0, 0.0, 0.0), unreal.Vector(1.0, 1.0, 1.0)))
    yield dressed.SETTLE
    view = p.controller().get_control_rotation()
    p.controller().set_control_rotation(
        unreal.Rotator(roll=0.0, pitch=dressed.LOOK_DOWN_DEG, yaw=view.yaw))
    yield dressed.SETTLE
    got = yield from dressed.pick_up(p, player, wc, food, view.yaw)
    if got is None and unreal.SystemLibrary.is_valid(food) and food in dressed.bag(p, wc):
        got = food
    p.controller().set_control_rotation(view)
    p.check("a mushroom is picked up", got is not None)
    if got is None:
        return
    yield from dressed.hold(p, wc, got)
    yield from _open(p, hud, True)
    p.set(survival, UV.Hunger, START_HUNGER)
    yield DRAW
    p.check("with the panel open the mushroom stays in hand, and every press is "
            "spent (the cursor is up): the fire key would eat nothing",
            p.get(wc, "Held") == got and bool(p.get(wc, WV.TriggerSpent)),
            f"TriggerSpent {p.get(wc, WV.TriggerSpent)}")
    before = p.get(survival, UV.Hunger)
    wc.call_method(USE_HELD)
    yield DRAW
    after = p.get(survival, UV.Hunger)
    p.check(f"{USE_HELD} (the right click on the hand's slot, the use key) eats it: "
            "out of the bag, and hunger refilled",
            got not in dressed.bag(p, wc) and after > before,
            f"in the bag {got in dressed.bag(p, wc)}, hunger {before:.1f} -> {after:.1f}")
    wc.call_method(USE_HELD)
    yield DRAW
    p.check("...and with nothing usable in hand it does nothing",
            p.get(survival, UV.Hunger) <= after + 1e-3)


def probe(p):
    yield lambda: p.pawn() is not None
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    yield 1.0
    hud = p.hud()
    ui = p.get(hud, "UiHud")
    held = []
    dressed.still(p, held, True)
    try:
        yield from _portrait(p, player, wc, hud, ui)
        yield from _use(p, player, wc, hud)
    finally:
        dressed.still(p, held, False)
        p.set(hud, WEAR_OPEN_VAR, False)
