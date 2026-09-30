"""BP_DayNightCycle: config defaults, the components, the graph's key nodes."""

import unreal

from combat.verify.common import (
    BEL, by_pins, cdo, check, component_template, components, graph, load, num_pin,
    pin_value,
)
from world import world_config as cfg
from world.day_night_blueprint import COMPONENTS, RANDOM_START_VAR
from world.paths import DAY_NIGHT_BP_PATH, SKY_MATERIAL_PATH, SKY_SPHERE_MESH_PATH, STATIC_SKY_TAG


def _check_defaults(bp):
    d = cdo(bp)
    for var, want in (("DayLengthSeconds", cfg.DAY_LENGTH_S),
                      ("NightLengthSeconds", cfg.NIGHT_LENGTH_S),
                      ("Clock", cfg.START_CLOCK_S)):
        got = d.get_editor_property(var)
        check(f"BP_DayNightCycle.{var} defaults to world_config ({want})",
              isinstance(got, float) and abs(got - want) < 1e-6, repr(got))
    got = d.get_editor_property(RANDOM_START_VAR)
    check(f"BP_DayNightCycle.{RANDOM_START_VAR} defaults to world_config "
          f"({cfg.RANDOM_START})", got is cfg.RANDOM_START, repr(got))


def _check_components(bp):
    have = set(components(bp))
    check("BP_DayNightCycle has its seven components", set(COMPONENTS) <= have,
          f"missing {sorted(set(COMPONENTS) - have)}")
    for name, index in (("Sun", 0), ("Moon", 1)):
        c = component_template(bp, name)
        ok = (isinstance(c, unreal.DirectionalLightComponent)
              and c.get_editor_property("mobility") == unreal.ComponentMobility.MOVABLE
              and c.get_editor_property("atmosphere_sun_light")
              and c.get_editor_property("atmosphere_sun_light_index") == index)
        check(f"{name}: a Movable directional light, atmosphere light {index}", ok)
    sky = component_template(bp, "SkyLight")
    check("SkyLight captures the sky in real time",
          sky is not None and sky.get_editor_property("real_time_capture"))
    dome = component_template(bp, "SkyDome")
    mesh = dome and dome.get_editor_property("static_mesh")
    mats = list(dome.get_editor_property("override_materials")) if dome else []
    check("SkyDome is SM_SkySphere wearing M_DayNightSky",
          mesh is not None and mesh.get_path_name() == SKY_SPHERE_MESH_PATH
          and mats and mats[0] and mats[0].get_path_name().split(".")[0] == SKY_MATERIAL_PATH,
          f"{mesh} / {mats}")
    check("SkyDome casts no shadow", dome is not None and not dome.get_editor_property("cast_shadow"))
    for name, prio, exposure in (("NightGrade", cfg.NIGHT_GRADE_PRIORITY, cfg.EXPOSURE[0]),
                                 ("DayGrade", cfg.DAY_GRADE_PRIORITY, cfg.EXPOSURE[1])):
        pp = component_template(bp, name)
        st = pp.get_editor_property("settings") if pp else None
        ok = (pp is not None and pp.get_editor_property("unbound")
              and abs(pp.get_editor_property("priority") - prio) < 1e-6
              and st.get_editor_property("override_auto_exposure_bias")
              and abs(st.get_editor_property("auto_exposure_bias")
                      - exposure["auto_exposure_bias"]) < 1e-4)
        check(f"{name}: unbound, priority {prio}, exposure bias "
              f"{exposure['auto_exposure_bias']}", ok)


def _check_graph(bp):
    nodes = graph(bp).list_all_nodes()
    tagged = by_pins(nodes, "Tag")
    check("BeginPlay removes the actors tagged " + STATIC_SKY_TAG,
          any(pin_value(n, "Tag") == STATIC_SKY_TAG for n in tagged),
          str([pin_value(n, "Tag") for n in tagged]))
    check("BeginPlay makes the dome's dynamic material",
          len(by_pins(nodes, "ElementIndex", "SourceMaterial")) == 1)
    picks = by_pins(nodes, "Min", "Max")
    check("BeginPlay, with RandomStart, sets Clock to a random point in the cycle",
          len(picks) == 1 and num_pin(picks[0], "Min") == 0.0
          and bool(BEL.find_input_pin(picks[0], "Max").list_connected_pins())
          and any("Set Clock" in str(BEL.get_node_title(unreal.BlueprintGraphPinLibrary
                                                        .get_owning_node(q)))
                  for q in BEL.find_output_pin(picks[0], "ReturnValue")
                  .list_connected_pins()),
          str([pin_value(n, "Min") for n in picks]))
    check("Tick turns the sun and the moon", len(by_pins(nodes, "NewRotation")) == 2)
    check("Tick sets three intensities (sun, moon, sky light)",
          len(by_pins(nodes, "NewIntensity")) == 3)
    params = {pin_value(n, "ParameterName") for n in by_pins(nodes, "ParameterName")}
    want = {"DayAmount", "StarBrightness", "SunDirection", "MoonDirection"}
    check("Tick feeds the dome DayAmount, StarBrightness and both directions",
          want <= params, f"has {sorted(params)}")
    ranges = [(num_pin(n, "InRangeA"), num_pin(n, "InRangeB"))
              for n in by_pins(nodes, "Value", "InRangeA", "InRangeB")]
    check("DayAmount maps the sun's elevation through the twilight band",
          (cfg.NIGHT_BELOW_DEG, cfg.DAY_ABOVE_DEG) in ranges, str(ranges))
    check("the stars follow the sun below the horizon",
          (0.0, cfg.STARS_FULL_BELOW_DEG) in ranges, str(ranges))
    mults = [num_pin(n, "B") for n in by_pins(nodes, "A", "B")]
    check("the sun's pitch swings to its max elevation",
          -cfg.SUN_MAX_ELEVATION_DEG in mults, str(mults))
    check("the moon's pitch swings to its max elevation",
          cfg.MOON_MAX_ELEVATION_DEG in mults, str(mults))


def run():
    bp = load(DAY_NIGHT_BP_PATH)
    check("BP_DayNightCycle exists", bp is not None, DAY_NIGHT_BP_PATH)
    if bp is None:
        return
    check("BP_DayNightCycle compiles", BEL.compile_blueprint(bp))
    _check_defaults(bp)
    _check_components(bp)
    _check_graph(bp)
