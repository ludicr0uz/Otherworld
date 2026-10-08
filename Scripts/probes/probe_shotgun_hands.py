"""With the shotgun up, the left hand lies under the pump and its fingers are
closed on the wood's right side (combat/shotgun_pose.py): the rifle pose it
was held in cups a deep handguard, so the knuckles stood inside the pump and
the fingers 3-5 cm out to its right.

The ready pose is raised the real way (RaiseForced, the probes' stand-in for
an aim key), then the sights (SightsForced), where the support hand's IK
holds the wrist on the gun. Each time the live mesh's left finger joints are
read in the held gun's own frame (+X down the barrel, +Y right, +Z up) against
the pump's measured box (weapon_models.SHOTGUN_PUMP):

  - no joint more than a centimetre inside the wood (a joint is the bone's
    axis, about a centimetre under the skin);
  - every joint within 2.5 cm of it, and none more than 2.5 cm right of it;
  - the last joints above the first: the fingers come UP the far side.

Run with --windowed and OW_GRIP_SHOTS=1 to save pictures of both hands from
round the gun to Saved/Screenshots/MacEditor.
"""

import os

import unreal

from combat.carry_tuning import RAISE_FORCED_VAR
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.seat_tuning import SEAT_VAR, SIGHTS_FORCED_VAR
from combat.skin import skin_of_mesh
from combat.weapon_models import SHOTGUN_PUMP
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
REACH_CM = 3.0
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


def _check_fingers(p, mesh, held, skin, where):
    into = held.get_actor_transform().inverse()
    at = {b: unreal.MathLibrary.transform_location(into, mesh.get_socket_location(b))
          for finger in skin.support_fingers for b in finger}
    dist = {b: _pump_distance(v) for b, v in at.items()}
    deepest, furthest = min(dist, key=dist.get), max(dist, key=dist.get)
    wide = max(at, key=lambda b: at[b].y)
    right = SHOTGUN_PUMP[1][1]
    p.check(f"{where}: the left hand is under the pump, no finger joint more "
            f"than {SINK_CM:g} cm inside the wood",
            dist[deepest] > -SINK_CM, f"{deepest} {dist[deepest]:.2f} cm")
    p.check(f"...its fingers closed on it: every joint within {REACH_CM:g} cm of "
            f"the wood, none more than {REACH_CM:g} cm right of it",
            dist[furthest] < REACH_CM and at[wide].y - right < REACH_CM,
            f"{furthest} {dist[furthest]:.2f} cm off; {wide} "
            f"{at[wide].y - right:.2f} cm right of the pump")
    low = [f[0] for f in skin.support_fingers if at[f[2]].z <= at[f[0]].z]
    p.check("...and each comes up the far side: its last joint above its knuckle",
            not low, str(low))


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
    _check_fingers(p, mesh, held, skin, "the shotgun raised at the hip")
    if SHOTS:
        yield from _shots(p, held, p.get(wc, "Inventory")[bag.index("BP_Matches_C")])
    p.set(wc, SIGHTS_FORCED_VAR, True)
    yield lambda: p.get(wc, SEAT_VAR) > SEATED
    yield 0.3
    _check_fingers(p, mesh, held, skin, "down its sights")
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
