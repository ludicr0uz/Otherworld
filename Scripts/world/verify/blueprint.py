"""BP_DayNightCycle: the components, the graph's key nodes. Its variables and
their defaults (world_config's) are var_tables.py's to check."""

import unreal

from combat.verify.common import (
    BEL, by_pins, cdo, check, component_template, components, graph, load, num_pin,
    pin_value,
)
from net.players_consts import LIVING_TITLE, PLAYERS_PIN
from world import world_config as cfg
from world.day_night_blueprint import (
    AMBIENT_SCALE_VAR, COMPONENTS, FOG_SCALE_VAR, LOOK_SCALE_VARS, MOON_DISC_SCALE_VAR,
    ITEM_HIGHLIGHT_VAR, MOON_SCALE_VAR, NIGHT_COLD_VAR, STAR_SCALE_VAR,
    SUN_DISC_SCALE_VAR, SUN_SCALE_VAR,
)
from combat.glimmer_tuning import (
    HIGHLIGHT_DEFAULT, MPC_ITEM_GLIMMER, MPC_NAME, PARAM_HIGHLIGHT,
)
from world.paths import DAY_NIGHT_BP_PATH, SKY_MATERIAL_PATH, SKY_SPHERE_MESH_PATH, STATIC_SKY_TAG


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


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _feeds(pin):
    return [_title(unreal.BlueprintGraphPinLibrary.get_owning_node(q))
            for q in pin.list_connected_pins()]


def _check_item_highlight(bp):
    """item_highlight.py: Tick writes the glimmer collection's switch."""
    nodes = graph(bp).list_all_nodes()
    writes = [n for n in by_pins(nodes, "Collection", "ParameterName", "ParameterValue")
              if MPC_NAME in pin_value(n, "Collection")]
    check(f"Tick writes {MPC_NAME}.{PARAM_HIGHLIGHT} once, from {ITEM_HIGHLIGHT_VAR}: "
          "the WORLD SETTINGS row switches every item's glimmer",
          len(writes) == 1 and pin_value(writes[0], "ParameterName") == PARAM_HIGHLIGHT
          and f"Get {ITEM_HIGHLIGHT_VAR}" in _feeds(
              BEL.find_input_pin(writes[0], "ParameterValue")),
          str([(pin_value(n, "Collection"), pin_value(n, "ParameterName")) for n in writes]))
    mpc = unreal.load_asset(MPC_ITEM_GLIMMER)
    params = {str(p.get_editor_property("parameter_name")):
              p.get_editor_property("default_value")
              for p in (mpc.get_editor_property("scalar_parameters") if mpc else [])}
    check(f"...and {MPC_NAME} has that scalar, on as built (a level without a cycle "
          "glimmers)", params.get(PARAM_HIGHLIGHT) == HIGHLIGHT_DEFAULT == 1.0, str(params))
    connected = [n for n in writes
                 if BEL.find_input_pin(n, "execute").list_connected_pins()]
    check("...on the Tick's chain, ahead of the night's cold (which stops with no player)",
          len(connected) == len(writes) == 1
          and not any("Cast" in t for n in writes
                      for t in _feeds(BEL.find_input_pin(n, "execute"))),
          str([_feeds(BEL.find_input_pin(n, "execute")) for n in writes]))


def _check_night_cold(bp):
    """night_cold.py: Tick lowers the player's Temperature by the cycle's rate."""
    nodes = graph(bp).list_all_nodes()
    sets = [n for n in nodes if _title(n) == "Set Temperature"]
    check("Tick writes Temperature once, on the player's survival component",
          len(sets) == 1 and any(t.replace(" ", "").endswith("CastToBP_SurvivalComponent")
                                 for t in _feeds(BEL.find_input_pin(sets[0], "self"))),
          str([_title(n) for n in sets]))
    if len(sets) != 1:
        return
    floors = [unreal.BlueprintGraphPinLibrary.get_owning_node(q)
              for q in BEL.find_input_pin(sets[0], "Temperature").list_connected_pins()]
    # A literal equal to its pin's default reads "" once loaded from disk.
    check("...floored at 0 (FMax), so the cold never takes it below empty",
          len(floors) == 1 and pin_value(floors[0], "B") in ("0.0", "0.000000", "", "0"),
          str([(_title(n), pin_value(n, "B")) for n in floors]))
    scaled = [n for n in by_pins(nodes, "A", "B")
              if f"Get {NIGHT_COLD_VAR}" in _feeds(BEL.find_input_pin(n, "A"))]
    flipped = [(num_pin(m, "OutRangeA"), num_pin(m, "OutRangeB"))
               for n in scaled for q in BEL.find_input_pin(n, "B").list_connected_pins()
               for m in [unreal.BlueprintGraphPinLibrary.get_owning_node(q)]
               if "Get DayAmount" in _feeds(BEL.find_input_pin(m, "Value"))]
    check(f"...by {NIGHT_COLD_VAR} x (1 - DayAmount): the night's, not the day's",
          len(scaled) == 1 and flipped == [(1.0, 0.0)], f"{len(scaled)} {flipped}")
    everyone = [n for n in nodes if _title(n) == LIVING_TITLE]
    owns = [unreal.BlueprintGraphPinLibrary.get_owning_node(q)
            for n in everyone
            for q in BEL.find_input_pin(n, "execute").list_connected_pins()]
    check("...with authority only (M26: Temperature is the server's, replicated to "
          "its owner)",
          len(owns) == 1 and "Switch Has Authority" in _title(owns[0])
          and str(unreal.BlueprintGraphPinLibrary.get_pin_name(
              BEL.find_input_pin(everyone[0], "execute").list_connected_pins()[0]))
          == "Authority", str([_title(n) for n in owns]))
    check("...of every living player's pawn: the write is in the body of a "
          "loop over them (net/players.py)",
          len(everyone) == 1 and not by_pins(nodes, "PlayerIndex")
          and any("For Each Loop" in t
                  for t in _feeds(BEL.find_output_pin(everyone[0], PLAYERS_PIN))),
          str(len(everyone)))


def _check_look(bp):
    """The look multipliers the GRAPHICS SETTINGS tab writes: 1 as built, and
    each one scaling the thing it names."""
    d = cdo(bp)
    off = {v: d.get_editor_property(v) for v in LOOK_SCALE_VARS
           if abs(d.get_editor_property(v) - 1.0) > 1e-6}
    check(f"the {len(LOOK_SCALE_VARS)} look multipliers default to 1 (the world as "
          "world_config has it)", not off, str(off))
    pins = unreal.BlueprintGraphPinLibrary
    nodes = graph(bp).list_all_nodes()

    def reaches(var):
        """(pin name, the node's ParameterName literal) for every input the
        variable drives, straight or through one multiply."""
        out = set()
        for n in nodes:
            if _title(n) != f"Get {var}":
                continue
            for q in BEL.find_output_pin(n, var).list_connected_pins():
                m = pins.get_owning_node(q)
                ends = [q] if str(pins.get_pin_name(q)) != "B" else \
                    BEL.find_output_pin(m, "ReturnValue").list_connected_pins()
                for e in ends:
                    owner = pins.get_owning_node(e)
                    param = BEL.find_input_pin(owner, "ParameterName")
                    out.add((_title(owner).replace(" ", ""),
                             pin_value(owner, "ParameterName") if param else ""))
        return out

    wrong = []
    for var, title, param in ((SUN_SCALE_VAR, "SetIntensity", ""),
                              (MOON_SCALE_VAR, "SetIntensity", ""),
                              (AMBIENT_SCALE_VAR, "SetIntensity", ""),
                              (FOG_SCALE_VAR, "SetFogDensity", ""),
                              (STAR_SCALE_VAR, "SetScalarParameterValue", "StarBrightness"),
                              (SUN_DISC_SCALE_VAR, "SetScalarParameterValue",
                               "SunDiscBrightness"),
                              (MOON_DISC_SCALE_VAR, "SetScalarParameterValue",
                               "MoonDiscBrightness")):
        got = reaches(var)
        if len(got) != 1 or not all(title in t and p == param for t, p in got):
            wrong.append(f"{var} -> {sorted(got)}")
    check("each multiplier scales its own output: the sun's, the moon's and the sky "
          "light's intensity, the fog's density, the stars and the two discs",
          not wrong, "; ".join(wrong))


def run():
    bp = load(DAY_NIGHT_BP_PATH)
    check("BP_DayNightCycle exists", bp is not None, DAY_NIGHT_BP_PATH)
    if bp is None:
        return
    check("BP_DayNightCycle compiles", BEL.compile_blueprint(bp))
    _check_components(bp)
    _check_graph(bp)
    _check_item_highlight(bp)
    _check_night_cold(bp)
    _check_look(bp)
