"""verify_graphics_menu.py's checks for the loot window (loot_tick, loot_find,
loot_take, loot_draw, wbp_loot). Here rather than in the verifier, which is
over its size budget.
"""

import unreal

from combat.tuning import INVENTORY_SIZE
from graphics_menu import loot_consts as LC
from graphics_menu import umg_consts as UC
from graphics_menu.loot_tick import loot_defaults
from graphics_menu.umg_checks import _tree
from combat.weapon_component.pose_weights import SEARCHING_VAR
from loot.consts import (
    BODY_ARRAYS, LOOT_ICONS_VAR, LOOT_RADIUS, LOOT_TINTS_VAR, LOOT_VAR,
)

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


def _into(n, pin="ReturnValue"):
    p = BEL.find_output_pin(n, pin)
    return [PIN.get_owning_node(q) for q in (p.list_connected_pins() if p else [])]


def _check_widgets(check):
    widgets = {name: w for name, (w, _var) in _tree(UC.WBP_HUD).items()}
    rows = widgets.get(LC.LOOT_ROWS_BOX)
    kids = list(rows.get_all_children()) if rows else []
    parts = (LC.LOOT_PROMPT, LC.LOOT_PANEL, LC.LOOT_EMPTY, LC.LOOT_FULL)
    check(f"WBP_HUD has the loot prompt, window, {LC.LOOT_ROWS} item rows, NOTHING "
          "and BAG FULL",
          all(n in widgets for n in parts) and len(kids) == LC.LOOT_ROWS
          and all(k.get_class().get_name() == "WBP_MenuRow_C" for k in kids),
          f"{len(kids)} rows; missing {[n for n in parts if n not in widgets]}")
    hidden = [n for n in parts if n in widgets
              and "COLLAPSED" in str(widgets[n].get_editor_property("visibility")).upper()]
    check("...all collapsed until the HUD shows them", len(hidden) == len(parts),
          str(hidden))
    icon = _tree(UC.WBP_MENU_ROW).get(UC.ROW_ICON, (None, False))
    # A DeprecateSlateVector2D exposes no fields; its text form is the way in.
    size = icon[0].get_editor_property("brush").get_editor_property("image_size") \
        .export_text() if icon[0] else ""
    check(f"a row has an icon, {UC.ROW_ICON_W:g} x {UC.ROW_ICON_H:g}, collapsed "
          "until a loot row shows it",
          icon[0] is not None and icon[1]
          and "COLLAPSED" in str(icon[0].get_editor_property("visibility")).upper()
          and size == f"(X={UC.ROW_ICON_W:.6f},Y={UC.ROW_ICON_H:.6f})", size or "no icon")


def _check_icons(check, nodes):
    """DrawHUD: a row is the item's icon in its tint, never its name."""
    def from_body(n, pin, var):
        return any(_title(g) == f"Get {var}" for f in _feeders(n, pin)
                   for g in _feeders(f, "TargetArray"))

    def on_row_icon(n):
        return any(_title(f) == f"Get {UC.ROW_ICON}" for f in _feeders(n, "self"))

    brushes = [n for n in nodes if "Texture" in _pins(n) and from_body(n, "Texture",
                                                                       LOOT_ICONS_VAR)]
    tints = [n for n in nodes if "InColorAndOpacity" in _pins(n)
             and from_body(n, "InColorAndOpacity", LOOT_TINTS_VAR)]
    check("a loot row shows the item's icon (LootIcons[i]) tinted its colour "
          "(LootTints[i]), on the row's Icon",
          len(brushes) == 1 and len(tints) == 1
          and on_row_icon(brushes[0]) and on_row_icon(tints[0]),
          f"{len(brushes)} brushes, {len(tints)} tints")
    named = [n for n in nodes if "LootNames" in _title(n) and _title(n).startswith("Get")
             and any("Text" in _title(x) for x in _into(n, "LootNames"))]
    check("...and never its name as text", not named, str(len(named)))
    empties = [n for n in nodes if _title(n) == f"Get {LC.LOOT_EMPTY}"]
    check("a body that carries nothing says so (LootEmpty shown while it has "
          "no icons to show)", len(empties) == 1, str(len(empties)))


def _check_kneel(check, nodes):
    told = [n for n in nodes if _title(n) == f"Set {SEARCHING_VAR}"]
    check(f"the open window is the weapon component's {SEARCHING_VAR} (the kneel)",
          len(told) == 1 and [_title(f) for f in _feeders(told[0], SEARCHING_VAR)]
          == [f"Get {LC.LOOT_OPEN_VAR}"],
          str([[_title(f) for f in _feeders(n, SEARCHING_VAR)] for n in told]))
    stops = [n for n in nodes if "bNewMoveInput" in _pins(n)]
    edge = [_title(f) for n in stops for f in _feeders(n, "execute")]
    gates = [g for n in stops for f in _feeders(n, "execute") for g in _feeders(f, "execute")
             if "Condition" in _pins(g)]
    differs = {_title(x) for g in gates for c in _feeders(g, "Condition")
               for x in _feeders(c, "A") + _feeders(c, "B")}
    check("...and the controller ignores move input while it is open, told once "
          "per change (LootOpen != LootKneeling)",
          len(stops) == 1
          and [_title(f) for f in _feeders(stops[0], "bNewMoveInput")]
          == [f"Get {LC.LOOT_OPEN_VAR}"]
          and edge == [f"Set {LC.LOOT_KNEELING_VAR}"]
          and differs == {f"Get {LC.LOOT_OPEN_VAR}", f"Get {LC.LOOT_KNEELING_VAR}"},
          f"{len(stops)} calls after {edge}, gated on {sorted(differs)}")


def check_loot(check, bp, nodes):
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    wrong = {k: cdo.get_editor_property(k) for k, v in loot_defaults().items()
             if cdo.get_editor_property(k) != v}
    check("the loot window starts shut, with nothing asked", not wrong, str(wrong))
    _check_widgets(check)

    scans = [n for n in nodes if "ActorClass" in _pins(n)
             and _value(n, "ActorClass").endswith("Character")]
    check("the HUD looks for a body among every Character", len(scans) == 1,
          str([_value(n, "ActorClass") for n in nodes if "ActorClass" in _pins(n)]))
    resets = [n for n in nodes if _title(n) == f"Set {LC.LOOT_BEST_VAR}"
              and not _feeders(n, LC.LOOT_BEST_VAR)]
    check(f"...within {LOOT_RADIUS:.0f} cm, reset every Tick",
          len(resets) == 1 and float(_value(resets[0], LC.LOOT_BEST_VAR)) == LOOT_RADIUS,
          str([_value(n, LC.LOOT_BEST_VAR) for n in resets]))
    nearer = [n for n in nodes if {"A", "B"} <= _pins(n)
              and any(_title(f) == f"Get {LC.LOOT_BEST_VAR}" for f in _feeders(n, "B"))
              and any("Distance" in _title(f) for f in _feeders(n, "A"))]
    check("...keeping the nearest (distance < LootBest)", len(nearer) == 1,
          str(len(nearer)))
    dead = [n for n in nodes if _title(n) == "Get Dead"
            and any("Cast" in _title(f) for f in _feeders(n, "self"))]
    others = [n for n in nodes if _title(n) == "Not Equal (Object)"
              and any("PlayerPawn" in _title(f) for f in _feeders(n, "B"))
              and any("For Each" in _title(f) for f in _feeders(n, "A"))]
    check("...that is Dead and is not the player's own", bool(dead) and len(others) == 1,
          f"{len(dead)} Dead, {len(others)} pawn tests")
    # The scan used to skip a body with an empty Loot; the one Loot read left
    # is the take's (below).
    stocked = [n for n in nodes if _title(n) == f"Get {LOOT_VAR}"
               and not any("Class" in _pins(s) or "IndexToRemove" in _pins(r)
                           for r in _into(n, LOOT_VAR) for s in _into(r, "Item") + [r])]
    check("...whether it carries anything or not (the scan reads no Loot)",
          not stocked, str(len(stocked)))

    polls = [n for n in nodes if {"Key", "self"} <= _pins(n)
             and _value(n, "Key") == LC.LOOT_KEY]
    check(f"[{LC.LOOT_KEY}] is polled once, and flips LootOpen",
          len(polls) == 1 and any(
              _title(n) == f"Set {LC.LOOT_OPEN_VAR}" and _feeders(n, LC.LOOT_OPEN_VAR)
              for n in nodes), str(len(polls)))
    asks = [n for n in nodes if _title(n) == f"Set {LC.LOOT_TAKE_VAR}"]
    check("Enter or a click on a row raises the take and Tick lowers it (and a "
          "lost body clears it)",
          sorted(_value(n, LC.LOOT_TAKE_VAR) for n in asks)
          == ["false", "false", "true", "true"],
          str([_value(n, LC.LOOT_TAKE_VAR) for n in asks]))

    fulls = [n for n in nodes if _title(n) == f"Set {LC.LOOT_BAG_FULL_VAR}"]
    tests = [t for n in fulls for t in _feeders(n, LC.LOOT_BAG_FULL_VAR)]
    check(f"the bag is full at {INVENTORY_SIZE} items",
          len(tests) == 1 and _value(tests[0], "B") == str(INVENTORY_SIZE),
          str([_value(t, "B") for t in tests]))

    spawns = [n for n in nodes if {"Class", "SpawnTransform"} <= _pins(n)
              and any(_title(g) == f"Get {LOOT_VAR}"
                      for f in _feeders(n, "Class") for g in _feeders(f, "TargetArray"))]
    check("a take spawns the item class read out of the body's Loot",
          len(spawns) == 1, str(len(spawns)))
    casts = [c for s in spawns for c in _into(s)]
    dropped = [x for x in nodes if _title(x) == "Set Dropped"
               and any(f in casts for f in _feeders(x, "self"))]
    check("...carried, not lying in the world (Dropped false)",
          len(dropped) == 1 and _value(dropped[0], "Dropped") == "false", str(len(dropped)))
    removes = [n for n in nodes if "IndexToRemove" in _pins(n)]
    emptied = sorted(_title(g) for n in removes for g in _feeders(n, "TargetArray"))
    check("...and taken out of every one of the body's arrays at LootSel",
          emptied == sorted(f"Get {v}" for v in BODY_ARRAYS)
          and all(_title(f) == f"Get {LC.LOOT_SEL_VAR}"
                  for n in removes for f in _feeders(n, "IndexToRemove")),
          str(emptied))
    gates = [n for n in nodes if "Condition" in _pins(n)
             and any(_title(g) == f"Get {LC.LOOT_BAG_FULL_VAR}"
                     for f in _feeders(n, "Condition") for g in _feeders(f, "A"))]
    check("...only while the bag has room", len(gates) == 1, str(len(gates)))
    some = [n for s in spawns for n in _feeders(s, "execute") if "Condition" in _pins(n)
               and any({"A", "B"} <= _pins(c) and _value(c, "B") in ("0", "")
                       for c in _feeders(n, "Condition"))]
    check("...and the body has something to take (an empty body is searched too)",
          len(some) == 1, str(len(some)))
    _check_icons(check, nodes)
    _check_kneel(check, nodes)

    guarded = [n for n in nodes if "Object" in _pins(n) and "IsValid" in _title(n)
               and any(_title(f) == f"Get {LC.LOOT_TARGET_VAR}" for f in _feeders(n, "Object"))]
    check("Tick and DrawHUD read the body only behind IsValid(LootTarget)",
          len(guarded) == 2, str(len(guarded)))
