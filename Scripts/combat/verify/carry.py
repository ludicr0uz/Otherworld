"""verify.carry -- the carry: a gun rides lowered until an aim key, the guard,
a shot or a reload raises it (weapon_component/carry.py writes Lowered, and the
ready pose follows it). probes/probe_carry.py shows the same in the game.
"""

from combat.carry_tuning import (
    CARRY_GRIP, CARRY_RAISE_HOLD_S, LOWERED_VAR, POSE_LOWERED_VAR, RAISE_FORCED_VAR,
)
from combat.paths import KNIFE_BP_PATH
from combat.seat_tuning import SEAT_HOLD, SEAT_VAR
from combat.weapon_component.stance import PRONE, STANCE_VAR
from combat.weapon_specs import _weapon_specs
from combat.weapon_component.look_vars import HandPose
from combat.verify.fixtures import titles, w, wg
from combat.verify.knife import is_melee_play
from combat.torch_tuning import BURNS_VAR
from combat.verify.common import (
    BEL, PIN, by_pins, cdo, check, in_pins, load, num_pin, out_pins,
)


def _feeds(pin, limit=60):
    """Every node behind a data pin, nearest first."""
    seen, stack = [], [pin]
    while stack and len(seen) < limit:
        for q in PIN.list_connected_pins(stack.pop()):
            node = PIN.get_owning_node(q)
            if node not in seen:
                seen.append(node)
                stack.extend(x for x in BEL.list_input_pins(node)
                             if str(PIN.get_pin_name(x)) != "execute")
    return seen


def _reads(nodes):
    return {name for n in nodes for name in out_pins(n)}


def _gate(node):
    """The node whose exec output runs ``node``."""
    ins = PIN.list_connected_pins(BEL.find_input_pin(node, "execute"))
    return PIN.get_owning_node(ins[0]) if ins else None


def check_carry_state():
    for name in (LOWERED_VAR, POSE_LOWERED_VAR):
        check(f"{name} exists and starts False, so frame one re-equips nothing",
              w.get_editor_property(name) is False, repr(w.get_editor_property(name)))
    check(f"{RAISE_FORCED_VAR}, the probes' stand-in for an aim key, is False in a "
          "real game", w.get_editor_property(RAISE_FORCED_VAR) is False)

    sets = [n for n, t in zip(wg, titles) if t == f"Set {LOWERED_VAR}"]
    check(f"{LOWERED_VAR} is written in two places: armed, and with empty hands",
          len(sets) == 2, f"{len(sets)} writes")
    behind = [(n, _feeds(BEL.find_input_pin(n, LOWERED_VAR))) for n in sets]
    armed = [(n, f) for n, f in behind if "Aiming" in _reads(f)]
    plain = [(n, f) for n, f in behind if "Aiming" not in _reads(f)]
    if len(armed) != 1 or len(plain) != 1:
        check("one write reads the aim and the other does not", False,
              f"{len(armed)} armed, {len(plain)} plain")
        return
    node, fed = armed[0]
    want = {"Sprinting", "Aiming", "Blocking", RAISE_FORCED_VAR, "Melee", "Consumable",
            BURNS_VAR, "NextFireTime", STANCE_VAR, SEAT_VAR}
    check("armed, it is made of Sprinting, Aiming, Blocking, Stance, Held's Melee, "
          "Consumable and Burns, and Held's NextFireTime against the clock",
          want <= _reads(fed)
          and any("GetTimeSeconds" in str(BEL.get_node_title(n)).replace(" ", "")
                  for n in fed),
          str(sorted(want - _reads(fed))))
    check(f"...a shot or a reload holds the gun up {CARRY_RAISE_HOLD_S:g} s past "
          f"NextFireTime",
          any(num_pin(n, "B") == CARRY_RAISE_HOLD_S for n in fed
              if "NextFireTime" in _reads(_feeds(BEL.find_input_pin(n, "A"), 2))),
          str(sorted({num_pin(n, "B") for n in fed} - {None})))
    check(f"...and the sight camera holds it up until it has left the gun "
          f"({SEAT_VAR} > {SEAT_HOLD:g}), so the view easing home does not dip "
          f"with the gun",
          any(num_pin(n, "B") == SEAT_HOLD for n in fed
              if SEAT_VAR in _reads(_feeds(BEL.find_input_pin(n, "A"), 2))),
          str(sorted({num_pin(n, "B") for n in fed} - {None})))
    check("...a prone body keeps the gun up: Stance is compared with PRONE",
          any(num_pin(n, "B") == PRONE for n in fed
              if STANCE_VAR in _reads(_feeds(BEL.find_input_pin(n, "A"), 2))),
          f"PRONE is {PRONE}")
    check("...and with empty hands it is Sprinting alone",
          _reads(plain[0][1]) == {"Sprinting"}, str(sorted(_reads(plain[0][1]))))
    gates = {_gate(n) for n in sets}
    gate = next(iter(gates)) if len(gates) == 1 else None
    cond = _feeds(BEL.find_input_pin(gate, "Condition"), 4) if gate else []
    check("both writes hang off one Branch on IsValid(Held), so Held is never "
          "read with empty hands",
          gate is not None and "Then" in {p.capitalize() for p in out_pins(gate)}
          and BEL.find_then_pin(gate) in
          PIN.list_connected_pins(BEL.find_input_pin(node, "execute"))
          and any("IsValid" in str(BEL.get_node_title(n)).replace(" ", "")
                  for n in cond),
          str([str(BEL.get_node_title(n)) for n in cond]))


def check_pose_follows_carry():
    check("the pose's state is remembered exactly once",
          titles.count(f"Set {POSE_LOWERED_VAR}") == 1,
          f"{titles.count(f'Set {POSE_LOWERED_VAR}')} writes")
    marks = [n for n, t in zip(wg, titles) if t == f"Set {POSE_LOWERED_VAR}"]
    edge = _feeds(BEL.find_input_pin(_gate(marks[0]), "Condition")) if marks else []
    check(f"...behind a Branch on {LOWERED_VAR} != {POSE_LOWERED_VAR}: re-equipping "
          "happens only on the frames the two disagree",
          {LOWERED_VAR, POSE_LOWERED_VAR} <= _reads(edge), str(sorted(_reads(edge))))

    # Every place that starts the ready pose (the equip and the keepalive) asks
    # Lowered first, and plays HandPose, the held item's AimPose as this copy
    # has it (verify/look.py); the punch and the slash are their own montages.
    plays = [n for n in by_pins(wg, "Asset", "SlotNodeName") if not is_melee_play(n)
             and HandPose in _reads(_feeds(BEL.find_input_pin(n, "Asset"), 3))]
    check("the ready pose is started in two places: the equip and the keepalive",
          len(plays) == 2, f"{len(plays)} plays")
    for i, n in enumerate(plays):
        gate = _gate(n)
        fed = _feeds(BEL.find_input_pin(gate, "Condition")) if gate else []
        check(f"ready pose play {i + 1} is not started while {LOWERED_VAR}",
              LOWERED_VAR in _reads(fed), str(sorted(_reads(fed))))


def check_shot_origin():
    # A lowered gun's first shot, and the reticle's wall check, start where the
    # muzzle is about to be, not at the knee (carry._author_shot_origin).
    picks = [n for n in by_pins(wg, "A", "B", "bPickA")
             if LOWERED_VAR in _reads(_feeds(BEL.find_input_pin(n, "bPickA"), 2))]
    # Two, the same sub-graph twice: the aim resolve's, on the machine with the
    # keys, and Server_Fire's own (shot.py), since the shot leaves the server's
    # muzzle. Each is checked below.
    check(f"a SelectVector picks the shot's start on {LOWERED_VAR}: the aim resolve's, "
          "and the server's own for the shot it traces", len(picks) == 2,
          f"{len(picks)} found")
    for pick in picks:
        _check_origin_pick(pick)
    starts = [len([n for n in by_pins(wg, "Start", "End", "TraceChannel")
                   if BEL.find_output_pin(pick, "ReturnValue")
                   in PIN.list_connected_pins(BEL.find_input_pin(n, "Start"))])
              for pick in picks]
    check("...and the wall check starts at the one and the pellets at the other: the "
          "same sub-graph on the machine that runs each, so the reticle and the shot "
          "agree", starts == [1, 1], f"{starts} traces")


def _check_origin_pick(pick):
    real = _feeds(BEL.find_input_pin(pick, "B"))
    raised = _feeds(BEL.find_input_pin(pick, "A"))
    check("...not lowered, it is the muzzle: Held's transform x MuzzleOffset",
          "MuzzleOffset" in _reads(real) and len(real) <= 4
          and not any({"X", "Y", "Z"} <= in_pins(n) for n in real),
          str(sorted(_reads(real))))
    grips = [n for n in raised if {"X", "Y", "Z"} <= in_pins(n)]
    got = tuple(num_pin(grips[0], a) for a in "XYZ") if grips else None
    check(f"...lowered, it is the body's transform x (MuzzleOffset + {CARRY_GRIP})",
          "MuzzleOffset" in _reads(raised) and got == CARRY_GRIP
          and any("GetOwner" in str(BEL.get_node_title(n)).replace(" ", "")
                  for n in raised), f"grip {got}")


def check_what_is_carried_lowered():
    for sp in _weapon_specs():
        d = cdo(load(sp["path"]))
        check(f"{sp['display']} is a gun to the carry: neither Melee nor Consumable",
              d.get_editor_property("Melee") is False
              and d.get_editor_property("Consumable") is False)
    check("the knife is Melee, so it keeps its hold pose up",
          cdo(load(KNIFE_BP_PATH)).get_editor_property("Melee") is True)


def run():
    check_carry_state()
    check_pose_follows_carry()
    check_shot_origin()
    check_what_is_carried_lowered()
