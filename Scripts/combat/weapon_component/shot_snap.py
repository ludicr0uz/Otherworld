"""A shot fired mid-flinch leaves from the shooting position.

The flinch (hit_reaction.py) plays in HitSlot, which shares the ready pose's
montage group: it stops the ready pose and throws the arms, the gun in the
right fist with them. Lowered stays false (an aim key or the last shot holds
the gun up), so carry._author_shot_origin read the real muzzle where the
flinch had put it, about crouch height, and the round left from there.

A shot now ends the flinch instead: SnapToShotPose (C++, the native base,
uebp/nodes/weapon.py) stops the flinch at once, plays HandPose into the aim
slot with no blend and poses the mesh again on the spot, which moves the gun
on its socket too. The muzzle read after it, by the same pure sub-graph as
before, is the ready pose's: the round leaves as it would had no hit landed.
Nothing happens when no flinch is playing.

Called where a shot reads the muzzle: on the machine with the keys before the
ask (shot._author_shot_ask), and in ShotFired before the server's muzzle is
read for the pellets (shot._author_shot_fired). The flinch plays on every
copy, the server's included (net/CLAUDE.md, A4), so each snaps its own.
"""

from uebp.graph import _connect, _node, _pin, out, then
from uebp.nodes.weapon import FN_SNAP_SHOT_POSE
from combat.weapon_component import vars as WV
from combat.weapon_component.look_vars import HandPose


def author_shot_snap(ed, exec_ins):
    """exec_ins -> SnapToShotPose(OwnerMesh, HandPose). Returns its exec out."""
    snap = _node(ed, FN_SNAP_SHOT_POSE)
    mesh = ed.add_get_member_variable_node(WV.OwnerMesh)
    pose = ed.add_get_member_variable_node(HandPose)
    _connect(out(mesh, WV.OwnerMesh), _pin(snap, "Mesh"))
    _connect(out(pose, HandPose), _pin(snap, "Pose"))
    for e in exec_ins:
        _connect(e, _pin(snap, "execute"))
    ed.add_comment_to_nodes(
        "A shot mid-flinch (shot_snap.py): SnapToShotPose stops the flinch, snaps the "
        "ready pose (HandPose) in with no blend and poses the mesh now, so the muzzle "
        "read next is where it is when no hit has landed. Nothing without a flinch.",
        [snap, mesh, pose])
    return then(snap)
