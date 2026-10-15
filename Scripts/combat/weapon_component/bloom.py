"""The bloom (combat/bloom_tuning.py has the rule): each round of an
automatic fired from the hip adds to Bloom, which settles back to zero soon
after the burst stops, and the cloud (accuracy.py) is widened by 1 + Bloom.

A round adds where the shot is: on the server in ShotFired (single player's
one machine too), and on a client of a server in its prediction of the ask,
so the client's reticle and the server's draw bloom alike. The settling runs
once a frame on every machine, at the head of the accuracy block, so the
cloud a remote shooter's round is drawn in on the server is the same shape.

Bloom is stored before anything reads it again: FInterpTo and the Min are
pure, and read after their Set they would step a second time.
"""

from uebp.g import _G
from uebp.graph import _set, out
from combat.paths import ITEM_CLASS_PATH
from combat.bloom_tuning import (
    BLOOM_HOLD_S, BLOOM_MAX, BLOOM_PER_SHOT, BLOOM_RECOVER_SPEED, Bloom, BloomShotTime,
)
from combat.weapon_component.slot_nodes import not_, op
from uebp.nodes.math import (
    FN_ADD_FF, FN_AND, FN_FMIN, FN_GREATER_FF, FN_INTERP_FF, FN_SUB_FF,
)
from uebp.nodes.system import FN_DELTA_SECONDS, FN_TIME_SECONDS
from combat import item_vars as IV
from combat.weapon_component import vars as WV


def bloom_scale(g):
    """The pin the cloud is multiplied by: 1 + Bloom."""
    n = g.call(FN_ADD_FF, A=g.get(Bloom))
    _set(n, "B", 1.0)
    return out(n)


def author_bloom_rest(ed, execs):
    """Once a frame: past the hold after the last round, Bloom eases to zero.
    Returns the exec pins to carry on from."""
    g = _G(ed)
    since = op(g, FN_SUB_FF, out(g.call(FN_TIME_SECONDS)), g.get(BloomShotTime))
    past = g.call(FN_GREATER_FF, A=since)
    _set(past, "B", BLOOM_HOLD_S)
    settle, hold = g.branch(out(past), execs)
    eased = g.call(FN_INTERP_FF, Current=g.get(Bloom),
                   DeltaTime=out(g.call(FN_DELTA_SECONDS)))
    _set(eased, "Target", 0.0)
    _set(eased, "InterpSpeed", BLOOM_RECOVER_SPEED)
    flow = g.put(Bloom, out(eased), [settle])
    ed.add_comment_to_nodes(
        f"The bloom settles (bloom.py): {BLOOM_HOLD_S:g} s after the last round it "
        f"eases to zero (FInterpTo, speed {BLOOM_RECOVER_SPEED:g}).", g.made)
    return [flow, hold]


def author_bloom_shot(ed, held, execs):
    """A round: an automatic fired from the hip adds BLOOM_PER_SHOT, up to
    BLOOM_MAX, and stamps the time. ``held`` is a valid Held's pin. Returns
    the exec pins to carry on from."""
    g = _G(ed, ITEM_CLASS_PATH)
    hip = op(g, FN_AND, g.iget(held, IV.Automatic), not_(g, g.get(WV.SightAiming)))
    adds, skip = g.branch(hip, execs)
    more = g.call(FN_ADD_FF, A=g.get(Bloom))
    _set(more, "B", BLOOM_PER_SHOT)
    capped = g.call(FN_FMIN, A=out(more))
    _set(capped, "B", BLOOM_MAX)
    flow = g.put(Bloom, out(capped), [adds])
    flow = g.put(BloomShotTime, out(g.call(FN_TIME_SECONDS)), [flow])
    ed.add_comment_to_nodes(
        f"The bloom (bloom.py): an automatic fired from the hip adds {BLOOM_PER_SHOT:g} "
        f"to Bloom, at most {BLOOM_MAX:g}, and stamps BloomShotTime. The cloud is "
        "1 + Bloom times the gun's own; down the sights it is zero and adds nothing.",
        g.made)
    return [flow, skip]
