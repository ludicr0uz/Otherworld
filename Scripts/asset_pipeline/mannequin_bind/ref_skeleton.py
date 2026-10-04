"""ref_skeleton -- the mannequin's reference skeleton, read out of its .uasset
host-side, and the same shape for any skeleton the bind builds.

WHY THE FILE AND NOT THE EDITOR
-------------------------------
The bind needs the mannequin's 89 bones: names, parents and reference
transforms. The editor would hand them over in one call, and an editor is a
30-second cold boot that cannot run while another task holds it. The asset on
disk has them in the clear: an FReferenceSkeleton is serialised as

    int32 N
    N x  FName (2 x int32), int32 parent, FString export name (int32 len, bytes)
    int32 N
    N x  FTransform as ten doubles: quat xyzw, translation xyz, scale xyz

and the export name is the bone's name as text, so nothing has to resolve the
package's name table. The block is found by its first bone ("root", parent
-1) and accepted only if it parses to the end: the right count twice, every
parent before its child, every quaternion unit.

Rotations compose the way Unreal's do: a bone's component rotation is its
parent's times its own, and its position its parent's plus the parent's
rotation of its local translation.
"""

import struct
from dataclasses import dataclass

from asset_pipeline.mannequin_bind.xform import add, conj, mul, qnorm, sub, turn

_ROOT = b"\x05\x00\x00\x00root\x00"
_MAX_BONES = 2000


@dataclass(frozen=True)
class RefSkeleton:
    """Bones in parent-before-child order, with local and component poses."""

    names: tuple
    parents: tuple               # index, -1 for the root
    local_q: tuple               # (x, y, z, w) per bone
    local_t: tuple               # (x, y, z) per bone, cm
    comp_q: tuple
    comp_t: tuple

    def index(self, name):
        return self._index[name]

    def __contains__(self, name):
        return name in self._index

    def parent_name(self, name):
        p = self.parents[self.index(name)]
        return self.names[p] if p >= 0 else None

    def children(self, name):
        i = self.index(name)
        return [n for n, p in zip(self.names, self.parents) if p == i]

    def pos(self, name):
        return self.comp_t[self.index(name)]

    def rot(self, name):
        return self.comp_q[self.index(name)]

    def descendants(self, name):
        root, out = self.index(name), []
        under = {root}
        for i, p in enumerate(self.parents):
            if p in under:
                under.add(i)
                out.append(self.names[i])
        return out

    @property
    def _index(self):
        cache = self.__dict__.get("_idx")
        if cache is None:
            cache = {n: i for i, n in enumerate(self.names)}
            object.__setattr__(self, "_idx", cache)
        return cache


def from_local(names, parents, local_q, local_t):
    """A skeleton from local poses; component poses are worked out."""
    comp_q, comp_t = [], []
    for i, p in enumerate(parents):
        if p < 0:
            comp_q.append(qnorm(local_q[i]))
            comp_t.append(tuple(local_t[i]))
        else:
            if p >= i:
                raise ValueError(f"{names[i]}: parent {p} does not come first")
            comp_q.append(qnorm(mul(comp_q[p], local_q[i])))
            comp_t.append(add(comp_t[p], turn(comp_q[p], local_t[i])))
    return RefSkeleton(tuple(names), tuple(parents),
                       tuple(tuple(q) for q in local_q),
                       tuple(tuple(t) for t in local_t),
                       tuple(comp_q), tuple(comp_t))


def from_component(names, parents, comp_q, comp_t):
    """A skeleton from component poses; local poses are worked out."""
    local_q, local_t = [], []
    for i, p in enumerate(parents):
        if p < 0:
            local_q.append(tuple(comp_q[i]))
            local_t.append(tuple(comp_t[i]))
        else:
            inv = conj(comp_q[p])
            local_q.append(qnorm(mul(inv, comp_q[i])))
            local_t.append(turn(inv, sub(comp_t[i], comp_t[p])))
    return from_local(names, parents, local_q, local_t)


def _parse(blob, at):
    """The skeleton whose first bone record starts at ``at``, or None."""
    if at < 4:
        return None
    (count,) = struct.unpack_from("<i", blob, at - 4)
    if not 0 < count <= _MAX_BONES:
        return None
    names, parents, o = [], [], at
    for i in range(count):
        if o + 16 > len(blob):
            return None
        _name, _number, parent, n = struct.unpack_from("<iiii", blob, o)
        o += 16
        if not 0 < n <= 256 or o + n > len(blob) or not -1 <= parent < i:
            return None
        try:
            names.append(blob[o:o + n - 1].decode("ascii"))
        except UnicodeDecodeError:
            return None
        parents.append(parent)
        o += n
    if o + 4 + count * 80 > len(blob):
        return None
    if struct.unpack_from("<i", blob, o)[0] != count:
        return None
    o += 4
    local_q, local_t = [], []
    for i in range(count):
        v = struct.unpack_from("<10d", blob, o + i * 80)
        if abs(sum(c * c for c in v[:4]) - 1.0) > 1e-3:
            return None
        if any(abs(s - 1.0) > 1e-3 for s in v[7:]):
            raise ValueError(f"{names[i]} is scaled {v[7:]} in its reference "
                             "pose: the bind assumes unscaled bones")
        local_q.append(v[:4])
        local_t.append(v[4:7])
    if len(set(names)) != count:
        return None
    return from_local(names, parents, local_q, local_t)


def read_uasset(path):
    """The reference skeleton serialised in a SkeletalMesh or Skeleton asset."""
    with open(path, "rb") as fh:
        blob = fh.read()
    at = blob.find(_ROOT)
    while at >= 0:
        skeleton = _parse(blob, at - 12)
        if skeleton:
            return skeleton
        at = blob.find(_ROOT, at + 1)
    raise ValueError(
        f"{path}: no reference skeleton found. It is read as a block that "
        "starts at a bone called 'root'; an asset saved compressed, or by an "
        "engine that serialises FReferenceSkeleton differently, needs "
        "ref_skeleton._parse looked at again.")
