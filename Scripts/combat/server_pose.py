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
"""

from uebp import props as EP
from uebp.g import _G
from uebp.graph import _connect, _loose_pin, _palette, _pin, _set, out, then
from uebp.nodes.actor import FN_GET_OWNER
from uebp.nodes.palette import NODE_CAST_CHARACTER
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
    ed.add_comment_to_nodes(
        "A dedicated server renders nothing, so by default no body there leaves its "
        "reference pose. It judges every shot: the owner's mesh refreshes its bones "
        "always, and the hit bodies and the gun in the hand are where the clients "
        "see them (server_pose.py).", g.made)
    return [then(put), screen, _pin(cast, "CastFailed", is_input=False)]
