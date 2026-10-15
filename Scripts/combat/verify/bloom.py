"""verify.bloom -- the hip burst's bloom (weapon_component/bloom.py,
combat/bloom_tuning.py): the numbers against the automatics' intervals, the
cloud widened by 1 + Bloom, a round's add in ShotFired and in the owning
client's prediction, and the settling once a frame.
"""

from combat.bloom_tuning import (
    BLOOM_HOLD_S, BLOOM_MAX, BLOOM_PER_SHOT, BLOOM_RECOVER_SPEED, Bloom, BloomShotTime,
)
from combat.shot_vars import SHOT_FIRED
from combat.verify.anchor import event_nodes, feeders, reads, runs, title
from combat.verify.common import BEL, check, has_in_pin, num_pin
from combat.verify.fixtures import _is_exec, exec_reach, wg
from combat.weapon_component.accuracy import AIM_SPREAD_VAR
from combat.weapon_specs import _weapon_specs


def _num(node, pin):
    """A pin's number, None for a node without the pin."""
    return num_pin(node, pin) if has_in_pin(node, pin) else None


def _sets(nodes, var):
    return [n for n in nodes if title(n) == f"Set {var}"]


def _value(node, var):
    """The one node feeding a Set's value, else None."""
    found = feeders(node, str(var))
    return found[0] if len(found) == 1 else None


def _adds(nodes):
    """The Set Bloom nodes among ``nodes`` that add a round: fed by a Min
    capped at BLOOM_MAX, over Bloom + BLOOM_PER_SHOT."""
    found = []
    for n in _sets(nodes, Bloom):
        v = _value(n, Bloom)
        if v is None or _num(v, "B") != BLOOM_MAX:
            continue
        inner = feeders(v, "A")
        if len(inner) == 1 and _num(inner[0], "B") == BLOOM_PER_SHOT \
                and f"Get {Bloom}" in reads(inner[0]):
            found.append(n)
    return found


def _guarded_hip(set_node):
    """The Branch that runs ``set_node`` asks Held.Automatic and SightAiming."""
    before = [n for n in wg if set_node in runs(n, "then") and title(n) == "Branch"]
    return bool(before) and all({"Get Automatic", "Get SightAiming"} <= reads(b)
                                for b in before)


def _then_runs(set_node):
    """What the exec after ``set_node`` reaches, BloomShotTime's stamp first."""
    return exec_reach([p for p in BEL.list_output_pins(set_node) if _is_exec(p)])


def check_bloom_numbers():
    autos = {sp["display"]: sp["interval"] for sp in _weapon_specs() if sp["automatic"]}
    check(f"the bloom holds {BLOOM_HOLD_S:g} s after a round, longer than any "
          f"automatic's interval, so a burst does not settle between its own rounds",
          bool(autos) and BLOOM_HOLD_S > max(autos.values()), str(autos))
    check(f"a round adds {BLOOM_PER_SHOT:g} up to {BLOOM_MAX:g}, and it settles at "
          f"{BLOOM_RECOVER_SPEED:g}", 0.0 < BLOOM_PER_SHOT < BLOOM_MAX
          and BLOOM_RECOVER_SPEED > 0.0)


def check_bloom_cloud():
    held = [n for n in _sets(wg, AIM_SPREAD_VAR) if _value(n, AIM_SPREAD_VAR) is not None]
    mul = _value(held[0], AIM_SPREAD_VAR) if len(held) == 1 else None
    scale = [f for pin in ("A", "B") for f in (feeders(mul, pin) if mul else [])
             if _num(f, "B") == 1.0 and f"Get {Bloom}" in reads(f)]
    check("the held gun's AimSpread is its cloud times 1 + Bloom",
          len(held) == 1 and len(scale) == 1,
          f"{len(held)} held write(s), {title(mul) if mul else None}, {len(scale)} scale(s)")


def check_bloom_shot():
    fired = list(event_nodes(SHOT_FIRED))
    served = _adds(fired)
    check(f"{SHOT_FIRED} adds the round's bloom, behind Held.Automatic and not "
          "SightAiming, and stamps BloomShotTime",
          len(served) == 1 and _guarded_hip(served[0])
          and _sets(runs(served[0], "then"), BloomShotTime),
          f"{len(served)} add(s)")
    names = {n.get_path_name() for n in fired}
    predicted = [n for n in _adds(wg) if n.get_path_name() not in names]
    reach = [title(n) for p in predicted for n in _then_runs(p)]
    check("the owning client's ask adds it too (its prediction), before Server_Fire",
          len(predicted) == 1 and _guarded_hip(predicted[0])
          and any("Server" in t and "Fire" in t for t in reach),
          f"{len(predicted)} predicted add(s)")


def check_bloom_settle():
    settles = []
    for n in _sets(wg, Bloom):
        v = _value(n, Bloom)
        if v is not None and _num(v, "InterpSpeed") == BLOOM_RECOVER_SPEED:
            settles.append(n)
    ok = len(settles) == 1
    gate = [b for b in wg if ok and settles[0] in runs(b, "then") and title(b) == "Branch"]
    reach = {title(n) for n in _then_runs(settles[0])} if ok else set()
    check(f"once a frame, {BLOOM_HOLD_S:g} s after the last round, Bloom eases to "
          "zero (FInterpTo), before the cloud is written",
          ok and _num(_value(settles[0], Bloom), "Target") in (0.0, None)
          and len(gate) == 1 and f"Get {BloomShotTime}" in reads(gate[0])
          and f"Set {AIM_SPREAD_VAR}" in reach,
          f"{len(settles)} settle(s), {len(gate)} gate(s)")


def run():
    check_bloom_numbers()
    check_bloom_cloud()
    check_bloom_shot()
    check_bloom_settle()
