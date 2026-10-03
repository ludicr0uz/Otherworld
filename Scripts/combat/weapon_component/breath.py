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
from uebp.graph import _connect, _node, _pin, _set, else_, then
from combat.sway_tuning import SWAY_RATE_VAR
from combat.weapon_component.accuracy import _mul, _select
from combat.weapon_component.common import _prop
from uebp.nodes.actor import FN_IS_KEY_DOWN
from uebp.nodes.math import (
    FN_ADD_FF, FN_AND, FN_CLAMP, FN_INTERP_FF, FN_LESS_FF, FN_LE_FF, FN_NOT, FN_OR)
from combat.weapon_component import vars as WV


def _author_hold_breath(ed, tick, pc_out, held, armed_out, key_pin, exec_ins):
    """Copy Held's sway rate, then hold or let go of the breath and ease the
    sway's scale. Returns the exec pin to carry on from."""
    made = []

    def keep(n):
        made.append(n)
        return n

    def out(n, name="ReturnValue"):
        return _pin(n, name, is_input=False)

    def get(var):
        return out(keep(ed.add_get_member_variable_node(var)), var)

    def call(fn, **ins):
        n = keep(_node(ed, fn))
        for name, v in ins.items():
            if isinstance(v, (int, float)):
                _set(n, name, v)
            else:
                _connect(v, _pin(n, name))
        return n

    def store(var, value, flow):
        n = keep(ed.add_set_member_variable_node(var))
        _connect(value, _pin(n, var))
        for e in flow:
            _connect(e, _pin(n, "execute"))
        return [then(n)]

    dt = out(tick, "DeltaSeconds")

    # The gun's rate, behind the Branch that knows Held is there.
    armed = keep(ed.add_branch_node())
    _connect(armed_out, _pin(armed, "Condition"))
    for e in exec_ins:
        _connect(e, _pin(armed, "execute"))
    rate, rate_n = _prop(ed, SWAY_RATE_VAR, held)
    keep(rate_n)
    flow = store(SWAY_RATE_VAR, rate, [then(armed)])
    flow.append(else_(armed))

    # Held: the key (or its stand-in), down the sights, not winded.
    down = call(FN_IS_KEY_DOWN, self=pc_out, Key=key_pin)
    key = call(FN_OR, A=out(down), B=get(BREATH_FORCED_VAR))
    calm = call(FN_NOT, A=get(WINDED_VAR))
    sighted = call(FN_AND, A=get(WV.SightAiming), B=out(calm))
    holding = call(FN_AND, A=out(key), B=out(sighted))
    flow = store(BREATH_HELD_VAR, out(holding), flow)

    # The breath drains while held and refills while not.
    is_held = get(BREATH_HELD_VAR)
    per_s = _select(ed, keep, -1.0, BREATH_HOLD_S / BREATH_RECOVER_S, is_held)
    step = _mul(ed, keep, per_s, dt)
    more = call(FN_ADD_FF, A=get(BREATH_VAR), B=step)
    kept = call(FN_CLAMP, Value=out(more), Min=0.0, Max=BREATH_HOLD_S)
    flow = store(BREATH_VAR, out(kept), flow)

    # Winded: run out, and until the breath is whole again.
    left = get(BREATH_VAR)
    empty = call(FN_LE_FF, A=left, B=0.0)
    short = call(FN_LESS_FF, A=left, B=BREATH_HOLD_S)
    still = call(FN_AND, A=get(WINDED_VAR), B=out(short))
    winded = call(FN_OR, A=out(empty), B=out(still))
    flow = store(WINDED_VAR, out(winded), flow)

    # The sway's width eases to what the breath makes it.
    rest = _select(ed, keep, BREATH_WINDED_SCALE, 1.0, get(WINDED_VAR))
    target = _select(ed, keep, BREATH_SWAY_SCALE, rest, get(BREATH_HELD_VAR))
    eased = call(FN_INTERP_FF,
                 Current=get(BREATH_SCALE_VAR), Target=target,
                 DeltaTime=dt, InterpSpeed=BREATH_EASE_SPEED)
    flow = store(BREATH_SCALE_VAR, out(eased), flow)

    ed.add_comment_to_nodes(
        f"Hold breath: SwayRate is Held's (behind IsValid). Down the sights the "
        f"hold breath key (or BreathForced) holds the breath for up to "
        f"{BREATH_HOLD_S:g} s, refilled in {BREATH_RECOVER_S:g} s; run out, the "
        f"player is Winded until it is full again. BreathScale, which sway.py "
        f"multiplies the sway's width by, eases to {BREATH_SWAY_SCALE:g} held, "
        f"{BREATH_WINDED_SCALE:g} winded, 1 otherwise. Each value is stored "
        f"before the next reads it.", made)
    return flow[0]
