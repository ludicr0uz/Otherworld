"""The four ways a patrolling wanderer notices the player: hurt, sight, touch
and sound. One fragment per sense, each an exec Branch with a yes and a no.

They are exec branches chained one after another (npc/agro.py) rather than one
big boolean, on purpose. Pure nodes are evaluated by whoever reads them and
BooleanAND does not short-circuit (see the possession gate in controller.py),
so a single OR of four senses would run the line-of-sight trace and the
GameMode cast on every heartbeat whether or not a cheaper sense had already
answered -- and could not say WHICH sense fired, which is the one thing the
log line is for.

Each fragment takes ``exec_in`` as a LIST of exec pins and returns
``(nodes, yes_pin, no_pins)``. ``no_pins`` is a list because a failed cast is
also a "no", and an exec input takes any number of links, so the next sense
simply takes them all.
"""

from combat.game_state import (
    DAMAGED_BY_PLAYER_VAR, NOISE_CONE_COS_VAR, NOISE_CONE_RANGE_VAR,
    NOISE_DIRECTION_VAR, NOISE_LOCATION_VAR, NOISE_RANGE_VAR, NOISE_TIME_VAR,
)
from combat.paths import GAME_MODE_CLASS_PATH
from combat.tuning import COMBAT
from npc.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set
from npc.nodes import (
    FN_ACTOR_LOC, FN_AND, FN_DISTANCE, FN_DOT_VV, FN_FORWARD, FN_GET_COMP,
    FN_GET_GAME_MODE, FN_GET_PAWN, FN_GET_PLAYER_PAWN, FN_GE_FF, FN_LE_FF,
    FN_LINE_OF_SIGHT, FN_MUL_FF, FN_NORMAL, FN_OR, FN_SUB_FF, FN_SUB_VV,
    FN_TIME_SECONDS, NODE_CAST_GAME_MODE, NODE_CAST_HEALTH, FN_DEG_COS,
)
from npc.paths import HEALTH_CLASS_PATH
from npc.tuned import tuned


class _Maker:
    """Collects the nodes a fragment makes, for its comment box."""

    def __init__(self, ed):
        self.ed, self.made = ed, []

    def __call__(self, node, x, y):
        self.made.append(_at(node, x, y))
        return node

    def fn(self, path, x, y):
        return self(_node(self.ed, path), x, y)

    def tuned(self, column, x, y):
        """This creature's number for ``column`` (npc/tuned.py): its pin."""
        node, out = tuned(self.ed, column, x, y)
        self.made.append(node)
        return out

    def out(self, node, name="ReturnValue"):
        return _pin(node, name, is_input=False)


def _locations(k, x0, y0):
    """(pawn location, player pawn, player location) as pure nodes."""
    pawn = k.fn(FN_GET_PAWN, x0, y0)
    here = k.fn(FN_ACTOR_LOC, x0 + 240, y0)
    _connect(k.out(pawn), _pin(here, "self"))
    player = k.fn(FN_GET_PLAYER_PAWN, x0, y0 + 140)
    _set(player, "PlayerIndex", 0)
    there = k.fn(FN_ACTOR_LOC, x0 + 240, y0 + 140)
    _connect(k.out(player), _pin(there, "self"))
    return pawn, k.out(here), k.out(player), k.out(there)


def _branch(k, condition, exec_in, x, y):
    b = k(k.ed.add_branch_node(), x, y)
    _connect(condition, _pin(b, "Condition"))
    for pin in exec_in:
        _connect(pin, _pin(b, "execute"))
    return b


def _author_hurt(ed, exec_in, x0, y0):
    """Has the player damaged this wanderer? BP_HealthComponent.DamagedByPlayer.

    The flag the kill count already trusts (see combat/game_state.py), so a
    wanderer the world-floor net wrote off does not count as shot. A sniper
    round from beyond hearing range still wakes what it hits.
    """
    k = _Maker(ed)
    pawn = k.fn(FN_GET_PAWN, x0, y0 + 300)
    comp = k.fn(FN_GET_COMP, x0 + 240, y0 + 300)
    _connect(k.out(pawn), _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)
    as_health = k(_palette(ed, NODE_CAST_HEALTH), x0 + 480, y0)
    _connect(k.out(comp), _pin(as_health, "Object"))
    for pin in exec_in:
        _connect(pin, _pin(as_health, "execute"))
    flag = k(ed.add_get_member_variable_node(DAMAGED_BY_PLAYER_VAR, HEALTH_CLASS_PATH),
             x0 + 720, y0 + 300)
    _connect(_loose_pin(as_health, "AsBPHealthComponent", is_input=False),
             _pin(flag, "self"))
    hurt = _branch(k, k.out(flag, DAMAGED_BY_PLAYER_VAR),
                   [BEL.find_then_pin(as_health)], x0 + 960, y0)
    return k.made, BEL.find_then_pin(hurt), [
        BEL.find_else_pin(hurt), _pin(as_health, "CastFailed", is_input=False)]


def _author_sight(ed, exec_in, x0, y0):
    """Is the player inside the vision cone, and is nothing in the way?

        distance <= vision_range  AND  facing . toward_player >= cos(half)
        AND  LineOfSightTo(player)

    Facing is the pawn's forward vector, which during a patrol is the way it
    is walking. LineOfSightTo is the controller's own (its self pin is left to
    default to this controller) and traces from the pawn's eyes, so a trunk
    between the two hides the player.
    """
    k = _Maker(ed)
    pawn, here, player, there = _locations(k, x0, y0 + 300)

    gap = k.fn(FN_DISTANCE, x0 + 480, y0 + 300)
    _connect(here, _pin(gap, "V1"))
    _connect(there, _pin(gap, "V2"))
    near = k.fn(FN_LE_FF, x0 + 720, y0 + 300)
    _connect(k.out(gap), _pin(near, "A"))
    _connect(k.tuned("vision_range_cm", x0 + 480, y0 + 200), _pin(near, "B"))

    toward = k.fn(FN_SUB_VV, x0 + 480, y0 + 460)
    _connect(there, _pin(toward, "A"))
    _connect(here, _pin(toward, "B"))
    unit = k.fn(FN_NORMAL, x0 + 720, y0 + 460)
    _connect(k.out(toward), _pin(unit, "A"))
    facing = k.fn(FN_FORWARD, x0 + 480, y0 + 600)
    _connect(k.out(pawn), _pin(facing, "self"))
    dot = k.fn(FN_DOT_VV, x0 + 960, y0 + 460)
    _connect(k.out(facing), _pin(dot, "A"))
    _connect(k.out(unit), _pin(dot, "B"))
    ahead = k.fn(FN_GE_FF, x0 + 1200, y0 + 460)
    _connect(k.out(dot), _pin(ahead, "A"))
    cos = k.fn(FN_DEG_COS, x0 + 960, y0 + 760)
    _connect(k.tuned("vision_half_angle_deg", x0 + 720, y0 + 760), _pin(cos, "A"))
    _connect(k.out(cos), _pin(ahead, "B"))

    clear = k.fn(FN_LINE_OF_SIGHT, x0 + 960, y0 + 620)
    _connect(player, _pin(clear, "Other"))

    in_cone = k.fn(FN_AND, x0 + 1440, y0 + 380)
    _connect(k.out(near), _pin(in_cone, "A"))
    _connect(k.out(ahead), _pin(in_cone, "B"))
    seen = k.fn(FN_AND, x0 + 1680, y0 + 380)
    _connect(k.out(in_cone), _pin(seen, "A"))
    _connect(k.out(clear), _pin(seen, "B"))
    sees = _branch(k, k.out(seen), exec_in, x0 + 1920, y0)
    return k.made, BEL.find_then_pin(sees), [BEL.find_else_pin(sees)]


def _author_touch(ed, exec_in, x0, y0):
    """Is the player within touch_range_cm, whichever way the wanderer faces?"""
    k = _Maker(ed)
    _pawn, here, _player, there = _locations(k, x0, y0 + 300)
    gap = k.fn(FN_DISTANCE, x0 + 480, y0 + 300)
    _connect(here, _pin(gap, "V1"))
    _connect(there, _pin(gap, "V2"))
    close = k.fn(FN_LE_FF, x0 + 720, y0 + 300)
    _connect(k.out(gap), _pin(close, "A"))
    _connect(k.tuned("touch_range_cm", x0 + 480, y0 + 440), _pin(close, "B"))
    bumped = _branch(k, k.out(close), exec_in, x0 + 960, y0)
    return k.made, BEL.find_then_pin(bumped), [BEL.find_else_pin(bumped)]


def _author_hearing(ed, exec_in, x0, y0):
    """Is this wanderer inside the reach of the latest noise?

        recent  = now - NoiseTime <= COMBAT.noise_hold_s
        d       = |pawn - NoiseLocation|
        round   = d <= NoiseRange * hearing_scale
        cone    = d <= NoiseConeRange * hearing_scale
                  AND NoiseDirection . unit(pawn - NoiseLocation) >= NoiseConeCos
        heard   = recent AND (round OR cone)

    The reach is the noise's (combat/noise.py); hearing_scale is the only
    thing the listener brings. "Recent" matters: without it a wanderer that
    strolls into range of a shot fired a minute ago would hear it now.
    """
    k = _Maker(ed)
    mode = k.fn(FN_GET_GAME_MODE, x0, y0 + 300)
    as_mode = k(_palette(ed, NODE_CAST_GAME_MODE), x0 + 240, y0)
    _connect(k.out(mode), _pin(as_mode, "Object"))
    for pin in exec_in:
        _connect(pin, _pin(as_mode, "execute"))
    mode_out = _loose_pin(as_mode, "AsBPThirdPersonGameMode", is_input=False)

    def read(name, x, y):
        n = k(ed.add_get_member_variable_node(name, GAME_MODE_CLASS_PATH), x, y)
        _connect(mode_out, _pin(n, "self"))
        return k.out(n, name)

    now = k.fn(FN_TIME_SECONDS, x0 + 480, y0 + 300)
    age = k.fn(FN_SUB_FF, x0 + 720, y0 + 300)
    _connect(k.out(now), _pin(age, "A"))
    _connect(read(NOISE_TIME_VAR, x0 + 480, y0 + 420), _pin(age, "B"))
    recent = k.fn(FN_LE_FF, x0 + 960, y0 + 300)
    _connect(k.out(age), _pin(recent, "A"))
    _set(recent, "B", COMBAT.noise_hold_s)

    pawn = k.fn(FN_GET_PAWN, x0 + 480, y0 + 560)
    here = k.fn(FN_ACTOR_LOC, x0 + 720, y0 + 560)
    _connect(k.out(pawn), _pin(here, "self"))
    source = read(NOISE_LOCATION_VAR, x0 + 720, y0 + 680)
    gap = k.fn(FN_DISTANCE, x0 + 960, y0 + 560)
    _connect(k.out(here), _pin(gap, "V1"))
    _connect(source, _pin(gap, "V2"))

    def within(reach_var, x, y):
        reach = k.fn(FN_MUL_FF, x, y)
        _connect(read(reach_var, x - 240, y), _pin(reach, "A"))
        _connect(k.tuned("hearing_scale", x - 240, y + 120), _pin(reach, "B"))
        inside = k.fn(FN_LE_FF, x + 240, y)
        _connect(k.out(gap), _pin(inside, "A"))
        _connect(k.out(reach), _pin(inside, "B"))
        return k.out(inside)

    all_round = within(NOISE_RANGE_VAR, x0 + 1200, y0 + 560)
    cone_reach = within(NOISE_CONE_RANGE_VAR, x0 + 1200, y0 + 700)

    away = k.fn(FN_SUB_VV, x0 + 960, y0 + 840)
    _connect(k.out(here), _pin(away, "A"))
    _connect(source, _pin(away, "B"))
    unit = k.fn(FN_NORMAL, x0 + 1200, y0 + 840)
    _connect(k.out(away), _pin(unit, "A"))
    dot = k.fn(FN_DOT_VV, x0 + 1440, y0 + 840)
    _connect(read(NOISE_DIRECTION_VAR, x0 + 1200, y0 + 960), _pin(dot, "A"))
    _connect(k.out(unit), _pin(dot, "B"))
    aimed = k.fn(FN_GE_FF, x0 + 1680, y0 + 840)
    _connect(k.out(dot), _pin(aimed, "A"))
    _connect(read(NOISE_CONE_COS_VAR, x0 + 1440, y0 + 960), _pin(aimed, "B"))
    in_cone = k.fn(FN_AND, x0 + 1920, y0 + 700)
    _connect(cone_reach, _pin(in_cone, "A"))
    _connect(k.out(aimed), _pin(in_cone, "B"))

    reached = k.fn(FN_OR, x0 + 2160, y0 + 560)
    _connect(all_round, _pin(reached, "A"))
    _connect(k.out(in_cone), _pin(reached, "B"))
    heard = k.fn(FN_AND, x0 + 2400, y0 + 300)
    _connect(k.out(recent), _pin(heard, "A"))
    _connect(k.out(reached), _pin(heard, "B"))
    hears = _branch(k, k.out(heard), [BEL.find_then_pin(as_mode)], x0 + 2640, y0)
    return k.made, BEL.find_then_pin(hears), [
        BEL.find_else_pin(hears), _pin(as_mode, "CastFailed", is_input=False)]
