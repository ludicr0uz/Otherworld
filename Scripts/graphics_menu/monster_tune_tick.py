"""The MONSTER TUNING tab's HUD Tick fragment: the tab's keys, nudge and save
(tune_tick.author_tab_flow, shared with GUN TUNING), then the table onto
every live wanderer.

    its M panel row taken   MonTuneOpen = NOT MonTuneOpen; TuneOpen and
                            WorldTuneOpen = false
    MenuOpen AND MonTuneOpen: Up/Down, Left/Right, Enter as GUN TUNING
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

from combat.graph import BEL, _at, _connect, _loose_pin, _palette, _pin
from combat.nodes import FN_ARR_GET, MACRO_FOR_EACH
from graphics_menu.dev_guns import _branch, _call, _get
from graphics_menu.gfx_tune_consts import GFX_TAB
from graphics_menu.monster_tune_consts import (
    MON_CONTROLLERS, MON_CREATURES, MON_STAT_COUNT, MONSTER_TAB,
)
from graphics_menu.tune_consts import GUN_TAB
from graphics_menu.tune_tick import author_tab_flow, declare_tab_vars, tab_defaults
from graphics_menu.world_tune_consts import WORLD_TAB
from npc.monster_tuning import MONSTER_STATS, monster_specs

FN_GET_ALL_ACTORS = "/Script/Engine.GameplayStatics.GetAllActorsOfClass"


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


def _author_creature(ed, c, bp_path, class_path, in_execs, x0, y0, made):
    """Creature ``c``'s row onto every live controller of its class. Returns
    the loop's Completed pin."""
    bp = unreal.load_asset(bp_path)      # for its class pin and cast node
    if not bp:
        raise RuntimeError(f"{bp_path} is missing -- run build_npc_blueprints.py first")
    find = _call(ed, FN_GET_ALL_ACTORS, x0, y0, made)
    _pin(find, "ActorClass").set_pin_value(class_path)
    for e in in_execs:
        _connect(e, _pin(find, "execute"))
    loop = _at(ed.add_macro_node(MACRO_FOR_EACH), x0 + 300, y0)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    made.append(loop)
    _connect(_pin(find, "OutActors", is_input=False), _loose_pin(loop, "Array"))
    _connect(BEL.find_then_pin(find), _loose_pin(loop, "Exec"))

    name = bp_path.rsplit("/", 1)[-1]
    cast = _at(_palette(ed, f"Utilities|Casting|CastTo{name}"), x0 + 600, y0)
    if not BEL.list_input_pins(cast):
        raise RuntimeError(f"no cast node for {name}")
    made.append(cast)
    _connect(_loose_pin(loop, "ArrayElement", is_input=False), _pin(cast, "Object"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(cast, "execute"))
    ai = _as_pin(cast)

    flow, x = BEL.find_then_pin(cast), x0 + 900
    for s, (_col, var, *_rest) in enumerate(MONSTER_STATS):
        # The cell's index is known at build time: a literal on Array_Get.
        cell = _call(ed, FN_ARR_GET, x + 240, y0 + 440, made,
                     TargetArray=_get(ed, MONSTER_TAB.values_var, x, y0 + 440, made),
                     Index=c * MON_STAT_COUNT + s)
        value = _pin(cell, "Item", is_input=False)
        n = _at(ed.add_set_member_variable_node(var, class_path), x + 480, y0)
        made.append(n)
        _connect(ai, _pin(n, "self"))
        _connect(value, _pin(n, var))
        _connect(flow, _pin(n, "execute"))
        flow = BEL.find_then_pin(n)
        x += 600
    return _loose_pin(loop, "Completed", is_input=False)


def _author_apply(ed, in_execs, x0, y0, made):
    """MonTuneTouched: the table onto every live wanderer. Returns the tails."""
    go, idle = _branch(ed, _get(ed, MONSTER_TAB.touched_var, x0 - 240, y0 + 300, made),
                       in_execs, x0, y0, made)
    flow = [go]
    for c, (_key, bp_path, class_path) in enumerate(MON_CONTROLLERS):
        flow = [_author_creature(ed, c, bp_path, class_path, flow,
                                 x0 + 300, y0 + c * 1200, made)]
    return flow + [idle]


def author_monster_tune_tick(ed, pc_out, in_execs, x0, y0):
    """The whole fragment (see the module docstring). Returns the exec tails."""
    made = []
    flow = author_tab_flow(ed, pc_out, in_execs, x0, y0, made, MONSTER_TAB,
                           len(MON_CREATURES),
                           (GUN_TAB.open_var, WORLD_TAB.open_var,
                            GFX_TAB.open_var))
    tails = _author_apply(ed, flow, x0 + 10400, y0, made)
    ed.add_comment_to_nodes(
        "Monster tuning (its row in the M panel): Up/Down pick a row, "
        "Left/Right change the creature or the stat, Enter saves monster_tuning.csv. "
        "Once anything is tuned, every live wanderer's controller takes its "
        "creature's row each Tick.", made[:1])
    return tails
