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

from combat.graph import (
    BEL, _at, _connect, _events, _log, _loose_pin, _node, _pin, _set,
)
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
        self.then = BEL.find_then_pin(node)
        return node


def _out(node, name="ReturnValue"):
    return _pin(node, name, is_input=False)


def _call(ed, fn, x, y, **inputs):
    """A call node with each input either wired (a pin) or set (a literal)."""
    n = _at(_node(ed, fn), x, y)
    for name, value in inputs.items():
        if hasattr(value, "try_create_connection"):
            _connect(value, _pin(n, name))
        else:
            _set(n, name, value)
    return n


def _get(ed, name, x, y):
    return _out(_at(ed.add_get_member_variable_node(name), x, y), name)


def _mul(ed, a, b, x, y):
    return _out(_call(ed, FN_MUL_FF, x, y, A=a, B=float(b)))


def _scaled(ed, value, scale_var, x, y):
    """value x one of the look multipliers (a variable, so it sits on B)."""
    return _out(_call(ed, FN_MUL_FF, x, y, A=value, B=_get(ed, scale_var, x - 200, y + 80)))


def _map(ed, value, in_a, in_b, out_a, out_b, x, y):
    return _out(_call(ed, FN_MAP_CLAMPED, x, y, Value=value,
                      InRangeA=float(in_a), InRangeB=float(in_b),
                      OutRangeA=float(out_a), OutRangeB=float(out_b)))


def _color(ed, rgba, x, y):
    c = list(rgba) + [1.0] * (4 - len(rgba))
    return _out(_call(ed, FN_MAKE_COLOR, x, y, R=float(c[0]), G=float(c[1]),
                      B=float(c[2]), A=float(c[3])))


def _set_var(ed, chain, name, value_pin, x, y):
    n = chain.step(_at(ed.add_set_member_variable_node(name), x, y))
    _connect(value_pin, _pin(n, name))
    return n


def _author_begin_play(ed, begin):
    """Destroy the level's tagged sky rig, make the dome's dynamic material,
    then (RandomStart) pick the starting clock."""
    chain = _Chain(BEL.find_then_pin(begin))
    found = chain.step(_call(ed, FN_ACTORS_WITH_TAG, 300, -900, Tag=STATIC_SKY_TAG))
    loop = _at(ed.add_macro_node(MACRO_FOR_EACH), 600, -900)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    _connect(chain.then, _loose_pin(loop, "Exec"))
    _connect(_out(found, "OutActors"), _loose_pin(loop, "Array"))
    kill = _at(_node(ed, FN_DESTROY), 900, -1000)
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(kill, "execute"))
    _connect(_loose_pin(loop, "ArrayElement", is_input=False), _pin(kill, "self"))

    chain = _Chain(_loose_pin(loop, "Completed", is_input=False))
    mid = chain.step(_call(ed, FN_CREATE_MID, 900, -800,
                           self=_get(ed, "SkyDome", 650, -700), ElementIndex=0))
    _set_var(ed, chain, SKY_MID_VAR, _out(mid), 1250, -800)

    pick = chain.step(_at(ed.add_branch_node(), 1550, -800))
    _connect(_get(ed, RANDOM_START_VAR, 1350, -650), _pin(pick, "Condition"))
    total = _out(_call(ed, FN_ADD_FF, 1600, -550,
                       A=_get(ed, "DayLengthSeconds", 1350, -550),
                       B=_get(ed, "NightLengthSeconds", 1350, -450)))
    anywhere = _call(ed, FN_RANDOM_FLOAT, 1850, -550, Min=0.0, Max=total)
    _set_var(ed, chain, "Clock", _out(anywhere), 2100, -800)


def _author_clock(ed, tick, chain):
    """Advance Clock, set IsDay; return (clock, day_len, sin(angle), sun_elev) pins."""
    day_len = _get(ed, "DayLengthSeconds", 200, 300)
    total = _out(_call(ed, FN_ADD_FF, 450, 350, A=day_len,
                       B=_get(ed, "NightLengthSeconds", 200, 400)))
    ahead = _out(_call(ed, FN_ADD_FF, 450, 200, A=_get(ed, "Clock", 200, 200),
                       B=_out(tick, "DeltaSeconds")))
    wrapped = _out(_call(ed, FN_PERCENT_FF, 700, 200, A=ahead, B=total))
    _set_var(ed, chain, "Clock", wrapped, 950, 0)

    clock = _get(ed, "Clock", 1200, 300)
    is_day = _out(_call(ed, FN_LESS_FF, 1450, 200, A=clock, B=day_len))
    _set_var(ed, chain, IS_DAY_VAR, is_day, 1650, 0)

    # angle = map(clock, 0..day -> 0..180) + map(clock, day..total -> 0..180)
    first = _call(ed, FN_MAP_CLAMPED, 1450, 400, Value=clock, InRangeA=0.0,
                  InRangeB=day_len, OutRangeA=0.0, OutRangeB=180.0)
    second = _call(ed, FN_MAP_CLAMPED, 1450, 650, Value=clock, InRangeA=day_len,
                   InRangeB=total, OutRangeA=0.0, OutRangeB=180.0)
    angle = _out(_call(ed, FN_ADD_FF, 1700, 500, A=_out(first), B=_out(second)))
    sin = _out(_call(ed, FN_DEG_SIN, 1900, 500, A=angle))
    sun_elev = _mul(ed, sin, cfg.SUN_MAX_ELEVATION_DEG, 2100, 600)
    day = _map(ed, sun_elev, cfg.NIGHT_BELOW_DEG, cfg.DAY_ABOVE_DEG, 0.0, 1.0, 2300, 600)
    _set_var(ed, chain, "DayAmount", day, 2500, 0)
    return angle, sin, sun_elev


def _author_bodies(ed, chain, angle, sin):
    """Point the sun and the moon, and light each by how far up it is."""
    x0 = 2800
    for name, pitch_scale, yaw_offset, y in (
            ("Sun", -cfg.SUN_MAX_ELEVATION_DEG, cfg.SUNRISE_YAW_DEG, 300),
            ("Moon", cfg.MOON_MAX_ELEVATION_DEG, cfg.SUNRISE_YAW_DEG - 180.0, 600)):
        rot = _call(ed, FN_MAKE_ROT, x0 + 250, y, Roll=0.0,
                    Pitch=_mul(ed, sin, pitch_scale, x0, y),
                    Yaw=_out(_call(ed, FN_ADD_FF, x0, y + 120, A=angle,
                                   B=float(yaw_offset))))
        chain.step(_call(ed, FN_SET_WORLD_ROT, x0 + 500, 0,
                         self=_get(ed, name, x0 + 300, y - 100),
                         NewRotation=_out(rot)))
        x0 += 500

    day = _get(ed, "DayAmount", x0, 400)
    chain.step(_call(ed, FN_LIGHT_INTENSITY, x0 + 400, 0,
                     self=_get(ed, "Sun", x0 + 200, 250),
                     NewIntensity=_scaled(ed, _mul(ed, day, cfg.SUN_LUX, x0 + 200, 400),
                                          SUN_SCALE_VAR, x0 + 300, 1000)))
    moon_elev = _mul(ed, sin, -cfg.MOON_MAX_ELEVATION_DEG, x0 + 400, 600)
    moon_up = _map(ed, moon_elev, 0.0, cfg.MOON_FADE_DEG, 0.0, 1.0, x0 + 600, 600)
    night = _map(ed, day, 0.0, 1.0, 1.0, 0.0, x0 + 600, 800)
    moon_amount = _out(_call(ed, FN_MUL_FF, x0 + 850, 700, A=moon_up, B=night))
    chain.step(_call(ed, FN_LIGHT_INTENSITY, x0 + 1100, 0,
                     self=_get(ed, "Moon", x0 + 900, 250),
                     NewIntensity=_scaled(
                         ed, _mul(ed, moon_amount, cfg.MOON_LUX, x0 + 1050, 700),
                         MOON_SCALE_VAR, x0 + 1150, 1000)))
    return x0 + 1400


def _author_air(ed, chain, x0):
    """Ambient, fog and exposure: each goes night value -> day value by DayAmount."""
    day = _get(ed, "DayAmount", x0, 400)
    night_sky, day_sky = cfg.SKY_LIGHT_INTENSITY
    chain.step(_call(ed, FN_SKY_INTENSITY, x0 + 400, 0,
                     self=_get(ed, "SkyLight", x0 + 200, 250),
                     NewIntensity=_scaled(
                         ed, _map(ed, day, 0, 1, night_sky, day_sky, x0 + 200, 400),
                         AMBIENT_SCALE_VAR, x0 + 300, 1000)))
    night_fog, day_fog = cfg.FOG_DENSITY
    fog = _get(ed, "Fog", x0 + 500, 250)
    chain.step(_call(ed, FN_FOG_DENSITY, x0 + 800, 0, self=fog,
                     Value=_scaled(
                         ed, _map(ed, day, 0, 1, night_fog, day_fog, x0 + 600, 400),
                         FOG_SCALE_VAR, x0 + 700, 1000)))
    tint = _call(ed, FN_COLOR_LERP, x0 + 1000, 500,
                 A=_color(ed, cfg.FOG_COLOR[0], x0 + 800, 550),
                 B=_color(ed, cfg.FOG_COLOR[1], x0 + 800, 700), Alpha=day)
    chain.step(_call(ed, FN_FOG_COLOR, x0 + 1200, 0, self=fog, Value=_out(tint)))

    weight = chain.step(_at(ed.add_set_member_variable_node("BlendWeight", PP_CLASS_PATH),
                            x0 + 1500, 0))
    _connect(_get(ed, "DayGrade", x0 + 1300, 250), _pin(weight, "self"))
    _connect(day, _pin(weight, "BlendWeight"))
    return x0 + 1800


def _author_sky(ed, chain, x0, sun_elev):
    """Feed the dome: how much day, how many stars, where the sun and moon are."""
    mid = _get(ed, SKY_MID_VAR, x0, 250)
    chain.step(_call(ed, FN_MID_SCALAR, x0 + 300, 0, self=mid, ParameterName="DayAmount",
                     Value=_get(ed, "DayAmount", x0, 400)))
    stars = _map(ed, sun_elev, 0.0, cfg.STARS_FULL_BELOW_DEG, 0.0, 1.0, x0 + 300, 500)
    chain.step(_call(ed, FN_MID_SCALAR, x0 + 600, 0, self=mid,
                     ParameterName="StarBrightness",
                     Value=_scaled(ed, _mul(ed, stars, cfg.STAR_BRIGHTNESS, x0 + 500, 500),
                                   STAR_SCALE_VAR, x0 + 600, 1000)))
    for i, (param, var) in enumerate((("SunDiscBrightness", SUN_DISC_SCALE_VAR),
                                      ("MoonDiscBrightness", MOON_DISC_SCALE_VAR))):
        chain.step(_call(ed, FN_MID_SCALAR, x0 + 900 + i * 300, 0, self=mid,
                         ParameterName=param,
                         Value=_get(ed, var, x0 + 700 + i * 300, 700)))
    x = x0 + 1500
    for body in ("Sun", "Moon"):
        fwd = _call(ed, FN_FORWARD_OF, x - 200, 400, self=_get(ed, body, x - 400, 400))
        toward = _call(ed, FN_NEGATE_V, x - 50, 450, A=_out(fwd))
        color = _call(ed, FN_VEC_TO_COLOR, x + 100, 500, InVec=_out(toward))
        chain.step(_call(ed, FN_MID_VECTOR, x + 300, 0, self=mid,
                         ParameterName=f"{body}Direction", Value=_out(color)))
        x += 700


def build_graph(bp, ed):
    """Wipe the EventGraph and author BeginPlay and Tick. Returns (tick, the
    Tick's chain, the x past its last node), for night_cold to extend."""
    tick, begin = _events(ed, rebuild=True)
    _author_begin_play(ed, begin)
    chain = _Chain(BEL.find_then_pin(tick))
    angle, sin, sun_elev = _author_clock(ed, tick, chain)
    x = _author_bodies(ed, chain, angle, sin)
    x = _author_air(ed, chain, x)
    _author_sky(ed, chain, x, sun_elev)
    _log(f"{bp.get_name()}: BeginPlay takes over the sky, Tick runs the clock")
    return tick, chain, x + 3400
