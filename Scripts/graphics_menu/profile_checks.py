"""verify_graphics_menu.py's checks for save and exit and the saved profile
(profile_asset, save_exit, profile_read/write, profile_draw). Here rather than
in the verifier, which is over its size budget.
"""

import unreal

from graphics_menu import profile_consts as PC
from graphics_menu.save_exit import profile_defaults

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
    if not bp:
        return
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    stats = {f: cdo.get_editor_property(f) for f, _o, _v in PC.STAT_FIELDS}
    check("the profile holds Health, Stamina, Hunger, Thirst and Temperature as floats",
          all(isinstance(v, float) for v in stats.values()),
          str({k: type(v).__name__ for k, v in stats.items()}))
    ints = [cdo.get_editor_property(f) for f in (PC.KILLS_FIELD, PC.EQUIPPED_FIELD)]
    check("...the kill count and the equipped slot as ints",
          all(isinstance(v, int) and not isinstance(v, bool) for v in ints),
          str([type(v).__name__ for v in ints]))
    arrays = [PC.ITEM_CLASSES_FIELD] + [f for f, _v in PC.AMMO_FIELDS]
    check("...and the inventory as class/Loaded/Reserve arrays",
          all(isinstance(cdo.get_editor_property(f), unreal.Array) for f in arrays))
    names = {str(n) for n in BEL.list_member_variable_names(bp, False)}
    expected = (set(stats) | {PC.KILLS_FIELD, PC.EQUIPPED_FIELD} | set(arrays))
    check("...and nothing else: no location is stored",
          names == expected, str(sorted(names ^ expected)))


def check_profile(check, bp, nodes):
    _check_asset(check)
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    wrong = {k: cdo.get_editor_property(k) for k, v in profile_defaults().items()
             if cdo.get_editor_property(k) != v}
    check("the countdown starts idle and the profile unlooked-for", not wrong, str(wrong))

    polls = [n for n in nodes if {"Key", "self"} <= _pins(n)
             and _value(n, "Key") == PC.EXIT_KEY]
    ands = [PIN.get_owning_node(q) for n in polls
            for q in BEL.find_output_pin(n, "ReturnValue").list_connected_pins()]
    gates = {_title(x) for a in ands for g in ("A", "B") for x in _feeders(a, g)}
    check(f"[{PC.EXIT_KEY}] starts the exit, only with the panel open",
          len(polls) == 1 and "Get MenuOpen" in gates, str(sorted(gates)))

    def _b(n):
        try:
            return float(_value(n, "B") or "nan")
        except ValueError:
            return float("nan")
    deadlines = [n for n in nodes if _pins(n) == {"A", "B"}
                 and abs(_b(n) - PC.EXIT_SECONDS) < 1e-6]
    check(f"...and it runs for {PC.EXIT_SECONDS:.0f} s", len(deadlines) == 1,
          str(len(deadlines)))

    hits = [n for n in nodes if _pins(n) == {"A", "B"}
            and {_title(f) for f in _feeders(n, "A")} == {"Get LastDamageTime"}]
    check("a hit after the start calls it off (LastDamageTime > ExitStartedAt)",
          len(hits) == 1
          and {_title(f) for f in _feeders(hits[0], "B")}
          == {f"Get {PC.EXIT_STARTED_VAR}"},
          str(len(hits)))

    saves = _on_slot(nodes, "SaveGameObject")
    check(f"the profile is saved once, to slot {PC.PROFILE_SLOT!r}", len(saves) == 1,
          str(len(saves)))
    opens = [n for n in nodes if "LevelName" in _pins(n) and "execute" in _pins(n)]
    after_save = [n for n in opens for d in _feeders(n, "execute")
                  if saves and saves[0] in _feeders(d, "execute")]
    check("...and then the current level reopens, onto the main menu",
          len(opens) == 2 and len(after_save) == 1,
          f"{len(opens)} OpenLevel, {len(after_save)} after the save")
    check("the profile is looked for, and loaded, once a game starts",
          len(_on_slot(nodes, "UserIndex")) == 4
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
    _check_freeze(check, nodes)


def _check_freeze(check, nodes):
    """The character stands still while the countdown runs; a hit frees it."""
    stops = [n for n in nodes if "DisableMovement" in _title(n).replace(" ", "")]
    waits = [b for n in stops for b in _feeders(n, "execute")
             if f"Get {PC.EXIT_AT_VAR}" in {_title(g) for c in _feeders(b, "Condition")
                                            for g in _feeders(c, "B")}]
    check("the character can't move while the exit counts down "
          "(DisableMovement every Tick it waits)",
          len(stops) == 1 and len(waits) == 1,
          f"{len(stops)} DisableMovement, {len(waits)} on the countdown's wait")
    walks = [n for n in nodes if "NewMovementMode" in _pins(n)]
    check("...and walks again when a hit calls the exit off",
          len(walks) == 1 and "Walking" in _value(walks[0], "NewMovementMode")
          and any(_title(f) == f"Set {PC.EXIT_CALLED_OFF_VAR}"
                  for f in _feeders(walks[0], "execute")),
          str([(_value(n, "NewMovementMode"), [_title(f) for f in _feeders(n, "execute")])
               for n in walks]))
