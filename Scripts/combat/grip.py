"""Where the weapon sits in the hand: HandGrip_R, the ready-pose socket axes
and the grip rotation solved per weapon.

HOW THE WEAPON IS ORIENTED
--------------------------
The weapon is rigidly attached to HandGrip_R and never rotated on its own. What
points it at the crosshair is the character: the body follows the camera's yaw
(face_the_camera) and the ready pose puts the arms down the sights, so the
barrel tracks the crosshair while staying in the fist.

Two things have to be right for that to hold, and each one looked like the
other's bug:

  * HandGrip_R carries the weapon's forward on its **+Y** axis, not its +X.
    _grip_rotation() has the measurements; aiming down +X puts the barrel 90
    degrees across the player's body.
  * The layered blend has to run in **mesh-space rotation** mode, or the ready
    pose's arms inherit the locomotion hips and lose their own pelvis yaw --
    worth a constant 21 degrees to the left. See patch_anim_blueprint().

Neither is visible in a static check of the grip: both rounds of solving it
produced self-consistent numbers and a gun pointing sideways. What settled it
was PrintString on Tick and reading yaws out of a -game run.

WHERE THE WEAPON SITS
---------------------
Rotation says where the barrel points; GripLocation says what the fingers
close round. It is solved too (_grip_location): in the ready pose each
closing finger's three joints lie on a circle, and the centre of that circle
is the axis the finger curls round. The mean of the four centres is the
middle of the fist, and the weapon is moved so its handle is there. Left at
the socket, a hand BONE held the handle 5-9 cm off the fingers, over the back
of the hand, because a bone's origin is the wrist and not the palm.

This module holds the socket and grip maths behind that.
"""

import unreal

from combat.graph import _assets, _component_object, _handles, _log, _rot
from combat.paths import CHARACTER_BP_PATH
from combat.skin import player_skin


# ─── Weapon geometry ─────────────────────────────────────────────────────────

def _rotate_vector(rotator, vector):
    try:
        return rotator.rotate_vector(vector)
    except AttributeError:
        return unreal.MathLibrary.greater_greater_vector_rotator(vector, rotator)


def _barrel_rotation():
    """Rotation that turns a Cylinder's +Z axis into the weapon's +X.

    Derived rather than hard-coded: the sign of the required pitch depends on
    UE's rotator handedness, which is easier to test than to argue about.
    """
    for pitch in (-90.0, 90.0):
        r = unreal.Rotator()
        r.pitch = pitch
        if _rotate_vector(r, unreal.Vector(0.0, 0.0, 1.0)).x > 0.9:
            return r
    raise RuntimeError("no pitch maps a cylinder's +Z onto +X")


def _pure_rotation(rotator):
    """A rotation-only Transform, so ComposeTransforms can be used as rotator algebra."""
    return unreal.Transform(location=unreal.Vector(0.0, 0.0, 0.0),
                            rotation=rotator,
                            scale=unreal.Vector(1.0, 1.0, 1.0))


class _BoneGrip:
    """A socket-shaped stand-in for a rig that has no grip socket.

    Python cannot create a SkeletalMeshSocket -- both SocketName and BoneName
    are read-only on it, so there is no way to say which bone a new socket
    hangs off -- and a Meshy rig arrives with none. Attaching to the BONE works
    instead: AttachToComponent resolves a socket name and a bone name out of
    the same namespace, and everything downstream of here only ever asks a
    socket for its bone and its rotation.

    The rotation is identity, and that is not an approximation. _grip_rotation
    *solves* for the transform that puts the barrel on the player's forward in
    a given pose, so whatever frame the hand bone happens to be authored in is
    taken out by the solve. What identity costs is position, not aim: the
    bone's origin is the wrist joint, which _grip_location solves out too.
    """

    def __init__(self, bone):
        self._bone = bone

    def get_editor_property(self, name):
        if name == "bone_name":
            return unreal.Name(self._bone)
        if name == "relative_rotation":
            return unreal.Rotator()
        if name == "relative_location":
            return unreal.Vector()
        raise AttributeError(name)


def _grip_socket():
    """(mesh yaw inside the actor, the grip socket) off the player's mesh."""
    bp = _assets().load_asset(CHARACTER_BP_PATH)
    if not bp:
        raise RuntimeError(f"could not load {CHARACTER_BP_PATH}")
    grip = player_skin().grip
    for handle, _name in _handles(bp):
        obj = _component_object(handle)
        if isinstance(obj, unreal.SkeletalMeshComponent):
            skeletal = obj.get_editor_property("skeletal_mesh_asset")
            socket = skeletal.find_socket(grip)
            if not socket:
                # Not an error unless the name is neither a socket nor a bone:
                # then the weapon would attach to the component root and hang
                # in the middle of the player's chest.
                if unreal.Name(grip) not in _mesh_bone_names(skeletal):
                    raise RuntimeError(
                        f"{skeletal.get_name()} has neither a {grip} socket nor "
                        f"a {grip} bone — a weapon could not be put in its hand")
                socket = _BoneGrip(grip)
            return obj.get_editor_property("relative_rotation").yaw, socket
    raise RuntimeError(f"{CHARACTER_BP_PATH} has no SkeletalMeshComponent")


def _mesh_bone_names(skeletal):
    """Every bone of a skeletal mesh, as Names.

    Off the skeleton's reference pose rather than off a spawned component: this
    runs during a headless build, where spawning an actor to ask it a question
    costs a level that then has to be left undirtied.
    """
    skel = skeletal.get_editor_property("skeleton")
    pose = unreal.AnimPoseExtensions.get_reference_pose(skel)
    return list(unreal.AnimPoseExtensions.get_bone_names(pose))


def socket_in_mesh(aim_pose_path):
    """(mesh yaw, HandGrip_R's rotation in mesh space) during a given pose.

    Sampled from the animation, not from a live mesh: a headless editor world
    only ever shows the *reference* pose, and that is not the pose a weapon is
    held in. With the layered blend in mesh-space rotation mode this sample is
    what the game actually uses -- the blended bones keep the ready pose's own
    component-space orientation rather than inheriting the locomotion hips.
    """
    mesh_yaw, socket = _grip_socket()
    anim = _assets().load_asset(aim_pose_path)
    if not anim:
        raise RuntimeError(f"could not load the pose {aim_pose_path}")
    pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(
        anim, 0.0, unreal.AnimPoseEvaluationOptions())
    # AnimPoseSpaces.WORLD means *component* space here -- a pose has no world
    # to be in -- and the mesh's own yaw is what carries that into the actor.
    bone = unreal.AnimPoseExtensions.get_bone_pose(
        pose, socket.get_editor_property("bone_name"), unreal.AnimPoseSpaces.WORLD)
    return mesh_yaw, unreal.MathLibrary.compose_transforms(
        _pure_rotation(socket.get_editor_property("relative_rotation")),
        bone).rotation.rotator()


def socket_pose_axes(aim_pose_path):
    """HandGrip_R's three axes, in the actor's space, during a given pose."""
    mesh_yaw, in_mesh = socket_in_mesh(aim_pose_path)
    return {name: _rotate_vector(_rot(yaw=mesh_yaw), _rotate_vector(in_mesh, vector))
            for name, vector in (("X", unreal.Vector(1.0, 0.0, 0.0)),
                                 ("Y", unreal.Vector(0.0, 1.0, 0.0)),
                                 ("Z", unreal.Vector(0.0, 0.0, 1.0)))}


def _grip_rotation(aim_pose_path):
    """The fixed rotation that seats a weapon in the hand aiming straight ahead.

    Two things had to be understood before this could be one line of maths.

    First, the axis. The Mannequin's HandGrip_R carries the weapon's forward on
    its **+Y**, not its +X. Measured in the actor's space:

        MM_Idle (arms down)   socket +Y = ( 0.07,  0.07, -0.99)  at the floor
        MF_Rifle_Idle_ADS     socket +Y = ( 0.97,  0.14,  0.21)  down the sights
        MF_Pistol_Idle_ADS    socket +Y = ( 0.99,  0.06,  0.14)  down the sights

    A hand at the side points its weapon axis at the floor and a hand in a ready
    pose points it where the player is looking; +X does neither -- in the rifle
    pose it reads 0.94 to the player's *left*.

    Second, the pose to solve against. It is this sampled one only because the
    layered blend runs in mesh-space rotation mode; in local space the arms
    inherit the locomotion hips and land somewhere else entirely.

    So: rotate the weapon's own +X onto whatever socket-space direction *is* the
    player's forward in this pose, keeping the weapon upright. Solving it this
    way rather than as a fixed 90 degree yaw also takes out the few degrees the
    ready poses are authored off-centre -- the rifle pose aims about 8 degrees
    right of the body -- and gives each weapon its own value for free, because
    the rifle hand and the pistol hand are not held at the same angle.
    """
    mesh_yaw, socket = socket_in_mesh(aim_pose_path)
    into_socket = unreal.MathLibrary.invert_transform(
        _pure_rotation(socket)).rotation.rotator()
    # The player's forward and up, as the socket sees them.
    forward_in_mesh = _rotate_vector(_rot(yaw=-mesh_yaw), unreal.Vector(1.0, 0.0, 0.0))
    grip = unreal.MathLibrary.make_rot_from_xz(
        _rotate_vector(into_socket, forward_in_mesh),
        _rotate_vector(into_socket, unreal.Vector(0.0, 0.0, 1.0)))

    barrel = _rotate_vector(
        _rot(yaw=mesh_yaw),
        _rotate_vector(unreal.MathLibrary.compose_transforms(
            _pure_rotation(grip), _pure_rotation(socket)).rotation.rotator(),
            unreal.Vector(1.0, 0.0, 0.0)))
    if barrel.x < 0.999:
        raise RuntimeError(f"{aim_pose_path}: the barrel would point "
                           f"{barrel.to_tuple()}, not straight ahead")
    _log(f"{aim_pose_path.rsplit('/', 1)[-1]}: grip pitch {grip.pitch:.1f}, "
         f"yaw {grip.yaw:.1f}, roll {grip.roll:.1f}")
    return grip


# ─── What the fingers close round ────────────────────────────────────────────

def _curl_centre(a, b, c):
    """Centre of the circle through three joints: what a curled finger wraps.

    A finger held straight has no such circle, and a weapon cannot be put in
    a hand that is not closed, so that raises rather than guessing.
    """
    ab, ac = b - a, c - a
    n = ab.cross(ac)
    nn = n.dot(n)
    if nn < 1e-4:
        raise RuntimeError("a gripping finger is straight in the ready pose -- "
                           "the fingers are not closing (see finger_verify.py)")
    return a + (n.cross(ab) * ac.dot(ac) + ac.cross(n) * ab.dot(ab)) * (0.5 / nn)


def fist_in_socket(aim_pose_path):
    """(fist centre, [[joint, joint, joint] per finger]) in the grip socket's
    frame during a given pose -- the frame GripLocation is written in.

    Sampled from the animation for the same reason socket_in_mesh() is: the
    ready pose, not the reference pose, is the one the weapon is held in.
    """
    _mesh_yaw, socket = _grip_socket()
    anim = _assets().load_asset(aim_pose_path)
    if not anim:
        raise RuntimeError(f"could not load the pose {aim_pose_path}")
    pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(
        anim, 0.0, unreal.AnimPoseEvaluationOptions())

    def at(bone):
        return unreal.AnimPoseExtensions.get_bone_pose(
            pose, bone, unreal.AnimPoseSpaces.WORLD)

    socket_xf = unreal.MathLibrary.compose_transforms(
        unreal.Transform(location=socket.get_editor_property("relative_location"),
                         rotation=socket.get_editor_property("relative_rotation"),
                         scale=unreal.Vector(1.0, 1.0, 1.0)),
        at(socket.get_editor_property("bone_name")))
    into_socket = unreal.MathLibrary.invert_transform(socket_xf)
    fingers = [[unreal.MathLibrary.transform_location(into_socket, at(b).translation)
                for b in joints] for joints in player_skin().grip_fingers]
    centres = [_curl_centre(*joints) for joints in fingers]
    fist = unreal.Vector(0.0, 0.0, 0.0)
    for c in centres:
        fist = fist + c
    return fist * (1.0 / len(centres)), fingers


def part_placement(parts, name):
    """(centre, rotation, half extents in cm) of one primitive part in the
    weapon's own frame. A Cube is 100 cm and a Cylinder 100 cm tall with a
    50 cm radius, so for either the half size is 50 x its scale."""
    for part, _mesh, loc, rot, scale, _mat in parts:
        if part == name:
            return (unreal.Vector(*loc), rot,
                    unreal.Vector(*(50.0 * s for s in scale)))
    raise RuntimeError(f"no {name!r} part to hold the weapon by")


def placed_part(weapon, parts, name):
    """(the part's Transform in the socket, the Transform into the part's own
    frame, its half extents) for a weapon placed in the socket by ``weapon``
    (GripLocation and GripRotation as a Transform)."""
    centre, rot, half = part_placement(parts, name)
    xf = unreal.MathLibrary.compose_transforms(
        unreal.Transform(location=centre, rotation=rot,
                         scale=unreal.Vector(1.0, 1.0, 1.0)), weapon)
    return xf, unreal.MathLibrary.invert_transform(xf), half


def box_distance(into, half, point):
    """Signed distance from a point to a box: negative inside."""
    p = unreal.MathLibrary.transform_location(into, point)
    d = [abs(v) - h for v, h in zip(p.to_tuple(), half.to_tuple())]
    out = sum(max(x, 0.0) ** 2 for x in d) ** 0.5
    return out if out > 0.0 else max(d)


def wrapping_joints(fingers):
    """The joints that close on a handle: the index's knuckle and all of the
    other three fingers. The index's outer joints are on the trigger."""
    index, rest = fingers[0], fingers[1:]
    return [index[0]] + [j for f in rest for j in f]


# A handle is seated at the middle of the fist, and that is where it stays
# when the hand fits it. A hand smaller than the one a handle was measured
# against closes tighter, and its joints then stand inside a thick handle (the
# stick's, 0.62 cm deep on the adventurer in boxers). So where any wrapping
# joint would sink past the first, the handle is eased off the middle by the
# least that brings them out to it, and never by more than the second (the
# verifier allows 0.5 cm of sink and 0.5 cm off the fist's middle); a handle
# that even that does not fit stays at the middle.
SEAT_SINK_CM = 0.35
SEAT_EASE_MAX_CM = 0.4
_EASE_STEP_CM = 0.05
_EASE_DIRS = tuple(unreal.Vector(x, y, z).normal()
                   for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1)
                   if (x, y, z) != (0, 0, 0))


def _sink(loc, grip_rot, parts, part, joints):
    weapon = unreal.Transform(location=loc, rotation=grip_rot,
                              scale=unreal.Vector(1.0, 1.0, 1.0))
    _xf, into, half = placed_part(weapon, parts, part)
    return -min(box_distance(into, half, j) for j in joints)


def _eased(loc, grip_rot, parts, part, fingers):
    """``loc``, or the nearest point to it (within SEAT_EASE_MAX_CM) where no
    wrapping joint is more than SEAT_SINK_CM inside ``part``; (location, how
    far it moved)."""
    joints = wrapping_joints(fingers)
    if _sink(loc, grip_rot, parts, part, joints) <= SEAT_SINK_CM:
        return loc, 0.0
    best = (_sink(loc, grip_rot, parts, part, joints), loc, 0.0)
    steps = int(round(SEAT_EASE_MAX_CM / _EASE_STEP_CM))
    for i in range(1, steps + 1):
        reach = i * _EASE_STEP_CM
        for d in _EASE_DIRS:
            at = loc + d * reach
            sink = _sink(at, grip_rot, parts, part, joints)
            if sink < best[0] - 1e-6:
                best = (sink, at, reach)
        if best[0] <= SEAT_SINK_CM:
            return best[1], best[2]
    # A handle no easing fits (a log with no handle, a matchbox): the middle
    # of the fist is still the best place for it.
    return loc, 0.0


def _grip_location(aim_pose_path, grip_rot, parts, part="Grip"):
    """The GripLocation that puts `part` in the middle of the fist.

    The weapon is attached at the socket, then moved by GripLocation and turned
    by GripRotation, both in the socket's frame; so a point p of the weapon
    lands at GripLocation + GripRotation(p). Solved for the handle's centre
    landing on the fist's, then eased out of any finger it stands in
    (_eased).
    """
    fist, fingers = fist_in_socket(aim_pose_path)
    centre = part_placement(parts, part)[0]
    loc, eased = _eased(fist - _rotate_vector(grip_rot, centre), grip_rot,
                        parts, part, fingers)
    _log(f"{aim_pose_path.rsplit('/', 1)[-1]}: {part} seated at the fist, "
         f"GripLocation ({loc.x:.1f}, {loc.y:.1f}, {loc.z:.1f})"
         + (f", eased {eased:.2f} cm out of the fingers" if eased else ""))
    return loc.to_tuple()
