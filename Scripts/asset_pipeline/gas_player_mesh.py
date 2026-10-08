"""gas_player_mesh -- the hidden mesh the player wears on the GAS side of the
bridge: the sample's SKM_UEFN_Mannequin, copied, with the game's sockets.

The UEFN mannequin has none of the sockets the game attaches to (HandGrip_R,
where every held item goes, is the one that matters).  The sample's mesh is
an uncommitted byte copy, so the sockets go on a copy of it beside the rest
of the bridge, on the same skeleton: every clip, database and anim blueprint
of the sample plays on it unchanged.

Each socket is the mannequin's own, by name: same bone, same offset in that
bone's space.  The two skeletons name and orient their bones alike, so a
grip solved in HandGrip_R's frame on the mannequin sits in the same place in
the UEFN hand; the UEFN hand is a little smaller, and the offset is not
re-measured for it (the task that puts the weapon layers back does that).
"""

import unreal

from asset_pipeline.gas_bridge_paths import (
    HIDDEN_MESH_GAS, PLAYER_MESH_GAS, PLAYER_SOCKETS, SOCKETS_FROM,
)
from asset_pipeline.rig_util import _load, _log

# What a socket made by SkeletalMeshSocket() is called until it is renamed:
# SocketName is read-only, and SkeletalMesh.rename_socket is the way round.
NEW_SOCKET_NAME = "Socket"


def _sockets(mesh):
    return {str(s.socket_name): s
            for s in (mesh.get_socket_by_index(i) for i in range(mesh.num_sockets()))}


def build_player_mesh():
    """PLAYER_MESH_GAS: the copy (made once), and every socket of
    PLAYER_SOCKETS on it as the mannequin has it."""
    eas = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    mesh = (eas.load_asset(PLAYER_MESH_GAS) if eas.does_asset_exist(PLAYER_MESH_GAS)
            else eas.duplicate_asset(HIDDEN_MESH_GAS, PLAYER_MESH_GAS))
    if not mesh:
        raise RuntimeError(f"could not copy {HIDDEN_MESH_GAS} to {PLAYER_MESH_GAS}")
    theirs = _sockets(_load(SOCKETS_FROM))
    for name in PLAYER_SOCKETS:
        src = theirs.get(name)
        if src is None:
            raise RuntimeError(f"{SOCKETS_FROM} has no socket {name}")
        socket = _sockets(mesh).get(name)
        if socket is None:
            if NEW_SOCKET_NAME in _sockets(mesh):
                raise RuntimeError(f"{PLAYER_MESH_GAS} already has a socket named "
                                   f"{NEW_SOCKET_NAME!r}: a new one could not be told apart")
            socket = unreal.SkeletalMeshSocket(outer=mesh)
            mesh.add_socket(socket, False)
            if not mesh.rename_socket(NEW_SOCKET_NAME, name):
                raise RuntimeError(f"could not name the new socket {name}")
        socket.set_socket_parent(mesh, src.bone_name)
        if str(socket.bone_name) != str(src.bone_name):
            raise RuntimeError(f"{mesh.skeleton.get_name()} has no bone {src.bone_name} "
                               f"for the socket {name}")
        for prop in ("relative_location", "relative_rotation", "relative_scale"):
            socket.set_editor_property(prop, src.get_editor_property(prop))
    missing = [n for n in PLAYER_SOCKETS if mesh.find_socket(n) is None]
    if missing:
        raise RuntimeError(f"{PLAYER_MESH_GAS} still lacks {missing}")
    eas.save_loaded_asset(mesh)
    _log(f"{PLAYER_MESH_GAS.rsplit('/', 1)[1]}: {len(PLAYER_SOCKETS)} sockets "
         f"as {SOCKETS_FROM.rsplit('/', 1)[1]} has them")
    return mesh
