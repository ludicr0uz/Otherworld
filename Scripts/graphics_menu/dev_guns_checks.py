"""verify_graphics_menu.py's checks for the dev-all-guns cheat (dev_guns.py).
Here rather than in the verifier, which is over its size budget.
"""

import unreal

from combat.tuning import INVENTORY_SIZE
from graphics_menu import dev_consts as DC
from graphics_menu import umg_consts as UC
from graphics_menu.dev_guns import dev_guns_defaults

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


def _short(class_path):
    return class_path.rsplit(".", 1)[1]


def check_dev_guns(check, bp, nodes):
    check("the M panel lists dev-all-guns",
          DC.DEV_GUNS_ROW_LABEL in UC.PAUSE_ROW_LABELS, str(UC.PAUSE_ROW_LABELS))
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    wrong = {k: cdo.get_editor_property(k) for k, v in dev_guns_defaults().items()
             if cdo.get_editor_property(k) != v}
    check("dev-all-guns starts unrequested", not wrong, str(wrong))

    polls = [n for n in nodes if {"Key", "self"} <= _pins(n)
             and _value(n, "Key") == DC.DEV_GUNS_KEY]
    ands = [PIN.get_owning_node(q) for n in polls
            for q in BEL.find_output_pin(n, "ReturnValue").list_connected_pins()]
    gates = {_title(x) for a in ands for g in ("A", "B") for x in _feeders(a, g)}
    check(f"[{DC.DEV_GUNS_KEY}] requests the guns, only with the panel open",
          len(polls) == 1 and "Get MenuOpen" in gates, str(sorted(gates)))
    raises = [n for n in nodes if _title(n) == f"Set {DC.DEV_GUNS_REQUEST_VAR}"]
    check("...and the request is raised once and served once",
          sorted(_value(n, DC.DEV_GUNS_REQUEST_VAR) for n in raises) == ["false", "true"],
          str([_value(n, DC.DEV_GUNS_REQUEST_VAR) for n in raises]))

    spawns = [n for n in nodes if {"Class", "SpawnTransform"} <= _pins(n)]
    spawned = [_value(n, "Class") for n in spawns]
    missing = [c for c in DC.DEV_GUN_CLASS_PATHS
               if sum(_short(c) in v for v in spawned) != 1]
    check(f"it spawns each of the {len(DC.DEV_GUN_CLASS_PATHS)} guns once",
          not missing, f"missing or doubled {missing}; spawns {spawned}")
    tests = [_value(n, "B") for n in nodes if _pins(n) == {"A", "B"}
             and any("Class" in _title(f) for f in _feeders(n, "A"))]
    unchecked = [c for c in DC.DEV_GUN_CLASS_PATHS
                 if sum(_short(c) in v for v in tests) != 1]
    check("...skipping a gun already carried (its class tested against the bag)",
          not unchecked, f"untested {unchecked}; tests {tests}")
    rooms = [n for n in nodes if _pins(n) == {"A", "B"}
             and _value(n, "B") == str(INVENTORY_SIZE)
             and any("Length" in _title(f) for f in _feeders(n, "A"))]
    check(f"...and only while fewer than {INVENTORY_SIZE} items are carried",
          len(rooms) == len(DC.DEV_GUN_CLASS_PATHS), str(len(rooms)))

    carried = [n for n in nodes if _title(n) == "Set Dropped"
               and any("Cast" in _title(f) for f in _feeders(n, "self"))]
    check("each given gun is carried (Dropped false)",
          len(carried) == len(DC.DEV_GUN_CLASS_PATHS)
          and all(_value(n, "Dropped") == "false" for n in carried),
          str(len(carried)))
    refresh = [n for n in nodes if _title(n) == "Set NeedsRefresh"
               and not any(_title(f) == "Set EquippedIndex"
                           for f in _feeders(n, "execute"))]
    check("...and the weapon component re-equips after (NeedsRefresh)",
          len(refresh) == 1 and _value(refresh[0], "NeedsRefresh") == "true",
          str(len(refresh)))
