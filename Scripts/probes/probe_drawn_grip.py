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
and each drawn elbow within ELBOW_NEAR_CM; and the fitted fingers
(A_DrawnGrip, combat/drawn_grip_graph.py, since 15 Oct 2026): each hand's
layer weighed in (the left only on a long gun or a raised one), no finger
of a hand on the gun deeper in it than drawn_grip_consts.PRESSED_CM
(PRESSED_CM_BY_GUN's own, CARRY_PRESSED_CM carried), none further off it
than OFF_CM (CARRY_OFF_CM carried, and not CARRY_OFF's), and the right
index's pad at the gun's TRIGGER; on the pistol (THUMB_REST) the right thumb
under the sights and forward along the frame's left side (combat/
drawn_thumb.py). A handgun's left fingers are measured to
the nearer of the gun and the right fingers, which they lie on.

  python3 Scripts/dev/uepy.py --game --windowed --probe Scripts/probes/probe_drawn_grip.py
"""

SYSTEMS = ('weapons', 'animation')

import json
import os

import unreal

from combat import drawn_grip as D
from combat import finger_fit, gun_hold
from combat.drawn_grip_consts import (
    CARRY_OFF, CARRY_OFF_CM, CARRY_PRESSED_CM, GRIP_LEFT_VAR, GRIP_RIGHT_VAR, HANDGUNS, OFF_CM,
    PRESSED_CM, PRESSED_CM_BY_GUN, THUMB_CEILING_CM, THUMB_NEAR_CM, THUMB_REST, TRIGGER,
    TRIGGER_NEAR_CM, TRIGGER_NEAR_CM_BY_GUN,
)
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.seat_tuning import SEAT_VAR, SIGHTS_FORCED_VAR
from combat.skin import skin_of_mesh
from combat.sprint_tuning import SPRINT_FORCED_VAR
from combat.weapon_component.stance import CROUCH, STAND
from combat.weapon_component import vars as WV
from combat.carry_pose_consts import CARRY_SEATED_GUNS
from combat.carry_tuning import LOWERED_VAR, RAISE_FORCED_VAR
from combat.weapon_models import GUN_HOLDS
from graphics_menu.dev_consts import DEV_GUNS_REQUEST_VAR
from probes import grip_report as R
from probes.metahuman_follow import _comp
from probes.probe_sight_align import HUD_BP_PATH

WRITABLE = [(HUD_BP_PATH, DEV_GUNS_REQUEST_VAR)] + [(WEAPON_COMP_BP_PATH, v) for v in
            (WV.Stance, RAISE_FORCED_VAR, SIGHTS_FORCED_VAR, SPRINT_FORCED_VAR)]

# (label, forward input, sprint, stance, raised, sights, pitch, seconds held).
# "raised" is the ready pose off the sights (an aim over the shoulder, a shot
# from the hip): the left hand where the clip has it.
STATES = (
    ("standing", 0.0, False, STAND, False, False, 0.0, 1.2),
    ("walking", 0.45, False, STAND, False, False, 0.0, 1.4),
    ("crouched", 0.0, False, CROUCH, False, False, 0.0, 1.4),
    ("sprinting", 1.0, True, STAND, False, False, 0.0, 1.8),
    ("raised", 0.0, False, STAND, True, False, 0.0, 1.2),
    ("ads pitch up", 0.0, False, STAND, True, True, 25.0, 1.2),
    ("ads level", 0.0, False, STAND, True, True, 0.0, 1.0),
    ("ads pitch down", 0.0, False, STAND, True, True, -25.0, 1.0),
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
# Wall seconds: five guns in eight states, and windowed two pictures each
# (about 50 s bare, past the runner's 60 rendered).
TIMEOUT = 180.0
FINGERS = ("thumb", "index", "middle", "ring", "little")
EYE_FOV = 50.0
# The close pictures' camera off the hands' middle (cm): (name, right, ahead,
# up). The left one is low and in front: level with the hands, the left
# forearm hides them down the sights.
VIEWS = (("left", -35.0, 40.0, -25.0), ("right", 55.0, 27.0, 12.0))
SHOTS_DIR = os.path.join(unreal.Paths.project_saved_dir(), "Screenshots", "MacEditor")
REPORT = os.path.join(unreal.Paths.project_saved_dir(), "grip_report", "drawn_grip.md")
# What the drawn finger fit is made from (combat/drawn_grip_bake.py): each drawn
# hand in the gun's frame and every bone under it in its parent's, per gun
# and state.
CAPTURE = os.path.join(unreal.Paths.project_saved_dir(), "grip_report", "drawn_hands.json")
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


def _measure(body, mannequin, held, surfaces, hands, fist=False):
    """{"drawn"/"mannequin": {"wrist"/"elbow": {hand: point}, "fingers":
    {(hand, finger): signed distances}}} in the gun's frame. ``fist``: a
    handgun, whose left fingers lie on the right fist as well as on the
    gun (finger_pose.fist, drawn_grip_bake), so theirs are to the nearer of
    the two (the right fingers' skin a finger_fit.SKIN_CM round their bones)."""
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
        pts = {k: _points(mesh, gun, bones, tip) for k, (bones, tip) in hands.items()}
        right = finger_fit.Capsules([s for (h, f), q in pts.items() if h == "right"
                                     and f != "thumb" for s in zip(q, q[1:])])
        fingers = {k: [min(_signed(surfaces, pt), right.distance(pt)) if fist and k[0] == "left"
                       else _signed(surfaces, pt) for pt in finger_fit.riding(q)]
                   for k, q in pts.items()}
        out[label] = {"wrist": wrist, "elbow": elbow, "turn": turn, "fingers": fingers}
    return out


def _grip(p, name, state, raised, body, held, hands, m):
    """The fitted fingers' checks (drawn_grip_consts' bounds): the layer
    on, no finger of a hand on the gun in it deeper than its bound, none
    further off it (but CARRY_OFF's, carried, on a gun whose carry is not
    seated: CARRY_SEATED_GUNS), and the right index's pad at
    the trigger."""
    anim = body.get_anim_instance()
    weight = {h: anim.get_editor_property(v) for h, v in
              (("right", GRIP_RIGHT_VAR), ("left", GRIP_LEFT_VAR))}
    on = {"right": True, "left": raised or name not in HANDGUNS}
    p.check(f"{name}, {state}: the fitted hands are laid over the drawn fingers",
            all(weight[h] > 0.99 if on[h] else weight[h] < 0.01 for h in on), f"right {weight['right']:.2f}, left {weight['left']:.2f}")
    fingers = {k: R.finger(v) for k, v in m["drawn"]["fingers"].items() if on[k[0]]}
    pressed = PRESSED_CM_BY_GUN.get(name, PRESSED_CM) if raised else CARRY_PRESSED_CM
    pen = max(fingers.items(), key=lambda kv: kv[1][1])
    held_on = {k: v for k, v in fingers.items()
               if raised or name in CARRY_SEATED_GUNS or k not in CARRY_OFF}
    gap = max(held_on.items(), key=lambda kv: kv[1][2])
    off = OFF_CM if raised else CARRY_OFF_CM
    p.check(f"{name}, {state}: no drawn finger is in the gun",
            pen[1][1] <= pressed, f"deepest {pen[0][0]} {pen[0][1]} {pen[1][1]:.2f} cm "
            f"(at most {pressed})")
    p.check(f"{name}, {state}: the drawn fingers are on the gun",
            gap[1][2] <= off, f"widest {gap[0][0]} {gap[0][1]} {gap[1][2]:.2f} cm "
            f"off (at most {off})")
    bones, tip = hands[("right", "index")]
    pad = finger_fit.riding(_points(body, held.get_actor_transform(), bones, tip))[D.PAD]
    near = finger_fit._len(finger_fit._sub(pad, finger_fit.aimed(TRIGGER[name], pad)))
    bound = TRIGGER_NEAR_CM_BY_GUN.get(name, TRIGGER_NEAR_CM) + R.SKIN_CM
    p.check(f"{name}, {state}: the right index is at the trigger",
            near <= bound, f"its pad {near:.2f} cm off the trigger's face (at most {bound:.2f})")


def _thumb(p, name, state, body, held, hands):
    """A gun of THUMB_REST (the pistol): the right thumb laid along the
    frame's left side, under the sights (combat/drawn_thumb.py): its tip on
    the rest's line (a skin off the mesh, so within THUMB_NEAR_CM and a skin
    of the line beside it) and no point of its skin above THUMB_CEILING_CM."""
    bones, tip_cm = hands[("right", "thumb")]
    pts = _points(body, held.get_actor_transform(), bones, tip_cm)
    top = max(q[2] for q in pts[1:] + finger_fit.riding(pts)) + R.SKIN_CM
    p.check(f"{name}, {state}: the right thumb is under the sights",
            top <= THUMB_CEILING_CM + 0.1, f"its skin's top at z {top:+.2f} cm "
            f"(at most {THUMB_CEILING_CM}; the slide's top 7.5)")
    tip = pts[-1]
    near = finger_fit._len(finger_fit._sub(tip, finger_fit.aimed(THUMB_REST[name], tip)))
    bound = THUMB_NEAR_CM + 2.0 * R.SKIN_CM
    p.check(f"{name}, {state}: the right thumb lies forward along the frame's left side",
            tip[1] < 0.0 and near <= bound,
            f"its tip at ({tip[0]:+.1f}, {tip[1]:+.1f}, {tip[2]:+.1f}), {near:.2f} cm off "
            f"the rest's line (at most {bound:.2f})")


def _xf(xf):
    t, q = xf.translation, xf.rotation
    return [[t.x, t.y, t.z], [q.x, q.y, q.z, q.w]]


def _under(body, hand):
    """Every bone below ``hand`` on ``body``, parents first."""
    names = [str(body.get_bone_name(i)) for i in range(body.get_num_bones())]
    out, keep = [], {hand}
    for name in names:
        if str(body.get_parent_bone(name)) in keep:
            keep.add(name)
            out.append(name)
    return out


def _capture(body, held):
    """{"hand_r"/"hand_l": [location, quat] in the gun's frame, "local":
    {bone: [location, quat] in its parent's}} of the drawn body."""
    gun = held.get_actor_transform()
    out = {h: _xf(unreal.MathLibrary.make_relative_transform(body.get_socket_transform(h), gun))
           for h in ("hand_r", "hand_l")}
    out["local"] = {b: _xf(body.get_socket_transform(
        b, unreal.RelativeTransformSpace.RTS_PARENT_BONE_SPACE))
        for h in ("hand_r", "hand_l") for b in _under(body, h)}
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
    wrists, rows, shots, summary, captured = [], [], [], [], {}
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
        for state, fwd, sprint, stance, raised, sights, pitch, hold_s in STATES:
            _clear_npcs(p)
            p.set(wc, WV.Stance, stance)
            p.set(wc, SPRINT_FORCED_VAR, sprint)
            p.set(wc, RAISE_FORCED_VAR, raised)
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
            reached = ((seat > SEATED) if sights else
                       (seat < 0.01 and (speed > 50.0) == bool(fwd)
                        and bool(p.get(wc, LOWERED_VAR)) != raised))
            p.check(f"{name}, {state}: the state is reached",
                    reached, f"seat {seat:.2f}, {speed:.0f} cm/s, "
                    f"view pitch {pc.get_control_rotation().pitch:+.0f}")
            m = _measure(body, mannequin, held, surfaces, hands, name in HANDGUNS)
            captured.setdefault(name, {})[state] = _capture(body, held)
            wrist, got = _rows(name, state, m)
            wrists.append([name, state, f"{speed:.0f}"] + wrist)
            rows += got
            pen, gap = R.worst(m["drawn"]["fingers"])
            summary.append([name, state, wrist[0], wrist[1],
                            f"{pen[0][0]} {pen[0][1]} {pen[1]:.2f}" if pen else "none",
                            f"{gap[0][0]} {gap[0][1]} {gap[1]:.2f}" if gap else "none"])
            _grip(p, name, state, raised, body, held, hands, m)
            if name in THUMB_REST:
                _thumb(p, name, state, body, held, hands)
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
    with open(CAPTURE, "w") as f:
        json.dump(captured, f, indent=1, sort_keys=True)
    p.note(f"report: {REPORT}; capture: {CAPTURE}")
