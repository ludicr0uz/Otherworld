"""verify.bullet_impact -- BP_BulletImpact: the chips and dust a bullet knocks
off the scenery, and the fire graph spawning it where the blood is not.
"""

import math

import unreal

from combat.blood import BLOOD_CONE_DEG
from combat.bullet_impact import (
    IMPACT_CHIPS, IMPACT_CONE_DEG, IMPACT_DRAG, IMPACT_DUST, IMPACT_GRAVITY,
    IMPACT_LIFETIME, _impact_pieces,
)
from combat.burst import BURST_PIECE_PREFIX, BURST_VELOCITY_ENCODE
from combat.materials import IMPACT_CHIP_COLOUR, IMPACT_DUST_COLOUR
from combat.paths import (
    BULLET_IMPACT_BP_PATH, CUBE, MAT_IMPACT_CHIP, MAT_IMPACT_DUST, SPHERE,
)
from combat.verify.common import (
    BEL, PIN, by_pins, check, component_template, components, graph, load,
    num_pin, titled,
)
from combat.verify import fx as fxv
from combat import fx_vars as FX
from combat.verify.fixtures import w, wg
from combat.weapon_component.surface_impact import IMPACT_CLASS_VAR


def _flat(path):
    """(base colour, roughness, emissive node, expression count) of a flat material."""
    mel = unreal.MaterialEditingLibrary
    mat = load(path)
    base = mel.get_material_property_input_node(
        mat, unreal.MaterialProperty.MP_BASE_COLOR)
    rough = mel.get_material_property_input_node(
        mat, unreal.MaterialProperty.MP_ROUGHNESS)
    colour = base.get_editor_property("constant") if base else None
    return ((colour.r, colour.g, colour.b) if colour else None,
            rough.get_editor_property("r") if rough else None,
            mel.get_material_property_input_node(
                mat, unreal.MaterialProperty.MP_EMISSIVE_COLOR),
            mel.get_num_material_expressions(mat))


# ─── The stuff: dry earth, not blood ─────────────────────────────────────────

def check_impact_materials():
    looks = {}
    for path, want in ((MAT_IMPACT_CHIP, IMPACT_CHIP_COLOUR),
                       (MAT_IMPACT_DUST, IMPACT_DUST_COLOUR)):
        name = path.rsplit("/", 1)[1]
        colour, rough, emissive, count = _flat(path)
        looks[path] = colour
        check(f"{name} carries the builder's colour",
              colour is not None
              and all(abs(a - b) < 1e-6 for a, b in zip(want, colour)), str(colour))
        check(f"{name} is lit rather than emissive", emissive is None,
              "a glowing chip sits on top of the scene's lighting, as blood would")
        check(f"{name} is dry and dull, which is what tells it from blood",
              rough is not None and rough >= 0.8, f"roughness {rough}")
        check(f"{name} is earth, not red",
              colour is not None and colour[0] / max(colour[1], 1e-6) < 2.0,
              f"R/G {colour[0] / max(colour[1], 1e-6):.2f}" if colour else "")
        check(f"{name} carries no expressions left over from an earlier build",
              count == 3, f"{count} expressions")
    chip, dust = looks[MAT_IMPACT_CHIP], looks[MAT_IMPACT_DUST]
    check("the dust is paler than the chips it came off",
          chip is not None and dust is not None and min(dust) > max(chip),
          f"dust {dust}, chips {chip}")


# ─── The burst: chips and dust, laid out from a seed ─────────────────────────

def check_impact_burst():
    bp = load(BULLET_IMPACT_BP_PATH)
    want = _impact_pieces()
    have = sorted(c for c in set(components(bp)) if c.startswith(BURST_PIECE_PREFIX))
    check(f"the impact has {len(want)} pieces: {IMPACT_CHIPS} chips and "
          f"{IMPACT_DUST} of dust",
          len(have) == len(want) == IMPACT_CHIPS + IMPACT_DUST, str(have))
    placed = dressed = unshadowed = True
    turns = set()
    for i, piece in enumerate(want):
        t = component_template(bp, f"{BURST_PIECE_PREFIX}{i}")
        if t is None:
            placed = dressed = False
            break
        loc = t.get_editor_property("relative_location")
        size = t.get_editor_property("relative_scale3d")
        placed &= (all(abs(a - b) < 1e-3
                       for a, b in zip((loc.x, loc.y, loc.z), piece.velocity))
                   and abs(size.x - piece.scale) < 1e-4
                   and abs(size.y - piece.scale) < 1e-4
                   and abs(size.z - piece.scale) < 1e-4)
        mesh = t.get_editor_property("static_mesh")
        mats = list(t.get_editor_property("override_materials"))
        dressed &= (mesh is not None
                    and mesh.get_path_name().split(".")[0] == piece.mesh
                    and len(mats) == 1 and mats[0] is not None
                    and mats[0].get_path_name().split(".")[0] == piece.material)
        unshadowed &= not t.get_editor_property("cast_shadow")
        if piece.turn is not None:
            rot = t.get_editor_property("relative_rotation")
            placed &= all(abs(a - b) < 1e-2 for a, b in
                          zip((rot.pitch, rot.yaw, rot.roll), piece.turn))
            turns.add((round(rot.pitch, 1), round(rot.yaw, 1), round(rot.roll, 1)))
    check("every piece carries the seeded launch velocity in its location", placed)
    check("chips are cubes in the chip material, dust is spheres in the dust's",
          dressed
          and [p.mesh for p in want] == [CUBE] * IMPACT_CHIPS + [SPHERE] * IMPACT_DUST
          and [p.material for p in want]
          == [MAT_IMPACT_CHIP] * IMPACT_CHIPS + [MAT_IMPACT_DUST] * IMPACT_DUST)
    check("every chip is turned its own way", len(turns) == IMPACT_CHIPS,
          f"{len(turns)} distinct turns: square to the actor, ten cubes read as "
          "one lattice")
    check("no piece casts a shadow", unshadowed,
          f"{len(want)} shadow casters per pellet, eight pellets to a shell")

    # Wider than blood's cone, so a single chip may leave more sideways than
    # out. What has to hold is that none goes in, and that the burst as a
    # whole leans along the normal rather than off to one side.
    out = sum(p.velocity[0] for p in want)
    aside = math.hypot(sum(p.velocity[1] for p in want),
                       sum(p.velocity[2] for p in want))
    check("the burst comes off the surface, along +X, the hit normal",
          min(p.velocity[0] for p in want) > 0.0 and out > 2.0 * aside,
          f"summed {out * BURST_VELOCITY_ENCODE:.0f} cm/s out against "
          f"{aside * BURST_VELOCITY_ENCODE:.0f} aside; a piece thrown into the "
          "surface would fly through it")
    check("a surface shatters wider than a wound sprays",
          IMPACT_CONE_DEG > BLOOD_CONE_DEG and IMPACT_CONE_DEG < 90.0,
          f"{IMPACT_CONE_DEG:.0f} deg against blood's {BLOOD_CONE_DEG:.0f}")
    speeds = [math.sqrt(sum(v * v for v in p.velocity)) * BURST_VELOCITY_ENCODE
              for p in want]
    chips, dust = speeds[:IMPACT_CHIPS], speeds[IMPACT_CHIPS:]
    check("the chips leave at different speeds",
          max(chips) / max(min(chips), 1e-6) >= 2.0,
          f"{min(chips):.0f}-{max(chips):.0f} cm/s")
    check("the dust hangs at the hole while the chips leave",
          sum(dust) / len(dust) < sum(chips) / len(chips) / 2.0
          and max(dust) < max(chips),
          f"dust <= {max(dust):.0f} cm/s, chips up to {max(chips):.0f} cm/s")
    # 100 cm is the engine cube's side and the sphere's diameter at scale 1.
    biggest = max(p.scale for p in want) * 100.0
    check("chips are chips", biggest <= 4.0, f"largest {biggest:.1f} cm across")
    check("the impact is over fast", 0.3 <= IMPACT_LIFETIME <= 0.9,
          f"{IMPACT_LIFETIME}s")

    bg = graph(bp).list_all_nodes()
    check("the pieces fly blood's solver: drag, with this burst's coefficient",
          bool(titled(bg, "Exp"))
          and any(abs((num_pin(n, "B") if num_pin(n, "B") is not None else 0.0)
                      + IMPACT_DRAG) < 1e-6 for n in by_pins(bg, "A", "B")),
          f"-{IMPACT_DRAG} on a B pin")
    falls = [n for n in bg if "MakeVector" in str(BEL.get_node_title(n))
             and num_pin(n, "Z") is not None
             and abs(num_pin(n, "Z") + IMPACT_GRAVITY) < 1e-6]
    check("...under real gravity, turned into the actor's frame",
          bool(falls) and bool(titled(bg, "InverseTransformDirection")),
          f"expected a (0, 0, -{IMPACT_GRAVITY:.0f}) constant")
    check("each piece is moved on its own, and the actor never",
          bool(titled(bg, "Set Relative Location"))
          and not titled(bg, "SetActorLocation"))
    check("size only ever falls away",
          any(num_pin(n, "Min") == 0.0 and num_pin(n, "Max") == 1.0
              for n in by_pins(bg, "Value", "Min", "Max")))
    check("the impact cleans itself up",
          any(num_pin(n, "InLifespan") == IMPACT_LIFETIME
              for n in by_pins(bg, "InLifespan")),
          f"{IMPACT_LIFETIME}s")
    check("no probe survives in the impact's Tick", not by_pins(bg, "InString"))


# ─── The fire graph: scenery chips, bodies bleed, never both ─────────────────

def _fed_by(node, pin):
    """(owning node, pin name) of whatever is linked into ``node``'s ``pin``."""
    return [(PIN.get_owning_node(q), str(PIN.get_pin_name(q)).replace(" ", ""))
            for q in PIN.list_connected_pins(BEL.find_input_pin(node, pin))]


def _spawn_of(var):
    """The SpawnActor nodes whose Class is the weapon component's ``var``."""
    return [n for n in by_pins(wg, "Class", "SpawnTransform")
            if any(str(BEL.get_node_title(src)) == f"Get {var}"
                   for src, _pin in _fed_by(n, "Class"))]


def check_impact_spawn():
    got = w.get_editor_property(IMPACT_CLASS_VAR)
    check(f"{IMPACT_CLASS_VAR} points at BP_BulletImpact_C",
          got is not None and got.get_name() == "BP_BulletImpact_C",
          got.get_name() if got else "None")
    # The axe's chips off a tree are the chop's (verify/chop.py), a thrown
    # blade's the throw's (verify/throw_strike.py): the pellet's bursts are
    # Fx_PelletHit's, told to every screen a shot at a time (verify/shot_hits.py).
    chips = fxv.in_fx(FX.PELLET_HIT, _spawn_of(IMPACT_CLASS_VAR))
    blood = fxv.in_fx(FX.PELLET_HIT, _spawn_of("BloodClass"))
    check("Fx_PelletHit spawns the impact once, and the blood once",
          len(chips) == 1 and len(blood) == 1,
          f"{len(chips)} impact spawn(s), {len(blood)} blood spawn(s)")
    if len(chips) != 1 or len(blood) != 1:
        return
    picks = _fed_by(chips[0], "execute") + _fed_by(blood[0], "execute")
    check("...one on each arm of a Branch on the event's Blood",
          [pin for _n, pin in picks] == ["else", "then"]
          and len({n.get_path_name() for n, _pin in picks}) == 1
          and all(_fed_by(n, "Condition") and _fed_by(n, "Condition")[0][0]
                  == fxv.event(FX.fx_event(FX.PELLET_HIT)) for n, _pin in picks),
          str([pin for _n, pin in picks]))
    chip_at, blood_at = (_fed_by(chips[0], "SpawnTransform"),
                         _fed_by(blood[0], "SpawnTransform"))
    check("both are spawned at the one transform: the impact point, turned onto "
          "the surface normal, sized by the round",
          len(chip_at) == 1 and len(blood_at) == 1
          and chip_at[0][0].get_path_name() == blood_at[0][0].get_path_name()
          and bool(_fed_by(chip_at[0][0], "Rotation"))
          and bool(_fed_by(chip_at[0][0], "Scale")),
          "the same MakeTransform node")
    check("the impact spawns whatever it overlaps",
          "AlwaysSpawn" in str(PIN.get_pin_value(
              BEL.find_input_pin(chips[0], "CollisionHandlingOverride"))),
          "it is spawned on a surface, which is by definition a collision")


def run():
    check_impact_materials()
    check_impact_burst()
    check_impact_spawn()
