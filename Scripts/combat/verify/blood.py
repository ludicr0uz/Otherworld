"""verify.blood -- BP_BloodSplash: the spray and the mist, and how they scale with damage.
"""

import math

import unreal

from combat.blood import (
    BLOOD_DRAG, BLOOD_DROPLETS, BLOOD_GRAVITY, BLOOD_LIFETIME, BLOOD_MIST,
    BLOOD_REFERENCE_DAMAGE, BLOOD_SCALE_MAX, BLOOD_SCALE_MIN,
    BLOOD_VELOCITY_ENCODE, _blood_blobs,
)
from combat.materials import BLOOD_BASE_COLOUR
from combat.paths import BLOOD_BP_PATH, MAT_BLOOD
from combat.verify.fixtures import wg
from combat.verify.common import (
    BEL, by_pins, check, component_template, components, graph, load, num_pin,
    titled,
)


# ─── Blood: the spray, not just the spheres ──────────────────────────────────

def check_blood():
    # The layout is generated from a fixed seed, so it can be recomputed here and
    # compared component by component -- a droplet nudged by hand in the editor, or
    # a seed changed without meaning to, shows up as a mismatch rather than as "the
    # blood looks a bit different from how I remember it".
    #
    # Most of what follows is about the thing that made the old burst read as a
    # cartoon rather than as blood, and every clause of it is asserted: the colour
    # is dark, desaturated and LIT; the droplets are droplets; they leave at wildly
    # different speeds; they fall under real gravity with drag; and nothing swells.

    mel = unreal.MaterialEditingLibrary
    blood_mat = load(MAT_BLOOD)
    lit = mel.get_material_property_input_node(
        blood_mat, unreal.MaterialProperty.MP_EMISSIVE_COLOR) is None
    check("blood is lit rather than emissive", lit,
          "an emissive droplet glows in its own little world instead of sitting in "
          "the scene's lighting, which is the loudest cartoon cue of the lot")
    base_node = mel.get_material_property_input_node(
        blood_mat, unreal.MaterialProperty.MP_BASE_COLOR)
    base = base_node.get_editor_property("constant") if base_node else None
    check("blood has a base colour at all", base is not None)
    if base is not None:
        check("blood is dark", max(base.r, base.g, base.b) <= 0.25,
              f"brightest channel {max(base.r, base.g, base.b):.3f} (linear)")
        check("blood is not pure saturated red",
              base.g > 0.004 and base.b > 0.004 and base.r / max(base.g, 1e-6) < 20.0,
              f"({base.r:.3f}, {base.g:.3f}, {base.b:.3f}) -- "
              f"R/G {base.r / max(base.g, 1e-6):.1f}")
        check("the builder's colour is the one on disk",
              all(abs(a - b) < 1e-6 for a, b in
                  zip(BLOOD_BASE_COLOUR, (base.r, base.g, base.b))))
    rough_node = mel.get_material_property_input_node(
        blood_mat, unreal.MaterialProperty.MP_ROUGHNESS)
    rough = rough_node.get_editor_property("r") if rough_node else None
    check("blood is wet, not chalk", rough is not None and rough <= 0.35,
          f"roughness {rough}")
    check("M_Blood carries no expressions left over from an earlier build",
          mel.get_num_material_expressions(blood_mat) == 3,
          f"{mel.get_num_material_expressions(blood_mat)} expressions")

    blood_bp = load(BLOOD_BP_PATH)
    want_blobs = _blood_blobs()
    check(f"the splash has {len(want_blobs)} droplets",
          len({c for c in components(blood_bp) if c.startswith("Blob")})
          == len(want_blobs),
          str(sorted({c for c in components(blood_bp) if c.startswith("Blob")})))
    placed = True
    unshadowed = True
    for i, (bx, by, bz, bscale) in enumerate(want_blobs):
        t = component_template(blood_bp, f"Blob{i}")
        if t is None:
            placed = False
            break
        loc = t.get_editor_property("relative_location")
        size = t.get_editor_property("relative_scale3d")
        placed &= (abs(loc.x - bx) < 1e-3 and abs(loc.y - by) < 1e-3
                   and abs(loc.z - bz) < 1e-3 and abs(size.x - bscale) < 1e-4)
        unshadowed &= not t.get_editor_property("cast_shadow")
    check("every droplet carries the seeded launch velocity in its location", placed)
    check("no droplet casts a shadow", unshadowed,
          "19 shadow casters per pellet, eight pellets to a shotgun shell")

    # The cone has to lean along +X, which is what the impact rotates onto the hit
    # normal. A symmetric ball of droplets would spray nowhere in particular.
    check("the cone reaches out along +X, the hit normal",
          max(b[0] for b in want_blobs) > 0.0
          and max(b[0] for b in want_blobs) > max(abs(b[1]) for b in want_blobs),
          f"reach {max(b[0] for b in want_blobs) * BLOOD_VELOCITY_ENCODE:.0f} cm/s")
    speeds = [math.sqrt(b[0] ** 2 + b[1] ** 2 + b[2] ** 2) * BLOOD_VELOCITY_ENCODE
              for b in want_blobs]
    check("the spray leaves at wildly different speeds",
          max(speeds) / max(min(speeds), 1e-6) >= 3.0,
          f"{min(speeds):.0f}-{max(speeds):.0f} cm/s, a {max(speeds) / min(speeds):.1f}x "
          "spread -- one speed for everything is what makes a burst read as one "
          "expanding shell")
    spray_speeds = speeds[:BLOOD_DROPLETS]
    mist_speeds = speeds[BLOOD_DROPLETS:]
    check("the mist hangs at the wound while the spray leaves",
          len(mist_speeds) == BLOOD_MIST
          and max(mist_speeds) < min(spray_speeds),
          f"mist <= {max(mist_speeds):.0f} cm/s, spray >= {min(spray_speeds):.0f} cm/s")
    # 100 cm is the engine sphere's diameter at scale 1, so scale IS size in metres.
    biggest = max(b[3] for b in want_blobs) * 100.0
    check("droplets are droplets", biggest <= 4.0, f"largest {biggest:.1f} cm across")
    check("the whole thing is over fast", 0.2 <= BLOOD_LIFETIME <= 0.6,
          f"{BLOOD_LIFETIME}s")

    bg = graph(blood_bp).list_all_nodes()
    check("nothing swells: the burst no longer rides a sine",
          not any("Sin" in str(BEL.get_node_title(n)) for n in bg),
          "blood does not inflate")
    check("droplets fly under drag rather than in a straight line",
          bool(titled(bg, "Exp")),
          "the closed form of dv/dt = g - kv needs an exponential in it")
    check("the drag coefficient is the one the builder states",
          any(abs((num_pin(n, "B") if num_pin(n, "B") is not None else 0.0)
                  + BLOOD_DRAG) < 1e-6 for n in by_pins(bg, "A", "B")),
          f"-{BLOOD_DRAG} on a B pin")
    check("gravity is rotated into the actor's own frame once",
          bool(titled(bg, "InverseTransformDirection")),
          "the actor faces the hit normal, so world -Z is not local -Z")
    falls = [n for n in bg if "MakeVector" in str(BEL.get_node_title(n))
             and num_pin(n, "Z") is not None
             and abs(num_pin(n, "Z") + BLOOD_GRAVITY) < 1e-6]
    check("and it is real gravity, not a stylised fraction of it", bool(falls),
          f"expected a (0, 0, -{BLOOD_GRAVITY:.0f}) constant")
    check("each droplet is moved on its own",
          bool(titled(bg, "Set Relative Location")),
          "the old burst moved the whole actor, so every sphere flew at one speed")
    check("the actor itself never moves after it spawns",
          not titled(bg, "SetActorLocation"),
          "the wound does not travel")
    check("the droplets are walked once a frame, not wired one by one",
          len(titled(bg, "For Each Loop")) >= 2,
          "one loop to read the launch velocities at BeginPlay, one to fly them")
    check("velocity is read back off each component, so no parallel table can "
          "fall out of step",
          bool(titled(bg, "GetRelativeTransform")))
    check("size only ever falls away",
          any(num_pin(n, "Min") == 0.0 and num_pin(n, "Max") == 1.0
              for n in by_pins(bg, "Value", "Min", "Max")),
          "the fade is a 0..1 clamp, so nothing can grow past the size it was built")
    check("the splash still cleans itself up",
          any(num_pin(n, "InLifespan") == BLOOD_LIFETIME
              for n in by_pins(bg, "InLifespan")),
          f"{BLOOD_LIFETIME}s")

    # The droplet solver was proved at runtime with a temporary PrintString in the
    # fly loop and a forced spawn at BeginPlay; this is what keeps either from
    # being left behind, the same way the ADS probe is kept out.
    check("no probe survives in the splash's Tick",
          not by_pins(bg, "InString"),
          "a PrintString per droplet per frame is 19 lines a frame")

    blood_vars = {str(v) for v in BEL.list_member_variable_names(blood_bp, False)}
    check("the splash keeps the three per-droplet tables it fills at BeginPlay",
          {"Blobs", "Velocity", "Size", "Fall", "Age"} <= blood_vars,
          str(sorted(blood_vars)))

    # And the half that makes the direction mean anything: the impact has to turn
    # the splash onto the surface normal it hit, and size it by the round.
    check("impacts point the splash down the surface normal",
          bool(titled(wg, "MakeRotFromX")),
          "without it the spray leaves along the world's +X, not out of the wound")
    check("the spray is sized by what the round did",
          any(num_pin(n, "Min") == BLOOD_SCALE_MIN
              and num_pin(n, "Max") == BLOOD_SCALE_MAX
              for n in by_pins(wg, "Value", "Min", "Max")),
          f"a clamp to {BLOOD_SCALE_MIN}..{BLOOD_SCALE_MAX} off Damage / "
          f"{BLOOD_REFERENCE_DAMAGE}")


def run():
    check_blood()
