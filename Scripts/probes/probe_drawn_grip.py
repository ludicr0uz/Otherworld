"""How the drawn hands hold each gun: the MetaHuman's (the Body component,
what a player sees), measured against the gun's real mesh, beside the hidden
mannequin's that every other grip check measures.

The grip is fitted on the hidden UEFN mannequin (combat/gun_hold.py,
finger_pose.py) and the gun is attached to its hand; the MetaHuman follows
that mesh through a retargeter that copies rotations, with each wrist pinned
to the mannequin's by a hand IK goal (asset_pipeline/hand_goals.py, since
15 Oct 2026; before it the drawn wrists sat 2.5 to 6.6 cm off). verify/gun_hold.py, verify/finger_pose.py and
probe_gun_hands.py all measure the mannequin against the guns' outline
boxes. This probe reads, for every gun of weapon_models.GUN_HOLDS, in each
state of STATES (lowered standing, walking, crouched and sprinting; down the
sights at pitch up, level and down):

  - each wrist of the drawn body and of the mannequin in the held gun's
    frame, and how far apart the two are;
  - each finger and thumb of both hands of both bodies: its riding points
    (finger_fit.riding: its two outer joints, its tip, the middle of its
    outer bones) as signed distances to the gun's own meshes (every drawn
    static or skeletal mesh on the held actor, read by GeometryScript in the
    actor's frame; negative inside), made into the finger's penetration and
    gap a skin off its axis (grip_report.py).

Rendered (--windowed), it saves two close pictures per gun and state, from
the left and the right, to Saved/Screenshots/MacEditor/grip_<gun>_<state>_
<side>.png. The tables go to the log (NOTE lines) and to
Saved/grip_report/drawn_grip.md.

The checks hold the staging (both bodies there and posed, each gun in hand,
its meshes read, each state reached, the pictures written) and, since the
retarget pins the drawn wrists to the mannequin's (asset_pipeline/
hand_goals.py), each drawn wrist within WRIST_PINNED_CM of the mannequin's
and each drawn elbow within ELBOW_NEAR_CM; the fingers are a measurement,
for a person to read.

  python3 Scripts/dev/uepy.py --game --windowed --probe Scripts/probes/probe_drawn_grip.py
"""

SYSTEMS = ('weapons', 'animation')

import os

import unreal

from combat import finger_fit, gun_hold
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.seat_tuning import SEAT_VAR, SIGHTS_FORCED_VAR
from combat.skin import skin_of_mesh
from combat.sprint_tuning import SPRINT_FORCED_VAR
from combat.weapon_component.stance import CROUCH, STAND
from combat.weapon_component import vars as WV
from combat.carry_tuning import RAISE_FORCED_VAR
from combat.weapon_models import GUN_HOLDS
from graphics_menu.dev_consts import DEV_GUNS_REQUEST_VAR
from probes import grip_report as R
from probes.metahuman_follow import _comp
from probes.probe_sight_align import HUD_BP_PATH

WRITABLE = [(HUD_BP_PATH, DEV_GUNS_REQUEST_VAR)] + [(WEAPON_COMP_BP_PATH, v) for v in
            (WV.Stance, RAISE_FORCED_VAR, SIGHTS_FORCED_VAR, SPRINT_FORCED_VAR)]

# (label, forward input, sprint, stance, sights, pitch, seconds held).
STATES = (
    ("standing", 0.0, False, STAND, False, 0.0, 1.2),
    ("walking", 0.45, False, STAND, False, 0.0, 1.4),
    ("crouched", 0.0, False, CROUCH, False, 0.0, 1.4),
    ("sprinting", 1.0, True, STAND, False, 0.0, 1.8),
    ("ads pitch up", 0.0, False, STAND, True, 25.0, 1.2),
    ("ads level", 0.0, False, STAND, True, 0.0, 1.0),
    ("ads pitch down", 0.0, False, STAND, True, -25.0, 1.0),
)
SEATED = 0.99
# The drawn wrists are pinned to the mannequin's by hand IK goals in the
# retarget (asset_pipeline/hand_goals.py): a wrist further off than this is
# not pinned.
WRIST_PINNED_CM = 1.0
# ...and turned as the mannequin's hand is (the gun hangs off its palm).
HAND_TURN_DEG = 3.0
# The elbow gives what the pin takes up (the two arms are not one length):
# 3 to 6 cm, and the left 9 to 11 cm down a long gun's sights, its arm
# reaching furthest (15 Oct 2026), where the pictures show a natural arm.
# Further than this off the mannequin's reads as a broken or flipped arm.
ELBOW_NEAR_CM = 12.0
SEAT_WAIT_S = 4.0
FINGERS = ("thumb", "index", "middle", "ring", "little")
EYE_FOV = 50.0
# The close pictures' camera off the hands' middle (cm): (name, right, ahead,
# up). The left one is low and in front: level with the hands, the left
# forearm hides them down the sights.
VIEWS = (("left", -35.0, 40.0, -25.0), ("right", 55.0, 27.0, 12.0))
SHOTS_DIR = os.path.join(unreal.Paths.project_saved_dir(), "Screenshots", "MacEditor")
REPORT = os.path.join(unreal.Paths.project_saved_dir(), "grip_report", "drawn_grip.md")
GS = unreal.GeometryScript_MeshSpatial
OPTS = unreal.GeometryScriptSpatialQueryOptions()


def _surfaces(held):
    """[(component name, DynamicMesh, BVH)] of every drawn mesh on the held
    gun, each moved into the actor's frame."""
    gun = held.get_actor_transform()
    out = []
    for c in held.get_components_by_class(unreal.MeshComponent):
        if not c.is_visible():
            continue
        if isinstance(c, unreal.StaticMeshComponent) and c.static_mesh:
            dm = unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(
                c.static_mesh, unreal.DynamicMesh(),
                unreal.GeometryScriptCopyMeshFromAssetOptions(),
                unreal.GeometryScriptMeshReadLOD())[0]
        elif isinstance(c, unreal.SkeletalMeshComponent) and c.get_skeletal_mesh_asset():
            dm = unreal.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(
                c.get_skeletal_mesh_asset(), unreal.DynamicMesh(),
                unreal.GeometryScriptCopyMeshFromAssetOptions(),
                unreal.GeometryScriptMeshReadLOD())[0]
        else:
            continue
        if unreal.GeometryScript_MeshQueries.get_num_triangle_i_ds(dm) == 0:
            continue
        rel = unreal.MathLibrary.make_relative_transform(c.get_world_transform(), gun)
        unreal.GeometryScript_MeshTransforms.transform_mesh(dm, rel)
        out.append((c.get_name(), dm, GS.build_bvh_for_mesh(dm)[1]))
    return out


def _signed(surfaces, pt):
    """The point's distance to the gun's surface (cm), negative inside it."""
    v = unreal.Vector(*pt)
    found = []
    for _name, dm, bvh in surfaces:
        q = GS.find_nearest_point_on_mesh(dm, bvh, v, OPTS)[1].position
        d = (v - q).length()
        found.append(-d if GS.is_point_inside_mesh(dm, bvh, v, OPTS)[1] else d)
    inside = [d for d in found if d < 0.0]
    return min(inside) if inside else min(found)


def _points(mesh, gun, bones, tip_cm):
    """A finger's joints and tip in the gun's frame (gun_hold.finger_points)."""
    comp = {}
    for bone in bones:
        xf = unreal.MathLibrary.make_relative_transform(mesh.get_socket_transform(bone), gun)
        t, q = xf.translation, xf.rotation
        comp[bone] = ((t.x, t.y, t.z), (q.x, q.y, q.z, q.w))
    return gun_hold.finger_points(bones, comp, tip_cm)


def _hands(skin):
    """{(hand, finger): (bones, tip cm)} of both hands, by the skin's rows;
    the MetaHuman's bones bear the same names."""
    out = {}
    for hand, thumb, fingers in (("right", skin.grip_thumb, skin.grip_fingers),
                                 ("left", skin.support_thumb, skin.support_fingers)):
        out[(hand, "thumb")] = (thumb, gun_hold.THUMB_TIP_CM)
        for name, bones in zip(FINGERS[1:], fingers):
            out[(hand, name)] = (bones, gun_hold.FINGER_TIP_CM)
    return out


def _measure(body, mannequin, held, surfaces, hands):
    """{"drawn"/"mannequin": {"wrist"/"elbow": {hand: point}, "fingers":
    {(hand, finger): signed distances}}} in the gun's frame."""
    gun = held.get_actor_transform()
    into = gun.inverse()
    out = {}
    for label, mesh in (("drawn", body), ("mannequin", mannequin)):
        wrist, elbow, turn = {}, {}, {}
        for hand, bone, arm in (("right", "hand_r", "lowerarm_r"),
                                ("left", "hand_l", "lowerarm_l")):
            v = unreal.MathLibrary.transform_location(into, mesh.get_socket_location(bone))
            wrist[hand] = (v.x, v.y, v.z)
            q = mesh.get_socket_rotation(bone).quaternion()
            turn[hand] = (q.x, q.y, q.z, q.w)
            v = unreal.MathLibrary.transform_location(into, mesh.get_socket_location(arm))
            elbow[hand] = (v.x, v.y, v.z)
        fingers = {k: [_signed(surfaces, pt) for pt in
                       finger_fit.riding(_points(mesh, gun, bones, tip))]
                   for k, (bones, tip) in hands.items()}
        out[label] = {"wrist": wrist, "elbow": elbow, "turn": turn, "fingers": fingers}
    return out


def _rows(gun, state, m):
    """The report's rows of one gun in one state."""
    d, k = m["drawn"], m["mannequin"]
    wrist = [R.offset(d[j][h], k[j][h]) for j in ("wrist", "elbow") for h in ("right", "left")]
    wrist += [R.angle(d["turn"][h], k["turn"][h]) for h in ("right", "left")]
    rows = []
    for hand in ("right", "left"):
        for f in FINGERS:
            rows.append([gun, state, hand, f, R.finger_cell(d["fingers"][(hand, f)]),
                         R.finger_cell(k["fingers"][(hand, f)])])
    return wrist, rows


def _camera(world):
    target = unreal.RenderingLibrary.create_render_target2d(
        world, 1280, 720, unreal.TextureRenderTargetFormat.RTF_RGBA8)
    eye = unreal.OtherworldLoadLibrary.spawn_actor_at(
        world, unreal.SceneCapture2D, unreal.Transform())
    cap = eye.capture_component2d
    cap.set_editor_property("texture_target", target)
    cap.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    cap.set_editor_property("fov_angle", EYE_FOV)
    cap.set_editor_property("capture_every_frame", True)
    cap.set_editor_property("always_persist_rendering_state", True)
    eye.root_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    return eye, target


def _aim_eye(eye, player, body, view):
    """The camera where ``view`` of VIEWS puts it, looking at the hands'
    middle."""
    _name, side, ahead, up = view
    mid = (body.get_socket_location("hand_r") + body.get_socket_location("hand_l")) * 0.5
    at = (mid + player.get_actor_right_vector() * side
          + player.get_actor_forward_vector() * ahead + unreal.Vector(0.0, 0.0, up))
    eye.set_actor_location_and_rotation(
        at, unreal.MathLibrary.find_look_at_rotation(at, mid), False, True)


def _clear_npcs(p):
    """Every AI pawn gone: the pack must not end a run that takes a minute."""
    for c in unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController):
        pawn = c.get_controlled_pawn()
        if pawn is not None:
            pawn.destroy_actor()


def probe(p):
    yield lambda: p.pawn() is not None
    player, pc, world = p.pawn(), p.controller(), p.world()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    yield lambda: len(p.get(wc, "Inventory")) > 0
    _clear_npcs(p)
    mannequin = player.get_editor_property("mesh")
    body = _comp(player, "Body")
    skin = skin_of_mesh(mannequin.get_skeletal_mesh_asset().get_path_name().split(".")[0])
    p.check("the player wears a known skin and a drawn Body",
            skin is not None and body is not None and body.get_skeletal_mesh_asset() is not None,
            f"{skin is not None}, {body}")
    if skin is None or body is None:
        return
    hands = _hands(skin)
    bones = {b for bs, _ in hands.values() for b in bs} | {"hand_r", "hand_l"}
    missing = [b for b in sorted(bones)
               if body.get_bone_index(b) < 0 or mannequin.get_bone_index(b) < 0]
    p.check("both bodies have every hand bone measured", not missing, str(missing))
    for m in (body, mannequin):
        m.set_editor_property("visibility_based_anim_tick_option",
                              unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
    rendered = "nullrhi" not in unreal.SystemLibrary.get_command_line().lower()
    eye, target = _camera(world) if rendered else (None, None)
    os.makedirs(SHOTS_DIR, exist_ok=True)
    p.set(p.hud(), DEV_GUNS_REQUEST_VAR, True)
    yield lambda: not p.get(p.hud(), DEV_GUNS_REQUEST_VAR)
    bag = [i.get_class().get_name() for i in p.get(wc, "Inventory")]
    guns = [name for name in GUN_HOLDS if name + "_C" in bag]
    p.check("every gun of GUN_HOLDS is in the bag", len(guns) == len(GUN_HOLDS), str(bag))
    wrists, rows, shots, summary = [], [], [], []
    yaw = pc.get_control_rotation().yaw
    for n, name in enumerate(guns):
        _clear_npcs(p)
        index = bag.index(name + "_C")
        p.hold(wc, index)
        yield lambda: p.get(wc, "Held") == p.get(wc, "Inventory")[index]
        held = p.get(wc, "Held")
        surfaces = _surfaces(held)
        p.check(f"{name}: its meshes are read", bool(surfaces),
                ", ".join(s[0] for s in surfaces))
        # Each gun the other way, so the runs stay on the level; a sprint
        # is forward of the view, so the view turns with it.
        facing = yaw + 180.0 * (n % 2)
        ahead = unreal.MathLibrary.get_forward_vector(
            unreal.Rotator(roll=0.0, pitch=0.0, yaw=facing))
        for state, fwd, sprint, stance, sights, pitch, hold_s in STATES:
            _clear_npcs(p)
            p.set(wc, WV.Stance, stance)
            p.set(wc, SPRINT_FORCED_VAR, sprint)
            p.set(wc, RAISE_FORCED_VAR, sights)
            p.set(wc, SIGHTS_FORCED_VAR, sights)
            look = unreal.Rotator(roll=0.0, pitch=pitch, yaw=facing)
            t0 = unreal.GameplayStatics.get_time_seconds(world)

            def step():
                # Held every frame: raised, the view's pitch up is drawn back
                # (it read +2 of +25 set once).
                pc.set_control_rotation(look)
                if fwd:
                    player.add_movement_input(ahead, fwd)
                return unreal.GameplayStatics.get_time_seconds(world) - t0 >= hold_s
            yield step
            if sights:
                end = unreal.GameplayStatics.get_time_seconds(world) + SEAT_WAIT_S
                yield lambda: (pc.set_control_rotation(look) or p.get(wc, SEAT_VAR) > SEATED
                               or unreal.GameplayStatics.get_time_seconds(world) > end)
            speed = player.get_velocity().length()
            seat = p.get(wc, SEAT_VAR)
            reached = (seat > SEATED) if sights else (seat < 0.01 and (speed > 50.0) == bool(fwd))
            p.check(f"{name}, {state}: the state is reached",
                    reached, f"seat {seat:.2f}, {speed:.0f} cm/s, "
                    f"view pitch {pc.get_control_rotation().pitch:+.0f}")
            m = _measure(body, mannequin, held, surfaces, hands)
            wrist, got = _rows(name, state, m)
            wrists.append([name, state, f"{speed:.0f}"] + wrist)
            rows += got
            pen, gap = R.worst(m["drawn"]["fingers"])
            summary.append([name, state, wrist[0], wrist[1],
                            f"{pen[0][0]} {pen[0][1]} {pen[1]:.2f}" if pen else "none",
                            f"{gap[0][0]} {gap[0][1]} {gap[1]:.2f}" if gap else "none"])
            p.check(f"{name}, {state}: the drawn wrists are on the mannequin's",
                    max(wrist[:2]) <= WRIST_PINNED_CM,
                    f"right {wrist[0]:.2f} cm, left {wrist[1]:.2f} cm "
                    f"(at most {WRIST_PINNED_CM})")
            p.check(f"{name}, {state}: the drawn hands are turned as the mannequin's",
                    max(wrist[4:]) <= HAND_TURN_DEG,
                    f"right {wrist[4]:.1f} deg, left {wrist[5]:.1f} deg "
                    f"(at most {HAND_TURN_DEG})")
            p.check(f"{name}, {state}: the drawn elbows stay by the mannequin's",
                    max(wrist[2:4]) <= ELBOW_NEAR_CM,
                    f"right {wrist[2]:.2f} cm, left {wrist[3]:.2f} cm "
                    f"(at most {ELBOW_NEAR_CM})")
            p.note(f"{name}, {state}: drawn wrist off the mannequin's: right "
                   f"{wrist[0]:.2f} cm, left {wrist[1]:.2f} cm; turned right {wrist[4]:.1f} "
                   f"deg, left {wrist[5]:.1f}; elbow right "
                   f"{wrist[2]:.2f} cm, left {wrist[3]:.2f} cm; drawn fingers: "
                   + ", ".join(f"{h[0]}.{f} {R.finger_cell(v)}"
                               for (h, f), v in m["drawn"]["fingers"].items()))
            if eye is not None:
                for view in VIEWS:
                    _aim_eye(eye, player, body, view)
                    shot_at = unreal.GameplayStatics.get_time_seconds(world) + 0.15
                    yield lambda: (pc.set_control_rotation(look) or
                                   unreal.GameplayStatics.get_time_seconds(world) > shot_at)
                    file = "_".join(["grip", name[3:].lower(), state.replace(" ", "_"), view[0]]) + ".png"
                    unreal.RenderingLibrary.export_render_target(world, target, SHOTS_DIR, file)
                    shots.append(file)
        p.set(wc, SIGHTS_FORCED_VAR, False)
        p.set(wc, RAISE_FORCED_VAR, False)
        p.set(wc, SPRINT_FORCED_VAR, False)
        p.set(wc, WV.Stance, STAND)
        pc.set_control_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=facing))
        yield 0.6
    if eye is not None:
        found = [f for f in shots if os.path.exists(os.path.join(SHOTS_DIR, f))]
        p.check("the close pictures are written", shots and len(found) == len(shots),
                f"{len(found)} of {len(shots)} in {SHOTS_DIR}")
    else:
        p.note("no pictures: run with --windowed for them")
    lines = ["# The drawn hands on the guns", "",
             f"Skin a finger's surface stands off its axis: {R.SKIN_CM} cm. "
             "\"in X\": its skin X cm inside the gun's mesh; \"off X\": X cm off it.", "",
             "## Worst drawn finger, and the drawn wrist off the mannequin's (cm)", ""]
    lines += R.table(["gun", "state", "right wrist", "left wrist", "deepest in",
                      "widest off"], summary)
    lines += ["", "## Wrist and elbow offset, drawn vs mannequin (cm)", ""]
    lines += R.table(["gun", "state", "speed cm/s", "right wrist", "left wrist",
                      "right elbow", "left elbow", "right turn deg", "left turn deg"],
                     wrists)
    lines += ["", "## Each finger: drawn and mannequin", ""]
    lines += R.table(["gun", "state", "hand", "finger", "drawn", "mannequin"], rows)
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w") as f:
        f.write("\n".join(lines) + "\n")
    p.note(f"report: {REPORT}")
