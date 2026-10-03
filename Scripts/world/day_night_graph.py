"""BP_DayNightCycle's EventGraph: BeginPlay takes over the sky, Tick runs it.

BeginPlay destroys every actor tagged STATIC_SKY_TAG (the level's own light,
sky light, fog, clouds and dome), gives the dome a dynamic material and, with
RandomStart, sets Clock to a random point in the whole cycle (so a game
starts at a random time of day).

Tick advances Clock and derives everything else from it, the same sums as
world_config.sun_state():

  angle      0-180 across the day, 180-360 across the night
  sun        pitch -SUN_MAX*sin(angle), yaw SUNRISE_YAW + angle
  moon       pitch +MOON_MAX*sin(angle), yaw SUNRISE_YAW + angle - 180
             (the sun's path, half a cycle later)
  DayAmount  the sun's elevation mapped through the twilight band, stored
  lights     sun lux x DayAmount; moon lux x its horizon fade x (1 - DayAmount)
  air        SkyLight intensity, fog density and colour, DayGrade's weight:
             all night value -> day value by DayAmount
  sky        the dome's DayAmount, StarBrightness, SunDirection, MoonDirection
  look       each light, the stars, the sky light, the fog's density and the
             two discs are then multiplied by a look variable
             (day_night_blueprint.LOOK_SCALE_VARS), 1 unless the GRAPHICS
             SETTINGS tab moved it
  cold       the player's Temperature falls at night: night_cold.py, which
             build_day_night.py chains on after build_graph()

Everything downstream of Clock is pure and re-evaluates on each read, which is
harmless here: Clock is set first and read unchanged for the rest of the frame.
Constants sit on B pins or range pins (a Kismet A pin will not hold a literal).
"""

from combat.log import _log
from uebp.graph import _connect, _events, _loose_pin, _node, _pin, _set, out, then
from combat.nodes import (
    FN_ADD_FF, FN_DESTROY, FN_LESS_FF, FN_MAKE_ROT, FN_MUL_FF, FN_RANDOM_FLOAT,
    MACRO_FOR_EACH,
)
from world import world_config as cfg
from world.day_night_blueprint import (
    AMBIENT_SCALE_VAR, FOG_SCALE_VAR, IS_DAY_VAR, MOON_DISC_SCALE_VAR, MOON_SCALE_VAR,
    RANDOM_START_VAR, SKY_MID_VAR, STAR_SCALE_VAR, SUN_DISC_SCALE_VAR, SUN_SCALE_VAR,
)
from world.paths import STATIC_SKY_TAG

KML = "/Script/Engine.KismetMathLibrary"
FN_PERCENT_FF = f"{KML}.Percent_FloatFloat"
FN_MAP_CLAMPED = f"{KML}.MapRangeClamped"
FN_DEG_SIN = f"{KML}.DegSin"
FN_NEGATE_V = f"{KML}.NegateVector"
FN_VEC_TO_COLOR = f"{KML}.Conv_VectorToLinearColor"
FN_MAKE_COLOR = f"{KML}.MakeColor"
FN_COLOR_LERP = f"{KML}.LinearColorLerp"
FN_ACTORS_WITH_TAG = "/Script/Engine.GameplayStatics.GetAllActorsWithTag"
FN_CREATE_MID = "/Script/Engine.PrimitiveComponent.CreateDynamicMaterialInstance"
FN_SET_WORLD_ROT = "/Script/Engine.SceneComponent.K2_SetWorldRotation"
FN_FORWARD_OF = "/Script/Engine.SceneComponent.GetForwardVector"
FN_LIGHT_INTENSITY = "/Script/Engine.LightComponent.SetIntensity"
FN_SKY_INTENSITY = "/Script/Engine.SkyLightComponent.SetIntensity"
FN_FOG_DENSITY = "/Script/Engine.ExponentialHeightFogComponent.SetFogDensity"
FN_FOG_COLOR = "/Script/Engine.ExponentialHeightFogComponent.SetFogInscatteringColor"
FN_MID_SCALAR = "/Script/Engine.MaterialInstanceDynamic.SetScalarParameterValue"
FN_MID_VECTOR = "/Script/Engine.MaterialInstanceDynamic.SetVectorParameterValue"
PP_CLASS_PATH = "/Script/Engine.PostProcessComponent"


class _Chain:
    """An exec wire that each step extends: step(node) links then -> execute."""

    def __init__(self, then_pin):
        self.then = then_pin

    def step(self, node):
        _connect(self.then, _pin(node, "execute"))
        self.then = then(node)
        return node


def _call(ed, fn, **inputs):
    """A call node with each input either wired (a pin) or set (a literal)."""
    n = _node(ed, fn)
    for name, value in inputs.items():
        if hasattr(value, "try_create_connection"):
            _connect(value, _pin(n, name))
        else:
            _set(n, name, value)
    return n


def _get(ed, name):
    return out(ed.add_get_member_variable_node(name), name)


def _mul(ed, a, b):
    return out(_call(ed, FN_MUL_FF, A=a, B=float(b)))


def _scaled(ed, value, scale_var):
    """value x one of the look multipliers (a variable, so it sits on B)."""
    return out(_call(ed, FN_MUL_FF, A=value, B=_get(ed, scale_var)))


def _map(ed, value, in_a, in_b, out_a, out_b):
    return out(_call(ed, FN_MAP_CLAMPED, Value=value,
                      InRangeA=float(in_a), InRangeB=float(in_b),
                      OutRangeA=float(out_a), OutRangeB=float(out_b)))


def _color(ed, rgba):
    c = list(rgba) + [1.0] * (4 - len(rgba))
    return out(_call(ed, FN_MAKE_COLOR, R=float(c[0]), G=float(c[1]), B=float(c[2]), A=float(c[3])))


def _set_var(ed, chain, name, value_pin):
    n = chain.step(ed.add_set_member_variable_node(name))
    _connect(value_pin, _pin(n, name))
    return n


def _author_begin_play(ed, begin):
    """Destroy the level's tagged sky rig, make the dome's dynamic material,
    then (RandomStart) pick the starting clock."""
    chain = _Chain(then(begin))
    found = chain.step(_call(ed, FN_ACTORS_WITH_TAG, Tag=STATIC_SKY_TAG))
    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    _connect(chain.then, _loose_pin(loop, "Exec"))
    _connect(out(found, "OutActors"), _loose_pin(loop, "Array"))
    kill = _node(ed, FN_DESTROY)
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(kill, "execute"))
    _connect(_loose_pin(loop, "ArrayElement", is_input=False), _pin(kill, "self"))

    chain = _Chain(_loose_pin(loop, "Completed", is_input=False))
    mid = chain.step(_call(ed, FN_CREATE_MID, self=_get(ed, "SkyDome"), ElementIndex=0))
    _set_var(ed, chain, SKY_MID_VAR, out(mid))

    pick = chain.step(ed.add_branch_node())
    _connect(_get(ed, RANDOM_START_VAR), _pin(pick, "Condition"))
    total = out(_call(ed, FN_ADD_FF,
                       A=_get(ed, "DayLengthSeconds"),
                       B=_get(ed, "NightLengthSeconds")))
    anywhere = _call(ed, FN_RANDOM_FLOAT, Min=0.0, Max=total)
    _set_var(ed, chain, "Clock", out(anywhere))


def _author_clock(ed, tick, chain):
    """Advance Clock, set IsDay; return (clock, day_len, sin(angle), sun_elev) pins."""
    day_len = _get(ed, "DayLengthSeconds")
    total = out(_call(ed, FN_ADD_FF, A=day_len, B=_get(ed, "NightLengthSeconds")))
    ahead = out(_call(ed, FN_ADD_FF, A=_get(ed, "Clock"), B=out(tick, "DeltaSeconds")))
    wrapped = out(_call(ed, FN_PERCENT_FF, A=ahead, B=total))
    _set_var(ed, chain, "Clock", wrapped)

    clock = _get(ed, "Clock")
    is_day = out(_call(ed, FN_LESS_FF, A=clock, B=day_len))
    _set_var(ed, chain, IS_DAY_VAR, is_day)

    # angle = map(clock, 0..day -> 0..180) + map(clock, day..total -> 0..180)
    first = _call(ed, FN_MAP_CLAMPED, Value=clock, InRangeA=0.0,
                  InRangeB=day_len, OutRangeA=0.0, OutRangeB=180.0)
    second = _call(ed, FN_MAP_CLAMPED, Value=clock, InRangeA=day_len,
                   InRangeB=total, OutRangeA=0.0, OutRangeB=180.0)
    angle = out(_call(ed, FN_ADD_FF, A=out(first), B=out(second)))
    sin = out(_call(ed, FN_DEG_SIN, A=angle))
    sun_elev = _mul(ed, sin, cfg.SUN_MAX_ELEVATION_DEG)
    day = _map(ed, sun_elev, cfg.NIGHT_BELOW_DEG, cfg.DAY_ABOVE_DEG, 0.0, 1.0)
    _set_var(ed, chain, "DayAmount", day)
    return angle, sin, sun_elev


def _author_bodies(ed, chain, angle, sin):
    """Point the sun and the moon, and light each by how far up it is."""
    for name, pitch_scale, yaw_offset in (
                                          ("Sun", -cfg.SUN_MAX_ELEVATION_DEG, cfg.SUNRISE_YAW_DEG),
                                          ("Moon", cfg.MOON_MAX_ELEVATION_DEG, cfg.SUNRISE_YAW_DEG - 180.0)):
        rot = _call(ed, FN_MAKE_ROT, Roll=0.0,
                    Pitch=_mul(ed, sin, pitch_scale),
                    Yaw=out(_call(ed, FN_ADD_FF, A=angle,
                                   B=float(yaw_offset))))
        chain.step(_call(ed, FN_SET_WORLD_ROT, self=_get(ed, name), NewRotation=out(rot)))

    day = _get(ed, "DayAmount")
    chain.step(_call(ed, FN_LIGHT_INTENSITY,
                     self=_get(ed, "Sun"),
                     NewIntensity=_scaled(ed, _mul(ed, day, cfg.SUN_LUX),
                                          SUN_SCALE_VAR)))
    moon_elev = _mul(ed, sin, -cfg.MOON_MAX_ELEVATION_DEG)
    moon_up = _map(ed, moon_elev, 0.0, cfg.MOON_FADE_DEG, 0.0, 1.0)
    night = _map(ed, day, 0.0, 1.0, 1.0, 0.0)
    moon_amount = out(_call(ed, FN_MUL_FF, A=moon_up, B=night))
    chain.step(_call(ed, FN_LIGHT_INTENSITY,
                     self=_get(ed, "Moon"),
                     NewIntensity=_scaled(
                         ed, _mul(ed, moon_amount, cfg.MOON_LUX),
                         MOON_SCALE_VAR)))


def _author_air(ed, chain):
    """Ambient, fog and exposure: each goes night value -> day value by DayAmount."""
    day = _get(ed, "DayAmount")
    night_sky, day_sky = cfg.SKY_LIGHT_INTENSITY
    chain.step(_call(ed, FN_SKY_INTENSITY,
                     self=_get(ed, "SkyLight"),
                     NewIntensity=_scaled(
                         ed, _map(ed, day, 0, 1, night_sky, day_sky),
                         AMBIENT_SCALE_VAR)))
    night_fog, day_fog = cfg.FOG_DENSITY
    fog = _get(ed, "Fog")
    chain.step(_call(ed, FN_FOG_DENSITY, self=fog,
                     Value=_scaled(
                         ed, _map(ed, day, 0, 1, night_fog, day_fog),
                         FOG_SCALE_VAR)))
    tint = _call(ed, FN_COLOR_LERP,
                 A=_color(ed, cfg.FOG_COLOR[0]),
                 B=_color(ed, cfg.FOG_COLOR[1]), Alpha=day)
    chain.step(_call(ed, FN_FOG_COLOR, self=fog, Value=out(tint)))

    weight = chain.step(ed.add_set_member_variable_node("BlendWeight", PP_CLASS_PATH))
    _connect(_get(ed, "DayGrade"), _pin(weight, "self"))
    _connect(day, _pin(weight, "BlendWeight"))


def _author_sky(ed, chain, sun_elev):
    """Feed the dome: how much day, how many stars, where the sun and moon are."""
    mid = _get(ed, SKY_MID_VAR)
    chain.step(_call(ed, FN_MID_SCALAR, self=mid, ParameterName="DayAmount",
                     Value=_get(ed, "DayAmount")))
    stars = _map(ed, sun_elev, 0.0, cfg.STARS_FULL_BELOW_DEG, 0.0, 1.0)
    chain.step(_call(ed, FN_MID_SCALAR, self=mid,
                     ParameterName="StarBrightness",
                     Value=_scaled(ed, _mul(ed, stars, cfg.STAR_BRIGHTNESS),
                                   STAR_SCALE_VAR)))
    for param, var in (("SunDiscBrightness", SUN_DISC_SCALE_VAR),
                       ("MoonDiscBrightness", MOON_DISC_SCALE_VAR)):
        chain.step(_call(ed, FN_MID_SCALAR, self=mid, ParameterName=param, Value=_get(ed, var)))
    for body in ("Sun", "Moon"):
        fwd = _call(ed, FN_FORWARD_OF, self=_get(ed, body))
        toward = _call(ed, FN_NEGATE_V, A=out(fwd))
        color = _call(ed, FN_VEC_TO_COLOR, InVec=out(toward))
        chain.step(_call(ed, FN_MID_VECTOR, self=mid,
                         ParameterName=f"{body}Direction", Value=out(color)))


def build_graph(bp, ed):
    """Wipe the EventGraph and author BeginPlay and Tick. Returns (tick, the
    Tick's chain), for night_cold to extend."""
    tick, begin = _events(ed, rebuild=True)
    _author_begin_play(ed, begin)
    chain = _Chain(then(tick))
    angle, sin, sun_elev = _author_clock(ed, tick, chain)
    _author_bodies(ed, chain, angle, sin)
    _author_air(ed, chain)
    _author_sky(ed, chain, sun_elev)
    _log(f"{bp.get_name()}: BeginPlay takes over the sky, Tick runs the clock")
    return tick, chain
