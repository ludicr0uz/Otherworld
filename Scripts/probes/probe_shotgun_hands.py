"""Down the shotgun's sights the left hand is on the pump, its thumb out of
the sight picture (combat/shotgun_hold.py). The shotgun is held in the
rifle's ready pose, a shipped clip that cups a deep handguard: as the clip
has it the thumb stands 3.7 cm above the shotgun's sight line and the hand is
at the pump's back end. So the shotgun's SupportPoint, the point the support
hand's IK holds the wrist on down the sights, is moved onto the pump.

The ready pose is raised the real way (RaiseForced, the probes' stand-in for
an aim key), then the sights (SightsForced). The live mesh's left finger and
thumb joints are read in the held gun's own frame (+X down the barrel, +Y
right, +Z up) against the pump's measured box (weapon_models.SHOTGUN_PUMP):

  - at the hip the hand is where the clip has it (noted, not checked);
  - down the sights no joint is more than 1.5 cm inside the wood (a joint is
    the bone's axis, about a centimetre under the skin), every joint is
    within 4.75 cm of it, and the hand has come down and forward onto it;
  - and the thumb's joints are under the barrel's top, so under the sight
    line.

Run with --windowed and OW_GRIP_SHOTS=1 to save pictures of both hands from
round the gun to Saved/Screenshots/MacEditor.
"""

SYSTEMS = ('weapons', 'animation')

import os

import unreal

from combat.carry_tuning import RAISE_FORCED_VAR
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.seat_tuning import SEAT_VAR, SIGHTS_FORCED_VAR
from combat.grip import part_placement
from combat.skin import skin_of_mesh
from combat.weapon_models import SHOTGUN_PUMP, shotgun_outline
from combat.weapon_component import vars as WV

WRITABLE = [(WEAPON_COMP_BP_PATH, WV.EquippedIndex),
            (WEAPON_COMP_BP_PATH, WV.NeedsRefresh),
            (WEAPON_COMP_BP_PATH, RAISE_FORCED_VAR),
            (WEAPON_COMP_BP_PATH, SIGHTS_FORCED_VAR)]
SHOTS = bool(os.environ.get("OW_GRIP_SHOTS"))
SEATED = 0.99           # the camera is on the sights
# As verify/shotgun_pose.py, with half a centimetre for the live blend: the
# pose is layered over the idle, and the arms drift a little apart.
SINK_CM = 1.5
REACH_CM = 4.75
# The hand comes at least this far down onto the pump from the hip's (cm).
DOWN_CM = 3.0
# (name, the camera in the gun's frame, what it looks at there), cm.
VIEWS = (("right", (5.0, 45.0, 5.0), (5.0, 0.0, -2.0)),
         ("left", (5.0, -45.0, 5.0), (5.0, 0.0, -2.0)),
         ("pump_right", (36.0, 45.0, 8.0), (34.0, 0.0, 0.0)),
         ("pump_left", (36.0, -45.0, 8.0), (34.0, 0.0, 0.0)),
         ("pump_under", (36.0, 15.0, -40.0), (34.0, 0.0, 0.0)),
         ("both", (20.0, 80.0, 25.0), (15.0, 0.0, 0.0)))


def _pump_distance(point):
    """Signed distance to the pump's box: negative inside."""
    lo, hi = SHOTGUN_PUMP
    d = [max(l - c, c - h) for c, l, h in zip(point.to_tuple(), lo, hi)]
    out = sum(max(x, 0.0) ** 2 for x in d) ** 0.5
    return out if out > 0.0 else max(d)


def _joints(mesh, held, skin):
    """({left finger joint: where}, [the left thumb's joints]) in the held
    gun's frame."""
    into = held.get_actor_transform().inverse()

    def at(bone):
        return unreal.MathLibrary.transform_location(into, mesh.get_socket_location(bone))

    return ({b: at(b) for finger in skin.support_fingers for b in finger},
            [at(b) for b in skin.support_thumb])


def _note_hip(p, mesh, held, skin):
    at, thumb = _joints(mesh, held, skin)
    dist = {b: _pump_distance(v) for b, v in at.items()}
    p.note(f"at the hip (the clip's own hand): joints {min(dist.values()):.2f} to "
           f"{max(dist.values()):.2f} cm from the pump, the thumb's top at z "
           f"{max(v.z for v in thumb):.1f}")
    return sum(v.z for v in at.values()) / len(at)


def _check_fingers(p, mesh, held, skin, hip_z):
    at, thumb = _joints(mesh, held, skin)
    dist = {b: _pump_distance(v) for b, v in at.items()}
    deepest, furthest = min(dist, key=dist.get), max(dist, key=dist.get)
    p.check("down its sights the left hand is under the pump, no finger joint "
            f"more than {SINK_CM:g} cm inside the wood",
            dist[deepest] > -SINK_CM, f"{deepest} {dist[deepest]:.2f} cm")
    p.check(f"...its fingers round it: every joint within {REACH_CM:g} cm of the wood",
            dist[furthest] < REACH_CM, f"{furthest} {dist[furthest]:.2f} cm off")
    z = sum(v.z for v in at.values()) / len(at)
    p.check(f"...the hand at least {DOWN_CM:g} cm lower on the gun than the clip "
            "has it at the hip: the gun's own point holds it",
            hip_z - z > DOWN_CM, f"{hip_z - z:.2f} cm lower")
    centre, _rot, half = part_placement(shotgun_outline(), "Barrel")
    top = centre.z + half.z
    line_z = held.get_editor_property("SightAim").z
    high = max(v.z for v in thumb)
    p.check(f"...and its thumb's joints under the barrel's top (z {top:g}), so "
            f"under the sight line (z {line_z:.1f})",
            high < top < line_z, f"highest joint z {high:.2f}")


def probe(p):
    yield lambda: p.pawn() is not None
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    yield lambda: len(p.get(wc, "Inventory")) > 0
    mesh = p.pawn().get_editor_property("mesh")
    # player_skin() asks the editor's asset subsystem, which a game has not.
    worn = mesh.get_skeletal_mesh_asset().get_path_name().split(".")[0]
    skin = skin_of_mesh(worn)
    p.check("the player wears a known skin", skin is not None, worn)
    bag = [i.get_class().get_name() for i in p.get(wc, "Inventory")]
    p.check("the shotgun is issued", "BP_Shotgun_C" in bag, str(bag))
    if skin is None or "BP_Shotgun_C" not in bag:
        return
    index = bag.index("BP_Shotgun_C")
    p.set(wc, "EquippedIndex", index)
    p.set(wc, "NeedsRefresh", True)
    yield lambda: p.get(wc, "Held") == p.get(wc, "Inventory")[index]
    held = p.get(wc, "Held")
    p.set(wc, RAISE_FORCED_VAR, True)
    yield 0.8
    hip_z = _note_hip(p, mesh, held, skin)
    if SHOTS:
        yield from _shots(p, held, p.get(wc, "Inventory")[bag.index("BP_Matches_C")])
    p.set(wc, SIGHTS_FORCED_VAR, True)
    yield lambda: p.get(wc, SEAT_VAR) > SEATED
    yield 0.3
    _check_fingers(p, mesh, held, skin, hip_z)
    p.set(wc, SIGHTS_FORCED_VAR, False)
    p.set(wc, RAISE_FORCED_VAR, False)


def _shots(p, held, eye_actor):
    """Look at the hands from each of VIEWS. A game has no way to spawn a
    camera from Python, so a spare item from the bag is the view target: an
    actor with no camera is looked through from where it is."""
    eye_actor.detach_from_actor(unreal.DetachmentRule.KEEP_WORLD,
                                unreal.DetachmentRule.KEEP_WORLD,
                                unreal.DetachmentRule.KEEP_WORLD)
    eye_actor.set_actor_hidden_in_game(True)
    p.controller().set_view_target_with_blend(eye_actor, 0.0)
    p.controller().player_camera_manager.set_editor_property("default_fov", 50.0)
    for name, eye, at in VIEWS:
        def place():
            xf = held.get_actor_transform()
            eye_w = xf.transform_location(unreal.Vector(*eye))
            at_w = xf.transform_location(unreal.Vector(*at))
            eye_actor.set_actor_location_and_rotation(
                eye_w, unreal.MathLibrary.find_look_at_rotation(eye_w, at_w), False, False)
        place()
        yield 0.2
        place()
        yield 0.05
        unreal.SystemLibrary.execute_console_command(p.world(), "shot")
        p.note(f"shot: {name}")
        yield 0.3
