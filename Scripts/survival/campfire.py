"""BP_Campfire: the fire a strike of the matches lights, and what warms the
player.

    [BeginPlay] --> SetLifeSpan(CAMPFIRE_BURN_S)      one piece of wood burns out
    [Tick] --> pawn = GetPlayerPawn(0); valid?
           --> within WarmRadius of this fire?
           --> its SurvivalComponent (GetComponentByClass, cast)
           --> Temperature = min(Temperature + WarmPerSecond * dt, MaxTemperature)

The fire measures its own distance on its own Tick, as BP_AmmoPickup does:
there are a few fires and one player, and a fire that has burned out costs
nothing. It writes the survival component the way the night's cold does
(world/night_cold.py), so the two simply add up: beside a fire the night's 0.1
a second is outrun by CAMPFIRE_WARM_PER_S.

combat/weapon_component/light.py spawns it, knowing only a class variable,
CampfireClass. install_campfire() writes this class onto BP_WeaponComponent's
default, as loot/install.py fills the health component's loot table.

The pawn is checked in a Branch of its own, and the distance in the next,
before anything reads off the pawn: a pure Get with a null self is an Accessed
None on every frame.

THE MODEL
---------
SM_Bonfire_Fire (CC0, Quaternius's Survival Pack): a ring of logs with flames
standing in it, 217 units across and 231 tall, a little off centre and
resting 6 units below z = 0. At CAMPFIRE_SCALE it is a fire 87 cm across with
flames to 90 cm. It blocks nothing: the player walks through it. A point
light at the flames' height lights the ground round it at night.
"""

import unreal

from combat.log import _log
from uebp.graph import (
    BEL, BGE, _add_component, _apply_defaults, _component_object, _connect,
    _create_blueprint, _declare, _drop_components, _events, _float_type, _loose_pin,
    _must_load, _node, _palette, _pin, _root_handle, _set, out, then)
from uebp.layout import arrange
from combat.light_tuning import CAMPFIRE_CLASS_VAR
from combat.paths import WEAPON_COMP_BP_PATH
from survival.paths import CAMPFIRE_BP_PATH, SURVIVAL_BP_PATH, SURVIVAL_CLASS_PATH
from survival.tuning import (
    CAMPFIRE_BURN_S, CAMPFIRE_WARM_PER_S, CAMPFIRE_WARM_RADIUS_CM,
)
from uebp.nodes.actor import FN_ACTOR_LOC, FN_GET_COMP, FN_LIFESPAN
from uebp.nodes.math import FN_ADD_FF, FN_DISTANCE, FN_FMIN, FN_LE_FF, FN_MUL_FF
from uebp.nodes.palette import NODE_CAST_SURVIVAL
from uebp.nodes.system import FN_GET_PLAYER_PAWN, FN_IS_VALID


CAMPFIRE_MESH = "/Game/Sourced/Quaternius/Survival/SM_Bonfire_Fire"
CAMPFIRE_SCALE = 0.4
# The mesh's middle on the ground and its lowest point, in its own units.
MESH_CENTRE_XY = (8.06, -1.27)
MESH_BOTTOM_Z = -5.94

WARM_RADIUS_VAR = "WarmRadius"
WARM_RATE_VAR = "WarmPerSecond"
TEMPERATURE_VAR = "Temperature"
MAX_TEMPERATURE_VAR = "MaxTemperature"

GLOW_HEIGHT_CM = 45.0
GLOW_COLOUR = (255, 140, 50)        # sRGB bytes: firelight
GLOW_INTENSITY = 3000.0
GLOW_RADIUS_CM = 900.0


def _build_model(bp):
    _drop_components(bp, {"Hearth", "Fire", "Glow"})
    root = _add_component(bp, _root_handle(bp), unreal.SceneComponent, "Hearth")
    fire = _component_object(_add_component(bp, root, unreal.StaticMeshComponent, "Fire"))
    fire.set_editor_property("static_mesh", _must_load(CAMPFIRE_MESH))
    fire.set_editor_property("relative_location", unreal.Vector(
        -MESH_CENTRE_XY[0] * CAMPFIRE_SCALE, -MESH_CENTRE_XY[1] * CAMPFIRE_SCALE,
        -MESH_BOTTOM_Z * CAMPFIRE_SCALE))
    fire.set_editor_property("relative_scale3d", unreal.Vector(*(CAMPFIRE_SCALE,) * 3))
    fire.set_collision_profile_name("NoCollision")
    glow = _component_object(_add_component(bp, root, unreal.PointLightComponent, "Glow"))
    glow.set_editor_property("relative_location", unreal.Vector(0.0, 0.0, GLOW_HEIGHT_CM))
    glow.set_editor_property("intensity", GLOW_INTENSITY)
    glow.set_editor_property("light_color", unreal.Color(r=GLOW_COLOUR[0], g=GLOW_COLOUR[1], b=GLOW_COLOUR[2], a=255))
    glow.set_editor_property("attenuation_radius", GLOW_RADIUS_CM)
    glow.set_editor_property("cast_shadows", False)


def _author_warmth(ed, tick):
    """Tick: warm the player's survival component while they are near."""
    def get(name):
        return out(ed.add_get_member_variable_node(name), name)

    pawn = _node(ed, FN_GET_PLAYER_PAWN)
    _set(pawn, "PlayerIndex", 0)
    is_there = _node(ed, FN_IS_VALID)
    _connect(out(pawn), _pin(is_there, "Object"))
    there = ed.add_branch_node()
    _connect(out(is_there), _pin(there, "Condition"))
    _connect(then(tick), _pin(there, "execute"))

    theirs = _node(ed, FN_ACTOR_LOC)
    _connect(out(pawn), _pin(theirs, "self"))
    mine = _node(ed, FN_ACTOR_LOC)
    gap = _node(ed, FN_DISTANCE)
    _connect(out(theirs), _pin(gap, "V1"))
    _connect(out(mine), _pin(gap, "V2"))
    close = _node(ed, FN_LE_FF)
    _connect(out(gap), _pin(close, "A"))
    _connect(get(WARM_RADIUS_VAR), _pin(close, "B"))
    near = ed.add_branch_node()
    _connect(out(close), _pin(near, "Condition"))
    _connect(then(there), _pin(near, "execute"))

    comp = _node(ed, FN_GET_COMP)
    _connect(out(pawn), _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(SURVIVAL_CLASS_PATH)
    if not unreal.load_asset(SURVIVAL_BP_PATH):   # the cast exists only for a loaded class
        raise RuntimeError(f"{SURVIVAL_BP_PATH} is missing -- build it first")
    cast = _palette(ed, NODE_CAST_SURVIVAL)
    if not BEL.list_input_pins(cast):
        raise RuntimeError("no cast node for BP_SurvivalComponent")
    _connect(out(comp), _pin(cast, "Object"))
    _connect(then(near), _pin(cast, "execute"))
    survival = _loose_pin(cast, "AsBPSurvivalComponent", is_input=False)

    def theirs_var(name):
        n = ed.add_get_member_variable_node(name, SURVIVAL_CLASS_PATH)
        _connect(survival, _pin(n, "self"))
        return out(n, name)

    step = _node(ed, FN_MUL_FF)
    _connect(out(tick, "DeltaSeconds"), _pin(step, "A"))
    _connect(get(WARM_RATE_VAR), _pin(step, "B"))
    more = _node(ed, FN_ADD_FF)
    _connect(theirs_var(TEMPERATURE_VAR), _pin(more, "A"))
    _connect(out(step), _pin(more, "B"))
    capped = _node(ed, FN_FMIN)
    _connect(out(more), _pin(capped, "A"))
    _connect(theirs_var(MAX_TEMPERATURE_VAR), _pin(capped, "B"))
    write = ed.add_set_member_variable_node(TEMPERATURE_VAR, SURVIVAL_CLASS_PATH)
    _connect(survival, _pin(write, "self"))
    _connect(out(capped), _pin(write, TEMPERATURE_VAR))
    _connect(_loose_pin(cast, "then", is_input=False), _pin(write, "execute"))
    ed.add_comment_to_nodes(
        "A campfire warms: while the player is within WarmRadius, their "
        "Temperature rises by WarmPerSecond, up to MaxTemperature.",
        [there, near, cast, write])


def build_campfire(rebuild=True):
    """BP_Campfire: the model, the glow, the burn time and the warmth."""
    bp = _create_blueprint(CAMPFIRE_BP_PATH, unreal.Actor)
    _build_model(bp)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    tick, begin = _events(ed, rebuild)
    for name in (WARM_RADIUS_VAR, WARM_RATE_VAR):
        _declare(ed, name, _float_type())

    life = _node(ed, FN_LIFESPAN)
    _set(life, "InLifespan", CAMPFIRE_BURN_S)
    _connect(then(begin), _pin(life, "execute"))
    _author_warmth(ed, tick)

    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{CAMPFIRE_BP_PATH} failed to compile")
    _apply_defaults(bp, {
        WARM_RADIUS_VAR: CAMPFIRE_WARM_RADIUS_CM,
        WARM_RATE_VAR: CAMPFIRE_WARM_PER_S,
    })
    _log(f"built {CAMPFIRE_BP_PATH} (+{CAMPFIRE_WARM_PER_S:g} temperature/s within "
         f"{CAMPFIRE_WARM_RADIUS_CM:.0f} cm, burning {CAMPFIRE_BURN_S:.0f} s)")
    return bp


def install_campfire(campfire_bp):
    """BP_WeaponComponent.CampfireClass: what a strike of the matches spawns."""
    _apply_defaults(_must_load(WEAPON_COMP_BP_PATH),
                    {CAMPFIRE_CLASS_VAR: BEL.generated_class(campfire_bp)})
    _log(f"{WEAPON_COMP_BP_PATH}.{CAMPFIRE_CLASS_VAR} -> {CAMPFIRE_BP_PATH}")
