"""lbs -- linear blend skinning: where a vertex goes when its bones move.

A bone's move is a rigid transform (rotation rows, translation) of the rest
pose; a vertex goes to the weighted mean of where each of its bones would
carry it.  The same sum an engine evaluates, so what the bind measures here
is what the body will do on screen.
"""

from asset_pipeline.mannequin_bind.xform import mat_vec, q_to_mat, sub, turn


def about(q, pivot, target):
    """The rigid transform turning by ``q`` about ``pivot`` and carrying the
    pivot to ``target``."""
    rot = q_to_mat(q)
    return rot, sub(target, mat_vec(rot, pivot))


def points(verts, weights, moves):
    out = []
    for v, w in zip(verts, weights):
        x = y = z = 0.0
        for bone, share in w.items():
            r, t = moves[bone]
            x += share * (r[0][0] * v[0] + r[0][1] * v[1] + r[0][2] * v[2] + t[0])
            y += share * (r[1][0] * v[0] + r[1][1] * v[1] + r[1][2] * v[2] + t[1])
            z += share * (r[2][0] * v[0] + r[2][1] * v[1] + r[2][2] * v[2] + t[2])
        out.append((x, y, z))
    return out


def directions(dirs, weights, moves):
    """Unit directions (normals, tangents) carried the same way; a fourth
    component (a tangent's sign) rides along untouched."""
    out = []
    for d, w in zip(dirs, weights):
        x = y = z = 0.0
        for bone, share in w.items():
            r = moves[bone][0]
            x += share * (r[0][0] * d[0] + r[0][1] * d[1] + r[0][2] * d[2])
            y += share * (r[1][0] * d[0] + r[1][1] * d[1] + r[1][2] * d[2])
            z += share * (r[2][0] * d[0] + r[2][1] * d[1] + r[2][2] * d[2])
        n = (x * x + y * y + z * z) ** 0.5
        if n < 1e-9:
            x, y, z, n = d[0], d[1], d[2], 1.0
        out.append((x / n, y / n, z / n) + tuple(d[3:]))
    return out


def pose_moves(skeleton, local_q):
    """Each bone's move from the reference pose, for a pose given as
    {bone: local rotation}; bones not named keep their reference rotation and
    every bone keeps its reference translation (which is what the Skeleton
    translation-retargeting mode plays)."""
    from asset_pipeline.mannequin_bind.xform import add, conj, mul, qnorm
    comp_q, comp_t, moves = [], [], {}
    for i, name in enumerate(skeleton.names):
        q = local_q.get(name, skeleton.local_q[i])
        p = skeleton.parents[i]
        if p < 0:
            comp_q.append(qnorm(q))
            comp_t.append(skeleton.local_t[i])
        else:
            comp_q.append(qnorm(mul(comp_q[p], q)))
            comp_t.append(add(comp_t[p], turn(comp_q[p], skeleton.local_t[i])))
        delta = mul(comp_q[i], conj(skeleton.comp_q[i]))
        moves[name] = about(delta, skeleton.comp_t[i], comp_t[i])
    return moves
