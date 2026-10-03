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
from uebp.graph import _connect, _loose_pin, _node, _palette, _pin, _set, else_, out, then
from npc.paths import HEALTH_CLASS_PATH
from npc.tuned import tuned
from uebp.nodes.actor import (
    FN_ACTOR_FORWARD, FN_ACTOR_LOC, FN_GET_COMP, FN_GET_PAWN, FN_LINE_OF_SIGHT)
from uebp.nodes.math import (
    FN_AND, FN_DEG_COS, FN_DISTANCE, FN_DOT_VV, FN_GE_FF, FN_LE_FF, FN_MUL_FF, FN_NORMAL,
    FN_OR, FN_SUB_FF, FN_SUB_VV)
from uebp.nodes.palette import NODE_CAST_GAME_MODE, NODE_CAST_HEALTH
from uebp.nodes.system import FN_GET_GAME_MODE, FN_GET_PLAYER_PAWN, FN_TIME_SECONDS


class _Maker:
    """Collects the nodes a fragment makes, for its comment box."""

    def __init__(self, ed):
        self.ed, self.made = ed, []

    def __call__(self, node):
        self.made.append(node)
        return node

    def fn(self, path):
        return self(_node(self.ed, path))

    def tuned(self, column):
        """This creature's number for ``column`` (npc/tuned.py): its pin."""
        node, out = tuned(self.ed, column)
        self.made.append(node)
        return out

    def out(self, node, name="ReturnValue"):
        return out(node, name)


def _locations(k):
    """(pawn location, player pawn, player location) as pure nodes."""
    pawn = k.fn(FN_GET_PAWN)
    here = k.fn(FN_ACTOR_LOC)
    _connect(k.out(pawn), _pin(here, "self"))
    player = k.fn(FN_GET_PLAYER_PAWN)
    _set(player, "PlayerIndex", 0)
    there = k.fn(FN_ACTOR_LOC)
    _connect(k.out(player), _pin(there, "self"))
    return pawn, k.out(here), k.out(player), k.out(there)


def _branch(k, condition, exec_in):
    b = k(k.ed.add_branch_node())
    _connect(condition, _pin(b, "Condition"))
    for pin in exec_in:
        _connect(pin, _pin(b, "execute"))
    return b


def _author_hurt(ed, exec_in):
    """Has the player damaged this wanderer? BP_HealthComponent.DamagedByPlayer.

    The flag the kill count already trusts (see combat/game_state.py), so a
    wanderer the world-floor net wrote off does not count as shot. A sniper
    round from beyond hearing range still wakes what it hits.
    """
    k = _Maker(ed)
    pawn = k.fn(FN_GET_PAWN)
    comp = k.fn(FN_GET_COMP)
    _connect(k.out(pawn), _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)
    as_health = k(_palette(ed, NODE_CAST_HEALTH))
    _connect(k.out(comp), _pin(as_health, "Object"))
    for pin in exec_in:
        _connect(pin, _pin(as_health, "execute"))
    flag = k(ed.add_get_member_variable_node(DAMAGED_BY_PLAYER_VAR, HEALTH_CLASS_PATH))
    _connect(_loose_pin(as_health, "AsBPHealthComponent", is_input=False),
             _pin(flag, "self"))
    hurt = _branch(k, k.out(flag, DAMAGED_BY_PLAYER_VAR), [then(as_health)])
    return k.made, then(hurt), [else_(hurt), out(as_health, "CastFailed")]


def _author_sight(ed, exec_in):
    """Is the player inside the vision cone, and is nothing in the way?

        distance <= vision_range  AND  facing . toward_player >= cos(half)
        AND  LineOfSightTo(player)

    Facing is the pawn's forward vector, which during a patrol is the way it
    is walking. LineOfSightTo is the controller's own (its self pin is left to
    default to this controller) and traces from the pawn's eyes, so a trunk
    between the two hides the player.
    """
    k = _Maker(ed)
    pawn, here, player, there = _locations(k)

    gap = k.fn(FN_DISTANCE)
    _connect(here, _pin(gap, "V1"))
    _connect(there, _pin(gap, "V2"))
    near = k.fn(FN_LE_FF)
    _connect(k.out(gap), _pin(near, "A"))
    _connect(k.tuned("vision_range_cm"), _pin(near, "B"))

    toward = k.fn(FN_SUB_VV)
    _connect(there, _pin(toward, "A"))
    _connect(here, _pin(toward, "B"))
    unit = k.fn(FN_NORMAL)
    _connect(k.out(toward), _pin(unit, "A"))
    facing = k.fn(FN_ACTOR_FORWARD)
    _connect(k.out(pawn), _pin(facing, "self"))
    dot = k.fn(FN_DOT_VV)
    _connect(k.out(facing), _pin(dot, "A"))
    _connect(k.out(unit), _pin(dot, "B"))
    ahead = k.fn(FN_GE_FF)
    _connect(k.out(dot), _pin(ahead, "A"))
    cos = k.fn(FN_DEG_COS)
    _connect(k.tuned("vision_half_angle_deg"), _pin(cos, "A"))
    _connect(k.out(cos), _pin(ahead, "B"))

    clear = k.fn(FN_LINE_OF_SIGHT)
    _connect(player, _pin(clear, "Other"))

    in_cone = k.fn(FN_AND)
    _connect(k.out(near), _pin(in_cone, "A"))
    _connect(k.out(ahead), _pin(in_cone, "B"))
    seen = k.fn(FN_AND)
    _connect(k.out(in_cone), _pin(seen, "A"))
    _connect(k.out(clear), _pin(seen, "B"))
    sees = _branch(k, k.out(seen), exec_in)
    return k.made, then(sees), [else_(sees)]


def _author_touch(ed, exec_in):
    """Is the player within touch_range_cm, whichever way the wanderer faces?"""
    k = _Maker(ed)
    _pawn, here, _player, there = _locations(k)
    gap = k.fn(FN_DISTANCE)
    _connect(here, _pin(gap, "V1"))
    _connect(there, _pin(gap, "V2"))
    close = k.fn(FN_LE_FF)
    _connect(k.out(gap), _pin(close, "A"))
    _connect(k.tuned("touch_range_cm"), _pin(close, "B"))
    bumped = _branch(k, k.out(close), exec_in)
    return k.made, then(bumped), [else_(bumped)]


def _author_hearing(ed, exec_in):
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
    mode = k.fn(FN_GET_GAME_MODE)
    as_mode = k(_palette(ed, NODE_CAST_GAME_MODE))
    _connect(k.out(mode), _pin(as_mode, "Object"))
    for pin in exec_in:
        _connect(pin, _pin(as_mode, "execute"))
    mode_out = _loose_pin(as_mode, "AsBPThirdPersonGameMode", is_input=False)

    def read(name):
        n = k(ed.add_get_member_variable_node(name, GAME_MODE_CLASS_PATH))
        _connect(mode_out, _pin(n, "self"))
        return k.out(n, name)

    now = k.fn(FN_TIME_SECONDS)
    age = k.fn(FN_SUB_FF)
    _connect(k.out(now), _pin(age, "A"))
    _connect(read(NOISE_TIME_VAR), _pin(age, "B"))
    recent = k.fn(FN_LE_FF)
    _connect(k.out(age), _pin(recent, "A"))
    _set(recent, "B", COMBAT.noise_hold_s)

    pawn = k.fn(FN_GET_PAWN)
    here = k.fn(FN_ACTOR_LOC)
    _connect(k.out(pawn), _pin(here, "self"))
    source = read(NOISE_LOCATION_VAR)
    gap = k.fn(FN_DISTANCE)
    _connect(k.out(here), _pin(gap, "V1"))
    _connect(source, _pin(gap, "V2"))

    def within(reach_var):
        reach = k.fn(FN_MUL_FF)
        _connect(read(reach_var), _pin(reach, "A"))
        _connect(k.tuned("hearing_scale"), _pin(reach, "B"))
        inside = k.fn(FN_LE_FF)
        _connect(k.out(gap), _pin(inside, "A"))
        _connect(k.out(reach), _pin(inside, "B"))
        return k.out(inside)

    all_round = within(NOISE_RANGE_VAR)
    cone_reach = within(NOISE_CONE_RANGE_VAR)

    away = k.fn(FN_SUB_VV)
    _connect(k.out(here), _pin(away, "A"))
    _connect(source, _pin(away, "B"))
    unit = k.fn(FN_NORMAL)
    _connect(k.out(away), _pin(unit, "A"))
    dot = k.fn(FN_DOT_VV)
    _connect(read(NOISE_DIRECTION_VAR), _pin(dot, "A"))
    _connect(k.out(unit), _pin(dot, "B"))
    aimed = k.fn(FN_GE_FF)
    _connect(k.out(dot), _pin(aimed, "A"))
    _connect(read(NOISE_CONE_COS_VAR), _pin(aimed, "B"))
    in_cone = k.fn(FN_AND)
    _connect(cone_reach, _pin(in_cone, "A"))
    _connect(k.out(aimed), _pin(in_cone, "B"))

    reached = k.fn(FN_OR)
    _connect(all_round, _pin(reached, "A"))
    _connect(k.out(in_cone), _pin(reached, "B"))
    heard = k.fn(FN_AND)
    _connect(k.out(recent), _pin(heard, "A"))
    _connect(k.out(reached), _pin(heard, "B"))
    hears = _branch(k, k.out(heard), [then(as_mode)])
    return k.made, then(hears), [else_(hears), out(as_mode, "CastFailed")]
