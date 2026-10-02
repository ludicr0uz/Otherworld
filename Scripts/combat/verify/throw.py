"""verify.throw -- the throw (weapon_component/throw.py): its key, the arc
actor, the prediction drawn while the key is held, the click that throws, the
clip's wind-up before the hand lets go (throw_windup.py), and the flight that
follows the same curve, tumbling (throw_flight.py).

Also the three predicates other sections use to leave the throw's nodes out
of their sweeps: is_throw_trace (the flight's two traces), is_throw_play (the
clip's play node) and launch_nodes (what feeds the launch, which reads the
control rotation).
"""

import math

import unreal

from combat.anim_blueprint import AIM_SLOT
from combat.paths import ITEM_BP_PATH, MAT_THROW_ARC, SPHERE, THROW_ARC_BP_PATH
from combat.skin import player_skin
from combat.throw_arc import ARC_COMPONENT
from combat.throw_tuning import (
    THROW_ARC_HZ, THROW_ARC_SIM_S, THROW_GRAVITY_Z, THROW_MAX_PITCH_DEG,
    THROW_PITCH_COLUMN, THROW_PITCH_UP_DEG, THROW_PITCH_VAR, THROW_RELEASE_S,
    THROW_SPEED, THROW_SPEED_VAR, THROW_SPIN_VAR, THROW_START_FORWARD,
    THROW_START_UP,
)
from combat.tuning import BIND_VARS, THROW_KEY
from combat.verify.common import (
    BEL, PIN, by_pins, check, component_template, load, num_pin, pin_value,
)
from combat.verify.fixtures import w, wg
from combat.weapon_component.consume import TRIGGER_SPENT
from combat.weapon_component.throw import (
    THROW_AIMING_VAR, THROW_ARC_CLASS_VAR, THROW_CLICK_FORCED_VAR,
    THROW_FORCED_VAR,
)
from combat.weapon_component.throw_flight import (
    THROWN_VAR, THROW_LAST_VAR, THROW_START_VAR, THROW_VELOCITY_VAR,
)
from combat.weapon_component.throw_windup import (
    THROW_ANIM_VAR, THROW_DUE_VAR, THROW_WINDING_VAR,
)
from combat.weapon_specs import _weapon_specs

PREDICT_PINS = ("StartPos", "LaunchVelocity", "OverrideGravityZ")


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _feeds(pins, limit=300):
    """Every node feeding these pins through DATA links only."""
    seen, stack = set(), list(pins)
    while stack and len(seen) < limit:
        for q in PIN.list_connected_pins(stack.pop()):
            node = PIN.get_owning_node(q)
            if node in seen:
                continue
            seen.add(node)
            stack.extend(x for x in BEL.list_input_pins(node)
                         if str(PIN.get_pin_name(x)) != "execute")
    return seen


def _source(node, pin):
    got = PIN.list_connected_pins(BEL.find_input_pin(node, pin))
    return got[0] if got else None


def _same_pin(a, b):
    """Pin wrappers do not compare equal; their node and name do."""
    return (a is not None and b is not None
            and PIN.get_owning_node(a) == PIN.get_owning_node(b)
            and str(PIN.get_pin_name(a)) == str(PIN.get_pin_name(b)))


def _predicts():
    return by_pins(wg, *PREDICT_PINS)


def is_throw_trace(node):
    """A trace of the throw's flight: fed, however far back, by ThrowLast."""
    return any(_title(n) == f"Get {THROW_LAST_VAR}"
               for n in _feeds([p for p in BEL.list_input_pins(node)
                                if str(PIN.get_pin_name(p)) != "execute"]))


def is_throw_play(node):
    """The play of the throw's clip: its Asset is ThrowAnim."""
    return any(_title(n) == f"Get {THROW_ANIM_VAR}"
               for n in _feeds([BEL.find_input_pin(node, "Asset")]))


def launch_nodes():
    """The nodes that compute the throw's launch (start and velocity)."""
    return _feeds([BEL.find_input_pin(p, name) for p in _predicts()
                   for name in ("StartPos", "LaunchVelocity")])


def check_throw_key():
    names = [v for v, _k in BIND_VARS]
    check(f"throwing is its own bind, {THROW_KEY} by default, appended last so "
          f"no saved bind changes meaning",
          names[-1] == "KeyThrow"
          and w.get_editor_property("KeyThrow").export_text() == THROW_KEY,
          str(names))
    check("the throw starts idle: not aiming, no probe holding the key or "
          "clicking, nothing winding up or in the air",
          w.get_editor_property(THROW_AIMING_VAR) is False
          and w.get_editor_property(THROW_WINDING_VAR) is None
          and w.get_editor_property(THROW_FORCED_VAR) is False
          and w.get_editor_property(THROW_CLICK_FORCED_VAR) is False
          and w.get_editor_property(THROWN_VAR) is None)


def _item_cdo(path):
    return unreal.get_default_object(BEL.generated_class(load(path)))


def check_arc_angle():
    base = _item_cdo(ITEM_BP_PATH).get_editor_property(THROW_PITCH_VAR)
    check(f"every item throws on a {THROW_PITCH_UP_DEG:g} degree arc unless it "
          f"says otherwise: a real lob, under the {THROW_MAX_PITCH_DEG:g} degree cap",
          isinstance(base, float) and base == THROW_PITCH_UP_DEG
          and 20.0 <= THROW_PITCH_UP_DEG < THROW_MAX_PITCH_DEG, str(base))
    bad = [f"{sp['display']}={got} spec {sp[THROW_PITCH_COLUMN]}"
           for sp in _weapon_specs()
           for got in [_item_cdo(sp["path"]).get_editor_property(THROW_PITCH_VAR)]
           if abs(got - float(sp[THROW_PITCH_COLUMN])) > 1e-4]
    check("...and each gun holds its own, the GUN TUNING tab's `throw_arc`",
          not bad, "; ".join(bad))
    tips = [n for n in launch_nodes() if _title(n) == f"Get {THROW_PITCH_VAR}"]
    held = [_title(PIN.get_owning_node(q)) for n in tips
            for q in PIN.list_connected_pins(BEL.find_input_pin(n, "self"))]
    check("the launch is tipped up by the held item's arc, not a literal",
          len(tips) == 1 and held == ["Get Held"], f"{len(tips)} reads off {held}")
    speeds = [n for n in launch_nodes() if _title(n) == f"Get {THROW_SPEED_VAR}"]
    held = [_title(PIN.get_owning_node(q)) for n in speeds
            for q in PIN.list_connected_pins(BEL.find_input_pin(n, "self"))]
    check("...and leaves at the held item's speed, not a literal",
          len(speeds) == 1 and held == ["Get Held"], f"{len(speeds)} reads off {held}")


def _carry(speed, pitch_deg):
    """(metres carried, cm risen over the hand, seconds in the air) of a level
    throw from the start height over flat ground."""
    a = math.radians(pitch_deg)
    vx, vz = speed * math.cos(a), speed * math.sin(a)
    h = 96.0 + THROW_START_UP
    g = -THROW_GRAVITY_Z
    t = (vz + math.sqrt(vz * vz + 2 * g * h)) / g
    return vx * t / 100.0, vz * vz / (2 * g), t


def check_arc_actor():
    bp = load(THROW_ARC_BP_PATH)
    check("BP_ThrowArc exists", bp is not None, THROW_ARC_BP_PATH)
    if bp is None:
        return
    dots = component_template(bp, ARC_COMPONENT)
    check(f"...drawn by one instanced mesh, {ARC_COMPONENT}",
          isinstance(dots, unreal.InstancedStaticMeshComponent), str(type(dots)))
    if not isinstance(dots, unreal.InstancedStaticMeshComponent):
        return
    mesh = dots.get_editor_property("static_mesh")
    mats = list(dots.get_editor_property("override_materials"))
    check("...of spheres in the arc's own emissive material",
          mesh is not None and mesh.get_path_name().startswith(SPHERE)
          and len(mats) == 1 and mats[0] is not None
          and mats[0].get_path_name().startswith(MAT_THROW_ARC),
          f"{mesh} {mats}")
    check("...that blocks nothing and casts no shadow",
          dots.get_collision_profile_name() == "NoCollision"
          and dots.get_editor_property("cast_shadow") is False,
          str(dots.get_collision_profile_name()))
    check("the weapon component spawns that class",
          w.get_editor_property(THROW_ARC_CLASS_VAR) == BEL.generated_class(bp),
          str(w.get_editor_property(THROW_ARC_CLASS_VAR)))


def check_arc():
    preds = _predicts()
    check("the arc is one Predict Projectile Path", len(preds) == 1, str(len(preds)))
    if len(preds) != 1:
        return
    p = preds[0]
    check("...traced on Visibility, which the flight traces on too",
          pin_value(p, "TraceChannel").endswith("ECC_Visibility")
          and pin_value(p, "bTracePath").lower() == "true",
          pin_value(p, "TraceChannel"))
    check("...under THROW_GRAVITY_Z, the flight's gravity",
          num_pin(p, "OverrideGravityZ") == THROW_GRAVITY_Z,
          pin_value(p, "OverrideGravityZ"))
    check("...a dot every 1/THROW_ARC_HZ s for THROW_ARC_SIM_S s, drawing no debug lines",
          num_pin(p, "SimFrequency") == THROW_ARC_HZ
          and num_pin(p, "MaxSimTime") == THROW_ARC_SIM_S
          and pin_value(p, "DrawDebugType").endswith("None"),
          f"{pin_value(p, 'SimFrequency')} Hz, {pin_value(p, 'MaxSimTime')} s")
    src = {_title(n) for n in launch_nodes()}
    check("...launched along the view from in front of the player",
          "GetControlRotation" in src and "Get Actor Location" in src, str(sorted(src)))
    keyed = [n for n in wg if "IsInputKeyDown" in _title(n)
             and any(_title(PIN.get_owning_node(q)) == "Get KeyThrow"
                     for q in PIN.list_connected_pins(BEL.find_input_pin(n, "Key")))]
    check("the arc is drawn while the throw key is held (polled, not tapped)",
          len(keyed) == 1, str(len(keyed)))
    adds = [n for n in wg if _title(n) == "AddInstance"]
    check("...as instances added to the arc actor's Dots, in world space: one "
          "per predicted point and one disc where it lands",
          len(adds) == 2 and all(pin_value(n, "bWorldSpace") == "true" for n in adds),
          str([pin_value(n, "bWorldSpace") for n in adds]))
    loops = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(
        BEL.find_output_pin(p, "OutPathPositions"))]
    check("...the dots walking the predicted path",
          len(loops) == 1 and "ForEach" in _title(loops[0]).replace(" ", ""),
          str([_title(n) for n in loops]))
    clears = [n for n in wg if _title(n) == "ClearInstances"]
    check("...cleared before each frame's arc, and once when the aim ends",
          len(clears) == 2, str(len(clears)))


def _upstream(node, pin):
    """Titles of every node feeding one input pin."""
    return {_title(n) for n in _feeds([BEL.find_input_pin(node, pin)])}


def check_click():
    """Hold the throw key for the arc, click the fire key to throw."""
    spends = [n for n in wg if _title(n) == f"Set {TRIGGER_SPENT}"
              and pin_value(n, TRIGGER_SPENT) == "true"]
    gates = [PIN.get_owning_node(q) for n in spends
             for q in PIN.list_connected_pins(BEL.find_input_pin(n, "execute"))
             if "Get KeyThrow" in _upstream(PIN.get_owning_node(q), "Condition")]
    check("the throw spends the click, so it cannot fire what is equipped next",
          len(gates) == 1, f"{len(spends)} spends, {len(gates)} behind the throw key")
    clicks = [n for n in wg if _title(n) == "Branch"
              and {f"Get {THROW_CLICK_FORCED_VAR}", f"Get {THROW_AIMING_VAR}",
                   "Get KeyFire"} <= _upstream(n, "Condition")]
    check("the throw is a click of the fire key (or the probe's) over an arc "
          "already showing", len(clicks) == 1, str(len(clicks)))
    if len(clicks) == 1 and len(gates) == 1:
        check("...taken only while the throw key is held with something in hand, "
              "and letting the key up throws nothing",
              {"Get KeyThrow", "Get Held"} <= _upstream(gates[0], "Condition")
              and "Get KeyThrow" not in _upstream(clicks[0], "Condition")
              and any("Get KeyThrow" in _upstream(PIN.get_owning_node(q), "Condition")
                      for q in PIN.list_connected_pins(
                          BEL.find_input_pin(clicks[0], "execute"))))
    # The fire gate: the Branch whose condition reads the trigger both ways.
    fires = [n for n in wg if _title(n) == "Branch"
             and {"Get KeyFire", "Get Sprinting", "Get Blocking", "Get KeyThrow",
                  f"Get {THROW_FORCED_VAR}"} <= _upstream(n, "Condition")
             and f"Get {THROW_AIMING_VAR}" not in _upstream(n, "Condition")]
    check("with the throw key down the fire gate stays shut: the click is the "
          "throw's, not a shot, a bite or a slash", len(fires) == 1, str(len(fires)))
    check("...and it stays shut while a throw winds up, when no arc is drawn "
          "either",
          len(fires) == 1 and len(gates) == 1
          and f"Get {THROW_WINDING_VAR}" in _upstream(fires[0], "Condition")
          and f"Get {THROW_WINDING_VAR}" in _upstream(gates[0], "Condition"))


def _hand_at(clip, t):
    """The grip hand's bone in the clip at t, as (ahead, up) of the capsule's
    centre in cm: the frame the launch point is given in. A pose comes back
    local, so it is composed up the hierarchy to the root."""
    skin = player_skin()
    lib = unreal.AnimationLibrary
    xf = unreal.Transform()
    for b in lib.find_bone_path_to_root(clip, skin.pose_bones["hand_r"]):
        xf = xf.multiply(lib.get_bone_pose_for_time(clip, b, t, False))
    at = xf.translation
    yaw = math.radians(skin.mesh_yaw)
    return at.x * math.cos(yaw) - at.y * math.sin(yaw), at.z + skin.mesh_z


def check_windup():
    """The click plays the throw's clip, and the item leaves the hand where
    the clip's hand lets go."""
    skin = player_skin()
    anim = w.get_editor_property(THROW_ANIM_VAR)
    check("the throw's clip is the worn skin's (none on a skin without one)",
          (anim.get_path_name().split(".")[0] if anim else None) == skin.throw,
          f"{anim} for {skin.throw}")
    plays = [n for n in by_pins(wg, "Asset", "SlotNodeName") if is_throw_play(n)]
    check(f"...played once into {AIM_SLOT}, upper body only, at its own rate",
          # A literal equal to its pin's default reads back empty off disk.
          len(plays) == 1 and pin_value(plays[0], "SlotNodeName") == AIM_SLOT
          and num_pin(plays[0], "InPlayRate") in (None, 1.0)
          and num_pin(plays[0], "LoopCount") in (None, 1.0), str(len(plays)))
    stamps = [n for n in wg if _title(n) == f"Set {THROW_DUE_VAR}"]
    delay = [num_pin(PIN.get_owning_node(q), "B") for n in stamps
             for q in PIN.list_connected_pins(BEL.find_input_pin(n, THROW_DUE_VAR))]
    check(f"...the hand letting go {THROW_RELEASE_S:g} s into it",
          delay == [THROW_RELEASE_S], str(delay))
    if len(plays) == 1 and len(stamps) == 1:
        skips = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(
            BEL.find_input_pin(stamps[0], "execute"))]
        check("...and only where there is a clip: without one the item leaves "
              "on the click",
              len(skips) == 1 and _title(skips[0]) == "Branch"
              and f"Get {THROW_ANIM_VAR}" in _upstream(skips[0], "Condition"),
              str([_title(n) for n in skips]))
    winds = [n for n in wg if _title(n) == f"Set {THROW_WINDING_VAR}"]
    kept = [n for n in winds if _source(n, THROW_WINDING_VAR)]
    check("the wind-up remembers the item it is throwing, and forgets it once",
          len(kept) == 1 and len(winds) == 2
          and _title(PIN.get_owning_node(_source(kept[0], THROW_WINDING_VAR)))
          == "Get Held", f"{len(kept)} of {len(winds)} sets")
    sets = [n for n in wg if _title(n) == f"Set {THROWN_VAR}" and _source(n, THROWN_VAR)]
    if len(sets) != 1:
        return
    # Walk the release's exec chain back to the Branch it hangs off.
    node, gate = sets[0], None
    for _ in range(8):
        prev = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(
            BEL.find_input_pin(node, "execute"))]
        if len(prev) != 1:
            break
        node = prev[0]
        if _title(node) == "Branch":
            gate = node
            break
    before = ([PIN.get_owning_node(q) for q in PIN.list_connected_pins(
        BEL.find_input_pin(gate, "execute"))] if gate else [])
    check("the release waits for the wind-up to come due, and runs only if the "
          "hand still holds that item",
          gate is not None
          and {f"Get {THROW_WINDING_VAR}", "Get Held"} <= _upstream(gate, "Condition")
          and len(before) == 1 and _title(before[0]) == "Branch"
          and {f"Get {THROW_WINDING_VAR}", f"Get {THROW_DUE_VAR}"}
          <= _upstream(before[0], "Condition"))
    if anim is None:
        return
    ahead, up = _hand_at(anim, THROW_RELEASE_S)
    check("at that moment the clip's hand is at the launch point, within 25 cm, "
          "so the item leaves from the hand",
          math.hypot(ahead - THROW_START_FORWARD, up - THROW_START_UP) <= 25.0
          and THROW_RELEASE_S < anim.get_editor_property("sequence_length"),
          f"hand {ahead:.0f} ahead, {up:.0f} up; launch {THROW_START_FORWARD:g}, "
          f"{THROW_START_UP:g}")


def check_release():
    preds = _predicts()
    # Set with a value: the landing's Set Thrown clears it with nothing wired.
    sets = {v: [n for n in wg if _title(n) == f"Set {v}" and _source(n, v)]
            for v in (THROWN_VAR, THROW_START_VAR, THROW_VELOCITY_VAR)}
    check("the release stores the item, its start and its velocity once each",
          all(len(s) == 1 for s in sets.values()),
          str({k: len(v) for k, v in sets.items()}))
    if len(preds) != 1 or not all(len(s) == 1 for s in sets.values()):
        return
    p = preds[0]
    check("...the very launch the arc was drawn from, start and velocity alike",
          _same_pin(_source(sets[THROW_START_VAR][0], THROW_START_VAR),
                    _source(p, "StartPos"))
          and _same_pin(_source(sets[THROW_VELOCITY_VAR][0], THROW_VELOCITY_VAR),
                        _source(p, "LaunchVelocity")))
    thrown = _source(sets[THROWN_VAR][0], THROWN_VAR)
    check("...and what flies is what was held",
          thrown is not None and _title(PIN.get_owning_node(thrown)) == "Get Held")


def check_flight():
    traces = [n for n in by_pins(wg, "Start", "End", "TraceChannel") if is_throw_trace(n)]
    check("the flight traces twice: the segment it just flew, and down to the ground",
          len(traces) == 2, str(len(traces)))
    falls = [n for n in wg if num_pin(n, "B") == 0.5 * THROW_GRAVITY_Z]
    check("...along start + v t + g t^2 / 2 under the arc's gravity",
          len(falls) == 1, str(len(falls)))
    lands = [n for n in wg if _title(n) == "Set Dropped"
             and any(_title(PIN.get_owning_node(q)) == f"Get {THROWN_VAR}"
                     for q in PIN.list_connected_pins(BEL.find_input_pin(n, "self")))]
    check("...and it lands as a Dropped item, which pick-up looks for",
          len(lands) == 1 and pin_value(lands[0], "Dropped") == "true", str(len(lands)))
    spins = [n for n in by_pins(wg, "DeltaRotation", "bSweep")
             if any(_title(PIN.get_owning_node(q)) == f"Get {THROWN_VAR}"
                    for q in PIN.list_connected_pins(BEL.find_input_pin(n, "self")))]
    check("the item in the air is turned every frame it flies",
          len(spins) == 1, str(len(spins)))
    if len(spins) == 1:
        src = _upstream(spins[0], "DeltaRotation")
        fed = _feeds([BEL.find_input_pin(spins[0], "DeltaRotation")])
        rates = [n for n in fed if _title(n) == f"Get {THROW_SPIN_VAR}"]
        of = [_title(PIN.get_owning_node(q)) for n in rates
              for q in PIN.list_connected_pins(BEL.find_input_pin(n, "self"))]
        back = [n for n in fed if num_pin(n, "B") == -1.0]
        check(f"...its own {THROW_SPIN_VAR} degrees a second of game time, end "
              "over end, top first, about the axis across the throw",
              len(rates) == 1 and of == [f"Get {THROWN_VAR}"] and len(back) == 1
              and f"Get {THROW_VELOCITY_VAR}" in src
              and any("DeltaSeconds" in t.replace(" ", "") for t in src),
              str(sorted(src)))
    # The numbers, replayed: a level throw from the start height over flat
    # ground should carry across a clearing, not to the thrower's feet or out
    # of sight.
    far, _rise, t = _carry(THROW_SPEED, THROW_PITCH_UP_DEG)
    check("a level throw carries 5-15 m over flat ground, inside the predicted "
          "THROW_ARC_SIM_S", 5.0 <= far <= 15.0 and t < THROW_ARC_SIM_S,
          f"{far:.1f} m in {t:.2f} s")


def run():
    check_throw_key()
    check_arc_angle()
    check_arc_actor()
    check_arc()
    check_click()
    check_windup()
    check_release()
    check_flight()
