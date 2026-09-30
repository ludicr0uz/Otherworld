"""verify.throw -- the throw (weapon_component/throw.py): its key, the arc
actor, the prediction drawn while the key is held, the release, and the
flight that follows the same curve.

Also the two predicates other sections use to leave the throw's nodes out of
their sweeps: is_throw_trace (the flight's two traces) and launch_nodes (what
feeds the launch, which reads the control rotation).
"""

import math

import unreal

from combat.paths import MAT_THROW_ARC, SPHERE, THROW_ARC_BP_PATH
from combat.throw_arc import ARC_COMPONENT
from combat.throw_tuning import (
    THROW_ARC_HZ, THROW_ARC_SIM_S, THROW_GRAVITY_Z, THROW_PITCH_UP_DEG,
    THROW_SPEED, THROW_START_UP,
)
from combat.tuning import BIND_VARS, THROW_KEY
from combat.verify.common import (
    BEL, PIN, by_pins, check, component_template, load, num_pin, pin_value,
)
from combat.verify.fixtures import w, wg
from combat.weapon_component.throw import (
    THROWN_VAR, THROW_AIMING_VAR, THROW_ARC_CLASS_VAR, THROW_FORCED_VAR,
    THROW_LAST_VAR, THROW_START_VAR, THROW_VELOCITY_VAR,
)

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
    check("the throw starts idle: not aiming, no probe holding the key, "
          "nothing in the air",
          w.get_editor_property(THROW_AIMING_VAR) is False
          and w.get_editor_property(THROW_FORCED_VAR) is False
          and w.get_editor_property(THROWN_VAR) is None)


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
    # The numbers, replayed: a level throw from the start height over flat
    # ground should carry across a clearing, not to the thrower's feet or out
    # of sight.
    a = math.radians(THROW_PITCH_UP_DEG)
    vx, vz = THROW_SPEED * math.cos(a), THROW_SPEED * math.sin(a)
    h = 96.0 + THROW_START_UP
    g = -THROW_GRAVITY_Z
    t = (vz + math.sqrt(vz * vz + 2 * g * h)) / g
    check("a level throw carries 5-15 m over flat ground, inside the predicted "
          "THROW_ARC_SIM_S", 500.0 <= vx * t <= 1500.0 and t < THROW_ARC_SIM_S,
          f"{vx * t / 100:.1f} m in {t:.2f} s")


def run():
    check_throw_key()
    check_arc_actor()
    check_arc()
    check_release()
    check_flight()
