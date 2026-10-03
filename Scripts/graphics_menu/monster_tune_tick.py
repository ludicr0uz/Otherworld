"""The MONSTER SETTINGS tab's HUD Tick fragment: the tab's keys, nudge and save
(tune_tick.author_tab_flow, shared with GUN SETTINGS), then the table onto
every live wanderer.

    its M panel row taken   MonTuneOpen = NOT MonTuneOpen; TuneOpen and
                            WorldTuneOpen = false
    MenuOpen AND MonTuneOpen: Up/Down, Left/Right, Enter as GUN SETTINGS
    MonTuneTouched -> for each creature c (MON_CONTROLLERS, in table order):
                      every live BP_ForestWandererAI_<c> (GetAllActorsOfClass)
                      gets each Tune* variable := MonTuneValues[c, stat]

The controller's graphs read every number off those variables
(npc/tuned.py), so a change lands on that wanderer's next behaviour-tree
pass (0.5 s at most): its senses, patrol, melee, speed (the Chase and Stroll
steps rewrite MaxWalkSpeed every pass) and health (re-applied, full, when
TuneHealth moves: npc/stats.py). Every Tick once touched, not once per nudge,
so a wanderer that respawns or spawns later gets the tuning too.
"""

import unreal

from uebp.graph import BEL, _connect, _loose_pin, _palette, _pin, out, then
from graphics_menu.dev_guns import _branch, _call, _get
from graphics_menu.monster_tune_consts import (
    MON_CONTROLLERS, MON_CREATURES, MON_STAT_COUNT, MONSTER_TAB,
)
from graphics_menu.tune_tabs import other_open_vars
from graphics_menu.tune_tick import author_tab_flow, declare_tab_vars, tab_defaults
from npc.monster_tuning import MONSTER_STATS, monster_specs
from uebp.nodes.array import FN_ARR_GET
from uebp.nodes.palette import MACRO_FOR_EACH
from uebp.nodes.system import FN_ALL_ACTORS


def declare_monster_tune_vars(ed):
    declare_tab_vars(ed, MONSTER_TAB)


def monster_table():
    """(creatures, values): NPC_VARIANTS' keys and their MONSTER_STATS cells,
    flattened creature by creature -- monster_specs, so monster_tuning.csv."""
    values = [float(monster_specs(key)[col]) for key in MON_CREATURES
              for col, *_rest in MONSTER_STATS]
    return list(MON_CREATURES), values


def monster_tune_defaults():
    creatures, values = monster_table()
    return tab_defaults(MONSTER_TAB, creatures, values,
                        [float(st[3]) for st in MONSTER_STATS],
                        [float(st[4]) for st in MONSTER_STATS])


def _as_pin(cast):
    """The cast's typed output ("AsBP Forest Wanderer AI Zombie")."""
    for p in BEL.list_output_pins(cast):
        if str(unreal.BlueprintGraphPinLibrary.get_pin_name(p)).replace(" ", "").startswith("As"):
            return p
    raise RuntimeError("the cast has no As<Class> pin")


def _author_creature(ed, c, bp_path, class_path, in_execs, made):
    """Creature ``c``'s row onto every live controller of its class. Returns
    the loop's Completed pin."""
    bp = unreal.load_asset(bp_path)      # for its class pin and cast node
    if not bp:
        raise RuntimeError(f"{bp_path} is missing -- run build_npc_blueprints.py first")
    find = _call(ed, FN_ALL_ACTORS, made)
    _pin(find, "ActorClass").set_pin_value(class_path)
    for e in in_execs:
        _connect(e, _pin(find, "execute"))
    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    made.append(loop)
    _connect(out(find, "OutActors"), _loose_pin(loop, "Array"))
    _connect(then(find), _loose_pin(loop, "Exec"))

    name = bp_path.rsplit("/", 1)[-1]
    cast = _palette(ed, f"Utilities|Casting|CastTo{name}")
    if not BEL.list_input_pins(cast):
        raise RuntimeError(f"no cast node for {name}")
    made.append(cast)
    _connect(_loose_pin(loop, "ArrayElement", is_input=False), _pin(cast, "Object"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(cast, "execute"))
    ai = _as_pin(cast)

    flow = then(cast)
    for s, (_col, var, *_rest) in enumerate(MONSTER_STATS):
        # The cell's index is known at build time: a literal on Array_Get.
        cell = _call(ed, FN_ARR_GET, made,
                     TargetArray=_get(ed, MONSTER_TAB.values_var, made),
                     Index=c * MON_STAT_COUNT + s)
        value = out(cell, "Item")
        n = ed.add_set_member_variable_node(var, class_path)
        made.append(n)
        _connect(ai, _pin(n, "self"))
        _connect(value, _pin(n, var))
        _connect(flow, _pin(n, "execute"))
        flow = then(n)
    return _loose_pin(loop, "Completed", is_input=False)


def _author_apply(ed, in_execs, made):
    """MonTuneTouched: the table onto every live wanderer. Returns the tails."""
    go, idle = _branch(ed, _get(ed, MONSTER_TAB.touched_var, made), in_execs, made)
    flow = [go]
    for c, (_key, bp_path, class_path) in enumerate(MON_CONTROLLERS):
        flow = [_author_creature(ed, c, bp_path, class_path, flow, made)]
    return flow + [idle]


def author_monster_tune_tick(ed, pc_out, in_execs):
    """The whole fragment (see the module docstring). Returns the exec tails."""
    made = []
    flow = author_tab_flow(ed, pc_out, in_execs, made, MONSTER_TAB,
                           len(MON_CREATURES),
                           other_open_vars(MONSTER_TAB))
    tails = _author_apply(ed, flow, made)
    ed.add_comment_to_nodes(
        "Monster tuning (its row in the M panel): Up/Down pick a row, "
        "Left/Right change the creature or the stat, Enter saves monster_tuning.csv. "
        "Once anything is tuned, every live wanderer's controller takes its "
        "creature's row each Tick.", made[:1])
    return tails
