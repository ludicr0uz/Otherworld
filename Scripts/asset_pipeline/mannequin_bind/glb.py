"""glb -- read a skinned binary glTF, and write it back on another skeleton.

Reading gives the mesh as the bind wants it: every vertex where it stands in
the rest pose (skinned through the file's own joints, so an armature scaled
0.01 over centimetre bones comes out in metres like the vertices beside it),
its weights by bone NAME, and each joint's rest position.

Writing keeps what the bind does not touch byte for byte -- indices, UVs,
materials, the embedded textures -- and replaces the scene: the old armature,
skin and animations go, the new joints come in, and each skinned primitive
gets new POSITION / NORMAL / TANGENT / JOINTS_0 / WEIGHTS_0 accessors appended
to the buffer.

glTF's own space throughout (metres, Y up, right-handed); space.py converts.
"""

import json
import struct
from array import array
from dataclasses import dataclass, field

GLB_MAGIC, CHUNK_JSON, CHUNK_BIN = 0x46546C67, 0x4E4F534A, 0x004E4942
FLOAT, UBYTE, USHORT, UINT = 5126, 5121, 5123, 5125
_CODE = {5120: "b", UBYTE: "B", 5122: "h", USHORT: "H", UINT: "I", FLOAT: "f"}
_WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
ARRAY_BUFFER = 34962
# glTF allows more sets (JOINTS_1...); whether Unreal's importer reads them is
# not something to find out on a body. Four is what Meshy ships and what every
# importer takes.
MAX_INFLUENCES = 4


def read_chunks(path):
    with open(path, "rb") as fh:
        blob = fh.read()
    magic, _version, _total = struct.unpack_from("<III", blob, 0)
    if magic != GLB_MAGIC:
        raise ValueError(f"{path} is not a GLB")
    n, kind = struct.unpack_from("<II", blob, 12)
    if kind != CHUNK_JSON:
        raise ValueError(f"{path}: first chunk is not JSON")
    doc = json.loads(blob[20:20 + n].decode("utf-8"))
    at = 20 + n
    m, kind = struct.unpack_from("<II", blob, at)
    if kind != CHUNK_BIN:
        raise ValueError(f"{path}: second chunk is not BIN")
    return doc, blob[at + 8:at + 8 + m]


def accessor(doc, bin_, index):
    """One accessor as a list of tuples (or of scalars), normalised ints
    turned to floats."""
    acc = doc["accessors"][index]
    if "sparse" in acc:
        raise ValueError("sparse accessors are not read")
    view = doc["bufferViews"][acc["bufferView"]]
    code, width = _CODE[acc["componentType"]], _WIDTH[acc["type"]]
    size = struct.calcsize(code) * width
    start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = view.get("byteStride") or size
    count = acc["count"]
    if stride == size:
        flat = array(code)
        flat.frombytes(bin_[start:start + size * count])
    else:
        flat = array(code)
        for i in range(count):
            flat.frombytes(bin_[start + i * stride:start + i * stride + size])
    if acc.get("normalized") and code != "f":
        top = float((1 << (8 * struct.calcsize(code))) - 1)
        flat = [v / top for v in flat]
    if width == 1:
        return list(flat)
    return [tuple(flat[i:i + width]) for i in range(0, len(flat), width)]


# ── 4x4 matrices, row-major tuples of rows ───────────────────────────────────

def _mat4_mul(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4))
                 for i in range(4))


def _node_matrix(node):
    if "matrix" in node:
        m = node["matrix"]                       # column-major in the file
        return tuple(tuple(m[c * 4 + r] for c in range(4)) for r in range(4))
    x, y, z, w = node.get("rotation", (0.0, 0.0, 0.0, 1.0))
    sx, sy, sz = node.get("scale", (1.0, 1.0, 1.0))
    tx, ty, tz = node.get("translation", (0.0, 0.0, 0.0))
    r = ((1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
         (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
         (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)))
    return ((r[0][0] * sx, r[0][1] * sy, r[0][2] * sz, tx),
            (r[1][0] * sx, r[1][1] * sy, r[1][2] * sz, ty),
            (r[2][0] * sx, r[2][1] * sy, r[2][2] * sz, tz),
            (0.0, 0.0, 0.0, 1.0))


def _world_matrices(doc):
    nodes = doc["nodes"]
    parent = {c: i for i, n in enumerate(nodes) for c in n.get("children", [])}
    world = {}

    def of(i):
        if i not in world:
            local = _node_matrix(nodes[i])
            world[i] = _mat4_mul(of(parent[i]), local) if i in parent else local
        return world[i]

    return [of(i) for i in range(len(nodes))], parent


# ── the mesh as read ─────────────────────────────────────────────────────────

@dataclass
class Primitive:
    index: tuple                 # (mesh index, primitive index) in the file
    positions: list              # rest pose, glTF space, metres
    normals: list
    tangents: list               # (x, y, z, w) or [] when the file has none
    weights: list                # per vertex {bone name: weight}, summing to 1
    triangles: list              # (a, b, c) vertex indices


@dataclass
class SkinnedMesh:
    path: str
    doc: dict
    bin_: bytes
    bones: list                  # joint names, in skin order
    parents: dict                # bone -> parent bone, None for the root joint
    joints: dict                 # bone -> rest position, glTF space, metres
    primitives: list = field(default_factory=list)


def _rest(m, v):
    return (m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2] + m[0][3],
            m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2] + m[1][3],
            m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2] + m[2][3])


def _rest_dir(m, v):
    out = (m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
           m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
           m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2])
    n = (out[0] ** 2 + out[1] ** 2 + out[2] ** 2) ** 0.5
    return (out[0] / n, out[1] / n, out[2] / n) if n > 1e-12 else v[:3]


def read_skinned(path):
    """The one skinned mesh in a GLB, in its rest pose."""
    doc, bin_ = read_chunks(path)
    skins = doc.get("skins", [])
    if len(skins) != 1:
        raise ValueError(f"{path}: {len(skins)} skins; the bind takes exactly one")
    skin = skins[0]
    nodes = doc["nodes"]
    world, parent = _world_matrices(doc)
    joint_nodes = skin["joints"]
    bones = [nodes[j].get("name", f"node{j}") for j in joint_nodes]
    if len(set(bones)) != len(bones):
        raise ValueError(f"{path}: two joints share a name")
    by_node = dict(zip(joint_nodes, bones))
    ibm = [tuple(tuple(m[c * 4 + r] for c in range(4)) for r in range(4))
           for m in accessor(doc, bin_, skin["inverseBindMatrices"])]
    # joint world * inverse bind: where a vertex bound to that joint rests.
    bind = [_mat4_mul(world[j], ibm[k]) for k, j in enumerate(joint_nodes)]

    out = SkinnedMesh(
        path=path, doc=doc, bin_=bin_, bones=bones,
        parents={by_node[j]: by_node.get(parent.get(j)) for j in joint_nodes},
        joints={by_node[j]: (world[j][0][3], world[j][1][3], world[j][2][3])
                for j in joint_nodes})

    skinned = {n["mesh"] for n in nodes if "mesh" in n and "skin" in n}
    for mi in sorted(skinned):
        for pi, prim in enumerate(doc["meshes"][mi]["primitives"]):
            at = prim["attributes"]
            if "JOINTS_1" in at:
                raise ValueError(f"{path}: more than four influences a vertex")
            pos = accessor(doc, bin_, at["POSITION"])
            nrm = accessor(doc, bin_, at["NORMAL"])
            tan = accessor(doc, bin_, at["TANGENT"]) if "TANGENT" in at else []
            jnt = accessor(doc, bin_, at["JOINTS_0"])
            wgt = accessor(doc, bin_, at["WEIGHTS_0"])
            P, N, T, W = [], [], [], []
            for i in range(len(pos)):
                total = sum(wgt[i])
                if total <= 0.0:
                    raise ValueError(f"{path}: vertex {i} is bound to nothing")
                acc = {}
                p, n, t = [0.0] * 3, [0.0] * 3, [0.0] * 3
                for j, w in zip(jnt[i], wgt[i]):
                    if w <= 0.0:
                        continue
                    w /= total
                    acc[bones[j]] = acc.get(bones[j], 0.0) + w
                    m = bind[j]
                    for k, c in enumerate(_rest(m, pos[i])):
                        p[k] += w * c
                    for k, c in enumerate(_rest_dir(m, nrm[i])):
                        n[k] += w * c
                    if tan:
                        for k, c in enumerate(_rest_dir(m, tan[i])):
                            t[k] += w * c
                P.append(tuple(p))
                N.append(_rest_dir(((1, 0, 0), (0, 1, 0), (0, 0, 1)), n))
                if tan:
                    T.append(_rest_dir(((1, 0, 0), (0, 1, 0), (0, 0, 1)), t)
                             + (tan[i][3],))
                W.append(acc)
            if prim.get("mode", 4) != 4:
                raise ValueError(f"{path}: a primitive that is not triangles")
            idx = (accessor(doc, bin_, prim["indices"]) if "indices" in prim
                   else list(range(len(pos))))
            tris = [tuple(idx[k:k + 3]) for k in range(0, len(idx) - 2, 3)]
            out.primitives.append(Primitive((mi, pi), P, N, T, W, tris))
    if not out.primitives:
        raise ValueError(f"{path}: no skinned mesh")
    return out


# ── writing ──────────────────────────────────────────────────────────────────

class _Buffer:
    """The original binary chunk with new views appended."""

    def __init__(self, doc, bin_):
        self.doc = doc
        self.parts = [bin_]
        self.size = len(bin_)

    def add(self, code, width_name, rows, component, target=ARRAY_BUFFER,
            bounds=False):
        pad = (-self.size) % 4
        if pad:
            self.parts.append(b"\x00" * pad)
            self.size += pad
        flat = array(code, [c for row in rows for c in row])
        data = flat.tobytes()
        view = {"buffer": 0, "byteOffset": self.size, "byteLength": len(data)}
        if target:
            view["target"] = target
        self.doc["bufferViews"].append(view)
        self.parts.append(data)
        self.size += len(data)
        acc = {"bufferView": len(self.doc["bufferViews"]) - 1,
               "componentType": component, "count": len(rows), "type": width_name}
        if bounds:
            width = len(rows[0])
            # Through float32, as stored: a validator compares with the data.
            stored = [flat[i::width] for i in range(width)]
            acc["min"] = [min(col) for col in stored]
            acc["max"] = [max(col) for col in stored]
        self.doc["accessors"].append(acc)
        return len(self.doc["accessors"]) - 1

    def bytes(self):
        pad = (-self.size) % 4
        return b"".join(self.parts) + b"\x00" * pad


def _mat4_column_major(rot, t):
    """A rigid transform (3 rows, translation) as glTF's 16 floats."""
    return (rot[0][0], rot[1][0], rot[2][0], 0.0,
            rot[0][1], rot[1][1], rot[2][1], 0.0,
            rot[0][2], rot[1][2], rot[2][2], 0.0,
            t[0], t[1], t[2], 1.0)


def write_bound(mesh, out_path, names, parents, local_q, local_t,
                inverse_bind, primitives, mesh_name):
    """Write ``mesh``'s file again on a new skeleton.

    names/parents/local_q/local_t   the joints, parents first, glTF space
    inverse_bind                    per joint (3 rotation rows, translation)
    primitives                      per Primitive, in mesh.primitives order:
                                    (positions, normals, tangents,
                                     [[(joint index, weight), ...] per vertex])
    """
    doc = json.loads(json.dumps(mesh.doc))       # a deep copy
    buf = _Buffer(doc, mesh.bin_)
    doc.pop("animations", None)

    joints = []
    for i, name in enumerate(names):
        joints.append({"name": name, "rotation": list(local_q[i]),
                       "translation": list(local_t[i])})
    for i, p in enumerate(parents):
        if p >= 0:
            joints[p].setdefault("children", []).append(i)
    roots = [i for i, p in enumerate(parents) if p < 0]
    if len(roots) != 1:
        raise ValueError("the skeleton needs exactly one root")

    used = sorted({mi for (mi, _pi) in (p.index for p in mesh.primitives)})
    mesh_nodes = [{"name": mesh_name if len(used) == 1 else f"{mesh_name}_{k}",
                   "mesh": mi, "skin": 0} for k, mi in enumerate(used)]
    doc["nodes"] = joints + mesh_nodes
    doc["scenes"] = [{"name": "Scene",
                      "nodes": roots + list(range(len(joints), len(doc["nodes"])))}]
    doc["scene"] = 0
    ibm = buf.add("f", "MAT4", [_mat4_column_major(r, t) for r, t in inverse_bind],
                  FLOAT, target=None)
    doc["skins"] = [{"name": "Mannequin", "joints": list(range(len(joints))),
                     "skeleton": roots[0], "inverseBindMatrices": ibm}]

    for prim, (pos, nrm, tan, influences) in zip(mesh.primitives, primitives):
        mi, pi = prim.index
        at = doc["meshes"][mi]["primitives"][pi]["attributes"]
        at["POSITION"] = buf.add("f", "VEC3", pos, FLOAT, bounds=True)
        at["NORMAL"] = buf.add("f", "VEC3", nrm, FLOAT)
        if tan:
            at["TANGENT"] = buf.add("f", "VEC4", tan, FLOAT)
        else:
            at.pop("TANGENT", None)
        j_rows, w_rows = [], []
        for inf in influences:
            if not 0 < len(inf) <= MAX_INFLUENCES:
                raise ValueError(f"a vertex has {len(inf)} influences")
            pad = MAX_INFLUENCES - len(inf)
            j_rows.append(tuple(j for j, _w in inf) + (0,) * pad)
            w_rows.append(tuple(w for _j, w in inf) + (0.0,) * pad)
        wide = len(joints) > 255
        at["JOINTS_0"] = buf.add("H" if wide else "B", "VEC4", j_rows,
                                 USHORT if wide else UBYTE)
        at["WEIGHTS_0"] = buf.add("f", "VEC4", w_rows, FLOAT)
        for extra in [k for k in at if k.startswith(("JOINTS_", "WEIGHTS_"))
                      and not k.endswith("_0")]:
            del at[extra]

    binary = buf.bytes()
    doc["buffers"] = [{"byteLength": len(binary)}]
    text = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    text += b" " * ((-len(text)) % 4)
    total = 12 + 8 + len(text) + 8 + len(binary)
    with open(out_path, "wb") as fh:
        fh.write(struct.pack("<III", GLB_MAGIC, 2, total))
        fh.write(struct.pack("<II", len(text), CHUNK_JSON))
        fh.write(text)
        fh.write(struct.pack("<II", len(binary), CHUNK_BIN))
        fh.write(binary)
    return total
