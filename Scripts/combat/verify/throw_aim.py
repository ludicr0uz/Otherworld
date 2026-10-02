"""verify.throw_aim -- where a throw is sent and how the arm waits for it:
the launch heading for the point the reticle rests on and pitched to pass
through it (weapon_component/throw_launch.py), and the ready pose held
while the key is down (throw_pose.py, weapon_component/throw_ready.py), which
the click's clip plays on from.

Also is_ready_node, which the older sweep over the slot's plays uses to leave
the ready pose's two nodes out.
"""

import math

from combat.anim_blueprint import AIM_SLOT, HIT_SLOT
from combat.paths import THROW_READY_ANIM_PATH
from combat.skin import player_skin
from combat.throw_tuning import (
    THROW_AIM_MIN_AHEAD, THROW_GRAVITY_Z, THROW_MELEE_SPEED, THROW_PITCH_VAR,
    THROW_READY_S, THROW_RELEASE_S, THROW_SPEED, THROW_WINDUP_S,
)
from combat.verify.common import (
    BEL, PIN, by_pins, check, has_in_pin, load, num_pin, pin_value,
)
from combat.verify.fixtures import w, wg
from combat.verify.throw import (
    _feeds, _hand_at, _predicts, _title, _upstream, is_throw_play, launch_nodes,
)
from combat.weapon_component.consume import TRIGGER_SPENT
from combat.weapon_component.throw import THROW_AIMING_VAR
from combat.weapon_component.throw_launch import AIM_POINT_VAR
from combat.weapon_component.throw_ready import THROW_READY_ANIM_VAR
from combat.weapon_component.throw_windup import THROW_ANIM_VAR

COCKED_BACK_CM = 30.0      # the ready hand is at least this far behind the body
COCKED_UP_CM = 30.0        # ...and over the capsule's centre


def is_ready_node(node):
    """A node of the ready pose's: its Asset is ThrowReadyAnim (the play, and
    the test of what the slot is playing)."""
    return any(_title(n) == f"Get {THROW_READY_ANIM_VAR}"
               for n in _feeds([BEL.find_input_pin(node, "Asset")]))


def aimed_pitch(d, h, v):
    """The flatter pitch, in degrees, of a throw at v cm/s that passes through
    a point d cm away over the ground and h cm up; None out of reach. The
    launch's own arithmetic (throw_launch._author_through)."""
    g = -THROW_GRAVITY_Z
    under = v ** 4 - g * (g * d * d + 2.0 * h * v * v)
    if under < 0.0:
        return None
    return math.degrees(math.atan2(v * v - math.sqrt(under), g * d))


def _height_at(d, pitch_deg, v):
    """How high a throw at that pitch is when it is d cm out."""
    a = math.radians(pitch_deg)
    t = d / (v * math.cos(a))
    return v * math.sin(a) * t + 0.5 * THROW_GRAVITY_Z * t * t


def check_reticle():
    preds = _predicts()
    if len(preds) != 1:
        check("the arc's one prediction is there to read the launch off", False,
              str(len(preds)))
        return
    launch = launch_nodes()
    aims = [n for n in launch if _title(n) == f"Get {AIM_POINT_VAR}"]
    check("every throw heads for the point the reticle rests on, so the arc "
          "stands under the reticle",
          len(aims) == 1
          and f"Get {AIM_POINT_VAR}" in _upstream(preds[0], "LaunchVelocity"),
          f"{len(aims)} reads of {AIM_POINT_VAR}")
    check("...from a launch point that is the body's alone: the reticle does "
          "not move where the hand lets go",
          f"Get {AIM_POINT_VAR}" not in _upstream(preds[0], "StartPos"))
    near = [n for n in launch if num_pin(n, "B") == THROW_AIM_MIN_AHEAD
            and ">=" in _title(n)]
    check(f"...unless that point is under {THROW_AIM_MIN_AHEAD:g} cm ahead of "
          "it (a wall at the shoulder): then along the view",
          len(near) == 1 and "GetControlRotation" in {_title(n) for n in launch},
          str(len(near)))

    solves = [n for n in launch if "Atan2" in _title(n).replace(" ", "")]
    roots = ({_title(n).replace(" ", "") for n in _feeds(
        [BEL.find_input_pin(solves[0], "Y")])} if len(solves) == 1 else set())
    # g three times: g d^2, g (...) under the root, and g d under the line.
    drops = [n for n in launch if num_pin(n, "B") == -THROW_GRAVITY_Z]
    check("it is pitched to pass through that point: the flatter of the two "
          "throws there are, at the held item's speed under the arc's gravity",
          len(solves) == 1 and {"Sqrt", "GetThrowSpeed"} <= roots and len(drops) == 3,
          f"{len(solves)} atan2, {len(drops)} uses of g, fed by {sorted(roots)}")
    picks = [n for n in launch if _title(n) == "SelectFloat"
             and solves and solves[0] in _feeds([BEL.find_input_pin(n, "A")])]
    lob = ({_title(n) for n in _feeds([BEL.find_input_pin(picks[0], "B")])}
           if len(picks) == 1 else set())
    check("...or, with no such throw (the point out of reach, the sky), "
          f"tipped the item's {THROW_PITCH_VAR} over the view: a lob",
          len(picks) == 1 and {f"Get {THROW_PITCH_VAR}", "GetControlRotation"} <= lob
          and f"Get {AIM_POINT_VAR}" not in lob, str(sorted(lob)))

    # The arithmetic, replayed: the pitch found for a point puts the curve on it.
    v = THROW_MELEE_SPEED
    off = []
    for d, h in ((300.0, 0.0), (1000.0, -146.0), (1500.0, 100.0), (2500.0, -146.0)):
        pitch = aimed_pitch(d, h, v)
        off.append(None if pitch is None else abs(_height_at(d, pitch, v) - h))
    check("that pitch puts the curve on the point, near and far, above and below",
          all(o is not None and o < 0.5 for o in off), str(off))
    flat = aimed_pitch(1000.0, 0.0, v)
    reach = v * v / -THROW_GRAVITY_Z
    lob_reach = THROW_SPEED * THROW_SPEED / -THROW_GRAVITY_Z
    check("...a nearly flat throw of a blade at 10 m, and no throw at all past "
          "what the speed reaches: a blade's well past the lobbed items'",
          flat is not None and flat < 12.0 and 2000.0 <= reach
          and aimed_pitch(reach + 100.0, 0.0, v) is None
          and 800.0 <= lob_reach < reach / 2.0
          and aimed_pitch(lob_reach + 100.0, 0.0, THROW_SPEED) is None,
          f"{flat:.1f} deg at 10 m, reach {reach / 100.0:.0f} m, "
          f"the lob's {lob_reach / 100.0:.0f} m")


def check_ready_pose():
    skin = player_skin()
    pose = w.get_editor_property(THROW_READY_ANIM_VAR)
    want = THROW_READY_ANIM_PATH if skin.throw else None
    check("the ready-to-throw pose is the worn skin's (none on a skin without "
          "a throw clip)",
          (pose.get_path_name().split(".")[0] if pose else None) == want,
          f"{pose} for {want}")
    if pose is None:
        return
    clip = load(skin.throw)
    there, here = _hand_at(clip, THROW_READY_S), _hand_at(pose, 0.0)
    later = _hand_at(pose, 0.5)
    check(f"...the throw's own clip stopped {THROW_READY_S:.3f} s in, and held",
          math.dist(there, here) < 1.0 and math.dist(here, later) < 0.1,
          f"hand {here[0]:.0f} ahead, {here[1]:.0f} up; the clip's "
          f"{there[0]:.0f}, {there[1]:.0f}")
    check("...where the arm is cocked: the hand behind the body and up beside "
          "the head", here[0] <= -COCKED_BACK_CM and here[1] >= COCKED_UP_CM,
          f"{here[0]:.0f} ahead, {here[1]:.0f} up")
    check("...before the hand lets go, so the click has the throw still to play",
          0.0 < THROW_READY_S < THROW_RELEASE_S
          and abs(THROW_WINDUP_S - (THROW_RELEASE_S - THROW_READY_S)) < 1e-9
          and THROW_WINDUP_S >= 0.05, f"{THROW_WINDUP_S:.3f} s from click to release")


def check_ready_graph():
    nodes = [n for n in by_pins(wg, "Asset", "SlotNodeName") if is_ready_node(n)]
    plays = [n for n in nodes if has_in_pin(n, "LoopCount")]
    tests = [n for n in nodes if n not in plays]
    check(f"the ready pose is played into {AIM_SLOT} by one node, looping",
          len(plays) == 1 and pin_value(plays[0], "SlotNodeName") == AIM_SLOT
          and (num_pin(plays[0], "LoopCount") or 0) >= 100, str(len(plays)))
    if len(plays) != 1:
        return
    gates = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(
        BEL.find_input_pin(plays[0], "execute"))]
    asked = _feeds([BEL.find_input_pin(gates[0], "Condition")]) if len(gates) == 1 else set()
    slots = {pin_value(n, "SlotNodeName") for n in asked
             if "IsSlotActive" in _title(n).replace(" ", "")}
    check("...only when the slot is not already playing it, so it is not "
          "restarted every frame and comes back after a re-equip",
          len(gates) == 1 and _title(gates[0]) == "Branch" and len(tests) == 1
          and tests[0] in asked and pin_value(tests[0], "SlotNodeName") == AIM_SLOT,
          f"{len(tests)} tests")
    check(f"...and never under a flinch ({HIT_SLOT}), which it would stop",
          slots == {HIT_SLOT}, str(sorted(slots)))
    before = ([PIN.get_owning_node(q) for q in PIN.list_connected_pins(
        BEL.find_input_pin(gates[0], "execute"))] if len(gates) == 1 else [])
    check("...on every frame the arc is drawn: straight after the aim is "
          "marked as showing",
          len(before) == 1 and _title(before[0]) == f"Set {THROW_AIMING_VAR}"
          and pin_value(before[0], THROW_AIMING_VAR) == "true",
          str([_title(n) for n in before]))

    clips = [n for n in by_pins(wg, "Asset", "SlotNodeName") if is_throw_play(n)]
    start = num_pin(clips[0], "InTimeToStartMontageAt") if len(clips) == 1 else None
    check("the click plays the throw's clip on from the ready pose's moment, "
          "so the arm goes forward out of the pose it waited in",
          start is not None and abs(start - THROW_READY_S) < 1e-4, str(start))

    # Called off: the Branch that spends the click on its true arm re-equips
    # on its false one.
    spends = [n for n in wg if _title(n) == f"Set {TRIGGER_SPENT}"
              and pin_value(n, TRIGGER_SPENT) == "true"]
    ends = [PIN.get_owning_node(q) for n in spends
            for q in PIN.list_connected_pins(BEL.find_input_pin(n, "execute"))
            if "Get KeyThrow" in _upstream(PIN.get_owning_node(q), "Condition")]
    downs = ([PIN.get_owning_node(q) for q in PIN.list_connected_pins(
        BEL.find_else_pin(ends[0]))] if len(ends) == 1 else [])
    check("letting the key go re-equips (NeedsRefresh), which puts the held "
          "item's own pose back",
          len(downs) == 1 and _title(downs[0]) == "Set NeedsRefresh"
          and pin_value(downs[0], "NeedsRefresh") == "true",
          str([_title(n) for n in downs]))
    check("a skin's ready pose and its throw clip come together",
          (w.get_editor_property(THROW_READY_ANIM_VAR) is None)
          == (w.get_editor_property(THROW_ANIM_VAR) is None))


def run():
    check_reticle()
    check_ready_pose()
    check_ready_graph()
