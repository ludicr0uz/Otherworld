"""verify_graphics_menu.py's checks for save and exit and the saved profile
(profile_asset, save_exit, profile_read/write, profile_draw). Here rather than
in the verifier, which is over its size budget.
"""

import unreal

from graphics_menu import profile_consts as PC
from combat.record_vars import VIEW_WORN
from combat.wear_tuning import WORN_VAR
from combat import ask_consts as AC
from graphics_menu.ask_checks import asks, fed, feeders
from graphics_menu.pause_checks import row_gates

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


def _on_slot(nodes, *pins):
    return [n for n in nodes if {"SlotName", *pins} <= _pins(n)
            and _value(n, "SlotName") == PC.PROFILE_SLOT]


def _check_asset(check):
    eas = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    bp = eas.load_asset(PC.PROFILE_BP_PATH)
    check("BP_Profile exists and is a SaveGame",
          bp is not None
          and BEL.get_blueprint_parent_class(bp) == unreal.SaveGame.static_class(),
          PC.PROFILE_BP_PATH)
    # What it holds, and that no location is among it, is PROFILE_TABLE's
    # (var_checks.py): the stats as floats, the counts as ints, the arrays.


def check_profile(check, bp, nodes):
    _check_asset(check)
    starts = asks(nodes, AC.ASK_SAVE_EXIT)
    check("the M panel's save-and-exit row asks the weapon component for the exit "
          f"({AC.ASK_SAVE_EXIT}; the row has no key: only an open panel's row can be "
          "taken), with none running: once in single player's Tick and once in a "
          "client's",
          len(starts) == 2 and all(
              row_gates(s, PC.EXIT_ACTION)
              and any(f"Get {AC.EXIT_PENDING_VAR}" in fed(c, "A")
                      for g in feeders(s, "execute") for x in feeders(g, "Condition")
                      for c in feeders(x, "A") + feeders(x, "B")) for s in starts)
          and not [n for n in nodes if {"Key", "self"} <= _pins(n)
                   and _value(n, "Key") == "X"], str(len(starts)))
    leaves = [n for n in nodes if _title(n) == f"Set {PC.EXIT_LEAVING_VAR}"]
    due = {t for n in leaves for g in _feeders(n, "execute") for c in _feeders(g, "Condition")
           for t in fed(c, "A") + [x for f in _feeders(c, "B") for x in fed(f, "A")]}
    check(f"the HUD leaves once the component says the countdown is over "
          f"({AC.EXIT_DUE_VAR}), and only once ({PC.EXIT_LEAVING_VAR}), in either "
          f"mode (single player's save, a client's disconnect: mode_checks.py)",
          len(leaves) == 2
          and all(_value(n, PC.EXIT_LEAVING_VAR) == "true" for n in leaves)
          and due == {f"Get {AC.EXIT_DUE_VAR}", f"Get {PC.EXIT_LEAVING_VAR}"},
          f"{len(leaves)} Set, on {sorted(due)}")

    saves = _on_slot(nodes, "SaveGameObject")
    check(f"...the profile is saved once, to slot {PC.PROFILE_SLOT!r}", len(saves) == 1,
          str(len(saves)))
    opens = [n for n in nodes if "LevelName" in _pins(n) and "execute" in _pins(n)]
    after_save = [n for n in opens for d in _feeders(n, "execute")
                  if saves and saves[0] in _feeders(d, "execute")]
    # The other two: the death menu's restart, and Join Server's (mode_tick.py).
    check("...and then the current level reopens, onto the main menu",
          len(opens) == 3 and len(after_save) == 1,
          f"{len(opens)} OpenLevel, {len(after_save)} after the save")
    # The fifth is the title's first row asking whether there is one to continue.
    check("the profile is looked for, and loaded, once a game starts",
          len(_on_slot(nodes, "UserIndex")) == 5
          and any("Load" in _title(n) for n in _on_slot(nodes)),
          str([_title(n) for n in _on_slot(nodes)]))
    wipes = [n for n in _on_slot(nodes) if "Delete" in _title(n)]
    check("dying deletes the profile", len(wipes) == 1, str(len(wipes)))
    # The profile's own: the dev-all-guns cheat sets both too, but its
    # NeedsRefresh follows no EquippedIndex and its items come through a cast.
    refresh = [n for n in nodes if _title(n) == "Set NeedsRefresh"
               and any(_title(f) == "Set EquippedIndex" for f in _feeders(n, "execute"))]
    dropped = [n for n in nodes if _title(n) == "Set Dropped"
               and not any("Cast" in _title(f) for f in _feeders(n, "self"))]
    check("the loaded items are carried (Dropped false) and equipped by the "
          "weapon component (NeedsRefresh)",
          len(refresh) == 1 and _value(refresh[0], "NeedsRefresh") == "true"
          and len(dropped) == 1 and _value(dropped[0], "Dropped") == "false",
          f"{len(refresh)} NeedsRefresh, {len(dropped)} Dropped")
    # What is worn (K6): saved by class per slot, worn again through the
    # weapon component's ViewWorn, which spawns, hides and draws it.
    adds = [n for n in nodes if "TargetArray" in _pins(n) and "NewItem" in _pins(n)
            and any(_title(f) == f"Get {PC.WORN_CLASSES_FIELD}"
                    for f in _feeders(n, "TargetArray"))]
    from_worn = [n for n in adds for k in _feeders(n, "NewItem")
                 for loop in _feeders(k, "Object")
                 if any(_title(w) == f"Get {WORN_VAR}" for w in _feeders(loop, "Array"))]
    check(f"the save writes each slot of {WORN_VAR} down as its garment's class "
          f"({PC.WORN_CLASSES_FIELD}), before the one save",
          len(adds) == 1 and len(from_worn) == 1, f"{len(adds)} Add, {len(from_worn)} off Worn")
    wears = [n for n in nodes if _title(n).replace(" ", "") == VIEW_WORN
             and {"Slot", "Class", "self"} <= _pins(n)]
    saved = [n for n in wears for loop in _feeders(n, "Class")
             if any(_title(w) == f"Get {PC.WORN_CLASSES_FIELD}" for w in _feeders(loop, "Array"))]
    check(f"the load wears each saved class again, slot by slot, through the weapon "
          f"component's {VIEW_WORN} (hidden, in {WORN_VAR}, drawn on the body)",
          len(wears) == 1 and len(saved) == 1, f"{len(wears)} call, {len(saved)} off the save")
