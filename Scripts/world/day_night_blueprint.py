"""BP_DayNightCycle's shape: its components, its variables and their defaults.

The graph that moves it is day_night_graph.py; this module is everything that
is set once, at build time.

The actor owns the whole sky rig -- a sun and a moon (two Movable directional
lights, atmosphere lights 0 and 1), a real-time SkyLight, the sky dome, the
height fog and two unbound post-process components (NightGrade always on,
DayGrade weighted by DayAmount) -- rather than steering the level's. The
level's rig is generated per preset and verified as generated; the cycle tags
it (level_placement.py) and destroys it at BeginPlay, so one set of components
with one set of values runs every level the same way.
"""

import unreal

from combat.graph import (
    BEL, _add_component, _apply_defaults, _component_object, _declare,
    _drop_components, _float_type, _must_load, _root_handle,
)
from world import world_config as cfg
from world.paths import SKY_MATERIAL_PATH, SKY_SPHERE_MESH_PATH

COMPONENTS = ("Sun", "Moon", "SkyLight", "SkyDome", "Fog", "NightGrade", "DayGrade")

# Variables. The two lengths and Clock are Instance Editable, so a level can
# run a different day, or start at a different hour, without a rebuild.
CONFIG_VARS = ("DayLengthSeconds", "NightLengthSeconds", "Clock")
STATE_FLOAT_VARS = ("DayAmount",)
IS_DAY_VAR = "IsDay"
SKY_MID_VAR = "SkyMaterial"


def _srgb(c):
    return unreal.Color(r=c[0], g=c[1], b=c[2], a=255)


def _linear(c):
    return unreal.LinearColor(c[0], c[1], c[2], c[3] if len(c) > 3 else 1.0)


def _light(obj, lux, color, index):
    obj.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    obj.set_editor_property("intensity", float(lux))
    obj.set_editor_property("light_color", _srgb(color))
    obj.set_editor_property("cast_shadows", True)
    obj.set_editor_property("dynamic_shadow_distance_movable_light",
                            float(cfg.SHADOW_DISTANCE_CM))
    obj.set_editor_property("atmosphere_sun_light", True)
    obj.set_editor_property("atmosphere_sun_light_index", index)


def _grade(obj, priority, weight, exposure):
    obj.set_editor_property("unbound", True)
    obj.set_editor_property("priority", float(priority))
    obj.set_editor_property("blend_weight", float(weight))
    st = obj.get_editor_property("settings")
    st.set_editor_property("override_auto_exposure_method", True)
    st.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_HISTOGRAM)
    for key in ("auto_exposure_min_brightness", "auto_exposure_max_brightness",
                "auto_exposure_bias"):
        st.set_editor_property(f"override_{key}", True)
        st.set_editor_property(key, float(exposure[key]))
    obj.set_editor_property("settings", st)


def build_components(bp):
    """Drop and re-add the seven components, and set each one's template."""
    _drop_components(bp, set(COMPONENTS))
    root = _root_handle(bp)
    made = {}
    for name, cls in (("Sun", unreal.DirectionalLightComponent),
                      ("Moon", unreal.DirectionalLightComponent),
                      ("SkyLight", unreal.SkyLightComponent),
                      ("SkyDome", unreal.StaticMeshComponent),
                      ("Fog", unreal.ExponentialHeightFogComponent),
                      ("NightGrade", unreal.PostProcessComponent),
                      ("DayGrade", unreal.PostProcessComponent)):
        made[name] = _component_object(_add_component(bp, root, cls, name))

    _light(made["Sun"], cfg.SUN_LUX, cfg.SUN_COLOR, 0)
    _light(made["Moon"], 0.0, cfg.MOON_COLOR, 1)

    sky = made["SkyLight"]
    sky.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    sky.set_editor_property("real_time_capture", True)
    sky.set_editor_property("intensity", float(cfg.SKY_LIGHT_INTENSITY[1]))

    dome = made["SkyDome"]
    dome.set_editor_property("static_mesh", _must_load(SKY_SPHERE_MESH_PATH))
    dome.set_editor_property("override_materials", [_must_load(SKY_MATERIAL_PATH)])
    dome.set_editor_property("relative_scale3d", unreal.Vector(
        cfg.SKY_DOME_SCALE, cfg.SKY_DOME_SCALE, cfg.SKY_DOME_SCALE))
    dome.set_editor_property("cast_shadow", False)
    dome.set_collision_profile_name("NoCollision")

    fog = made["Fog"]
    fog.set_editor_property("enable_volumetric_fog", True)
    fog.set_editor_property("fog_density", float(cfg.FOG_DENSITY[1]))
    fog.set_editor_property("fog_inscattering_luminance", _linear(cfg.FOG_COLOR[1]))
    fog.set_editor_property("volumetric_fog_extinction_scale",
                            float(cfg.FOG_VOLUMETRIC_EXTINCTION))

    _grade(made["NightGrade"], cfg.NIGHT_GRADE_PRIORITY, 1.0, cfg.EXPOSURE[0])
    _grade(made["DayGrade"], cfg.DAY_GRADE_PRIORITY, 1.0, cfg.EXPOSURE[1])
    return made


def declare_variables(ed):
    for name in CONFIG_VARS + STATE_FLOAT_VARS:
        _declare(ed, name, _float_type())
    _declare(ed, IS_DAY_VAR, BEL.get_basic_type_by_name("bool"))
    _declare(ed, SKY_MID_VAR, BEL.get_object_reference_type(
        unreal.MaterialInstanceDynamic.static_class()))


def apply_config(bp):
    """Instance Editable lengths and clock; defaults from world_config (compiles, saves)."""
    for name in CONFIG_VARS:
        BEL.set_blueprint_variable_instance_editable(bp, name, True)
    # The CDO only has the new variables once the class is compiled.
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{bp.get_name()} failed to compile")
    _apply_defaults(bp, {
        "DayLengthSeconds": float(cfg.DAY_LENGTH_S),
        "NightLengthSeconds": float(cfg.NIGHT_LENGTH_S),
        "Clock": float(cfg.START_CLOCK_S),
    })
