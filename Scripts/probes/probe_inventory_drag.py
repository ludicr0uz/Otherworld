"""The I panel's drag in a game: an item dragged out of the inventory is set
down on the ground (the weapon component's DropRequest), and while a drag is
on its icon is shown on the cursor and the mouse does not turn the view
(graphics_menu/inv_drag.py, inv_carry.py).

No headless probe can aim a cursor at a cell or hold a button, so the probe
writes what the mouse writes: DropRequest on the component, InvDragFrom on
the HUD, and calls the HUD's ReceiveDrawHUD itself, as probe_menu_scroll
does. The press, the release over a real cell and the icon under a real
cursor need a window and a hand. Any profile on disk is set aside first, so
the game starts on the issued loadout, and put back at the end.
"""

import os
import shutil

import unreal

from combat.paths import ITEM_BP_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.slot_tuning import (
    BAG_FIRST, DROP_REQUEST_VAR, HAND, NO_REQUEST, PISTOL_SLOT, SECONDARY, SLOT_COUNT,
    SLOT_ITEMS_VAR, SLOT_VAR, UNPLACED,
)
from combat.tuning import DROP_FORWARD
from combat.wear_tuning import WORN_VAR
from graphics_menu.inv_consts import DRAG_FROM_VAR, DRAG_ICON, LOOK_HELD_VAR, NO_SLOT
from graphics_menu.profile_consts import PROFILE_SLOT
from graphics_menu.wear_consts import WEAR_OPEN_VAR

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = ([(WEAPON_COMP_BP_PATH, v) for v in (DROP_REQUEST_VAR, WORN_VAR)]
            + [(ITEM_BP_PATH, "Dropped")]
            + [(HUD_BP_PATH, v) for v in (WEAR_OPEN_VAR, DRAG_FROM_VAR)])
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


def _drop(p, wc, code):
    p.set(wc, DROP_REQUEST_VAR, code)
    yield lambda: p.get(wc, DROP_REQUEST_VAR) == NO_REQUEST
    yield SETTLE


def _on_ground(player, item):
    """Dropped, shown, out of every slot, and about DROP_FORWARD ahead."""
    away = (item.get_actor_location() - player.get_actor_location())
    flat = (away.x ** 2 + away.y ** 2) ** 0.5
    return (item.get_editor_property("Dropped") is True
            and not item.get_editor_property("hidden")
            and item.get_editor_property(SLOT_VAR) == UNPLACED
            and item.get_attach_parent_actor() is None
            and abs(flat - DROP_FORWARD) < 15.0), f"{flat:.0f} cm"


def _draw(hud):
    hud.call_method("ReceiveDrawHUD", (1920, 1080))


def _shown(widget):
    return "COLLAPSED" not in str(widget.get_visibility()).upper()


def _run(p):
    yield lambda: p.pawn() is not None
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    yield lambda: p.get(wc, "Held") is not None
    yield 0.3
    inv = list(p.get(wc, "Inventory"))
    shotgun, pistol, _knife, axe = inv[:4]

    # A slot's item that is not in hand.
    yield from _drop(p, wc, PISTOL_SLOT)
    ok, where = _on_ground(player, pistol)
    p.check("the pistol dragged out of the inventory lies on the ground ahead: Dropped, "
            "shown, detached, in no slot", ok, where)
    p.check("...out of Inventory and of its slot, and what is in hand stays there",
            pistol not in list(p.get(wc, "Inventory"))
            and p.get(wc, SLOT_ITEMS_VAR)[PISTOL_SLOT] is None
            and p.get(wc, "Held") == shotgun, str(p.get(wc, "Held")))

    # A bag slot's.
    yield from _drop(p, wc, BAG_FIRST)
    ok, where = _on_ground(player, axe)
    p.check("the axe dragged out of its bag slot lies on the ground too",
            ok and axe not in list(p.get(wc, "Inventory")), where)

    # An empty slot: nothing to set down.
    count = len(p.get(wc, "Inventory"))
    yield from _drop(p, wc, SECONDARY)
    p.check("an empty slot's drop does nothing, and the request is lowered",
            len(p.get(wc, "Inventory")) == count
            and p.get(wc, DROP_REQUEST_VAR) == NO_REQUEST)

    # A worn garment: the dropped pistol stands in for one, out of Inventory
    # as a worn garment is.
    p.set(pistol, "Dropped", False)
    pistol.set_actor_hidden_in_game(True)
    p.set(wc, WORN_VAR, [None, pistol])
    yield SETTLE
    yield from _drop(p, wc, SLOT_COUNT + 1)
    ok, where = _on_ground(player, pistol)
    p.check("a worn slot's item dragged out of the inventory leaves Worn and lies on "
            "the ground", ok and list(p.get(wc, WORN_VAR)) == [None, None], where)

    # The hand's own.
    yield from _drop(p, wc, HAND)
    yield lambda: p.get(wc, "Held") is None
    ok, where = _on_ground(player, shotgun)
    p.check("the held shotgun dragged out lies on the ground and the hands are empty",
            ok and p.get(wc, "Held") is None
            and shotgun not in list(p.get(wc, "Inventory")), where)

    # The HUD's half: the icon on the cursor, the look held.
    hud, pc = p.hud(), p.controller()
    icon = p.get(hud, "UiHud").get_editor_property(DRAG_ICON)
    p.set(hud, WEAR_OPEN_VAR, True)
    yield SETTLE
    _draw(hud)
    p.check("the I panel open with no drag on: no icon on the cursor, the look free",
            not _shown(icon) and not pc.is_look_input_ignored())
    knife_slot = _knife.get_editor_property(SLOT_VAR)
    p.set(hud, DRAG_FROM_VAR, knife_slot)
    _draw(hud)
    p.check("a drag on: the mouse does not turn the view (the look input is ignored)",
            pc.is_look_input_ignored() and p.get(hud, LOOK_HELD_VAR) is True)
    p.check("...and the dragged item's icon is shown, the knife's own",
            _shown(icon) and icon.get_editor_property("brush").get_editor_property(
                "resource_object") == _knife.get_editor_property("Icon"),
            str(icon.get_editor_property("brush").get_editor_property("resource_object")))
    _draw(hud)
    _draw(hud)
    p.set(hud, DRAG_FROM_VAR, NO_SLOT)       # the release
    _draw(hud)
    p.check("the drag over: the icon is gone and one call gives the look back (held "
            "on the edge only, over three frames)",
            not _shown(icon) and not pc.is_look_input_ignored())
    p.set(hud, DRAG_FROM_VAR, knife_slot)
    _draw(hud)
    p.set(hud, WEAR_OPEN_VAR, False)         # I pressed mid-drag
    yield SETTLE
    _draw(hud)
    p.check("the panel shut in the middle of a drag calls it off: no drag, no icon, "
            "the look free",
            p.get(hud, DRAG_FROM_VAR) == NO_SLOT and not _shown(icon)
            and not pc.is_look_input_ignored())
