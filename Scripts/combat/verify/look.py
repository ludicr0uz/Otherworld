"""verify.look -- the look (weapon_component/look.py): what another machine's
copy of a character poses by. The three variables replicated to everyone but
the owner and nothing else on the component, the Server event that keeps
them, the component replicating (its own default and the character's), the
owning machine's report on a change, the mirror a remote copy runs before the
pose, and HandPose in the equip.

That the pose arrives is two processes' to prove: probes/probe_net_look.py.
"""

from combat.aim_pitch import AIM_PITCH_VAR
from combat.carry_tuning import LOWERED_VAR
from combat.verify.common import BEL, PIN, check, in_pins
from combat.verify.fixtures import _wg_all, char, wc, wg, wg_mirror
from combat.verify.sights import _feeds, _title
from combat.weapon_component import vars as WV
from combat.weapon_component.look_vars import (
    LOOK_PARAMS, REPLICATED, SERVER_SET_LOOK, TABLE, HandPose, LookAim, LookLowered, LookPose,
    SentAim, SentLowered, SentPose)
from combat.weapon_component.stance import STANCE_VAR
from uebp import net


def _sources(node, pin):
    found = BEL.find_input_pin(node, pin)
    return {_title(n) for n in _feeds(found)} if found else set()


def _ran_by(node):
    pin = BEL.find_input_pin(node, "execute")
    return [PIN.get_owning_node(q) for q in PIN.list_connected_pins(pin)] if pin else []


def check_replication():
    for var in REPLICATED:
        want = (net.REPLICATED, "None", "COND_SKIP_OWNER")
        got = net.variable_replication(wc, var)
        check(f"{var} is Replicated to everyone but the owner, who has the keys",
              got == want, str(got))
        check(f"...and compiled so", net.compiled_replication(wc, var)[0] == net.REPLICATED,
              str(net.compiled_replication(wc, var)))
    others = [str(v) for v in TABLE if v not in REPLICATED
              and net.variable_replication(wc, v)[0] != net.NONE]
    extra = [v for v in (WV.Held, WV.Inventory, WV.Aiming, WV.SightAiming, WV.SightBlend,
                         STANCE_VAR, LOWERED_VAR, WV.Stamina, WV.Sprinting)
             if net.variable_replication(wc, v)[0] != net.NONE]
    check("nothing else of the look is replicated: the working copies and what was "
          "last sent are each machine's own", not others and not extra, str(others + extra))
    check(f"{SERVER_SET_LOOK} is a reliable Server event: it is sent only on a change, "
          "so a lost one would leave the pose stale", net.compiled_rpc(wc, SERVER_SET_LOOK)
          == (net.SERVER, True), str(net.compiled_rpc(wc, SERVER_SET_LOOK)))
    check("BP_WeaponComponent replicates by default", net.replicates(wc))
    check("...and so does the player's WeaponComponent, on a character that replicates",
          net.replicates(char, "WeaponComponent") and net.replicates(char))


def check_server_event():
    writes = {v: [n for n in _wg_all if _title(n) == f"Set {v}"] for v in REPLICATED}
    check("each replicated variable is written in one place", all(
        len(w) == 1 for w in writes.values()), str({str(k): len(w) for k, w in writes.items()}))
    for (param, _type), var in zip(LOOK_PARAMS, REPLICATED):
        sets = writes[var]
        fed = _sources(sets[0], str(var)) if sets else set()
        check(f"...{var}, from the event's {param}", SERVER_SET_LOOK in fed, str(sorted(fed)))
    aim = writes[LookAim][0] if writes[LookAim] else None
    clamp = [n for n in (_feeds(BEL.find_input_pin(aim, str(LookAim))) if aim else [])
             if {"Value", "Min", "Max"} <= in_pins(n)]
    check("the aim mode a client reports is clamped to the three there are",
          len(clamp) == 1, str(len(clamp)))


def check_report():
    # The call, by its pins: the event itself gives the three out, the call takes them in.
    calls = [n for n in wg if {"execute", *(p for p, _ in LOOK_PARAMS)} <= in_pins(n)]
    check(f"the Tick calls {SERVER_SET_LOOK} in one place", len(calls) == 1, str(len(calls)))
    if len(calls) != 1:
        return
    call = calls[0]
    for (param, _type), sent in zip(LOOK_PARAMS, (SentAim, SentLowered, SentPose)):
        check(f"...{param} from {sent}, stored first (the mode is a pure chain)",
              _sources(call, param) == {f"Get {sent}"}, str(sorted(_sources(call, param))))
    # Walk back up the Sent* stores to the Branch that asks whether any changed.
    node, stores = call, []
    while _ran_by(node) and _title(_ran_by(node)[0]).startswith("Set Sent"):
        node = _ran_by(node)[0]
        stores.append(_title(node))
    gate = [n for n in _ran_by(node) if _title(n) == "Branch"]
    check("...after the three stores", sorted(stores) == sorted(
        f"Set {v}" for v in (SentAim, SentLowered, SentPose)), str(stores))
    reads = _sources(gate[0], "Condition") if gate else set()
    check("...and only on a frame one of them changed: a Branch on the mode, Lowered "
          "and HandPose against what was last sent",
          {f"Get {v}" for v in (SentAim, SentLowered, SentPose, LOWERED_VAR, HandPose,
                                WV.Aiming, WV.SightAiming)} <= reads, str(sorted(reads)))
    local = [n for n in wg if _title(n) == "Branch"
             and _sources(n, "Condition") == {f"Get {WV.LocalInput}"}]
    carry = [n for n in wg if _title(n) == f"Set {LOWERED_VAR}"]
    check("the carry, and the report after it, run only where the keys are: every "
          f"write of {LOWERED_VAR} outside the mirror is behind a Branch on LocalInput",
          len(carry) == 2 and bool(local), f"{len(carry)} writes, {len(local)} local gates")


def check_mirror():
    titles = [_title(n) for n in wg_mirror]
    for var in (STANCE_VAR, WV.Aiming, WV.SightAiming, WV.SightBlend, LOWERED_VAR, HandPose,
                WV.NeedsRefresh, AIM_PITCH_VAR):
        check(f"the mirror writes {var} once", titles.count(f"Set {var}") == 1,
              str(titles.count(f"Set {var}")))

    def fed(var):
        sets = [n for n in wg_mirror if _title(n) == f"Set {var}"]
        return _sources(sets[0], str(var)) if sets else set()
    squashed = lambda names: {n.replace(" ", "").lower() for n in names}
    check("...Stance off the movement component (GetStance), not off a key",
          "getstance" in squashed(fed(STANCE_VAR)), str(sorted(fed(STANCE_VAR))))
    for var in (WV.Aiming, WV.SightAiming):
        check(f"...{var} off {LookAim}", f"Get {LookAim}" in fed(var), str(sorted(fed(var))))
    check(f"...{WV.SightBlend} eased towards {WV.SightAiming}, as the sights ease it",
          {f"Get {WV.SightBlend}", f"Get {WV.SightAiming}"} <= fed(WV.SightBlend),
          str(sorted(fed(WV.SightBlend))))
    check(f"...{LOWERED_VAR} off {LookLowered}", fed(LOWERED_VAR) == {f"Get {LookLowered}"},
          str(sorted(fed(LOWERED_VAR))))
    check(f"...{HandPose} off {LookPose}", fed(HandPose) == {f"Get {LookPose}"},
          str(sorted(fed(HandPose))))
    check(f"...the anim BP's {AIM_PITCH_VAR} off the pawn's replicated view "
          f"(GetBaseAimRotation) times {WV.SightBlend}",
          "getbaseaimrotation" in squashed(fed(AIM_PITCH_VAR))
          and f"Get {WV.SightBlend}" in fed(AIM_PITCH_VAR), str(sorted(fed(AIM_PITCH_VAR))))
    pose = [n for n in wg_mirror if _title(n) == f"Set {HandPose}"]
    gate = [n for n in (_ran_by(pose[0]) if pose else []) if _title(n) == "Branch"]
    check("a new pose re-equips, and only a new one: HandPose and NeedsRefresh are "
          f"behind a Branch on {HandPose} != {LookPose}",
          bool(gate) and {f"Get {HandPose}", f"Get {LookPose}"} <= _sources(gate[0], "Condition"),
          str(sorted(_sources(gate[0], "Condition")) if gate else "no Branch"))
    keys = [t for t in titles if "InputKey" in t.replace(" ", "")]
    check("the mirror reads no key", not keys, str(keys))


def check_hand_pose():
    sets = [n for n in wg if _title(n) == f"Set {HandPose}"]
    check(f"outside the mirror {HandPose} is written by the equip alone: Held's "
          "AimPose, and none with empty hands", len(sets) == 2
          and sorted(len(_sources(n, str(HandPose))) > 0 for n in sets) == [False, True],
          str([sorted(_sources(n, str(HandPose))) for n in sets]))
    took = [n for n in sets if _sources(n, str(HandPose))]
    check("...AimPose read off Held", bool(took) and {"Get AimPose", f"Get {WV.Held}"}
          <= _sources(took[0], str(HandPose)),
          str(sorted(_sources(took[0], str(HandPose))) if took else ""))
    valid = [n for n in (_ran_by(took[0]) if took else []) if _title(n) == "Branch"]
    local = [n for v in valid for n in _ran_by(v) if _title(n) == "Branch"]
    check("...behind IsValid(Held), behind a Branch on LocalInput: a remote copy's "
          "Held is not its player's item", bool(valid) and bool(local)
          and _sources(local[0], "Condition") == {f"Get {WV.LocalInput}"},
          str(sorted(_sources(local[0], "Condition")) if local else "no gate"))


def run():
    check_replication()
    check_server_event()
    check_report()
    check_mirror()
    check_hand_pose()
