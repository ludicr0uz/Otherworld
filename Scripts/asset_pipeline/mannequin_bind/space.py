"""space -- between glTF's space and Unreal's.

    glTF     metres,       Y up, right-handed, a character faces +Z
    Unreal   centimetres,  Z up, left-handed,  the mannequin faces +Y

The bind works in Unreal's, in the mannequin's own numbers, and the file is
written in glTF's. The conversion is the one Unreal's glTF importer applies
(swap Y and Z, scale by 100): a body the bind puts in the mannequin's pose
must come back out of the import in it, bone for bone.

Swapping two axes is a mirror, so a rotation does not convert the way a
direction does: its axis is a pseudo-vector and changes sign as well, which
is the (-x, -z, -y, w) below. import_bound.py checks the round trip against
the mannequin's own reference pose in the editor, because this file is the
one place a convention could be wrong without any number looking wrong here.
"""

from asset_pipeline.mannequin_bind.xform import q_to_mat

CM_PER_M = 100.0


def point_to_ue(p):
    return (p[0] * CM_PER_M, p[2] * CM_PER_M, p[1] * CM_PER_M)


def point_to_gltf(p):
    return (p[0] / CM_PER_M, p[2] / CM_PER_M, p[1] / CM_PER_M)


def dir_swap(v):
    """A direction either way: the swap is its own inverse."""
    return (v[0], v[2], v[1])


def tangent_swap(t):
    """A tangent either way. The sign in w says which way the bitangent runs
    from normal x tangent; it is the file's own and goes back to the file
    unchanged, so it is carried and not reasoned about."""
    return (t[0], t[2], t[1], t[3])


def quat_swap(q):
    """A rotation either way."""
    return (-q[0], -q[2], -q[1], q[3])


def rigid_to_gltf(q, t):
    """An Unreal rigid transform as glTF's (3 rotation rows, translation)."""
    return q_to_mat(quat_swap(q)), point_to_gltf(t)
