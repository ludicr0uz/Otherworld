"""Down the sights the player can hold their breath, which all but stills the
sway; and the sway's rate is the held gun's.

    if IsValid(Held): SwayRate = Held.SwayRate
    BreathHeld  = (IsInputKeyDown(KeyHoldBreath) OR BreathForced)
                  AND SightAiming AND NOT Winded
    Breath      = Clamp(Breath + dt x (BreathHeld ? -1 : HOLD_S / RECOVER_S),
                        0, BREATH_HOLD_S)
    Winded      = Breath <= 0 OR (Winded AND Breath < BREATH_HOLD_S)
    BreathScale = FInterpTo(BreathScale,
                            BreathHeld ? BREATH_SWAY_SCALE
                            : Winded ? BREATH_WINDED_SCALE : 1, dt, EASE)

sway.py multiplies the sway's width by BreathScale and advances its clock by
dt x SwayRate. Run before it, after the aim state (SightAiming) is written.

Why Winded and not just "Breath > 0": with the breath at 0 the hold would
let go, a frame's refill would let it take hold again, and the sway would
flicker between steady and not while the key was held. Run out, the player
has to get the whole breath back first, and meanwhile shakes harder.

Why SwayRate is copied rather than read where the clock is: Held.SwayRate
off a null Held is an Accessed None a frame, so it is read only behind the
IsValid Branch, and the sway reads the component's copy (the last gun's
rate with empty hands, where SightBlend is 0 and the sway nothing anyway).

Each value is stored before the next one reads it: the pure nodes behind a
Set would otherwise be pulled again, after the Set, and read the new value.
BreathForced is the probes' stand-in for the key (no key can be injected
into a headless game); false in every real game.
"""

from combat.breath_tuning import (
    BREATH_EASE_SPEED, BREATH_FORCED_VAR, BREATH_HELD_VAR, BREATH_HOLD_S,
    BREATH_RECOVER_S, BREATH_SCALE_VAR, BREATH_SWAY_SCALE, BREATH_VAR,
    BREATH_WINDED_SCALE, WINDED_VAR,
)
from combat.graph import BEL, _at, _connect, _node, _pin, _set
from combat.nodes import (
    FN_ADD_FF, FN_AND, FN_CLAMP, FN_INTERP_FF, FN_IS_KEY_DOWN, FN_LE_FF,
    FN_LESS_FF, FN_NOT_B, FN_OR,
)
from combat.sway_tuning import SWAY_RATE_VAR
from combat.weapon_component.accuracy import _mul, _select
from combat.weapon_component.common import _prop


def _author_hold_breath(ed, tick, pc_out, held, armed_out, key_pin, exec_ins,
                        x0, y0):
    """Copy Held's sway rate, then hold or let go of the breath and ease the
    sway's scale. Returns the exec pin to carry on from."""
    made = []

    def keep(n):
        made.append(n)
        return n

    def out(n, name="ReturnValue"):
        return _pin(n, name, is_input=False)

    def get(var, x, y):
        return out(keep(_at(ed.add_get_member_variable_node(var), x, y)), var)

    def call(fn, x, y, **ins):
        n = keep(_at(_node(ed, fn), x, y))
        for name, v in ins.items():
            if isinstance(v, (int, float)):
                _set(n, name, v)
            else:
                _connect(v, _pin(n, name))
        return n

    def store(var, value, flow, x):
        n = keep(_at(ed.add_set_member_variable_node(var), x, y0))
        _connect(value, _pin(n, var))
        for e in flow:
            _connect(e, _pin(n, "execute"))
        return [BEL.find_then_pin(n)]

    dt = out(tick, "DeltaSeconds")

    # The gun's rate, behind the Branch that knows Held is there.
    armed = keep(_at(ed.add_branch_node(), x0, y0))
    _connect(armed_out, _pin(armed, "Condition"))
    for e in exec_ins:
        _connect(e, _pin(armed, "execute"))
    rate, rate_n = _prop(ed, SWAY_RATE_VAR, held, x0, y0 + 300)
    keep(rate_n)
    flow = store(SWAY_RATE_VAR, rate, [BEL.find_then_pin(armed)], x0 + 300)
    flow.append(BEL.find_else_pin(armed))

    # Held: the key (or its stand-in), down the sights, not winded.
    down = call(FN_IS_KEY_DOWN, x0 + 600, y0 + 300, self=pc_out, Key=key_pin)
    key = call(FN_OR, x0 + 860, y0 + 300, A=out(down),
               B=get(BREATH_FORCED_VAR, x0 + 600, y0 + 440))
    calm = call(FN_NOT_B, x0 + 860, y0 + 560, A=get(WINDED_VAR, x0 + 600, y0 + 560))
    sighted = call(FN_AND, x0 + 1120, y0 + 440, A=get("SightAiming", x0 + 860, y0 + 440),
                   B=out(calm))
    holding = call(FN_AND, x0 + 1380, y0 + 300, A=out(key), B=out(sighted))
    flow = store(BREATH_HELD_VAR, out(holding), flow, x0 + 1640)

    # The breath drains while held and refills while not.
    is_held = get(BREATH_HELD_VAR, x0 + 1900, y0 + 440)
    per_s = _select(ed, keep, -1.0, BREATH_HOLD_S / BREATH_RECOVER_S, is_held,
                    x0 + 2160, y0 + 440)
    step = _mul(ed, keep, per_s, dt, x0 + 2420, y0 + 440)
    more = call(FN_ADD_FF, x0 + 2680, y0 + 300, A=get(BREATH_VAR, x0 + 2420, y0 + 300),
                B=step)
    kept = call(FN_CLAMP, x0 + 2940, y0 + 300, Value=out(more), Min=0.0,
                Max=BREATH_HOLD_S)
    flow = store(BREATH_VAR, out(kept), flow, x0 + 3200)

    # Winded: run out, and until the breath is whole again.
    left = get(BREATH_VAR, x0 + 3460, y0 + 300)
    empty = call(FN_LE_FF, x0 + 3720, y0 + 300, A=left, B=0.0)
    short = call(FN_LESS_FF, x0 + 3720, y0 + 440, A=left, B=BREATH_HOLD_S)
    still = call(FN_AND, x0 + 3980, y0 + 440, A=get(WINDED_VAR, x0 + 3720, y0 + 580),
                 B=out(short))
    winded = call(FN_OR, x0 + 4240, y0 + 300, A=out(empty), B=out(still))
    flow = store(WINDED_VAR, out(winded), flow, x0 + 4500)

    # The sway's width eases to what the breath makes it.
    rest = _select(ed, keep, BREATH_WINDED_SCALE, 1.0,
                   get(WINDED_VAR, x0 + 4760, y0 + 580), x0 + 5020, y0 + 580)
    target = _select(ed, keep, BREATH_SWAY_SCALE, rest,
                     get(BREATH_HELD_VAR, x0 + 4760, y0 + 440), x0 + 5280, y0 + 440)
    eased = call(FN_INTERP_FF, x0 + 5540, y0 + 300,
                 Current=get(BREATH_SCALE_VAR, x0 + 5280, y0 + 300), Target=target,
                 DeltaTime=dt, InterpSpeed=BREATH_EASE_SPEED)
    flow = store(BREATH_SCALE_VAR, out(eased), flow, x0 + 5800)

    ed.add_comment_to_nodes(
        f"Hold breath: SwayRate is Held's (behind IsValid). Down the sights the "
        f"hold breath key (or BreathForced) holds the breath for up to "
        f"{BREATH_HOLD_S:g} s, refilled in {BREATH_RECOVER_S:g} s; run out, the "
        f"player is Winded until it is full again. BreathScale, which sway.py "
        f"multiplies the sway's width by, eases to {BREATH_SWAY_SCALE:g} held, "
        f"{BREATH_WINDED_SCALE:g} winded, 1 otherwise. Each value is stored "
        f"before the next reads it.", made)
    return flow[0]
