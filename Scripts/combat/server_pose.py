"""A dedicated server poses the bodies it judges shots against.

A skeletal mesh that is never rendered ticks its animation but does not
refresh its bones (``USkinnedMeshComponent::ShouldUpdateTransform``: rendered
recently, or ``AlwaysTickPoseAndRefreshBones``), and a dedicated server
renders nothing. Left so, every body there stands in its reference pose: the
physics bodies a round is traced against (hit_bodies.py) are not where any
client sees the creature, and the gun in a player's hand, whose muzzle the
server's shot leaves (weapon_component/shot.py), hangs off an arm held out in
an A-pose.

So BP_HealthComponent's BeginPlay, on a dedicated server alone, sets its
owner's mesh to refresh its bones always. Every body that can be hit has the
component, the players and the wanderers alike. A machine with a screen keeps
the engine's default: it poses what it draws. The later lag compensation
(a history of hit-box transforms) reads the same bones.

Always is not every frame (task A4). The same arm hands the body to
ThrottleServerPose (C++, OtherworldServerPose.h; the numbers are
pose_tuning.py): within 30 m of another player the mesh is posed every frame,
further off ten times a second, with nobody near or as a ragdoll twice, and
the hit history blends between the poses it gets. Every other skinned mesh on
the body (a MetaHuman's body, face and clothes) is drawn only, and stops
ticking there: measured, those were 73% of a 32-player server's frame.
"""

from uebp import props as EP
from uebp.g import _G
from uebp.graph import _connect, _loose_pin, _palette, _pin, _set, out, then
from uebp.nodes.actor import FN_GET_OWNER
from combat.pose_tuning import FAR_HZ, FULL_WITHIN_CM, NOBODY_BEYOND_CM, NOBODY_HZ
from uebp.nodes.palette import NODE_CAST_CHARACTER
from uebp.nodes.pose import FN_THROTTLE_SERVER_POSE
from uebp.nodes.system import FN_IS_DEDICATED_SERVER

CHARACTER_CLASS_PATH = "/Script/Engine.Character"
SKINNED_CLASS_PATH = "/Script/Engine.SkinnedMeshComponent"
TICK_OPTION = "VisibilityBasedAnimTickOption"
ALWAYS_REFRESH = "AlwaysTickPoseAndRefreshBones"


def author_server_pose(ed, execs):
    """See the module docstring. Returns the exec pins to carry on from."""
    g = _G(ed)
    server, screen = g.branch(out(g.call(FN_IS_DEDICATED_SERVER)), execs)
    cast = g.keep(_palette(ed, NODE_CAST_CHARACTER))
    _connect(out(g.call(FN_GET_OWNER)), _pin(cast, "Object"))
    _connect(server, _pin(cast, "execute"))
    body = _loose_pin(cast, "AsCharacter", is_input=False)
    mesh = g.iget(body, EP.MESH, CHARACTER_CLASS_PATH)
    put = g.keep(ed.add_set_member_variable_node(TICK_OPTION, SKINNED_CLASS_PATH))
    _connect(mesh, _pin(put, "self"))
    _set(put, TICK_OPTION, ALWAYS_REFRESH)
    _connect(then(cast), _pin(put, "execute"))
    throttle = g.call(FN_THROTTLE_SERVER_POSE, [then(put)], Body=body)
    for name, value in (("FullWithinCm", FULL_WITHIN_CM), ("FarHz", FAR_HZ),
                        ("NobodyBeyondCm", NOBODY_BEYOND_CM), ("NobodyHz", NOBODY_HZ)):
        _set(throttle, name, value)
    ed.add_comment_to_nodes(
        "A dedicated server renders nothing, so by default no body there leaves its "
        "reference pose. It judges every shot: the owner's mesh refreshes its bones "
        "always, and the hit bodies and the gun in the hand are where the clients "
        f"see them. Not every frame: within {FULL_WITHIN_CM / 100:g} m of another "
        f"player it is, further off {FAR_HZ:g} times a second, with nobody within "
        f"{NOBODY_BEYOND_CM / 100:g} m or as a ragdoll {NOBODY_HZ:g}, and nothing else "
        "skinned on the body ticks (server_pose.py, pose_tuning.py).", g.made)
    return [then(throttle), screen, _pin(cast, "CastFailed", is_input=False)]
