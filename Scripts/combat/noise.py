"""Making a noise the wanderers can hear: the one fragment every noise-maker
calls to write the GameMode's noise record.

WHY ONE RECORD ON THE GAMEMODE
------------------------------
The emitters (BP_WeaponComponent's shot, BP_FootstepComponent's step) and the
listeners (every wanderer's AI controller) are built by different builders and
share no reference to each other. The GameMode is already the project's
world-scoped wiring point (spawn and kill counters, PlayerDead, DebugMode), so
a noise is written there and each patrolling wanderer reads it on its own
heartbeat (Scripts/npc/senses.py). No event dispatch, no list of listeners, and
a respawned wanderer hears the next noise with nothing registering it.

The cost of one record is that a new noise replaces the old one, so the write
is guarded: it lands only if the current record is STALE (older than
COMBAT.noise_hold_s) or the new noise is at least as LOUD. A footstep a
fraction of a second after a gunshot therefore cannot erase the gunshot before
the pack has checked for it -- noise_hold_s outlasts one NPC heartbeat, which
the verifier asserts. Loudness is the larger of the two reaches, all-round and
cone.

What the record holds is the noise's own reach, because how far a noise
carries belongs to what made it (a pistol, a sprint). The listener only scales
it (AgroSettings.hearing_scale in forest_generator/npc_agro.py).
"""

from combat.game_state import (
    NOISE_CONE_COS_VAR, NOISE_CONE_RANGE_VAR, NOISE_DIRECTION_VAR,
    NOISE_LOCATION_VAR, NOISE_RANGE_VAR, NOISE_TIME_VAR,
)
from combat.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set
from combat.nodes import (
    FN_GET_GAME_MODE, FN_GE_FF, FN_MAX_FF, FN_OR, FN_SUB_FF, FN_TIME_SECONDS,
    NODE_CAST_GAME_MODE,
)
from combat.paths import GAME_MODE_CLASS_PATH
from combat.tuning import COMBAT


def _author_make_noise(ed, exec_in, location, reach, x0, y0,
                       direction=None, cone_reach=None, cone_cos=1.0):
    """Write a noise into the GameMode's record, if it is allowed to replace
    the one already there. Returns ``(nodes, then_pin)``.

        exec_in -> GetGameMode -> cast
                -> [record stale  OR  this noise at least as loud?]
                     yes -> NoiseTime = now, NoiseLocation, NoiseRange,
                            NoiseDirection, NoiseConeRange, NoiseConeCos
                -> then (every path, the failed cast included)

    ``location``, ``reach`` and the optional ``direction``/``cone_reach`` are
    data pins; ``cone_cos`` is a literal. An all-round noise leaves
    ``cone_reach`` None, which writes a cone reach of 0 -- nothing is ever
    inside a cone that reaches nowhere -- and leaves the direction unwritten.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    mode = keep(_at(_node(ed, FN_GET_GAME_MODE), x0, y0 + 300))
    as_mode = keep(_at(_palette(ed, NODE_CAST_GAME_MODE), x0 + 240, y0))
    _connect(_pin(mode, "ReturnValue", is_input=False), _pin(as_mode, "Object"))
    _connect(exec_in, _pin(as_mode, "execute"))
    mode_out = _loose_pin(as_mode, "AsBPThirdPersonGameMode", is_input=False)

    def read(name, x, y):
        n = keep(_at(ed.add_get_member_variable_node(name, GAME_MODE_CLASS_PATH), x, y))
        _connect(mode_out, _pin(n, "self"))
        return _pin(n, name, is_input=False)

    # --- is the record stale? ------------------------------------------------
    now = keep(_at(_node(ed, FN_TIME_SECONDS), x0 + 240, y0 + 440))
    now_out = _pin(now, "ReturnValue", is_input=False)
    age = keep(_at(_node(ed, FN_SUB_FF), x0 + 480, y0 + 440))
    _connect(now_out, _pin(age, "A"))
    _connect(read(NOISE_TIME_VAR, x0 + 240, y0 + 560), _pin(age, "B"))
    stale = keep(_at(_node(ed, FN_GE_FF), x0 + 720, y0 + 440))
    _connect(_pin(age, "ReturnValue", is_input=False), _pin(stale, "A"))
    _set(stale, "B", COMBAT.noise_hold_s)

    # --- ...or is this one at least as loud? ---------------------------------
    if cone_reach is not None:
        mine = keep(_at(_node(ed, FN_MAX_FF), x0 + 480, y0 + 700))
        _connect(reach, _pin(mine, "A"))
        _connect(cone_reach, _pin(mine, "B"))
        loudness = _pin(mine, "ReturnValue", is_input=False)
    else:
        loudness = reach
    theirs = keep(_at(_node(ed, FN_MAX_FF), x0 + 480, y0 + 840))
    _connect(read(NOISE_RANGE_VAR, x0 + 240, y0 + 840), _pin(theirs, "A"))
    _connect(read(NOISE_CONE_RANGE_VAR, x0 + 240, y0 + 960), _pin(theirs, "B"))
    louder = keep(_at(_node(ed, FN_GE_FF), x0 + 720, y0 + 760))
    _connect(loudness, _pin(louder, "A"))
    _connect(_pin(theirs, "ReturnValue", is_input=False), _pin(louder, "B"))

    either = keep(_at(_node(ed, FN_OR), x0 + 960, y0 + 600))
    _connect(_pin(stale, "ReturnValue", is_input=False), _pin(either, "A"))
    _connect(_pin(louder, "ReturnValue", is_input=False), _pin(either, "B"))
    lands = keep(_at(ed.add_branch_node(), x0 + 1200, y0))
    _connect(_pin(either, "ReturnValue", is_input=False), _pin(lands, "Condition"))
    _connect(BEL.find_then_pin(as_mode), _pin(lands, "execute"))

    # --- write it ------------------------------------------------------------
    tail = BEL.find_then_pin(lands)
    x = x0 + 1460

    def write(name, value_pin=None, literal=None):
        nonlocal tail, x
        n = keep(_at(ed.add_set_member_variable_node(name, GAME_MODE_CLASS_PATH), x, y0))
        _connect(mode_out, _pin(n, "self"))
        if value_pin is not None:
            _connect(value_pin, _pin(n, name))
        else:
            _set(n, name, literal)
        _connect(tail, _pin(n, "execute"))
        tail = BEL.find_then_pin(n)
        x += 260

    write(NOISE_TIME_VAR, now_out)
    write(NOISE_LOCATION_VAR, location)
    write(NOISE_RANGE_VAR, reach)
    if cone_reach is not None:
        write(NOISE_DIRECTION_VAR, direction)
        write(NOISE_CONE_RANGE_VAR, cone_reach)
    else:
        write(NOISE_CONE_RANGE_VAR, literal=0.0)
    write(NOISE_CONE_COS_VAR, literal=cone_cos)

    # One exec out whether or not the record was replaced, and whether or not
    # the GameMode was the one this project builds.
    out = keep(_at(ed.add_branch_node(), x, y0))
    _set(out, "Condition", "true")
    for pin in (tail, BEL.find_else_pin(lands),
                _pin(as_mode, "CastFailed", is_input=False)):
        _connect(pin, _pin(out, "execute"))
    return made, BEL.find_then_pin(out)
