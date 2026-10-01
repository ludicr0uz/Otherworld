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
from loot.consts import LOOT_NAMES_VAR, LOOT_RADIUS, LOOT_VAR

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
    check(f"WBP_HUD has the loot prompt, window, {LC.LOOT_ROWS} item rows and BAG FULL",
          all(n in widgets for n in (LC.LOOT_PROMPT, LC.LOOT_PANEL, LC.LOOT_FULL))
          and len(kids) == LC.LOOT_ROWS
          and all(k.get_class().get_name() == "WBP_MenuRow_C" for k in kids),
          f"{len(kids)} rows; missing "
          f"{[n for n in (LC.LOOT_PROMPT, LC.LOOT_PANEL, LC.LOOT_FULL) if n not in widgets]}")
    hidden = [n for n in (LC.LOOT_PROMPT, LC.LOOT_PANEL, LC.LOOT_FULL) if n in widgets
              and "COLLAPSED" in str(widgets[n].get_editor_property("visibility")).upper()]
    check("...all collapsed until the HUD shows them", len(hidden) == 3, str(hidden))


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
    stocked = [n for n in nodes if _title(n) == f"Get {LOOT_VAR}"]
    check("...that is Dead and still carries Loot", bool(dead) and bool(stocked),
          f"{len(dead)} Dead, {len(stocked)} Loot reads")

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
    check("...and taken out of the body's Loot and LootNames at LootSel",
          emptied == sorted([f"Get {LOOT_VAR}", f"Get {LOOT_NAMES_VAR}"])
          and all(_title(f) == f"Get {LC.LOOT_SEL_VAR}"
                  for n in removes for f in _feeders(n, "IndexToRemove")),
          str(emptied))
    gates = [n for n in nodes if "Condition" in _pins(n)
             and any(_title(g) == f"Get {LC.LOOT_BAG_FULL_VAR}"
                     for f in _feeders(n, "Condition") for g in _feeders(f, "A"))]
    check("...only while the bag has room", len(gates) == 1, str(len(gates)))

    guarded = [n for n in nodes if "Object" in _pins(n) and "IsValid" in _title(n)
               and any(_title(f) == f"Get {LC.LOOT_TARGET_VAR}" for f in _feeders(n, "Object"))]
    check("Tick and DrawHUD read the body only behind IsValid(LootTarget)",
          len(guarded) == 2, str(len(guarded)))
