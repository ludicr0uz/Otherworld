"""verify.punch -- the empty-handed punch (weapon_component/punch.py): the
press gate, the swing's clip, the sweep and the blow's damage.

The helpers is_punch_play / is_punch_sweep / is_punch_gate / is_punch_write
pick out the punch's nodes; verify/knife.py's is_melee_* (punch or knife) let
the sections that count the ready-pose plays, the traces, the fire gate and the
hit's stamps set both melee attacks' nodes aside.
"""

import unreal

from asset_pipeline import lyra_paths as LYRA
from combat.anim_blueprint import AIM_SLOT
from combat.skin import player_skin
from combat.tuning import COMBAT
from combat.verify.common import (
    take_hits,
    BEL, PIN, by_pins, check, in_pins, load, num_pin, pin_value,
)
from combat.verify import fx as fxv
from combat import fx_vars as FX
from combat.verify.fixtures import w, wg
from combat.weapon_component.punch import (
    NEXT_PUNCH_VAR, PUNCH_ANIM_VAR, PUNCH_DUE_VAR, PUNCH_PENDING_VAR,
    PUNCH_QUEUED_VAR,
)


ANIM = unreal.AnimationLibrary


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _feeders(node, pin):
    p = BEL.find_input_pin(node, pin)
    return [PIN.get_owning_node(q) for q in PIN.list_connected_pins(p)] if p else []


def _feeds(pin, limit=250):
    """Every node feeding this pin through DATA links only."""
    seen, stack = set(), [pin]
    while stack and len(seen) < limit:
        for q in PIN.list_connected_pins(stack.pop()):
            node = PIN.get_owning_node(q)
            if node in seen:
                continue
            seen.add(node)
            stack.extend(x for x in BEL.list_input_pins(node)
                         if str(PIN.get_pin_name(x)) != "execute")
    return seen


def is_punch_play(node):
    return any(_title(f) == f"Get {PUNCH_ANIM_VAR}" for f in _feeders(node, "Asset"))


def is_punch_sweep(node):
    # The knife's sweep is a sphere too (verify/knife.py); the radius tells them apart.
    return "Radius" in in_pins(node) and num_pin(node, "Radius") == COMBAT.punch_radius_cm


def is_punch_gate(node):
    return (_title(node) == "Branch"
            and f"Get {NEXT_PUNCH_VAR}"
            in {_title(x) for x in _feeds(BEL.find_input_pin(node, "Condition"))})


def is_punch_write(node, pin):
    """A write whose value comes off the punch sweep's hit result."""
    return any(is_punch_sweep(t) for b in _feeders(node, pin)
               for t in _feeders(b, "Hit"))


def _reach(clip, bone, t):
    """How far forward of the character (its mesh's +Y, cm) ``bone`` is,
    ``t`` seconds into ``clip``."""
    at = unreal.Transform()
    for b in ANIM.find_bone_path_to_root(clip, bone):
        at = at * ANIM.get_bone_pose_for_time(clip, b, t, False)
    return at.translation.y


def check_punch_clip(skin, clip):
    """The blow is timed, not notified: its time has to be one the clip's
    fist is out at."""
    if skin.gas:
        check("on the motion-matching skin the punch is Lyra's melee, retargeted "
              "(asset_pipeline/import_lyra.py)",
              skin.punch == LYRA.uefn_clip(LYRA.PUNCH)
              and load(LYRA.PUNCH) is not None
              and abs(clip.get_play_length() - load(LYRA.PUNCH).get_play_length()) < 0.05,
              skin.punch)
    check("...in place: a clip with root motion played into the slot would root the player",
          not clip.get_editor_property("enable_root_motion"))
    start, fist = COMBAT.punch_clip_start_s, skin.pose_bones["hand_r"]
    check("...the swing starts inside the clip, and the clip outlasts the blow",
          0.0 <= start and start + COMBAT.punch_impact_s < clip.get_play_length(),
          f"{start} + {COMBAT.punch_impact_s} of {clip.get_play_length():.2f} s")
    steps = int(COMBAT.punch_interval_s / 0.05) + 1
    reach = [_reach(clip, fist, min(start + i * 0.05, clip.get_play_length()))
             for i in range(steps)]
    back, out_ = min(reach), max(reach)
    at_blow = _reach(clip, fist, start + COMBAT.punch_impact_s)
    check("...and the fist is out when the blow lands: at least 80% of the way from "
          "where the swing draws it back to where it stops",
          out_ - back > 30.0 and at_blow >= back + 0.8 * (out_ - back),
          f"{at_blow:.0f} cm of {back:.0f}..{out_:.0f}")


def check_punch_defaults():
    skin = player_skin()
    clip = w.get_editor_property(PUNCH_ANIM_VAR)
    want = load(skin.punch)
    check(f"{PUNCH_ANIM_VAR} is the worn skin's punch",
          clip is not None and clip == want, f"{clip} vs {skin.punch}")
    if clip is not None:
        check_punch_clip(skin, clip)
    worn = load(skin.mesh)
    check("...authored for the worn skeleton, or the slot would play nothing",
          clip is not None and worn is not None
          and clip.get_editor_property("skeleton") == worn.get_editor_property("skeleton"),
          str(clip.get_editor_property("skeleton").get_name()) if clip else "missing")
    check("no punch is queued or pending at the start",
          w.get_editor_property(PUNCH_QUEUED_VAR) is False
          and w.get_editor_property(PUNCH_PENDING_VAR) is False)
    times = [w.get_editor_property(v) for v in (NEXT_PUNCH_VAR, PUNCH_DUE_VAR)]
    check("its two deadlines are floats (not ints) starting at 0",
          all(isinstance(t, float) and t == 0.0 for t in times), repr(times))
    check("the blow lands inside the swing, the swing inside the cooldown",
          0.0 < COMBAT.punch_impact_s < COMBAT.punch_interval_s
          and COMBAT.punch_damage > 0.0 and COMBAT.punch_reach_cm > 0.0)


def check_punch_press():
    gates = [n for n in wg if is_punch_gate(n)]
    # Two: the press (the cooldown) and the blow (NextPunchTime is not in it,
    # PunchDueTime is), so filter to the one reading the fire key.
    press = [g for g in gates if "Get KeyFire"
             in {_title(x) for x in _feeds(BEL.find_input_pin(g, "Condition"))}]
    check("one punch press gate, on the fire key", len(press) == 1, str(len(press)))
    if len(press) != 1:
        return
    src = _feeds(BEL.find_input_pin(press[0], "Condition"))
    names = {_title(x) for x in src}
    check("...a tap, off cooldown, not sprinting, not blocking, not a spent press",
          {"Get KeyFire", f"Get {NEXT_PUNCH_VAR}", "Get Sprinting", "Get Blocking",
           "Get TriggerSpent"} <= names
          and any("WasInputKeyJustPressed" in t.replace(" ", "") for t in names),
          str(sorted(names)))
    valid = [x for x in src if "IsValid" in _title(x)]
    check("...with empty hands: IsValid(Held) through a NOT",
          len(valid) == 1 and any("NOT" in _title(c).upper() for c in
                                  [PIN.get_owning_node(q) for q in
                                   BEL.find_output_pin(valid[0], "ReturnValue")
                                   .list_connected_pins()]),
          str([_title(x) for x in valid]))
    through_held = [_title(x) for x in src if "IsValid" not in _title(x)
                    and any(_title(f) == "Get Held" for f in _feeders(x, "self"))]
    check("...and reads nothing off Held (an Accessed None per empty frame)",
          not through_held, str(through_held))
    after = [PIN.get_owning_node(q) for q in
             PIN.list_connected_pins(BEL.find_then_pin(press[0]))]
    check("...and only queues the punch",
          [_title(a) for a in after] == [f"Set {PUNCH_QUEUED_VAR}"]
          and pin_value(after[0], PUNCH_QUEUED_VAR) == "true",
          str([_title(a) for a in after]))


def check_punch_swing():
    plays = [n for n in by_pins(wg, "Asset", "SlotNodeName") if is_punch_play(n)]
    check("one punch clip play, in its Fx_ event: the Server event's Multicast and "
          "the owning client's prediction both call it (verify/fx.py)",
          len(plays) == 1 and fxv.in_fx(FX.PUNCH, plays) == plays, str(len(plays)))
    if len(plays) != 1:
        return
    check(f"...into {AIM_SLOT}, the upper-body slot, once",
          all(pin_value(p, "SlotNodeName") == AIM_SLOT
              and int(float(pin_value(p, "LoopCount"))) == 1 for p in plays))
    check("...from COMBAT.punch_clip_start_s into the clip, the wind-up the blow's time "
          "has no room for skipped",
          num_pin(plays[0], "InTimeToStartMontageAt") == COMBAT.punch_clip_start_s,
          pin_value(plays[0], "InTimeToStartMontageAt"))
    # The two callers: the server's tell, and the client's prediction.
    plays = fxv.calls(FX.PUNCH) + fxv.predicts(FX.PUNCH)

    def chain(node):
        """The Sets before a play, walked back along the exec chain."""
        seen = []
        for _ in range(6):
            prev = _feeders(node, "execute")
            if len(prev) != 1:
                break
            node = prev[0]
            seen.append(_title(node))
        return set(seen)

    served = [p for p in plays if f"Set {PUNCH_PENDING_VAR}" in chain(p)]
    mine = [p for p in plays if p not in served]
    check("...the Server event tells it (Multicast) and the Tick predicts it (Fx_): one "
          "call each", len(plays) == 2 and len(fxv.calls(FX.PUNCH)) == 1
          and len(fxv.predicts(FX.PUNCH)) == 1, str(len(plays)))
    stamps = {f"Set {v}" for v in (NEXT_PUNCH_VAR, PUNCH_DUE_VAR, PUNCH_PENDING_VAR)}
    check("...the server's after the cooldown, the blow's time and "
          "PunchPending are stamped; the client's after its own cooldown alone",
          len(served) == 1 and stamps <= chain(served[0]) and len(mine) == 1
          and chain(mine[0]) & stamps == {f"Set {NEXT_PUNCH_VAR}"},
          str([sorted(chain(p)) for p in plays]))
    delays = {num_pin(n, "B") for n in by_pins(wg, "A", "B")}
    check("...the cooldown and the blow's delay are COMBAT.punch_*",
          {COMBAT.punch_interval_s, COMBAT.punch_impact_s} <= delays)


def check_punch_blow():
    sweeps = [n for n in by_pins(wg, "Start", "End", "TraceChannel") if is_punch_sweep(n)]
    check("one punch sweep", len(sweeps) == 1, str(len(sweeps)))
    if len(sweeps) != 1:
        return
    s = sweeps[0]
    check("...a sphere of COMBAT.punch_radius_cm on Visibility, ignoring the player",
          num_pin(s, "Radius") == COMBAT.punch_radius_cm
          and pin_value(s, "TraceChannel") == "TraceTypeQuery1"
          and pin_value(s, "bIgnoreSelf") == "true",
          f"{pin_value(s, 'Radius')} {pin_value(s, 'TraceChannel')}")
    gate = _feeders(s, "execute")
    gate = _feeders(gate[0], "execute") if gate else []
    names = ({_title(x) for x in _feeds(BEL.find_input_pin(gate[0], "Condition"))}
             if gate else set())
    check("...swept only when PunchPending and PunchDueTime has come",
          {f"Get {PUNCH_PENDING_VAR}", f"Get {PUNCH_DUE_VAR}"} <= names, str(sorted(names)))
    writes = [n for n in take_hits(wg) if num_pin(n, "Amount") == COMBAT.punch_damage
              and not _feeders(n, "Amount")]
    check(f"...and the body it meets is told to take {COMBAT.punch_damage:.0f} HP "
          "(its TakeHit: combat/damage.py)",
          len(writes) == 1, f"{len(writes)} call(s)")
    if writes:
        told = {pin: [_title(f).replace(" ", "") for f in _feeders(writes[0], pin)]
                for pin in ("From", "InstigatedBy", "Cause")}
        check("...stamped like a pellet: which way it came (the sweep's impact normal), "
              "who struck it (this character's controller) and with what (the item in "
              "hand, nothing for a fist)",
              is_punch_write(writes[0], "From")
              and told["InstigatedBy"] == ["GetInstigatorController"]
              and told["Cause"] == ["GetHeld"], str(told))


def run():
    check_punch_defaults()
    check_punch_press()
    check_punch_swing()
    check_punch_blow()
