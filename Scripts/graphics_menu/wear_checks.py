"""verify_graphics_menu.py's checks for the I panel (wear_tick, wear_draw,
wbp_wear) and its portrait. Here rather than in the verifier, which is over its size budget.
The weapon component's side (the wear and the take-off) is
combat/verify/wear.py's.
"""

import unreal

from combat import ask_consts as AC
from combat.wear_tuning import NOT_CLOTHING, WORN_VAR
from combat.weapon_component.dead import OWNER_DEAD_VAR
from graphics_menu import umg_consts as UC
from graphics_menu.ask_checks import asks, fed
from graphics_menu import wear_consts as WC
from graphics_menu.umg_checks import _tree
from graphics_menu.wear_tick import WEAR_STILL_VAR, wear_defaults
from graphics_menu.inv_carry import carry_defaults
from graphics_menu.inv_consts import (
    DRAG_FROM_VAR, DRAG_ICON, INV_OVER_VAR, LOOK_HELD_VAR, NO_SLOT)
from item_icons.items import UI_ART_DIR, icon_name
from item_icons.portrait import PORTRAIT_TEXTURE

BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _pins(n):
    return {str(PIN.get_pin_name(p)) for p in BEL.list_input_pins(n)}


def _value(n, pin):
    return str(BEL.find_input_pin(n, pin).get_pin_value())


def _feeders(n, pin):
    p = BEL.find_input_pin(n, pin)
    return [PIN.get_owning_node(q) for q in (p.list_connected_pins() if p else [])]


def _check_widgets(check):
    widgets = {name: w for name, (w, _var) in _tree(UC.WBP_HUD).items()}
    grid = widgets.get(WC.WEAR_SLOTS_BOX)
    kids = list(grid.get_all_children()) if grid else []
    ghosts = [g.get_name() if g else None
              for g in (k.get_editor_property(UC.SLOT_GHOST_VAR) for k in kids)]
    places = [(k.get_editor_property("slot").get_editor_property("row"),
               k.get_editor_property("slot").get_editor_property("column")) for k in kids]
    check("WBP_HUD has the I panel: one inventory slot per worn slot, in rows of "
          f"{WC.WEAR_COLUMNS}, each with its garment's silhouette and no text, and "
          "its close line",
          WC.WEAR_PANEL in widgets and WC.WEAR_CLOSE in widgets
          and ghosts == [icon_name(d) for d in WC.WEAR_GHOSTS]
          and places == [divmod(i, WC.WEAR_COLUMNS) for i in range(WC.WEAR_ROWS)]
          and all(k.get_class().get_name() == "WBP_InventorySlot_C" for k in kids),
          f"{ghosts} at {places}")
    panel = widgets.get(WC.WEAR_PANEL)
    check("...collapsed until the HUD shows it",
          panel is not None
          and "COLLAPSED" in str(panel.get_editor_property("visibility")).upper())


def _check_portrait(check, nodes):
    widgets = {name: w for name, (w, _var) in _tree(UC.WBP_HUD).items()}
    outer, image = widgets.get(WC.WEAR_PORTRAIT), widgets.get(WC.WEAR_PORTRAIT_IMAGE)
    drawn = image.get_editor_property("brush").get_editor_property("resource_object") \
        if image else None
    check(f"WBP_HUD has the character's portrait: {PORTRAIT_TEXTURE}, collapsed until "
          "the HUD shows it",
          outer is not None and drawn is not None
          and drawn == unreal.EditorAssetLibrary.load_asset(f"{UI_ART_DIR}/{PORTRAIT_TEXTURE}")
          and "COLLAPSED" in str(outer.get_editor_property("visibility")).upper(),
          str(drawn.get_name() if drawn else None))
    sets = [n for n in nodes if "InVisibility" in _pins(n)
            and [_title(f) for f in _feeders(n, "self")] == [f"Get {WC.WEAR_PORTRAIT}"]]
    gates = {_title(g) for n in sets for b in _feeders(n, "execute")
             for c in _feeders(b, "Condition") for g in _feeders(c, "A")}
    check(f"...shown and collapsed on one branch, which reads {WC.WEAR_OPEN_VAR}",
          len(sets) == 2 and len({_value(n, "InVisibility") for n in sets}) == 2
          and gates == {f"Get {WC.WEAR_OPEN_VAR}"}, f"{len(sets)} sets, gated by {gates}")


def _check_keys(check, nodes):
    polls = [n for n in nodes if {"Key", "self"} <= _pins(n)
             and _value(n, "Key") == WC.WEAR_KEY]
    flips = [n for n in nodes if _title(n) == f"Set {WC.WEAR_OPEN_VAR}"
             and _feeders(n, WC.WEAR_OPEN_VAR)]
    check(f"[{WC.WEAR_KEY}] is polled once, and flips {WC.WEAR_OPEN_VAR}",
          len(polls) == 1 and len(flips) == 1, f"{len(polls)} polls, {len(flips)} flips")
    dying = [n for n in nodes if "Condition" in _pins(n)
             and [_title(f) for f in _feeders(n, "Condition")] == [f"Get {OWNER_DEAD_VAR}"]
             and any(_title(PIN.get_owning_node(q)) == f"Set {WC.WEAR_OPEN_VAR}"
                     for q in BEL.find_then_pin(n).list_connected_pins())]
    shuts = [PIN.get_owning_node(q) for n in dying
             for q in BEL.find_then_pin(n).list_connected_pins()]
    check(f"a dead player wears nothing new: {OWNER_DEAD_VAR} shuts the panel",
          len(dying) == 1 and [_value(n, WC.WEAR_OPEN_VAR) for n in shuts] == ["false"],
          str([_title(n) for n in shuts]))
    offs = asks(nodes, AC.ASK_TAKE_OFF)
    by_sel = [n for n in offs if fed(n, "Slot") == [f"Get {WC.WEAR_SEL_VAR}"]]
    check(f"a take-off is asked of the weapon component: {AC.ASK_TAKE_OFF}("
          f"{WC.WEAR_SEL_VAR}, into the bag) once (Enter, a click), and once by a drag "
          "off a worn slot",
          len(offs) == 2 and len(by_sel) == 1
          and _value(by_sel[0], "To") == str(NOT_CLOTHING),
          str([fed(n, "Slot") for n in offs]))
    drags = [n for n in offs if n not in by_sel]
    wears = asks(nodes, AC.ASK_WEAR)
    check("...the drag names the slot it dropped the garment on (To := InvOver), "
          f"and a slot's item dropped on the worn grid is asked worn ({AC.ASK_WEAR}("
          f"{DRAG_FROM_VAR}))",
          len(drags) == 1 and len(wears) == 1
          and fed(drags[0], "To") == [f"Get {INV_OVER_VAR}"]
          and fed(wears[0], "From") == [f"Get {DRAG_FROM_VAR}"],
          f"{len(drags)} drags, {len(wears)} wears")
    takes = sorted(_value(n, WC.WEAR_TAKE_VAR) for n in nodes
                   if _title(n) == f"Set {WC.WEAR_TAKE_VAR}")
    check("Enter or a click on a worn slot raises the take-off, and Tick lowers it (and "
          "death clears it)", takes == ["false", "false", "true", "true"], str(takes))
    stills = [n for n in nodes if "bNewMoveInput" in _pins(n)
              and [_title(f) for f in _feeders(n, "bNewMoveInput")]
              == [f"Get {WC.WEAR_OPEN_VAR}"]]
    edge = [_title(f) for n in stills for f in _feeders(n, "execute")]
    check("the open panel holds the walk, told on WearOpen's edges only",
          len(stills) == 1 and edge == [f"Set {WEAR_STILL_VAR}"], str(edge))


def _check_draw(check, nodes):
    worn = [n for n in nodes if _title(n) == f"Get {WORN_VAR}"]
    check(f"the panel shows the weapon component's {WORN_VAR}, off a cast (the draw's "
          "read, and the drag's)",
          len(worn) == 2
          and all(any("Cast" in _title(f) for f in _feeders(n, "self")) for n in worn),
          str(len(worn)))
    def off_worn(n):
        return any(_title(a) == f"Get {WORN_VAR}"
                   for f in _feeders(n, "self") for a in _feeders(f, "TargetArray"))

    icons = [n for n in nodes if _title(n) == "Get Icon" and off_worn(n)]
    names = [n for n in nodes if _title(n) == "Get DisplayName" and off_worn(n)]
    check("...each slot's picture the worn garment's own Icon, read off Worn[i] (and "
          "the icon a drag carries, off the dragged one), and no name written",
          len(icons) == 2 and not names, f"{len(icons)} icons, {len(names)} names")


def _check_carry(check, bp, nodes):
    """inv_carry.py, and inv_drag.py's drop: the icon on the cursor, the
    look held, the drag out of the inventory."""
    icon = _tree(UC.WBP_HUD).get(DRAG_ICON)
    check(f"WBP_HUD has {DRAG_ICON}, the icon a drag carries: a variable, collapsed "
          "until one is on",
          icon is not None and icon[1]
          and "COLLAPSED" in str(icon[0].get_editor_property("visibility")).upper())
    moves = [n for n in nodes if "Translation" in _pins(n)
             and [_title(f) for f in _feeders(n, "self")] == [f"Get {DRAG_ICON}"]]
    place = [_title(g) for n in moves for f in _feeders(n, "Translation")
             for g in _feeders(f, "AbsoluteCoordinate")]
    check("...moved onto the cursor every frame a drag is on (its translation the "
          "cursor's place in the HUD's own space)",
          len(moves) == 1 and place == ["Get CursorPos"], f"{len(moves)} moves, {place}")
    drops = asks(nodes, AC.ASK_DROP)
    check(f"a drag released outside the inventory asks the weapon component to set "
          f"the item down: {AC.ASK_DROP}({DRAG_FROM_VAR}), once",
          len(drops) == 1 and fed(drops[0], "From") == [f"Get {DRAG_FROM_VAR}"],
          str(len(drops)))
    ends = [_value(n, DRAG_FROM_VAR) for n in nodes if _title(n) == f"Set {DRAG_FROM_VAR}"
            and not _feeders(n, DRAG_FROM_VAR)]
    check("a drag ends on the release, and when the panel is not open",
          ends == [str(NO_SLOT)] * 2, str(ends))
    holds = [n for n in nodes if "bNewLookInput" in _pins(n)
             and [_title(f) for f in _feeders(n, "bNewLookInput")]
             == [f"Get {LOOK_HELD_VAR}"]]
    edge = [_title(f) for n in holds for f in _feeders(n, "execute")]
    check("while a drag is on the mouse does not turn the view: SetIgnoreLookInput, "
          "told on the drag's edges only",
          len(holds) == 1 and edge == [f"Set {LOOK_HELD_VAR}"], str(edge))
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    wrong = {k: v for k, v in carry_defaults().items() if cdo.get_editor_property(k) != v}
    check("...and the look starts free", not wrong, str(wrong))


def check_wear(check, bp, nodes):
    _check_widgets(check)
    _check_portrait(check, nodes)
    _check_keys(check, nodes)
    _check_draw(check, nodes)
    _check_carry(check, bp, nodes)
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    wrong = {k: v for k, v in wear_defaults().items() if cdo.get_editor_property(k) != v}
    check("the I panel's variables start shut, on the first slot", not wrong, str(wrong))
