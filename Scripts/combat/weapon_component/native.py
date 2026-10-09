"""BP_WeaponComponent's native parent (task W1): the reparent onto
OtherworldWeaponComponentBase (C++, Source/Otherworld; uebp/nodes/weapon.py
has its nodes), and the names it finds the Blueprints' variables by.

The base holds the shot's server half: Server_Fire's guard, refusals, round
and deadline, the pellets' traces and the damage they hand over. Held is
still this Blueprint's variable, the round and the deadline the item's, and
the health component a Blueprint, so C++ reads and writes them by name
(Source/CLAUDE.md, "A Blueprint variable read or written from C++ is found
by name"). The names are properties of the class defaults, written here from
the builders' own constants and held to them by combat/verify/shot.py.
"""

import unreal

from combat import health_vars as HV
from combat import item_vars as IV
from combat.damage import TAKE_HIT
from combat.light_tuning import LIGHTS_VAR
from combat.log import _log
from combat.paths import HEALTH_CLASS_PATH
from combat.shot_vars import FIRE_GRACE_S, SERVER_FIRE, AsksServed
from combat.weapon_component import vars as WV
from uebp.graph import BEL
from uebp.nodes.weapon import WEAPON_BASE_CLASS

# The base's property -> the name it reads by.
NAMES = {
    "fire_event_name": SERVER_FIRE,
    "held_var": str(WV.Held),
    "asks_served_var": str(AsksServed),
    "item_melee_var": str(IV.Melee),
    "item_consumable_var": str(IV.Consumable),
    "item_lights_var": str(LIGHTS_VAR),
    "item_uses_ammo_var": str(IV.UsesAmmo),
    "item_loaded_var": str(IV.Loaded),
    "item_next_fire_time_var": str(IV.NextFireTime),
    "item_fire_interval_var": str(IV.FireInterval),
    "take_hit_event": TAKE_HIT,
    "health_var": str(HV.Health),
    "health_dead_var": str(HV.Dead),
    "head_bones_var": str(HV.HeadBones),
    "limb_bones_var": str(HV.LimbBones),
    "head_multiplier_var": str(HV.HeadMultiplier),
    "limb_multiplier_var": str(HV.LimbMultiplier),
}
# ...and its numbers.
NUMBERS = {"fire_grace_seconds": FIRE_GRACE_S}
# The class a body is asked for its health by, as the graphs ask
# (GetComponentByClass): {property: class path}.
CLASSES = {"health_class": HEALTH_CLASS_PATH}


def _must_load_class(path):
    cls = unreal.load_class(None, path)
    if cls is None:
        raise RuntimeError(f"could not load the class {path}")
    return cls


def base_class():
    cls = unreal.load_class(None, WEAPON_BASE_CLASS)
    if cls is None:
        raise RuntimeError(f"{WEAPON_BASE_CLASS} is not loaded: compile the Otherworld "
                           "module (Source/CLAUDE.md)")
    return cls


def reparent(bp, ed):
    """Make ``bp`` a child of the native base, keeping its variables. Before
    the graph is authored: the shot's nodes are the base's.

    A component built before W1 has a custom event named as the base's
    Server_Fire, which the compile on the new parent refuses: that event
    node goes first (its calls then find the base's function, and the build
    that follows replaces the whole graph).
    """
    parent = base_class()
    if BEL.get_blueprint_parent_class(bp) == parent:
        return
    before = {str(v) for v in BEL.list_member_variable_names(bp)}
    old = ed.find_event_node(SERVER_FIRE)
    if old:
        ed.remove_nodes([old])
    BEL.reparent_blueprint(bp, parent)
    if BEL.get_blueprint_parent_class(bp) != parent:
        raise RuntimeError(f"{bp.get_name()} did not take {WEAPON_BASE_CLASS}")
    lost = before - {str(v) for v in BEL.list_member_variable_names(bp)}
    if lost:
        raise RuntimeError(f"{bp.get_name()} lost variables in the reparent: {sorted(lost)}")
    _log(f"BP_WeaponComponent: reparented onto {parent.get_name()}")


def write_names(bp):
    """The names and numbers onto the class defaults. Before the compile
    that bakes the defaults in; wrong_names says whether they held."""
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    for prop, value in {**NAMES, **NUMBERS}.items():
        cdo.set_editor_property(prop, value)
    for prop, path in CLASSES.items():
        cdo.set_editor_property(prop, _must_load_class(path))


def wrong_names(bp):
    """{property: what it holds} for every name or number the class defaults
    do not hold as the tables have it."""
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    wrong = {p: str(cdo.get_editor_property(p)) for p, name in NAMES.items()
             if str(cdo.get_editor_property(p)) != name}
    wrong.update({p: cdo.get_editor_property(p) for p, value in NUMBERS.items()
                  if abs(float(cdo.get_editor_property(p)) - value) > 1e-6})
    for prop, path in CLASSES.items():
        held = cdo.get_editor_property(prop)
        if held is None or held.get_path_name() != path:
            wrong[prop] = str(held)
    return wrong
