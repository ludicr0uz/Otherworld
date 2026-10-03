"""The inventory's look, in a rendered window: the hand slot and the weapon
slots bottom centre, the worn panel bottom right, and with I open the
backpack under it and the character's portrait left of it, then a drag on
(the held item's icon carried on the cursor, which is put at the middle of
the window). Saves `shot showui` pictures to
Saved/Screenshots/MacEditor/ (the I panel shut, open, and a drag on) for a look.

    python3 Scripts/dev/uepy.py --game --windowed --probe Scripts/probes/probe_inventory_window.py

A -nullrhi run lays nothing out, so the checks here are only that the
widgets are shown; the look is the pictures'.
"""

import unreal

from combat.paths import WEAPON_COMP_CLASS_PATH
from combat.slot_tuning import HAND
from graphics_menu.inv_consts import BAG_PANEL, DRAG_FROM_VAR, DRAG_ICON, HAND_BOX, WEAPON_BOX
from graphics_menu.wear_consts import WEAR_OPEN_VAR, WEAR_PANEL, WEAR_PORTRAIT

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HUD_BP_PATH, WEAR_OPEN_VAR), (HUD_BP_PATH, DRAG_FROM_VAR)]
SHOWN = unreal.SlateVisibility.HIT_TEST_INVISIBLE
# The slot grids keep the designer's visibility: the HUD never writes it.
DRAWN = (SHOWN, unreal.SlateVisibility.SELF_HIT_TEST_INVISIBLE)


def _shot(p, what):
    unreal.SystemLibrary.execute_console_command(p.world(), "shot showui")
    p.note(f"shot showui: {what}")


def probe(p):
    yield lambda: p.pawn() is not None
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    yield lambda: p.get(wc, "Held") is not None
    yield 1.0
    hud = p.hud()
    ui = p.get(hud, "UiHud")
    p.check("the hand slot, the weapon slots, the worn slots and the backpack show "
            "with I shut",
            all(ui.get_editor_property(n).get_visibility() in DRAWN
                for n in (HAND_BOX, WEAPON_BOX))
            and all(ui.get_editor_property(n).get_visibility()
                    != unreal.SlateVisibility.COLLAPSED for n in (WEAR_PANEL, BAG_PANEL)),
            str([str(ui.get_editor_property(n).get_visibility())
                 for n in (HAND_BOX, WEAPON_BOX, WEAR_PANEL, BAG_PANEL)]))
    p.check("...and the character's portrait does not",
            ui.get_editor_property(WEAR_PORTRAIT).get_visibility()
            == unreal.SlateVisibility.COLLAPSED)
    _shot(p, "the I panel shut")
    yield 1.0
    p.set(hud, WEAR_OPEN_VAR, True)
    yield 1.0
    p.check("...and with I open the backpack still shows",
            ui.get_editor_property(BAG_PANEL).get_visibility() == SHOWN)
    p.check("...and so does the character's portrait",
            ui.get_editor_property(WEAR_PORTRAIT).get_visibility() == SHOWN)
    _shot(p, "the I panel open")
    yield 1.0
    # A drag on (no button is down, so nothing releases it): the hand's item
    # carried on the cursor, in the middle of the window.
    size = unreal.WidgetLayoutLibrary.get_viewport_size(p.world())
    p.controller().set_mouse_location(int(size.x / 2), int(size.y / 2))
    p.set(hud, DRAG_FROM_VAR, HAND)
    yield 1.0
    p.check("a drag on: the dragged item's icon shows, and the look is held",
            ui.get_editor_property(DRAG_ICON).get_visibility() == SHOWN
            and p.controller().is_look_input_ignored(),
            str(ui.get_editor_property(DRAG_ICON).get_visibility()))
    _shot(p, "a drag on: the icon at the middle of the window")
    yield 1.0
